"""H1: note, pause, resume work from files alone, and the brief stays under 60 lines."""

import re
from pathlib import Path

import pytest

from ledger import brief
from ledger.cli import main
from ledger.store import Ledger, read_table, render_table

STAMP = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} (?:[A-Z]{2,5}|[+-]\d{2}(?:\d{2})?)")


@pytest.fixture
def root(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.delenv("RAWTREE_API_KEY", raising=False)
    monkeypatch.setenv("LEDGER_HOST", "pytest")
    return tmp_path / ".ledger"


def run(root: Path, *argv: str) -> int:
    return main(["--dir", str(root), *argv])


def test_note_is_clock_stamped_and_append_only(root: Path):
    assert run(root, "note", "first thing") == 0
    assert run(root, "note", "second thing", "--body", "- a detail") == 0
    text = (root / "STATUS.md").read_text()
    entries = Ledger(root).entries()
    assert [entry.title for entry in entries] == ["first thing", "second thing"]
    assert all(STAMP.fullmatch(entry.stamp) for entry in entries)
    assert entries[1].body == "- a detail"
    assert text.index("first thing") < text.index("second thing")
    events = (root / "events.jsonl").read_text().splitlines()
    assert len(events) == 2 and '"kind": "note"' in events[0]


def test_gate_flips_only_on_measurement(root: Path, capsys):
    run(root, "gate", "add", "H1", "--threshold", "brief < 60 lines", "--by", "12:30", "--owner", "P1", "--kill", "stop")
    assert Ledger(root).find_gate("H1")["status"] == "open"
    with pytest.raises(SystemExit):
        run(root, "gate", "pass", "H1")  # --measured is required by the parser
    assert run(root, "gate", "pass", "H1", "--measured", "41 lines") == 0
    gate = Ledger(root).find_gate("H1")
    assert gate["status"] == "pass" and gate["measured"] == "41 lines"
    assert "gate H1 PASS" in (root / "STATUS.md").read_text()


def test_obligation_round_trip(root: Path):
    run(root, "obligation", "add", "nimble-key", "--hypothesis-inhabited", "unknown", "--consumer", "watch")
    item = Ledger(root).find_obligation("nimble-key")
    assert item["hypothesis inhabited"] == "unknown" and item["consumer"] == "watch"
    run(root, "obligation", "close", "nimble-key", "--how", "key arrived")
    assert Ledger(root).find_obligation("nimble-key")["status"] == "closed"


def test_pause_then_resume_from_files_alone(root: Path, capsys):
    run(root, "note", "built the store")
    run(root, "gate", "add", "H2", "--threshold", "endpoint answers", "--by", "13:30", "--owner", "P3", "--kill", "local only")
    run(root, "pause", "--resume", "finish the RawTree query", "--cap", "subagents ≤ 2",
        "--ruling", "board reads RawTree not disk", "--first", "plans/design.md")
    pause = Ledger(root).last_pause()
    assert pause is not None and pause.paused
    assert "1. finish the RawTree query" in pause.body
    assert "First file to read: plans/design.md" in pause.body
    assert (root / "pause.md").read_text().startswith("### ⏸ PAUSED")

    capsys.readouterr()
    assert run(root, "resume", "--check", "--quiet") == 0
    out = capsys.readouterr().out
    assert out.startswith("# Resume brief")
    assert "finish the RawTree query" in out
    assert "H2 [open]" in out
    assert out.count("\n") <= brief.MAX_LINES


def test_brief_stays_under_limit_with_many_entries(root: Path):
    for index in range(80):
        run(root, "note", f"entry {index} " + "x" * 200)
    for index in range(12):
        run(root, "gate", "add", f"G{index}", "--threshold", "t" * 100, "--by", "later", "--owner", "me", "--kill", "k")
    for index in range(9):
        run(root, "obligation", "add", f"O{index}", "--hypothesis-inhabited", "no")
    run(root, "pause", "--note", "\n".join(f"line {index}" for index in range(40)))
    text = brief.build(Ledger(root))
    assert text.count("\n") <= brief.MAX_LINES


def test_table_round_trip(tmp_path: Path):
    path = tmp_path / "t.md"
    rows = [{"name": "a|b", "status": "open"}, {"name": "c", "status": ""}]
    path.write_text("# heading\n\n" + render_table(["name", "status"], rows))
    back = read_table(path)
    assert back == [{"name": "a/b", "status": "open"}, {"name": "c", "status": ""}]


@pytest.mark.parametrize("zone_name", ["Asia/Dubai", "America/Sao_Paulo", "Asia/Kolkata", "UTC"])
def test_stamps_parse_back_in_zones_without_letter_abbreviations(root: Path, monkeypatch, zone_name: str):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from ledger import clock

    monkeypatch.setattr(clock, "now", lambda: datetime(2026, 9, 25, 10, 4, tzinfo=ZoneInfo(zone_name)))
    run(root, "note", "written here")
    run(root, "pause", "--resume", "carry on")
    entries = Ledger(root).entries()
    assert [entry.title for entry in entries] == ["written here", "resume here"]
    assert entries[1].paused and all(STAMP.fullmatch(entry.stamp) for entry in entries)


def test_fixed_offset_zone_falls_back_to_numeric_offset(monkeypatch):
    from datetime import datetime, timedelta, timezone

    from ledger import clock

    monkeypatch.setattr(clock, "now", lambda: datetime(2026, 9, 25, 10, 4, tzinfo=timezone(timedelta(hours=5, minutes=30))))
    assert clock.stamp() == "2026-09-25 10:04 +0530"  # strftime("%Z") alone would give "UTC+05:30"


def test_a_torn_events_line_is_skipped(root: Path, capsys):
    from ledger import events

    run(root, "note", "before")
    with (root / "events.jsonl").open("a") as handle:
        handle.write('{"ts": "2026-09-25T10:0\n')  # cut short mid-write
    run(root, "note", "after")
    assert [row["text"] for row in events.read_events(Ledger(root))] == ["before", "after"]
    assert run(root, "events") == 0 and run(root, "stats") == 0 and run(root, "board", "--local") == 0


def test_ledger_identity_is_written_once_and_unique(tmp_path: Path):
    first = Ledger(tmp_path / "a" / ".ledger")
    second = Ledger(tmp_path / "b" / ".ledger")
    assert first.identity() == first.identity()
    assert first.identity() != second.identity()
    assert first.identity().startswith("a-") and (tmp_path / "a" / ".ledger" / "id").exists()
