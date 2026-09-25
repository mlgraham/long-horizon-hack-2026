"""The files. Plain Markdown under .ledger/ in whatever repo the tool runs in."""

from __future__ import annotations

import logging
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from ledger import clock

log = logging.getLogger(__name__)

GATE_COLUMNS = ["name", "threshold", "by", "owner", "kill criterion", "status", "measured"]
OBLIGATION_COLUMNS = ["name", "hypothesis inhabited", "consumer", "status"]

STATUS_HEADER = """# STATUS — ledger

Append-only. Every heading is stamped from the clock in the command that writes it. Newest entry last.

## Log
"""

GATES_HEADER = """# Gates

Pre-registered hinges. A gate is written before the work starts: a threshold, a date, an owner and a kill
criterion. `ledger gate pass|fail <name> --measured "<value>"` flips it. Nobody re-prices a failed gate by argument.

"""

OBLIGATIONS_HEADER = """# Obligations

Every named-but-unproved claim. *Hypothesis inhabited* asks whether the claim can be met at all: an obligation
nobody can satisfy is worse than a gap, because it reads as closed.

"""

HEADING_RE = re.compile(rf"^### (?P<stamp>\d{{4}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}} {clock.ZONE_PATTERN}) — (?P<title>.*)$")
PAUSE_RE = re.compile(rf"^### ⏸ PAUSED (?P<stamp>\d{{4}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}} {clock.ZONE_PATTERN}) — (?P<title>.*)$")


@dataclass
class Entry:
    stamp: str
    title: str
    body: str
    paused: bool = False


def find_root(start: Path | None = None) -> Path:
    """The .ledger directory: LEDGER_DIR if set, else the nearest .ledger walking up, else ./.ledger."""
    explicit = os.environ.get("LEDGER_DIR")
    if explicit:
        return Path(explicit).expanduser().resolve()
    here = (start or Path.cwd()).resolve()
    for directory in [here, *here.parents]:
        candidate = directory / ".ledger"
        if candidate.is_dir():
            return candidate
        if (directory / ".git").exists():
            return directory / ".ledger"
    return here / ".ledger"


class Ledger:
    def __init__(self, root: Path | None = None):
        self.root = root or find_root()
        self.status = self.root / "STATUS.md"
        self.gates_path = self.root / "gates.md"
        self.obligations_path = self.root / "obligations.md"
        self.pause_path = self.root / "pause.md"
        self.events_path = self.root / "events.jsonl"
        self.id_path = self.root / "id"
        self.covers = self.root / "covers"

    # ---- setup -------------------------------------------------------------

    def exists(self) -> bool:
        return self.status.exists()

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.status.exists():
            self.status.write_text(STATUS_HEADER)
        if not self.gates_path.exists():
            self.gates_path.write_text(GATES_HEADER + render_table(GATE_COLUMNS, []))
        if not self.obligations_path.exists():
            self.obligations_path.write_text(OBLIGATIONS_HEADER + render_table(OBLIGATION_COLUMNS, []))
        if not self.id_path.exists():
            self.id_path.write_text(f"{self.root.parent.name}-{uuid.uuid4().hex[:12]}\n")

    def identity(self) -> str:
        """A stable id for this ledger, written once at init: <repo name>-<12 hex>. Two ledgers created at the
        same path on different days get different ids, so a shared event table never mixes them."""
        self.ensure()
        return self.id_path.read_text().strip()

    # ---- STATUS.md ---------------------------------------------------------

    def append(self, title: str, body: str = "", paused: bool = False) -> Entry:
        """Append one clock-stamped heading. Returns what was written."""
        self.ensure()
        when = clock.stamp()
        marker = "### ⏸ PAUSED " if paused else "### "
        heading = f"{marker}{when} — {title.strip()}"
        text = f"\n{heading}\n"
        if body.strip():
            text += f"\n{body.rstrip()}\n"
        with self.status.open("a") as handle:
            handle.write(text)
        log.info("appended %s", heading)
        return Entry(stamp=when, title=title.strip(), body=body.rstrip(), paused=paused)

    def entries(self) -> list[Entry]:
        if not self.status.exists():
            return []
        found: list[Entry] = []
        current: Entry | None = None
        body: list[str] = []
        for line in self.status.read_text().splitlines():
            match = HEADING_RE.match(line)
            pause = PAUSE_RE.match(line)
            if match or pause:
                if current is not None:
                    current.body = "\n".join(body).strip()
                    found.append(current)
                hit = match or pause
                current = Entry(stamp=hit["stamp"], title=hit["title"].strip(), body="", paused=bool(pause))
                body = []
            elif current is not None:
                body.append(line)
        if current is not None:
            current.body = "\n".join(body).strip()
            found.append(current)
        return found

    def last_pause(self) -> Entry | None:
        pauses = [entry for entry in self.entries() if entry.paused]
        return pauses[-1] if pauses else None

    # ---- tables ------------------------------------------------------------

    def gates(self) -> list[dict[str, str]]:
        return read_table(self.gates_path)

    def obligations(self) -> list[dict[str, str]]:
        return read_table(self.obligations_path)

    def upsert_gate(self, row: dict[str, str]) -> None:
        self.ensure()
        rows = [gate for gate in self.gates() if gate["name"] != row["name"]]
        rows.append({column: row.get(column, "") for column in GATE_COLUMNS})
        self.gates_path.write_text(GATES_HEADER + render_table(GATE_COLUMNS, rows))

    def upsert_obligation(self, row: dict[str, str]) -> None:
        self.ensure()
        rows = [item for item in self.obligations() if item["name"] != row["name"]]
        rows.append({column: row.get(column, "") for column in OBLIGATION_COLUMNS})
        self.obligations_path.write_text(OBLIGATIONS_HEADER + render_table(OBLIGATION_COLUMNS, rows))

    def find_gate(self, name: str) -> dict[str, str] | None:
        return next((gate for gate in self.gates() if gate["name"] == name), None)

    def find_obligation(self, name: str) -> dict[str, str] | None:
        return next((item for item in self.obligations() if item["name"] == name), None)


# ---- Markdown tables -------------------------------------------------------


def _cell(value: str) -> str:
    return str(value).replace("|", "/").replace("\n", " ").strip()


def render_table(columns: list[str], rows: list[dict[str, str]]) -> str:
    lines = ["| " + " | ".join(columns) + " |", "|" + "|".join("---" for _ in columns) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(_cell(row.get(column, "")) for column in columns) + " |")
    return "\n".join(lines) + "\n"


def read_table(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    columns: list[str] | None = None
    rows: list[dict[str, str]] = []
    for line in path.read_text().splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if columns is None:
            columns = cells
            continue
        if all(set(cell) <= set("-: ") for cell in cells):
            continue
        rows.append(dict(zip(columns, cells)))
    return rows
