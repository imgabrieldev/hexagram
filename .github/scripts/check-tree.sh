#!/usr/bin/env bash
#
# The checks that are about the tree rather than about the markdown.
# Runnable by hand: bash .github/scripts/check-tree.sh
#
# ONE TRAP RUNS THROUGH THIS WHOLE FILE. Every search here — git grep,
# git check-ignore — exits 1 when it finds NOTHING. Under `set -euo pipefail`
# that kills the script at the exact moment the repo is clean, so the run is
# red on a green repo and green on a red one. Every search below therefore ends
# in `|| true` and is judged by its OUTPUT, never by its status. It cost three
# separate debugging rounds to stop re-learning this.

set -euo pipefail

fail=0
err()  { echo "::error::$1"; fail=1; }
warn() { echo "::warning::$1"; }

# ------------------------------------------------------------------ JSON parse
#
# `claude plugin validate` probes only the manifests its schema knows about. It
# never opens skills/setup-machine/plugins.json or template/.mcp.json — both of
# which a running Claude Code parses, and crashes on. jq is preinstalled.

echo "::group::JSON"
while IFS= read -r f; do
  if jq -e . "$f" >/dev/null 2>&1; then
    echo "  ok   $f"
  else
    err "$f is not valid JSON"
    jq . "$f" 2>&1 | head -3 | sed 's/^/       /' || true
  fi
done < <(git ls-files '*.json')
echo "::endgroup::"

# -------------------------------------------------------- ignored-but-tracked
#
# The defect: a runtime .log was committed, and a script kept appending to it.
# .gitignore already said *.log — it simply does not apply to what is already
# in the index. `--no-index` is the entire point: without it, check-ignore
# skips exactly the files being hunted.

echo "::group::tracked files that .gitignore excludes"
tracked_ignored=$(git ls-files -z | git check-ignore --no-index --stdin -z 2>/dev/null | tr '\0' '\n' || true)
if [ -n "$tracked_ignored" ]; then
  err "tracked, but .gitignore says to ignore them — git rm --cached these:"
  echo "$tracked_ignored" | sed 's/^/       /'
else
  echo "  ok   nothing tracked that .gitignore excludes"
fi
echo "::endgroup::"

# ------------------------------------------------------------ manifest -> disk
#
# Forward direction, and an error: every plugin-root path the manifests promise
# has to exist. A hook whose script is gone fails at load, on a stranger's
# machine, with no clue pointing back here. The load smoke test does NOT cover
# this — I deleted hooks/self-update.sh and `claude plugin install` still
# reported the plugin enabled.
#
# EVERY SCAN IN THIS FILE EXCLUDES .github. A linter that greps the repo will
# otherwise find its own documentation: the first draft of this check reported
# a missing path that existed only in the comment three lines above it, and the
# reverse check below silently passed because these comments name the very keys
# it is looking for. Self-reference is the default failure of a grep-based
# linter, not an edge case.

SELF=':!.github'

