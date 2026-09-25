#!/usr/bin/env bash
# The 3-minute demo: plan, act, observe, self-correct across a build cycle, with the history thrown away.
# Run from the repo root with the venv on PATH:
#
#   source .venv/bin/activate && bash demo/run.sh
#
# Needs: ledger on PATH, Ollama with hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF pulled, and the claude CLI.
# Set DEMO_SKIP_HOST=1 to skip step 5 (the headless Claude Code session).
# Set DEMO_WAIT=1 to pause for Enter before starting, so a screen recording can begin first.
# Each step's elapsed time is written to $DEMO/steps.tsv for scripts/narrate.py.
# Set DEMO_PAUSE=<seconds> to hold after steps 3, 4 and 5 so a narration has room (8 is comfortable).
# Set DEMO_CUES=<cues.tsv> (from scripts/narration_track.py) to pace each step to a pre-made narration:
# step k waits until its cue time before starting. DEMO_AUDIO=<wav> plays the track from the start.
set -euo pipefail

SOURCE_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEMO=/tmp/ledger-demo
LEDGER_DIR="$DEMO/.ledger"
URL="https://news.ycombinator.com"
TOPIC="${TOPIC:-AI agents news today}"   # Nimble searches this live; without a key, URL is fetched directly

STEPS_FILE=""
START_EPOCH=0
now_s() { python3 -c 'import time; print(f"{time.time():.2f}")'; }
wait_for_cue() {
  [ -n "${DEMO_CUES:-}" ] || return 0
  local cue
  cue="$(awk -F'\t' -v k="$1" '$1==k{print $2}' "$DEMO_CUES")"
  [ -n "$cue" ] || return 0
  python3 - "$START_EPOCH" "$cue" <<'PY'
import sys, time
start, cue = float(sys.argv[1]), float(sys.argv[2])
remaining = start + cue - time.time()
if remaining > 0:
    time.sleep(remaining)
PY
}
step() {
  wait_for_cue "${1%%.*}"
  if [ -n "$STEPS_FILE" ]; then
    printf '%s\t%s\n' "${1%%.*}" "$(python3 -c "import time; print(f'{time.time() - $START_EPOCH:.2f}')")" >> "$STEPS_FILE"
  fi
  printf '\n\033[1m== %s ==\033[0m\n' "$*"
}

command -v ledger >/dev/null || { echo "ledger is not on PATH: source .venv/bin/activate" >&2; exit 1; }

if [ "${DEMO_WAIT:-0}" = "1" ]; then
  printf 'Start the screen recording, then press Enter to begin.'; read -r _
fi
case "$DEMO" in /tmp/ledger-demo) rm -rf "$DEMO" ;; esac
mkdir -p "$DEMO/tests"
START_EPOCH="$(now_s)"
STEPS_FILE="$DEMO/steps.tsv"; : > "$STEPS_FILE"
if [ -n "${DEMO_AUDIO:-}" ]; then afplay "$DEMO_AUDIO" & fi

step "1. A scratch repo and a fresh ledger"
git -C "$DEMO" init -q
ledger --dir "$LEDGER_DIR" init
ls "$LEDGER_DIR"

step "2. Observe: three ticks pull live web data (Nimble search, or the URL without a key), Liquid distills, raw is discarded"
for count in 1 2 3; do
  echo "-- tick $count"
  ledger --dir "$LEDGER_DIR" tick "$TOPIC" --url "$URL" --distiller liquid
done

step "3. Plan: the spec is a gate, the tests are its measurement, the first implementation is wrong"
cat > "$DEMO/slug.py" <<'PY'
"""Spec: slugify(text) returns lowercase ASCII letters and digits, words joined by single hyphens,
no leading or trailing hyphen. See tests/test_slug.py; the gate `build` passes when they do."""


def slugify(text: str) -> str:
    return text  # first attempt: wrong on purpose, the next host must self-correct
PY
cat > "$DEMO/tests/test_slug.py" <<'PY'
from slug import slugify


