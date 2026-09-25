"""The board: two tables over the event stream, from RawTree when a key is set, else the local mirror."""

from __future__ import annotations

import html
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from ledger import clock, events
from ledger.store import Ledger

log = logging.getLogger(__name__)

BOARD_COLUMNS = ["kind", "host", "events", "bytes_discarded", "tokens_in", "tokens_out", "last_ts"]
RECENT_COLUMNS = ["ts", "kind", "host", "gate", "text"]
SOURCE_RAWTREE = "RawTree"
SOURCE_LOCAL = "local mirror (.ledger/events.jsonl)"


@dataclass
class Board:
    source: str
    hours: int
    recent_hours: int
    rollup: list[dict] = field(default_factory=list)
    recent: list[dict] = field(default_factory=list)
    generated: str = ""


def parse_ts(value: str) -> datetime:
    """Local rows carry an offset; RawTree rows are ISO strings with offsets. Both come back timezone-aware."""
    parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def display_ts(value: str) -> str:
    try:
        return parse_ts(value).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    except ValueError:
        return str(value)


# ---- sources ------------------------------------------------------------------


def compute_local(rows: list[dict], hours: int, recent_hours: int, limit: int = 200, now: datetime | None = None) -> tuple[list[dict], list[dict]]:
    """The same two tables the `board` and `what_changed_last_hour` endpoints return."""
    moment = now or clock.now()
    board_since = moment - timedelta(hours=hours)
    recent_since = moment - timedelta(hours=recent_hours)
    groups: dict[tuple[str, str], dict] = {}
    recent: list[tuple[datetime, dict]] = []
    for row in rows:
        try:
            when = parse_ts(row["ts"])
        except (KeyError, ValueError):
            log.debug("skipping row without a usable ts: %s", row)
            continue
        if when >= board_since:
            key = (row.get("kind", ""), row.get("host", ""))
            group = groups.setdefault(
                key,
                {"kind": key[0], "host": key[1], "events": 0, "bytes_discarded": 0, "tokens_in": 0, "tokens_out": 0, "last_ts": row["ts"], "_last": when},
            )
            group["events"] += 1
            group["bytes_discarded"] += int(row.get("bytes_discarded") or 0)
            group["tokens_in"] += int(row.get("tokens_in") or 0)
            group["tokens_out"] += int(row.get("tokens_out") or 0)
            if when > group["_last"]:
                group["_last"], group["last_ts"] = when, row["ts"]
        if when >= recent_since:
            recent.append((when, row))
    rollup = sorted(groups.values(), key=lambda group: group["_last"], reverse=True)
    for group in rollup:
        group.pop("_last")
    recent.sort(key=lambda pair: pair[0], reverse=True)
    return rollup, [row for _, row in recent[:limit]]


def build(ledger: Ledger, hours: int = 24, recent_hours: int = 1, prefer_remote: bool = True) -> Board:
    board = Board(source=SOURCE_LOCAL, hours=hours, recent_hours=recent_hours)
    fetched = False
    if prefer_remote:
        try:
            from sponsors import rawtree

            if rawtree.configured():
                scope = events.ledger_id(ledger)
                board.rollup = rawtree.board(hours, ledger_root=scope)
                board.recent = rawtree.what_changed(recent_hours, ledger_root=scope)
                board.source = SOURCE_RAWTREE
                fetched = True
        except Exception as error:  # noqa: BLE001 - fall back to the local mirror
            log.warning("rawtree board unavailable, using the local mirror: %s", error)
    if not fetched:
        board.rollup, board.recent = compute_local(events.read_events(ledger), hours, recent_hours)
    board.generated = clock.stamp()
    return board


# ---- rendering ----------------------------------------------------------------


def _cells(row: dict, columns: list[str], text_width: int | None) -> list[str]:
    cells = []
    for column in columns:
        value = row.get(column, "")
        if column in ("ts", "last_ts"):
            value = display_ts(value)
        value = str(value).replace("\n", " ")
        if column == "text" and text_width and len(value) > text_width:
            value = value[: text_width - 1] + "…"
        cells.append(value)
    return cells


