"""The persist / derived / discarded split, measured on the ledger as it stands."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from ledger import brief as brief_module
from ledger import events
from ledger.store import Ledger

log = logging.getLogger(__name__)


@dataclass
class Stats:
    persisted_bytes: int
    entries: int
    brief_lines: int
    brief_bytes: int
    discarded_bytes: int
    ticks: int
    tokens_in: int
    tokens_out: int

    @property
    def discarded_per_persisted(self) -> float:
        return self.discarded_bytes / self.persisted_bytes if self.persisted_bytes else 0.0

    def as_dict(self) -> dict:
        data = asdict(self)
        data["discarded_per_persisted"] = round(self.discarded_per_persisted, 3)
        return data


def _size(path: Path) -> int:
    """Bytes of the file, following a symlink (this repo's .ledger/STATUS.md points at ../STATUS.md)."""
    try:
        return path.resolve().stat().st_size
    except FileNotFoundError:
        return 0


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def measure(ledger: Ledger) -> Stats:
    persisted = sum(_size(path) for path in (ledger.status, ledger.gates_path, ledger.obligations_path, ledger.pause_path))
    brief = brief_module.build(ledger)
    rows = events.read_events(ledger)
    ticks = [row for row in rows if row.get("kind") == "tick"]
    return Stats(
        persisted_bytes=persisted,
        entries=len(ledger.entries()),
        brief_lines=brief.count("\n"),  # the same count `ledger resume --check` uses
        brief_bytes=len(brief.encode()),
        discarded_bytes=sum(_int(row.get("bytes_discarded")) for row in ticks),
        ticks=len(ticks),
        tokens_in=sum(_int(row.get("tokens_in")) for row in rows),
        tokens_out=sum(_int(row.get("tokens_out")) for row in rows),
    )


def render_text(stats: Stats) -> str:
    return (
        f"persisted  {stats.persisted_bytes} bytes in STATUS.md, gates.md, obligations.md, pause.md; {stats.entries} entries\n"
        f"derived    resume brief: {stats.brief_lines} lines, {stats.brief_bytes} bytes (computed now)\n"
        f"discarded  {stats.discarded_bytes} raw bytes over {stats.ticks} ticks; "
        f"tokens in {stats.tokens_in}, tokens out {stats.tokens_out} (all events)\n"
        f"ratio      {stats.discarded_per_persisted:.3f} discarded bytes per persisted byte\n"
    )


def one_line(stats: Stats) -> str:
    return (
        f"stats: persisted {stats.persisted_bytes} B / {stats.entries} entries; "
        f"brief {stats.brief_lines} lines; discarded {stats.discarded_bytes} B over {stats.ticks} ticks; "
        f"{stats.discarded_per_persisted:.3f} discarded per persisted byte"
    )
