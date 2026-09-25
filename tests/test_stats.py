"""ledger stats: the persist / derived / discarded split, from files alone."""

import json
from pathlib import Path

import pytest

from ledger import config
from ledger import stats as stats_module
from ledger.cli import main
from ledger.store import Ledger


@pytest.fixture
def root(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setattr(config, "_loaded", True)  # a real .env must never leak into these tests
    monkeypatch.delenv("RAWTREE_API_KEY", raising=False)
    monkeypatch.setenv("LEDGER_HOST", "pytest")
    return tmp_path / ".ledger"


def run(root: Path, *argv: str) -> int:
    return main(["--dir", str(root), *argv])


def add_events(root: Path, rows: list[dict]) -> None:
    with (root / "events.jsonl").open("a") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def test_empty_ledger_prints_zeros(root: Path, capsys):
    assert run(root, "stats") == 0
    out = capsys.readouterr().out
    assert "0 entries" in out and "0 raw bytes over 0 ticks" in out and "0.000 discarded" in out
    assert run(root, "stats", "--json") == 0
    data = json.loads(capsys.readouterr().out)
    assert data["persisted_bytes"] == 0 and data["ticks"] == 0 and data["discarded_per_persisted"] == 0.0
    assert not root.exists()  # stats without --note writes nothing


def test_split_is_measured_from_files(root: Path, capsys):
    run(root, "note", "first")
    run(root, "pause", "--resume", "carry on")
    add_events(root, [
        {"ts": "2026-09-25T10:00:00-07:00", "kind": "tick", "host": "pytest", "bytes_discarded": 4000, "tokens_in": 100, "tokens_out": 10},
        {"ts": "2026-09-25T10:10:00-07:00", "kind": "tick", "host": "pytest", "bytes_discarded": 1000, "tokens_in": 50, "tokens_out": 5},
        {"ts": "2026-09-25T10:20:00-07:00", "kind": "resume", "host": "pytest", "bytes_discarded": 999, "tokens_in": 7},
    ])
    ledger = Ledger(root)
    measured = stats_module.measure(ledger)
    expected_persisted = sum(path.stat().st_size for path in (ledger.status, ledger.gates_path, ledger.obligations_path, ledger.pause_path))
    assert measured.persisted_bytes == expected_persisted
    assert measured.entries == 2
    assert measured.ticks == 2 and measured.discarded_bytes == 5000  # only tick events count as discarded
    assert measured.tokens_in == 157 and measured.tokens_out == 15  # tokens over all events
    assert measured.brief_lines > 0 and measured.brief_bytes > measured.brief_lines
    assert measured.discarded_per_persisted == pytest.approx(5000 / expected_persisted)
    events_before = (root / "events.jsonl").read_text().count("\n")
    run(root, "stats")
    assert (root / "events.jsonl").read_text().count("\n") == events_before


def test_status_symlink_is_resolved(root: Path, tmp_path: Path):
    run(root, "note", "real file lives outside")
    outside = tmp_path / "STATUS.md"
    (root / "STATUS.md").rename(outside)
    (root / "STATUS.md").symlink_to(outside)
    ledger = Ledger(root)
    assert stats_module.measure(ledger).persisted_bytes >= outside.stat().st_size
    assert stats_module.measure(ledger).entries == 1


def test_note_appends_entry_and_emits_one_event(root: Path, capsys):
    run(root, "note", "first")
    assert run(root, "stats", "--note") == 0
    entries = Ledger(root).entries()
    assert entries[-1].title.startswith("stats: persisted ")
    kinds = [json.loads(line)["kind"] for line in (root / "events.jsonl").read_text().splitlines()]
    assert kinds == ["note", "stats"]
