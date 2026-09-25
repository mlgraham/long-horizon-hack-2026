"""`ledger doctor` with no keys: one line per component, a mark and a reason, exit 0."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from ledger import config
from ledger.cli import main

COMPONENTS = ["ledger", "rawtree", "nimble", "liquid", "bfl", "anthropic", "claude", "ollama"]
LINE = re.compile(r"(✓|✗) (\S+)\s+(\S.*)")


def test_doctor_with_no_keys(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr(config, "_loaded", True)
    for name in ("RAWTREE_API_KEY", "NIMBLE_API_KEY", "LIQUID_API_KEY", "BFL_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LIQUID_BASE_URL", "http://127.0.0.1:9/v1")  # nothing listens: fails fast, no Ollama call
    monkeypatch.setenv("LEDGER_HOST", "pytest")
    monkeypatch.setattr(shutil, "which", lambda binary: "/usr/bin/claude" if binary == "claude" else None)
    root = tmp_path / ".ledger"
    assert main(["--dir", str(root), "note", "first"]) == 0
    capsys.readouterr()

    assert main(["--dir", str(root), "doctor"]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == len(COMPONENTS) + 1
    parsed = [LINE.fullmatch(line) for line in lines[:-1]]
    assert all(parsed), lines
    assert [match[2] for match in parsed] == COMPONENTS
    marks = {match[2]: (match[1], match[3]) for match in parsed}
    assert marks["ledger"][0] == "✓"
    for name, variable in (("rawtree", "RAWTREE_API_KEY"), ("nimble", "NIMBLE_API_KEY"),
                           ("bfl", "BFL_API_KEY"), ("anthropic", "ANTHROPIC_API_KEY")):
        assert marks[name] == ("✗", f"{variable} not set")
    assert marks["liquid"][0] == "✗" and "not served at http://127.0.0.1:9/v1" in marks["liquid"][1]
    assert marks["claude"] == ("✓", "/usr/bin/claude")
    assert marks["ollama"] == ("✗", "ollama not on PATH")
    assert lines[-1] == "2/8 ok"


def test_doctor_reports_missing_ledger(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr(config, "_loaded", True)
    monkeypatch.setenv("LIQUID_BASE_URL", "http://127.0.0.1:9/v1")
    for name in ("RAWTREE_API_KEY", "NIMBLE_API_KEY", "LIQUID_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    root = tmp_path / ".ledger"
    assert main(["--dir", str(root), "doctor"]) == 0
    first = capsys.readouterr().out.splitlines()[0]
    assert first.startswith("✗ ledger") and "run ledger init" in first
    assert not root.exists()  # doctor never creates anything
