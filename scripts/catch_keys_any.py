#!/usr/bin/env python3
"""Open several sponsor dashboards in one headed browser and catch keys from the clipboard in any order.

    python scripts/catch_keys_any.py [--timeout 1800]

Assignment is by the key's prefix: rt_ -> RAWTREE_API_KEY, bfl_ -> BFL_API_KEY; a 64-char hex string
-> NIMBLE_API_KEY. Each caught key is written to .env, the clipboard is cleared, and the script keeps
waiting until every wanted key is in or the timeout passes. The key itself is never printed.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catch_key import PROFILE, clear_clipboard, clipboard, write_env  # noqa: E402

SITES = {
    "RAWTREE_API_KEY": ("https://rawtree.com/login", re.compile(r"^rt_[A-Za-z0-9._\-]{8,}$")),
    "BFL_API_KEY": ("https://dashboard.bfl.ai/", re.compile(r"^bfl_[A-Za-z0-9._\-]{8,}$")),
    "NIMBLE_API_KEY": ("https://online.nimbleway.com/", re.compile(r"^[0-9a-f]{64}$")),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--env", default=str(Path(__file__).resolve().parent.parent / ".env"))
    parser.add_argument("names", nargs="*", default=["RAWTREE_API_KEY", "BFL_API_KEY"])
    args = parser.parse_args()
    wanted = {name: SITES[name] for name in args.names}

    from playwright.sync_api import sync_playwright

    before = clipboard()
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(PROFILE), headless=False, viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        first = True
        for name, (url, _pattern) in wanted.items():
            page = context.pages[0] if first and context.pages else context.new_page()
            first = False
            page.goto(url)
            print(f"[{name}] tab open at {url}: sign in, create the key, press Copy", flush=True)
        deadline = time.monotonic() + args.timeout
        while wanted and time.monotonic() < deadline:
            time.sleep(1.5)
            current = clipboard()
            if not current or current == before:
                continue
            for name, (_url, pattern) in list(wanted.items()):
                if pattern.match(current):
                    write_env(name, current, Path(args.env))
                    clear_clipboard()
                    before = ""
                    print(f"[{name}] caught a {len(current)}-char key starting {current[:4]}…; written to {args.env}; clipboard cleared", flush=True)
                    del wanted[name]
                    break
            else:
                before = current  # something else was copied; ignore it once
        context.close()
    if wanted:
        print(f"not caught: {', '.join(wanted)}", flush=True)
        return 1
    print("all keys caught", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
