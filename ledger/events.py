"""One event per verb. Always appended locally; mirrored to RawTree when a key is present."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field

from ledger import clock, config
from ledger.store import Ledger

log = logging.getLogger(__name__)


@dataclass
class Event:
    ts: str
    kind: str
    host: str
    model: str = ""
    gate: str = ""
    text: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    bytes_discarded: int = 0
    ledger: str = ""  # the resolved .ledger root, so ledgers sharing one RawTree table stay apart
    extra: dict = field(default_factory=dict)

    def row(self) -> dict:
        data = asdict(self)
        data.pop("extra")
        return data


def emit(ledger: Ledger, kind: str, text: str = "", **fields) -> Event:
    """Append to .ledger/events.jsonl, then try the RawTree mirror. The mirror never blocks a verb."""
    event = Event(ts=clock.iso(), kind=kind, host=config.host_name(), text=text[:2000], ledger=ledger_id(ledger), **fields)
    ledger.ensure()
    with ledger.events_path.open("a") as handle:
        handle.write(json.dumps(event.row(), ensure_ascii=False) + "\n")
    try:
        from sponsors import rawtree

        if rawtree.configured():
            # sync_local posts this row plus any backlog and advances .rawtree_offset,
            # so a later `ledger sync` never re-sends what the live mirror already sent.
            rawtree.sync_local(ledger, timeout=5.0)
    except Exception as error:  # noqa: BLE001 - the mirror is best-effort by design
        log.warning("rawtree mirror skipped: %s", error)
    return event


def ledger_id(ledger: Ledger) -> str:
    """The value of the `ledger` column: the id written at init (see Ledger.identity)."""
    return ledger.identity()


def belongs_to(row: dict, ledger: Ledger) -> bool:
    """Whether a row of this ledger's events.jsonl is this ledger's. Rows written before the column existed
    carry no `ledger` field ("" when read) or the old path form; they sit in this ledger's own file, so they
    count as its own."""
    return str(row.get("ledger") or "") in ("", ledger_id(ledger), str(ledger.root.resolve()))


def read_events(ledger: Ledger, limit: int | None = None) -> list[dict]:
    if not ledger.events_path.exists():
        return []
    rows = []
    for number, line in enumerate(ledger.events_path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            # a line cut short by a crash mid-write must not take down events, board, stats or sync
            log.warning("events.jsonl line %d is not JSON; skipped", number)
    return rows[-limit:] if limit else rows
