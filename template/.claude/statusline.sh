#!/bin/bash
input=$(cat)
command -v jq >/dev/null 2>&1 || exit 0

# The statusline receives its JSON on stdin; project_dir is the documented field.
# Fallbacks keep it working if the schema or the invocation ever changes.
BASE=$(echo "$input" | jq -r '.workspace.project_dir // .cwd // empty')
BASE="${BASE:-${CLAUDE_PROJECT_DIR:-$PWD}}"

MODEL=$(echo "$input" | jq -r '.model.display_name // "?"')
PCT=$(echo "$input" | jq -r '.context_window.used_percentage // 0' | cut -d. -f1)
COST=$(echo "$input" | jq -r '.cost.total_cost_usd // 0')
COST=$(printf '%.2f' "$COST" 2>/dev/null || echo 0)

# Context bar with color
if [ "$PCT" -ge 90 ]; then BAR_COLOR='\033[31m'
elif [ "$PCT" -ge 70 ]; then BAR_COLOR='\033[33m'
else BAR_COLOR='\033[32m'; fi

FILLED=$((PCT / 10))
EMPTY=$((10 - FILLED))
BAR=""
for ((i=0; i<FILLED; i++)); do BAR="${BAR}#"; done
for ((i=0; i<EMPTY; i++)); do BAR="${BAR}-"; done

# Git status (single repo)
GIT_INFO=""
if git -C "$BASE" rev-parse --git-dir >/dev/null 2>&1; then
  BRANCH=$(git -C "$BASE" symbolic-ref --quiet --short HEAD 2>/dev/null || echo "?")
  CHANGED=$(git -C "$BASE" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
  if [ "$CHANGED" -gt 0 ]; then
    GIT_INFO=" ${BRANCH}*${CHANGED}"
  else
    GIT_INFO=" ${BRANCH}"
  fi
fi

RESET='\033[0m'
DIM='\033[2m'

echo -e "${DIM}${MODEL}${GIT_INFO}${RESET} | ${BAR_COLOR}[${BAR}]${RESET} ${PCT}% | \$${COST}"
