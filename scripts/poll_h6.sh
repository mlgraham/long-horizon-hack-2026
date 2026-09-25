#!/usr/bin/env bash
# Retry the H6 (FLUX cover) hinge every 5 minutes until it passes or 2 hours pass. Detached, log-only.
cd "$(dirname "$0")/.."
export PATH="$PWD/.venv/bin:$PATH"
LOG="${1:-/tmp/h6-poll.log}"; SCRATCH="${2:-/tmp/ledger-hinge-h6}"
for attempt in $(seq 1 24); do
  echo "== attempt $attempt at $(date '+%H:%M:%S')" >> "$LOG"
  if SCRATCH="$SCRATCH" bash scripts/hinges.sh H6 >> "$LOG" 2>&1; then echo "H6 PASSED at $(date '+%H:%M:%S')" >> "$LOG"; exit 0; fi
  sleep 300
done
echo "H6 gave up after 2 hours at $(date '+%H:%M:%S')" >> "$LOG"; exit 1