echo "::group::manifest references resolve"
while IFS= read -r p; do
  rel=${p#*CLAUDE_PLUGIN_ROOT}; rel=${rel#\}}; rel=${rel#/}
  if [ -e "$rel" ]; then
    echo "  ok   plugin-root/$rel"
  else
    err "a manifest points at plugin-root/$rel — that path is not in the repo"
  fi
done < <(git grep -hoE '\$\{?CLAUDE_PLUGIN_ROOT\}?/[A-Za-z0-9._/-]+' -- '*.json' '*.md' '*.sh' "$SELF" 2>/dev/null | sort -u || true)
echo "::endgroup::"

# ------------------------------------------------------------ disk -> manifest
#
# Reverse direction — the literal defect from the audit, a manifest field that
# outlived the script reading it — and only a WARNING, because it is a
# substring search and it knows it. A key named `transport` cannot be told
# apart from the English word: I renamed that field to `protocol` to test this
# and it did NOT fire, because skills/diagrams happens to use the word. It
# fires reliably for identifier-shaped keys, which is most of them, and it can
# never go red on its own. That asymmetry is the point — a dead manifest field
# is worth a nudge, not a broken build, and a check with known blind spots must
# not be allowed to look authoritative.
#
# `$comment` is exempt on purpose: JSON has no comments, so the key IS the
# documentation and having no reader is its entire job.

echo "::group::manifest fields still have a reader"
catalogue=skills/setup-machine/plugins.json
while IFS= read -r k; do
  # A plain `if`, not `[ ... ] && continue`: under `set -e` a bare test that
  # fails as the last statement of a list is a trap not worth re-deriving.
  if [ "$k" = '$comment' ]; then
    continue
  fi
  hits=$(git grep -lF -- "$k" -- ":!$catalogue" "$SELF" 2>/dev/null || true)
  if [ -n "$hits" ]; then
    echo "  ok   $k"
  else
    warn "$catalogue declares \"$k\" and nothing outside that file mentions it — wire it up or delete it"
  fi
done < <(jq -r '[.. | objects | keys[]] | unique[]' "$catalogue")
echo "::endgroup::"

# -------------------------------------------------------------------- shellcheck
#
# Matched by SHEBANG, not by extension. Three of the five shell files in this
# repo are not named *.sh (`.githooks/commit-msg`, `template/.githooks/commit-msg`)
# and `#!/usr/bin/env bash` has no slash before `bash`, so the obvious
# `^#!.*/(ba)?sh` regex quietly checks none of the hooks that actually ship.
#
# shellcheck is worthless against the fenced snippets — it exits 0 on
# `claude plugin install <name>@x` at every severity, including -S error — but
# these are real executables that ship and run on every session start.
#
# `.github` is excluded here for the same reason as every other scan, plus one
# more: shellcheck is not installed on the author's Mac, so this file's own
# cleanliness could not be verified before it was written. Rather than have the
# very first CI run go red on a style warning in the linter itself, the linter
# stays out of scope. Drop `"$SELF"` from this one line after the first green
# run if you want it covered — by then you can see the output before the repo
# depends on it.

echo "::group::shellcheck"
mapfile -t shfiles < <(git grep -lE '^#!.*[ /](ba|da|k|z)?sh$' -- ':!*.md' "$SELF" 2>/dev/null || true)
if [ ${#shfiles[@]} -eq 0 ]; then
  echo "  no shell scripts"
elif ! command -v shellcheck >/dev/null 2>&1; then
  echo "::notice::shellcheck not installed — skipped (preinstalled on ubuntu-latest)"
else
  printf '  %s\n' "${shfiles[@]}"
  shellcheck "${shfiles[@]}" || fail=1
fi
echo "::endgroup::"

# ------------------------------------------------- board: uuid addressing only
#
# skills/board is immune to the upstream kanban numbering defect for exactly one
# reason: it never addresses a card by its PREFIX-N identifier, only by uuid. A
# comment saying so is not enforcement; this is.
#
# TWO TRAPS, both hit while writing this, both silent:
#
#   * A card identifier and an encoding name are the same shape. `[A-Z]{2,}-[0-9]+`
#     matches UTF-8 and ASCII-8BIT, and encoding names appear in skills/board
#     because reading as UTF-8 is itself a rule there. Full-line comments are
#     stripped first, and the encoding tokens are excluded BY NAME, not by shape.
#   * `git grep -E` does NOT support `\b`. POSIX ERE has no word boundary, so a
#     pattern that works in `grep -E` on a Mac matches NOTHING under git grep --
#     the check reported a clean tree while a planted `KAN-7` sat in the file.
#     Verified by planting one. No `\b` here, and `-P` is not portable enough
#     to rely on.

#   * A THIRD trap, found when the renderer arrived: the shape is not the hazard.
#     `show.py` must read card_number to print PREFIX-N and to sort by it, and the
#     docs must show the output the tool actually produces. Flagging those made
#     the check cry wolf on its own skill. The hazard is an identifier used as an
#     ARGUMENT, so code now needs an audited per-line waiver and prose is checked
#     for the argument shape rather than for any identifier at all. The waiver
#     count is printed: an exemption that can grow in silence is not a check.

echo "::group::board addresses cards by uuid, never by identifier"
if [ -d skills/board ]; then
  # Code: any identifier or card_number, unless the line carries the waiver.
  code_hits=$(git grep -nE 'card_number|[A-Z]{2,5}-[0-9]+' \
                 -- 'skills/board/*.py' 'skills/board/*.sh' \
              | grep -vE ':[0-9]+:[[:space:]]*#' \
              | grep -vE 'UTF-8|ASCII-8BIT' \
              | grep -v 'board-id-ok' || true)
  # Prose: only an identifier passed to the binary, which is the actual defect.
  # An identifier merely PRINTED in sample output cannot corrupt anything.
  doc_hits=$(git grep -nE 'kanban[^|]*[A-Z]{2,5}-[0-9]+' -- 'skills/board/*.md' \
             | grep -vE 'UTF-8|ASCII-8BIT' || true)
  board_hits=$(printf '%s\n%s' "$code_hits" "$doc_hits" | grep -v '^$' || true)
  waivers=$(git grep -c 'board-id-ok' -- 'skills/board/*.py' 'skills/board/*.sh' \
            | awk -F: '{n += $2} END {print n + 0}')
  if [ -n "$board_hits" ]; then
    err "board must address cards by uuid, never by identifier or card_number:"
    echo "$board_hits" | sed 's/^/       /'
  else
    echo "  ok   no identifier addressing in skills/board ($waivers display waiver(s))"
  fi
else
  echo "  no skills/board"
fi
echo "::endgroup::"

exit "$fail"