def test_lowercases_and_hyphenates():
    assert slugify("Hello World") == "hello-world"


def test_strips_punctuation():
    assert slugify("Ledger, over history!") == "ledger-over-history"


def test_collapses_and_trims():
    assert slugify("  two   spaces--and dashes  ") == "two-spaces-and-dashes"
PY
ledger --dir "$LEDGER_DIR" gate add build \
  --threshold "python -m pytest -q tests passes all 3 tests in tests/test_slug.py" \
  --by "this session" --owner "whichever host resumes" --kill "task stays open; nothing is claimed"
ledger --dir "$LEDGER_DIR" note "spec written as gate build; tests/test_slug.py written; slug.py stub returns its input" \
  --body "- first pytest run below fails on purpose; the fix is the next host's job"
echo "-- pytest before the fix"
(cd "$DEMO" && python -m pytest -q tests 2>&1 | tail -1) || true
sleep "${DEMO_PAUSE:-0}"

step "4. Pause mid-task, then the brief: everything the next host will know"
ledger --dir "$LEDGER_DIR" pause \
  --resume "Fix slug.py so that 'python -m pytest -q tests' passes; iterate until green; then run: ledger gate pass build --measured \"<the exact pytest summary line>\"" \
  --cap "edit only slug.py; do not touch the tests" \
  --first "tests/test_slug.py" \
  --cover
ls "$LEDGER_DIR/covers/" 2>/dev/null || echo "(no cover: BFL_API_KEY not set or no credits)"
ledger --dir "$LEDGER_DIR" resume --quiet
sleep "${DEMO_PAUSE:-0}"

step "5. Act, observe, self-correct: a different session, fed only by the brief, finishes the build cycle"
if [ "${DEMO_SKIP_HOST:-0}" = "1" ]; then
  echo "(skipped: DEMO_SKIP_HOST=1)"
else
  # Run the second host in the background and show the ledger entries it writes, as it writes them.
  (cd "$DEMO" && bash "$SOURCE_REPO/hosts/claude_code.sh" "$LEDGER_DIR" > "$DEMO/host.out" 2>&1) &
  HOST_PID=$!
  SEEN=$(grep -c '^### ' "$LEDGER_DIR/STATUS.md")
  echo "-- the second host is working; its ledger entries appear below as it writes them"
  while kill -0 "$HOST_PID" 2>/dev/null; do
    NOW=$(grep -c '^### ' "$LEDGER_DIR/STATUS.md")
    if [ "$NOW" -gt "$SEEN" ]; then
      grep '^### ' "$LEDGER_DIR/STATUS.md" | tail -n "$((NOW - SEEN))" | sed 's/^### /  ledger ← /'
      SEEN=$NOW
    fi
    sleep 1
  done
  wait "$HOST_PID" || true
  echo "-- the second host's closing words"
  sed -n '1,6p' "$DEMO/host.out"
  echo "-- pytest after the second host"
  (cd "$DEMO" && python -m pytest -q tests 2>&1 | tail -1) || true
  echo "-- gates"
  ledger --dir "$LEDGER_DIR" gate list
fi
sleep "${DEMO_PAUSE:-0}"

step "6. The record: what persisted, what was discarded, and the board as a query"
ledger --dir "$LEDGER_DIR" stats
echo
ledger --dir "$LEDGER_DIR" board
echo
sleep "${DEMO_PAUSE:-0}"; sleep "${DEMO_PAUSE:-0}"; sleep "${DEMO_PAUSE:-0}"   # hold on the board for the last narration block
wait_for_cue end   # paced mode: stay on the board until the track ends
printf 'end\t%s\n' "$(python3 -c "import time; print(f'{time.time() - $START_EPOCH:.2f}')")" >> "$STEPS_FILE"
echo "ledger: $LEDGER_DIR/STATUS.md   board: $LEDGER_DIR/board.html   steps: $STEPS_FILE"