def _text_table(columns: list[str], rows: list[dict]) -> str:
    if not rows:
        return "  (no events in this window)\n"
    grid = [columns] + [_cells(row, columns, 60) for row in rows]
    widths = [max(len(line[index]) for line in grid) for index in range(len(columns))]
    lines = ["  ".join(cell.ljust(width) for cell, width in zip(line, widths)).rstrip() for line in grid]
    lines.insert(1, "  ".join("-" * width for width in widths))
    return "\n".join(lines) + "\n"


def render_text(board: Board) -> str:
    return (
        f"source: {board.source}\n\n"
        f"board, last {board.hours}h (one row per kind and host)\n"
        + _text_table(BOARD_COLUMNS, board.rollup)
        + f"\nwhat changed, last {board.recent_hours}h (newest first)\n"
        + _text_table(RECENT_COLUMNS, board.recent)
        + f"\ngenerated {board.generated}\n"
    )


def _html_table(columns: list[str], rows: list[dict], numeric: set[str]) -> str:
    if not rows:
        return '<p class="empty">No events in this window.</p>'
    head = "".join(f'<th class="{"num" if column in numeric else ""}">{html.escape(column.replace("_", " "))}</th>' for column in columns)
    body = []
    for row in rows:
        cells = _cells(row, columns, 240)
        body.append(
            "<tr>"
            + "".join(
                f'<td class="{"num" if column in numeric else column}">{html.escape(cell)}</td>'
                for column, cell in zip(columns, cells)
            )
            + "</tr>"
        )
    return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


STYLE = """
:root { --bg:#fbfaf7; --fg:#1d1d1b; --muted:#6b6a65; --rule:#e4e1d9; --accent:#2f5d50; --row:#f3f1ec; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#161615; --fg:#ecebe6; --muted:#9a9890; --rule:#2e2d2a; --accent:#8cc4b0; --row:#1e1e1c; }
}
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
  font:15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
main { max-width:960px; margin:0 auto; padding:24px 16px 40px; }
header h1 { font-size:1.4rem; margin:0 0 4px; letter-spacing:-0.01em; }
.source { margin:0 0 24px; color:var(--muted); font-size:0.9rem; }
.source strong { color:var(--accent); font-weight:600; }
h2 { font-size:1rem; margin:28px 0 8px; }
h2 span { color:var(--muted); font-weight:400; }
.scroll { overflow-x:auto; -webkit-overflow-scrolling:touch; border-top:1px solid var(--rule); }
table { border-collapse:collapse; width:100%; font-size:0.875rem; }
th, td { text-align:left; padding:6px 10px 6px 0; border-bottom:1px solid var(--rule); vertical-align:top; }
th { color:var(--muted); font-weight:500; white-space:nowrap; }
td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; }
td.ts, td.last_ts { white-space:nowrap; font-variant-numeric:tabular-nums; color:var(--muted); }
td.text { min-width:16ch; }
tbody tr:nth-child(even) { background:var(--row); }
.empty { color:var(--muted); font-style:italic; }
footer { margin-top:32px; color:var(--muted); font-size:0.8rem; }
"""


def render_html(board: Board) -> str:
    numeric = {"events", "bytes_discarded", "tokens_in", "tokens_out"}
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ledger board</title>
<style>{STYLE}</style>
</head>
<body>
<main>
<header>
<h1>Ledger board</h1>
<p class="source">Source: <strong>{html.escape(board.source)}</strong></p>
</header>
<h2>Board <span>· last {board.hours}h · one row per kind and host</span></h2>
{_html_table(BOARD_COLUMNS, board.rollup, numeric)}
<h2>What changed <span>· last {board.recent_hours}h · newest first</span></h2>
{_html_table(RECENT_COLUMNS, board.recent, numeric)}
<footer>Generated {html.escape(board.generated)} by <code>ledger board</code>.</footer>
</main>
</body>
</html>
"""
