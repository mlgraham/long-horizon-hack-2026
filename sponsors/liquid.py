"""Liquid AI: the distiller on every tick. LFM2.5 through Ollama's OpenAI-compatible endpoint by default,
or any OpenAI-compatible host (LIQUID_BASE_URL + LIQUID_API_KEY). The big model never sees the raw page."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from ledger import config

log = logging.getLogger(__name__)

DEFAULT_MODEL = "hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF"
DEFAULT_BASE = "http://localhost:11434/v1"

SYSTEM = (
    "You distill web pages into a ledger. Given the previous state and a fresh page, write at most three "
    "short lines, each starting with '- ', stating only facts that appear in the fresh page and are not already "
    "in the previous state. Quote names, numbers and dates from the page; never invent. If the previous state "
    "already covers the page, write exactly '- no change'. No preamble, no commentary."
)


def model_name() -> str:
    return config.get("LIQUID_MODEL") or DEFAULT_MODEL


def base_url() -> str:
    return (config.get("LIQUID_BASE_URL") or DEFAULT_BASE).rstrip("/")


def configured() -> bool:
    """True when a Liquid endpoint answers: a hosted key, or a local Ollama that has the model."""
    if config.get("LIQUID_API_KEY"):
        return True
    try:
        with urllib.request.urlopen(f"{base_url()}/models", timeout=2) as response:
            names = [item.get("id", "") for item in json.loads(response.read().decode()).get("data", [])]
        return any(model_name() in name or name in model_name() for name in names)
    except (urllib.error.URLError, OSError, ValueError):
        return False


def chat(messages: list[dict], max_tokens: int = 300, temperature: float = 0.0, timeout: float = 180.0) -> tuple[str, dict]:
    """One chat completion. Returns (text, usage)."""
    headers = {"Content-Type": "application/json"}
    key = config.get("LIQUID_API_KEY")
    if key:
        headers["Authorization"] = f"Bearer {key}"
    body = json.dumps(
        {"model": model_name(), "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    ).encode()
    request = urllib.request.Request(f"{base_url()}/chat/completions", data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode())
    text = payload["choices"][0]["message"]["content"] or ""
    return text.strip(), payload.get("usage", {})


def distill(raw: str, previous: str, topic: str, max_chars: int = 12000) -> tuple[str, dict]:
    """raw page + last state -> <= 3-line delta. Returns (delta, usage)."""
    clipped = raw[:max_chars]
    user = (
        f"Topic: {topic}\n\nPrevious state (from the ledger):\n{previous or '(none yet)'}\n\n"
        f"Fresh page ({len(raw)} bytes, clipped to {len(clipped)}):\n{clipped}\n\n"
        "Delta, at most three lines:"
    )
    text, usage = chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}])
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    lines = [line if line.startswith("- ") else f"- {line.lstrip('-* ')}" for line in lines][:3]
    return "\n".join(lines) or "- no change", usage
