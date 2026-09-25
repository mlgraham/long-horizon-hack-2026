"""`ledger doctor`: one line per component, pass or fail, with the reason. A report, never a gate."""

from __future__ import annotations

import logging
import shutil
import time
from dataclasses import dataclass

from ledger import config
from ledger.store import Ledger

log = logging.getLogger(__name__)

PASS_MARK = "✓"
FAIL_MARK = "✗"
REQUIRED_FILES = ("STATUS.md", "gates.md", "obligations.md")


@dataclass
class Check:
    name: str
    ok: bool
    reason: str

    def line(self) -> str:
        return f"{PASS_MARK if self.ok else FAIL_MARK} {self.name:<10} {self.reason}"


def _short(error: Exception) -> str:
    return f"{type(error).__name__}: {error}"[:160]


def check_ledger(ledger: Ledger) -> Check:
    if not ledger.root.is_dir():
        return Check("ledger", False, f"no directory at {ledger.root}; run ledger init")
    missing = [name for name in REQUIRED_FILES if not (ledger.root / name).exists()]
    if missing:
        return Check("ledger", False, f"{ledger.root} is missing {', '.join(missing)}")
    return Check("ledger", True, f"{ledger.root}: {len(ledger.entries())} entries, {len(ledger.gates())} gates")


def check_rawtree() -> Check:
    from sponsors import rawtree

    if not rawtree.configured():
        return Check("rawtree", False, "RAWTREE_API_KEY not set")
    started = time.monotonic()
    try:
        rawtree.query("SELECT 1", timeout=5.0)
    except Exception as error:  # noqa: BLE001 - doctor reports, never raises
        return Check("rawtree", False, f"key set, SELECT 1 failed: {_short(error)}")
    return Check("rawtree", True, f"SELECT 1 answered by {rawtree.base_url()} in {time.monotonic() - started:.1f}s")


def check_nimble() -> Check:
    from sponsors import nimble

    if not nimble.configured():
        return Check("nimble", False, "NIMBLE_API_KEY not set")
    started = time.monotonic()
    try:
        results = nimble.search("ledger", max_results=1, full_content=False, depth="lite", timeout=30.0)
    except Exception as error:  # noqa: BLE001
        return Check("nimble", False, f"key set, lite search failed: {_short(error)}")
    return Check("nimble", True, f"lite search returned {len(results)} result(s) in {time.monotonic() - started:.1f}s")


def check_liquid() -> Check:
    from sponsors import liquid

    if not liquid.configured():
        return Check("liquid", False, f"no LIQUID_API_KEY and {liquid.model_name()} not served at {liquid.base_url()}")
    started = time.monotonic()
    try:
        liquid.chat([{"role": "user", "content": "Say ok."}], max_tokens=1, timeout=60.0)
    except Exception as error:  # noqa: BLE001
        return Check("liquid", False, f"endpoint found, 1-token chat failed: {_short(error)}")
    return Check("liquid", True, f"{liquid.model_name()} answered a 1-token chat in {time.monotonic() - started:.1f}s")


def check_key(name: str, variable: str, note: str = "") -> Check:
    if config.get(variable):
        return Check(name, True, f"{variable} set{note}")
    return Check(name, False, f"{variable} not set")


def check_binary(binary: str) -> Check:
    found = shutil.which(binary)
    return Check(binary, bool(found), found or f"{binary} not on PATH")


def run_all(ledger: Ledger) -> list[Check]:
    return [
        check_ledger(ledger),
        check_rawtree(),
        check_nimble(),
        check_liquid(),
        check_key("bfl", "BFL_API_KEY", " (not called: no credits spent)"),
        check_key("anthropic", "ANTHROPIC_API_KEY"),
        check_binary("claude"),
        check_binary("ollama"),
    ]
