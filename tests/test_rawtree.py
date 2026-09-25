"""RawTree mirror: insert shape, idempotent sync, no double posting, clean refusal without a key."""

import json
from pathlib import Path

import pytest

from ledger.cli import main
from ledger.store import Ledger
from sponsors import rawtree


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


@pytest.fixture
def root(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("LEDGER_HOST", "pytest")
    return tmp_path / ".ledger"


def test_post_events_sends_json_array_with_bearer(monkeypatch):
    monkeypatch.setenv("RAWTREE_API_KEY", "rt_test")
    monkeypatch.setenv("RAWTREE_DATABASE", "hack")
    seen = {}

    def fake_urlopen(request, timeout=0):
        seen["url"] = request.full_url
        seen["headers"] = {key.lower(): value for key, value in request.header_items()}
        seen["body"] = json.loads(request.data.decode())
        return FakeResponse({"inserted": 2})

    monkeypatch.setattr(rawtree.urllib.request, "urlopen", fake_urlopen)
    rows = [{"ts": "2026-09-25T10:04:00-07:00", "kind": "note"}, {"ts": "2026-09-25T10:05:00-07:00", "kind": "tick"}]
    assert rawtree.post_events(rows) == 2
    assert seen["url"] == "https://api.rawtree.com/v1/tables/ledger_events"
    assert seen["headers"]["authorization"] == "Bearer rt_test"
    assert seen["headers"]["x-rawtree-database"] == "hack"
    assert seen["body"] == rows


def test_query_posts_sql_and_returns_data(monkeypatch):
    monkeypatch.setenv("RAWTREE_API_KEY", "rt_test")
    seen = {}

    def fake_urlopen(request, timeout=0):
        seen["body"] = json.loads(request.data.decode())
        return FakeResponse({"meta": [], "data": [{"n": 1}], "rows": 1})

    monkeypatch.setattr(rawtree.urllib.request, "urlopen", fake_urlopen)
    assert rawtree.what_changed(hours=2, limit=5, ledger_root="/x/.ledger") == [{"n": 1}]
    assert "INTERVAL 2 HOUR" in seen["body"]["sql"] and "ledger = '/x/.ledger'" in seen["body"]["sql"]
    assert rawtree.board(hours=3) == [{"n": 1}]
    assert "GROUP BY kind, host" in seen["body"]["sql"] and "ledger =" not in seen["body"]["sql"]


def test_sync_is_idempotent(root: Path, monkeypatch):
    posted: list[list[dict]] = []
    monkeypatch.setattr(rawtree, "post_events", lambda rows, timeout=15.0: posted.append(rows) or len(rows))
    for index in range(3):
        main(["--dir", str(root), "note", f"entry {index}"])
    ledger = Ledger(root)
    assert rawtree.sync_local(ledger) == 3
    assert rawtree.read_offset(ledger) == 3
    assert rawtree.sync_local(ledger) == 0
    main(["--dir", str(root), "note", "entry 3"])
    assert rawtree.sync_local(ledger) == 1
    assert (root / ".rawtree_offset").read_text().strip() == "4"
    assert all("ledger" in row for batch in posted for row in batch)


def test_live_mirror_and_sync_do_not_double_post(root: Path, monkeypatch):
    monkeypatch.setenv("RAWTREE_API_KEY", "rt_test")
    posted: list[dict] = []
    monkeypatch.setattr(rawtree, "post_events", lambda rows, timeout=15.0: posted.extend(rows) or len(rows))
    main(["--dir", str(root), "note", "mirrored live"])
    main(["--dir", str(root), "note", "also live"])
    assert len(posted) == 2
    assert main(["--dir", str(root), "sync"]) == 0
    assert len(posted) == 2


def test_sync_without_key_exits_1(root: Path):
    main(["--dir", str(root), "note", "offline"])
    assert main(["--dir", str(root), "sync"]) == 1
    assert not (root / ".rawtree_offset").exists()


def test_sync_skips_a_torn_line(root: Path, monkeypatch):
    posted: list[dict] = []
    monkeypatch.setattr(rawtree, "post_events", lambda rows, timeout=15.0: posted.extend(rows) or len(rows))
    main(["--dir", str(root), "note", "one"])
    with (root / "events.jsonl").open("a") as handle:
        handle.write('{"ts": "2026-09-25T10:00:00-07:00", "kind": "no')
        handle.write("\n")
    main(["--dir", str(root), "note", "two"])
    assert rawtree.sync_local(Ledger(root)) == 2
    assert rawtree.read_offset(Ledger(root)) == 3
