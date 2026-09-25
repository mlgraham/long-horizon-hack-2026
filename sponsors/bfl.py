"""Black Forest Labs: on `pause --cover`, one FLUX image from the day's digest into .ledger/covers/."""

from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.request

from ledger import config

log = logging.getLogger(__name__)

ENDPOINT = "https://api.bfl.ai/v1/flux-2-pro-preview"


def configured() -> bool:
    return bool(config.get("BFL_API_KEY"))


def _headers() -> dict:
    key = config.get("BFL_API_KEY")
    if not key:
        raise RuntimeError("BFL_API_KEY not set")
    return {"x-key": key, "accept": "application/json", "Content-Type": "application/json"}


def generate(prompt: str, width: int = 1024, height: int = 768, max_wait: float = 120.0) -> bytes:
    """Submit, poll the returned polling_url until Ready, download the signed sample."""
    request = urllib.request.Request(
        ENDPOINT, data=json.dumps({"prompt": prompt, "width": width, "height": height}).encode(),
        headers=_headers(), method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        submitted = json.loads(response.read().decode())
    polling_url = submitted["polling_url"]
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        time.sleep(1.0)
        poll = urllib.request.Request(polling_url, headers=_headers())
        with urllib.request.urlopen(poll, timeout=30) as response:
            status = json.loads(response.read().decode())
        state = status.get("status")
        if state == "Ready":
            with urllib.request.urlopen(status["result"]["sample"], timeout=60) as image:
                return image.read()
        if state in ("Error", "Failed"):
            raise RuntimeError(f"flux failed: {status}")
    raise TimeoutError("flux result not ready in time")


def prompt_from_digest(entries: list, topic_hint: str = "") -> str:
    """The day's headlines become one editorial-illustration prompt. No text rendering requested."""
    heads = [entry.title for entry in entries if not entry.paused][-8:]
    digest = "; ".join(re.sub(r"[`*_#]", "", head)[:80] for head in heads)
    return (
        "Editorial illustration, muted paper tones, one teal accent, clean vector style, no text or letters. "
        f"A ledger book on a desk, dated pages, a small lamp; the day's work: {digest}. {topic_hint}"
    ).strip()


def cover_for_pause(ledger, entry) -> str | None:
    if not configured():
        log.info("BFL_API_KEY not set; no cover")
        return None
    ledger.covers.mkdir(parents=True, exist_ok=True)
    prompt = prompt_from_digest(ledger.entries())
    image = generate(prompt)
    name = entry.stamp.replace(" ", "_").replace(":", "") + ".jpg"
    path = ledger.covers / name
    path.write_bytes(image)
    # Relative to the file the link is written into: .ledger/STATUS.md normally, the repo root when it is a symlink.
    link = os.path.relpath(path, ledger.status.resolve().parent)
    with ledger.status.open("a") as handle:
        handle.write(f"\n![cover]({link})\n")
    from ledger import events

    events.emit(ledger, "cover", text=prompt[:200], model="flux-2-pro-preview")
    return str(path)
