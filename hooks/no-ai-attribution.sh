#!/usr/bin/env bash
# PreToolUse(Bash) — refuse a git commit that carries AI attribution.
#
# This is a SAFETY NET, not the enforcement. It only fires when the commit goes
# through the Bash tool. A commit typed in a terminal, made from an IDE or made
# by any other tool bypasses it entirely. The real guard is the repo's
# .githooks/commit-msg, wired with `git config core.hooksPath .githooks`, which
# strips the trailer no matter who commits.
#
# It exists because a rule that is only written down is a rule that gets skipped.

set -uo pipefail
input=$(cat)

# ⚠️ Without this guard a machine with no jq fails OPEN: the pipeline exits 127, `|| exit 0`
# swallows it, and an attributed commit sails through with nothing said. A safety net that is
# missing is worse than one that was never claimed, so say so instead of passing silently.
if ! command -v jq >/dev/null 2>&1; then
  echo "hexagram: jq is not installed, so the AI-attribution check did not run." >&2
  exit 0
fi

cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null) || exit 0
[ -n "$cmd" ] || exit 0

# only look at commits
printf '%s' "$cmd" | grep -qE '\bgit\b[^|;]*\bcommit\b' || exit 0

if printf '%s' "$cmd" | grep -qiE 'co-authored-by:[^"]*<(noreply|claude)@anthropic\.com>|generated with \[claude code\]'; then
  cat >&2 <<'MSG'
This commit message carries AI attribution, which the house style forbids.

The trailer creates no GitHub contributor, but the commit page renders the
co-author as a linked profile anyway: visible, permanent, and not undone by
rewriting history alone.

Rewrite the message without it. If this repo has .githooks/commit-msg wired
(`git config core.hooksPath .githooks`) it would have been stripped anyway.
MSG
  exit 2
fi
exit 0
