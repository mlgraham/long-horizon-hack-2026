"""Nimble: every observation in `watch` comes through here. REST v2, Bearer token, no SDK dependency."""

from __future__ import annotations

import json
import logging
import time
import urllib.request

from ledger import config

log = logging.getLogger(__name__)

BASE = "https://sdk.nimbleway.com/v2"


def configured() -> bool:
    return bool(config.get("NIMBLE_API_KEY"))


def _call(path: str, body: dict | None = None, timeout: float = 120.0) -> dict:
    key = config.get("NIMBLE_API_KEY")
    if not key:
        raise RuntimeError("NIMBLE_API_KEY not set")
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        method="POST" if body is not None else "GET",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode() or "{}")


def search(
    query: str, max_results: int = 5, full_content: bool = True, depth: str = "standard", timeout: float = 120.0
) -> list[dict]:
    """Live web search. Each result: title, url, description, content (full page when asked)."""
    payload = _call(
        "/search",
        {"query": query, "max_results": max_results, "search_depth": depth, "full_content": full_content},
        timeout=timeout,
    )
    return payload.get("results", [])


def extract(url: str, render: bool = True, poll_seconds: float = 2.0, max_wait: float = 120.0) -> dict:
    """Extract one URL. Handles both the synchronous shape and the task_id + poll shape."""
    payload = _call("/extract", {"url": url, "render": render})
    task_id = payload.get("task_id")
    if not task_id:
        return payload
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        status = _call(f"/tasks/{task_id}")
        state = str(status.get("status", "")).lower()
        if state in ("completed", "success", "done", "ready"):
            return _call(f"/tasks/{task_id}/results")
        if state in ("failed", "error"):
            raise RuntimeError(f"nimble task {task_id} failed: {status}")
        time.sleep(poll_seconds)
    raise TimeoutError(f"nimble task {task_id} still running after {max_wait}s")


def _text_of(payload) -> str:
    """Best-effort text from an extract result, whatever nesting the API used."""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, list):
        return "\n".join(_text_of(item) for item in payload)
    if isinstance(payload, dict):
        for key in ("markdown", "text", "content", "html", "data", "parsing", "results", "result"):
            if key in payload and payload[key]:
                found = _text_of(payload[key])
                if found.strip():
                    return found
        return ""
    return ""


def observe(topic: str, url: str | None = None, max_results: int = 3) -> tuple[str, str]:
    """One observation for a tick: (raw text, source label). The caller discards the raw text."""
    if url:
        text = _text_of(extract(url))
        return text, f"nimble extract {url}"
    parts = []
    for item in search(topic, max_results=max_results, full_content=True):
        parts.append(f"# {item.get('title','')}\n{item.get('url','')}\n{item.get('description','')}\n{item.get('content','')}")
    return "\n\n".join(parts), f"nimble search {topic!r} ({len(parts)} results)"
