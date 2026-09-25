"""watch/tick: observe → distill → note the delta → discard the raw page. The brief's own diagram, running."""

from __future__ import annotations

import logging
import re
import time
import urllib.request
from pathlib import Path

from ledger import config, events
from ledger.store import Ledger

log = logging.getLogger(__name__)


def parse_every(text: str) -> float:
    match = re.fullmatch(r"(\d+)([smh]?)", text.strip())
    if not match:
        raise ValueError(f"bad interval {text!r}; use 30s, 10m, 1h")
    number, unit = int(match[1]), match[2] or "s"
    return number * {"s": 1, "m": 60, "h": 3600}[unit]


def previous_state(ledger: Ledger, topic: str, limit: int = 5) -> str:
    prefix = f"watch {topic}:"
    # Failed ticks carry an error, not an observation. The "source: ...; raw N bytes discarded" line does not
    # start with "- ", so every "- " line of a tick body is a delta line, including one that mentions "raw".
    bodies = [
        entry.body for entry in ledger.entries()
        if entry.title.startswith(prefix) and entry.title != f"{prefix} tick failed"
    ]
    deltas = []
    for body in bodies[-limit:]:
        deltas.append("\n".join(line for line in body.splitlines() if line.startswith("- ")))
    return "\n".join(deltas)


def observe(topic: str, url: str | None, fixture: str | None) -> tuple[str, str]:
    if fixture:
        return Path(fixture).read_text(), f"fixture {fixture}"
    from sponsors import nimble

    if nimble.configured():
        # Default to a live search on the topic (the documented synchronous shape). NIMBLE_MODE=extract
        # pulls the given URL through the extract API instead.
        mode = (config.get("NIMBLE_MODE") or "search").lower()
        return nimble.observe(topic, url if mode == "extract" else None)
    if url:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 ledger-watch"})
        with urllib.request.urlopen(request, timeout=30) as response:
            html = response.read().decode(errors="replace")
        text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text), f"urllib {url} (no Nimble key)"
    raise RuntimeError("no NIMBLE_API_KEY, no --url and no --fixture: nothing to observe")


def heuristic_delta(raw: str, previous: str) -> str:
    seen = set(previous.splitlines())
    fresh = []
    for line in re.split(r"(?<=[.!?])\s+|\n", raw):
        line = " ".join(line.split())
        if 30 <= len(line) <= 160 and f"- {line}" not in seen:
            fresh.append(f"- {line}")
        if len(fresh) == 3:
            break
    return "\n".join(fresh) or "- no change"


def dedupe(delta: str, previous: str, threshold: float = 0.8) -> str:
    """The ledger, not the model, decides what is new: drop lines already in the previous state."""
    from difflib import SequenceMatcher

    seen = [" ".join(line.lower().split()) for line in previous.splitlines() if line.strip()]
    kept = []
    for line in delta.splitlines():
        normalised = " ".join(line.lower().split())
        if not normalised or normalised == "- no change":
            continue
        if any(SequenceMatcher(None, normalised, old).ratio() >= threshold for old in seen):
            continue
        kept.append(line)
    return "\n".join(kept) or "- no change"


def distill(raw: str, previous: str, topic: str, distiller: str | None) -> tuple[str, str, dict]:
    """Returns (delta, model label, usage)."""
    choice = distiller
    if choice is None:
        from sponsors import liquid

        choice = "liquid" if liquid.configured() else "none"
    if choice == "liquid":
        from sponsors import liquid

        delta, usage = liquid.distill(raw, previous, topic)
        return delta, liquid.model_name(), usage
    if choice == "bedrock":
        from sponsors import bedrock, liquid

        text, usage = bedrock.complete(liquid.SYSTEM, [{"role": "user", "content": f"Topic: {topic}\nPrevious:\n{previous}\n\nPage:\n{raw[:12000]}"}])
        return text, "bedrock", usage
    return heuristic_delta(raw, previous), "heuristic", {}


def tick(ledger: Ledger, topic: str, url: str | None = None, fixture: str | None = None, distiller: str | None = None) -> int:
    started = time.monotonic()
    raw, source = observe(topic, url, fixture)
    raw_bytes = len(raw.encode())
    previous = previous_state(ledger, topic)
    delta, model, usage = distill(raw, previous, topic, distiller)
    delta = dedupe(delta, previous)
    elapsed = time.monotonic() - started
    first = delta.splitlines()[0].lstrip("- ").strip() if delta else "no change"
    body = delta + f"\n\nsource: {source}; raw {raw_bytes} bytes discarded; distiller: {model}; {elapsed:.1f}s"
    entry = ledger.append(f"watch {topic}: {first[:90]}", body)
    events.emit(
        ledger, "tick", text=delta, model=model, gate=topic,
        tokens_in=int(usage.get("prompt_tokens", 0) or 0), tokens_out=int(usage.get("completion_tokens", 0) or 0),
        bytes_discarded=raw_bytes,
    )
    del raw  # the point: nothing raw survives the tick
    print(f"{entry.stamp} — {entry.title}\n{delta}\n[{raw_bytes} bytes discarded · {model} · {elapsed:.1f}s]")
    return 0


def loop(ledger: Ledger, topic: str, url: str | None, every: str, ticks: int, fixture: str | None, distiller: str | None) -> int:
    interval = parse_every(every)
    count = 0
    while True:
        try:
            tick(ledger, topic, url, fixture, distiller)
        except Exception as error:  # noqa: BLE001 - a failed tick is noted, not fatal
            log.error("tick failed: %s", error)
            ledger.append(f"watch {topic}: tick failed", f"- {error}")
            events.emit(ledger, "tick_failed", text=str(error), gate=topic)
        count += 1
        if ticks and count >= ticks:
            return 0
        time.sleep(interval)
