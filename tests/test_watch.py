"""watch/tick from a fixture with the heuristic distiller: a delta is noted, the raw page is not kept."""

from pathlib import Path

from ledger.cli import main
from ledger.store import Ledger
from ledger.watch import heuristic_delta, parse_every, previous_state

FIXTURE = Path(__file__).parent / "fixtures" / "nimble-search-page.txt"


def test_parse_every():
    assert parse_every("30s") == 30 and parse_every("10m") == 600 and parse_every("1h") == 3600


def test_tick_from_fixture_discards_raw(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("RAWTREE_API_KEY", raising=False)
    monkeypatch.setenv("LEDGER_HOST", "pytest")
    root = tmp_path / ".ledger"
    assert main(["--dir", str(root), "tick", "nimble", "--fixture", str(FIXTURE), "--distiller", "none"]) == 0
    entries = Ledger(root).entries()
    assert entries[-1].title.startswith("watch nimble:")
    assert "bytes discarded" in entries[-1].body
    status = (root / "STATUS.md").read_text()
    assert len(status) < FIXTURE.stat().st_size / 4  # the page itself is not in the ledger
    event = (root / "events.jsonl").read_text().splitlines()[-1]
    assert '"kind": "tick"' in event and '"bytes_discarded": ' in event
    assert previous_state(Ledger(root), "nimble").startswith("- ")


def test_heuristic_delta_skips_seen_lines():
    raw = "Alpha beta gamma delta epsilon zeta eta theta iota. Second sentence with enough characters in it."
    first = heuristic_delta(raw, "")
    assert first.count("\n") <= 2
    assert heuristic_delta(raw, first) == "- no change"


def test_dedupe_drops_lines_already_in_state():
    from ledger.watch import dedupe

    previous = "- Hacker News updates on Anthropic and court ruling\n- Platform-Independent SIMD in Go highlighted"
    delta = "- Hacker News update on Anthropic and the court ruling\n- A genuinely new headline about Rust"
    assert dedupe(delta, previous) == "- A genuinely new headline about Rust"
    assert dedupe(previous, previous) == "- no change"


def test_previous_state_keeps_raw_lines_and_skips_failed_ticks(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("RAWTREE_API_KEY", raising=False)
    ledger = Ledger(tmp_path / ".ledger")
    ledger.append("watch dairy: raw milk prices", "- raw milk up 4% in Ohio\n\nsource: fixture x; raw 900 bytes discarded; distiller: none; 0.1s")
    ledger.append("watch dairy: tick failed", "- HTTP Error 503: Service Unavailable")
    state = previous_state(ledger, "dairy")
    assert state == "- raw milk up 4% in Ohio"


def test_tick_with_unreachable_distiller_fails_cleanly(tmp_path: Path, monkeypatch, caplog):
    monkeypatch.setenv("LIQUID_BASE_URL", "http://127.0.0.1:9/v1")  # nothing listens here
    root = tmp_path / ".ledger"
    code = main(["--dir", str(root), "tick", "nimble", "--fixture", str(FIXTURE), "--distiller", "liquid"])
    assert code == 1
    assert "tick failed: URLError" in caplog.text
    assert not (root / "events.jsonl").exists()  # a failed tick records no tick event


def test_observe_prefers_nimble_search_when_configured(monkeypatch):
    from ledger import watch
    from sponsors import nimble

    calls = []
    monkeypatch.setattr(nimble, "configured", lambda: True)
    monkeypatch.setattr(nimble, "observe", lambda topic, url=None, max_results=3: calls.append((topic, url)) or ("page", "nimble"))
    assert watch.observe("agents", "https://example.com", None) == ("page", "nimble")
    assert calls[-1] == ("agents", None)
    monkeypatch.setenv("NIMBLE_MODE", "extract")
    watch.observe("agents", "https://example.com", None)
    assert calls[-1] == ("agents", "https://example.com")
