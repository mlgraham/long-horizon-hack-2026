"""hosts/loop.py without a backend: path confinement, the file tools, and --dry-run."""

from __future__ import annotations

from pathlib import Path

import pytest

from hosts import loop
from ledger import config
from ledger.cli import main
from ledger.store import Ledger


@pytest.fixture
def ledger(tmp_path: Path, monkeypatch) -> Ledger:
    monkeypatch.setattr(config, "_loaded", True)
    monkeypatch.delenv("RAWTREE_API_KEY", raising=False)
    monkeypatch.setenv("LEDGER_HOST", "pytest")
    root = tmp_path / "repo" / ".ledger"
    assert main(["--dir", str(root), "note", "built the store"]) == 0
    return Ledger(root)


@pytest.mark.parametrize("escape", ["../outside.txt", "../../etc/passwd", "notes/../../outside.txt", "/etc/passwd"])
def test_safe_path_rejects_escapes(tmp_path: Path, escape: str):
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(ValueError, match="escapes"):
        loop.safe_path(repo, escape)


def test_safe_path_allows_inside(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    assert loop.safe_path(repo, "notes/../plan.md") == (repo / "plan.md").resolve()
    assert loop.safe_path(repo, ".") == repo.resolve()


def test_run_tool_write_read_round_trip(ledger: Ledger):
    reply = loop.run_tool(ledger, "write_file", {"path": "out/answer.md", "content": "# Answer\n42\n"})
    assert reply.startswith("wrote 12 chars to out/answer.md")
    assert (ledger.root.parent / "out" / "answer.md").read_text() == "# Answer\n42\n"
    assert loop.run_tool(ledger, "read_file", {"path": "out/answer.md"}) == "# Answer\n42\n"
    assert loop.run_tool(ledger, "list_files", {"path": "."}) == "out/"  # .ledger is hidden
    with pytest.raises(ValueError, match="escapes"):
        loop.run_tool(ledger, "write_file", {"path": "../escaped.md", "content": "no"})
    assert not (ledger.root.parent.parent / "escaped.md").exists()


def test_run_tool_note_appends_to_ledger(ledger: Ledger):
    assert loop.run_tool(ledger, "note", {"text": "wrote the answer"}).startswith("noted at ")
    assert ledger.entries()[-1].title == "wrote the answer"


def test_dry_run_prints_system_prompt_and_calls_no_backend(ledger: Ledger, monkeypatch, capsys):
    def no_backend(*args, **kwargs):
        raise AssertionError("dry run must not build a backend")

    monkeypatch.setattr(loop, "make_backend", no_backend)
    before = len(ledger.entries())
    assert loop.main(["--dir", str(ledger.root), "--dry-run", "write the summary"]) == 0
    out = capsys.readouterr().out
    assert "built the store" in out
    assert loop.SYSTEM_TAIL in out
    assert out.rstrip().endswith("Task: write the summary")
    assert len(ledger.entries()) == before  # nothing written to the ledger
