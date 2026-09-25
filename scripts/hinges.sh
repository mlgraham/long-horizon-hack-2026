#!/usr/bin/env bash
# Run one pre-registered hinge test. Prints the measurement; the operator then records it with `ledger gate pass|fail`.
#
#   scripts/hinges.sh H2   RawTree: sync the local mirror, then query the last hour back
#   scripts/hinges.sh H4   Nimble: three ticks on a real topic in a scratch ledger, raw bytes discarded
#   scripts/hinges.sh H5   Liquid: one tick on a real page with the Liquid distiller
#   scripts/hinges.sh H6   FLUX: a pause with --cover in a scratch ledger
set -uo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/.venv/bin:$PATH"
SCRATCH="${SCRATCH:-/tmp/ledger-hinge}"
TOPIC="${TOPIC:-Long Horizon Agents Hackathon San Francisco}"
URL="${URL:-https://news.ycombinator.com}"

case "${1:-}" in
  H2)
    ledger sync || exit 1
    python - <<'PY'
from sponsors import rawtree
rows = rawtree.what_changed(hours=1, limit=5)
print(f"what_changed(1h) returned {len(rows)} rows; first: {rows[0] if rows else None}")
PY
    ;;
  H4)
    rm -rf "$SCRATCH"; mkdir -p "$SCRATCH"
    for tick in 1 2 3; do
      echo "== tick $tick"; ledger --dir "$SCRATCH/.ledger" tick "$TOPIC" --distiller liquid || exit 1
    done
    echo "== ledger size vs bytes discarded"
    wc -c "$SCRATCH/.ledger/STATUS.md"
    python -c "import json;rows=[json.loads(l) for l in open('$SCRATCH/.ledger/events.jsonl')];print('discarded:',sum(r['bytes_discarded'] for r in rows if r['kind']=='tick'),'bytes over',sum(1 for r in rows if r['kind']=='tick'),'ticks')"
    ;;
  H5)
    rm -rf "$SCRATCH"; mkdir -p "$SCRATCH"
    time ledger --dir "$SCRATCH/.ledger" tick "$TOPIC" --url "$URL" --distiller liquid
    ;;
  H6)
    rm -rf "$SCRATCH"; mkdir -p "$SCRATCH"
    ledger --dir "$SCRATCH/.ledger" note "hinge H6: a pause with a FLUX cover" >/dev/null
    ledger --dir "$SCRATCH/.ledger" pause --resume "nothing; this is the cover test" --cover || exit 1
    ls -la "$SCRATCH/.ledger/covers/"
    if ! ls "$SCRATCH/.ledger/covers/"*.jpg >/dev/null 2>&1; then echo "H6: no cover file landed (see the warning above)"; exit 1; fi
    echo "H6: cover landed"
    ;;
  *) sed -n '2,8p' "$0"; exit 2 ;;
esac
