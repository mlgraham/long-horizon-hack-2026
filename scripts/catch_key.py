#!/usr/bin/env python3
"""Open a sponsor dashboard in a headed browser and catch the API key from the clipboard.

    python scripts/catch_key.py NAME URL [--timeout 900]

The operator signs in (2FA and all) in the window, creates or reveals the key, and presses its copy button.
This script polls the clipboard, writes NAME=value to .env (replacing any old line), clears the clipboard,
and closes the window. The key is never printed; only its length and first four characters are.
Runs on macOS (pbpaste/pbcopy). Uses Playwright from this repo's .venv (the `video` extra) with a persistent
profile so sign-ins survive between sponsors.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

PROFILE = Path.home() / ".ledger-keys-browser"
KEY_RE = re.compile(r"^[A-Za-z0-9._\-]{20,}$")


def clipboard() -> str:
    return subprocess.run(["pbpaste"], capture_output=True, text=True).stdout.strip()


def clear_clipboard() -> None:
    subprocess.run(["pbcopy"], input="", text=True)


def write_env(name: str, value: str, env_path: Path) -> None:
    lines = env_path.read_text().splitlines() if env_path.exists() else []
    lines = [line for line in lines if not line.startswith(f"{name}=")]
    lines.append(f"{name}={value}")
    env_path.write_text("\n".join(lines) + "\n")
    env_path.chmod(0o600)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("url")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--env", default=str(Path(__file__).resolve().parent.parent / ".env"))
    args = parser.parse_args()

    from playwright.sync_api import sync_playwright

    before = clipboard()
    print(f"[{args.name}] opening {args.url}; sign in, then press the key's Copy button", flush=True)
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(PROFILE), headless=False, viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(args.url)
        deadline = time.monotonic() + args.timeout
        found = ""
        while time.monotonic() < deadline:
            time.sleep(1.5)
            current = clipboard()
            if current and current != before and KEY_RE.match(current):
                found = current
                break
        context.close()
    if not found:
        print(f"[{args.name}] nothing key-shaped copied within {args.timeout}s", flush=True)
        return 1
    write_env(args.name, found, Path(args.env))
    clear_clipboard()
    print(f"[{args.name}] caught a {len(found)}-char key starting {found[:4]}…; written to {args.env}; clipboard cleared", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
