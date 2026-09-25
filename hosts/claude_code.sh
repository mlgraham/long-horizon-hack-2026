#!/usr/bin/env bash
# The second host, headless: a fresh Claude Code session whose whole context is `ledger resume`.
#
#   hosts/claude_code.sh [LEDGER_DIR] [TASK]
#
# LEDGER_DIR defaults to ./.ledger. TASK defaults to item 1 of the latest ⏸ pause entry.
# The session gets no transcript from the first host. It may only run `ledger`, `ls`, `cat`, `python`
# (for the tests), and read or write files. Works from inside another Claude Code session (CLAUDECODE is unset).
set -euo pipefail

SOURCE_REPO="$(cd "$(dirname "$0")/.." && pwd)"
# Sponsor keys live in the source repo's .env; the scratch repo has none, so export them here.
if [ -f "$SOURCE_REPO/.env" ]; then set -a; . "$SOURCE_REPO/.env"; set +a; fi

LEDGER_DIR="${1:-$PWD/.ledger}"
LEDGER_DIR="$(cd "$(dirname "$LEDGER_DIR")" && pwd)/$(basename "$LEDGER_DIR")"
REPO="$(dirname "$LEDGER_DIR")"
TASK="${2:-}"
BRIEF="$(ledger --dir "$LEDGER_DIR" resume --quiet --model claude-code-headless)"

if [ -z "$TASK" ]; then
  TASK="Do the task in item 1 of the pause entry above."
fi

PROMPT="$BRIEF

You are a fresh session with no memory of the previous host. $TASK
Work only inside $REPO. Use the 'ledger' command with --dir $LEDGER_DIR:
run 'ledger note \"<what you did>\"' after each real step. If the brief lists an open gate for this task, run its
test yourself and flip it with 'ledger gate pass <name> --measured \"<the exact output line>\"' (or 'gate fail');
never claim a pass you did not run. Finish with 'ledger note \"done: <summary>\"'."

cd "$REPO"
env -u CLAUDECODE LEDGER_HOST=claude-code-headless \
  claude -p "$PROMPT" \
    --allowedTools "Bash(ledger:*),Bash(ls:*),Bash(cat:*),Bash(python:*),Read,Write,Edit" \
    --permission-mode acceptEdits < /dev/null
