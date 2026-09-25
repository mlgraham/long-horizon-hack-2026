"""The two-minute brief. The only thing a new host needs in its context."""

from __future__ import annotations

from ledger import clock, config
from ledger.store import Ledger

MAX_LINES = 60
RULES = [
    "Timestamps come from the clock, never typed. Append; never rewrite an entry.",
    "Never cite a number you have not run. A failed gate is recorded, not argued.",
    "Write `ledger note` as you go and `ledger pause` before stopping.",
]


def _clip(text: str, width: int = 110) -> str:
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 1] + "…"


def build(ledger: Ledger, recent: int = 5) -> str:
    entries = ledger.entries()
    pause = ledger.last_pause()
    gates = ledger.gates()
    obligations = ledger.obligations()
    open_gates = [gate for gate in gates if gate.get("status", "open") in ("", "open")]
    open_obligations = [item for item in obligations if item.get("status", "open") in ("", "open")]

    lines: list[str] = []
    lines.append(f"# Resume brief — {ledger.root.parent.name} — read {clock.stamp()} on {config.host_name()}")
    if entries:
        lines.append(f"{len(entries)} entries; first {entries[0].stamp}, last {entries[-1].stamp}.")
    else:
        lines.append("No entries yet.")
    lines.append("")

    if pause:
        lines.append(f"## Paused {pause.stamp} — {pause.title}")
        lines.extend(pause.body.splitlines()[:14])
    else:
        lines.append("## No pause entry. Resume from the last entries below.")
    lines.append("")

    lines.append(f"## Gates: {len(open_gates)} open of {len(gates)}")
    for gate in gates[-8:]:
        status = gate.get("status") or "open"
        measured = f" — measured: {_clip(gate['measured'], 50)}" if gate.get("measured") else ""
        lines.append(f"- {gate['name']} [{status}] {_clip(gate.get('threshold', ''), 60)} by {gate.get('by', '?')}{measured}")
    lines.append("")

    lines.append(f"## Obligations: {len(open_obligations)} open of {len(obligations)}")
    for item in open_obligations[-6:]:
        lines.append(
            f"- {item['name']} — hypothesis inhabited: {item.get('hypothesis inhabited') or 'unknown'};"
            f" consumer: {item.get('consumer') or 'none found'}"
        )
    lines.append("")

    lines.append(f"## Last {min(recent, len(entries))} entries")
    for entry in entries[-recent:]:
        marker = "⏸ " if entry.paused else ""
        lines.append(f"- {entry.stamp} — {marker}{_clip(entry.title)}")
    lines.append("")

    lines.append("## Rules")
    lines.extend(f"- {rule}" for rule in RULES)
    return "\n".join(lines).rstrip() + "\n"
