#!/usr/bin/env bash
# self-update.sh — SessionStart hook. Keeps hexagram current without anyone typing a command.
#
# The problem it solves: a plugin installed on five machines is five machines that drift. The
# manual cure is two commands per machine per update, which is the same as no cure.
#
# How it behaves, and why each part is the way it is:
#
#   * It does not block the session. The update runs detached and this script returns at once.
#     A hook that waits on the network is a hook that makes every session start feel broken.
#   * It reports the PREVIOUS run's result, because the current one has not finished yet. So an
#     update lands silently and is announced at the following session start, with the restart
#     note — which is honest: that is exactly when it becomes usable.
#   * It says nothing at all when there is nothing to say. SessionStart stdout is injected into
#     the context of every session; a heartbeat line there is a tax paid forever.
#   * It never fails the session. Every path exits 0.
#
# Opt out with HEXAGRAM_NO_SELF_UPDATE=1.

STATE="${XDG_STATE_HOME:-$HOME/.local/state}/hexagram"
STAMP="$STATE/last-update-check"
RESULT="$STATE/last-update-result"
LOCK="$STATE/update.lock"
LOG="$STATE/self-update.log"
PLUGIN="${HEXAGRAM_PLUGIN:-hexagram@hexagram}"
MARKET="${PLUGIN#*@}"
INTERVAL_H="${HEXAGRAM_UPDATE_INTERVAL_H:-24}"

mkdir -p "$STATE" 2>/dev/null || exit 0

# Announce what the last background run did, once, then forget it. This is the only thing this
# hook ever writes to the session.
if [ -s "$RESULT" ]; then
  printf 'hexagram was updated in the background (%s). Restart Claude Code to load it.\n' \
    "$(tr -d '\n' < "$RESULT")"
  rm -f "$RESULT"
fi

[ "${HEXAGRAM_NO_SELF_UPDATE:-0}" = "1" ] && exit 0
command -v claude >/dev/null 2>&1 || exit 0

# A hand-set interval that is not an integer must not silently disable the rate limit: the
# arithmetic below would fail, the guard would never fire, and every session start would fetch.
# Digits only is not enough: a 20-digit value passes the character test and then overflows the
# 64-bit arithmetic below, `[` errors, and the rate limit never fires at all.
case "$INTERVAL_H" in ''|*[!0-9]*) INTERVAL_H=24 ;; esac
[ "${#INTERVAL_H}" -le 6 ] || INTERVAL_H=24

age_h() {  # hours since $1 was last modified, or a large number if it does not exist
  [ -e "$1" ] || { echo 999999; return; }
  t=$(date -r "$1" +%s 2>/dev/null || stat -c %Y "$1" 2>/dev/null || echo 0)
  echo $(( ( $(date +%s) - t ) / 3600 ))
}

# Rate limit. Without it every `claude` invocation in a shell loop is a git fetch.
[ "$(age_h "$STAMP")" -lt "$INTERVAL_H" ] && exit 0

# ⚠️ A leaked lock must not disable updates forever. The EXIT trap below survives SIGTERM and
# SIGHUP, and a background job in a non-interactive shell never sees SIGINT — so the only ways
# to leak it are SIGKILL, force-quit and power loss. Rare, but the failure is silent and
# permanent: the hook goes on exiting 0 with no output, and the README promises the user they
# never have to do anything. An update that cannot outlive one kill -9 is not automatic.
#
# Six hours is far past any real run (two 120s network timeouts is the worst legitimate case).
# ⚠️ Guard on EXISTENCE first. age_h returns a huge number for a lock that is not there, so an
# unguarded staleness branch rmdir's nothing, returns success to the next test, and lets a second
# process walk straight into the critical section — measured at ~20% of concurrent starts, and
# once two are inside, the first to finish releases the lock while the second still holds it.
# The mutex then stops being a mutex.
if [ -d "$LOCK" ] && [ "$(age_h "$LOCK")" -ge 6 ]; then
  rmdir "$LOCK" 2>/dev/null && echo "hexagram: cleared a stale update lock." >>"$LOG"
fi

# mkdir is the atomic one. Two sessions opening together must not both fetch.
mkdir "$LOCK" 2>/dev/null || exit 0
touch "$STAMP"

# Detached so the session never waits on the network. `disown` removes it from the shell's job
# table, which is what stops the exiting shell from signalling it; the redirections below cut it
# loose from the hook's stdio so nothing downstream blocks on an open pipe. It stays in this
# process group — good enough here, because the EXIT trap releases the lock on every signal a
# normal teardown sends, and the staleness check above covers the ones it cannot catch.
(
  trap 'rmdir "$LOCK" 2>/dev/null' EXIT
  {
    echo "--- $(date '+%Y-%m-%d %H:%M:%S') ---"
    claude plugin marketplace update "$MARKET" 2>&1
    out="$(claude plugin update "$PLUGIN" --yes 2>&1)"
    echo "$out"
    # "updated from X to Y" is the only outcome worth a word to the user. "already at the
    # latest version" is the normal case and stays in the log.
    case "$out" in
      *"updated from"*)
        echo "$out" | sed -n 's/.*updated from \(.*\) for scope.*/\1/p' | head -1 > "$RESULT"
        [ -s "$RESULT" ] || echo "new version" > "$RESULT" ;;
    esac
  } >>"$LOG" 2>&1
  # Keep the log from growing without bound on a machine that runs for years.
  [ "$(wc -l <"$LOG" 2>/dev/null || echo 0)" -gt 500 ] && { tail -200 "$LOG" > "$LOG.t" && mv "$LOG.t" "$LOG"; }
  :
) </dev/null >/dev/null 2>&1 &
disown 2>/dev/null

exit 0
