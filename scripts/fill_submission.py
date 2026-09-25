#!/usr/bin/env python3
"""Fill the tokens& hackathon submission form for `ledger` and leave the window open. Never submits.

    python scripts/fill_submission.py [--log /tmp/fill.log] [--hold 3600]

Field ids were read from the live form on 2026-09-25. The window stays open for the operator to review and
press "Submit project" themselves.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORM = "https://tokensand.com/horizonagentshack/submit"
REPO = "https://github.com/mlgraham/long-horizon-hack-2026"
VIDEO = f"{REPO}/raw/main/demo/ledger-demo.mp4"

SUMMARY = ("A host-agnostic CLI that keeps a long-horizon agent's state as dated, falsifiable Markdown, so a task "
           "killed under one agent host finishes under another from a two-minute brief.")

TOOLS_LISTED = ["Liquid AI", "Nimble", "Black Forest Labs"]
TOOLS_CUSTOM = ["RawTree", "Claude Code"]

ARCHITECTURE = """Plain Markdown under .ledger/ is the only state: STATUS.md (append-only, every heading stamped from the clock), gates.md (pre-registered thresholds that flip only on a measurement), obligations.md, pause.md (the resume-here entry). `ledger resume` rebuilds a brief of under 60 lines from those files; that brief is the whole context a second host gets.

Every verb emits one event (ts, kind, host, model, gate, text, tokens, bytes_discarded) to a local mirror and to one RawTree table; "what changed in the last hour" and the board are two SQL queries. `ledger tick`/`watch` observe a live topic through Nimble search, distill it with Liquid LFM2.5-1.2B running locally through Ollama into at most three new lines, deduplicate against the ledger, and discard the raw page. `ledger pause --cover` renders a FLUX image from the day's headlines. The second host is a fresh headless Claude Code session (hosts/claude_code.sh) or a bare tool-calling loop (hosts/loop.py). Core is Python 3.11 standard library only; 55 tests."""

SETUP = """uv venv .venv && uv pip install -e '.[dev,video]'
ollama pull hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF
cp .env.example .env   # RAWTREE_API_KEY, NIMBLE_API_KEY, BFL_API_KEY; every key is optional, each verb degrades to a local fallback
ledger doctor          # one line per component
bash demo/run.sh       # the 3-minute demo: observe, plan (spec as a gate), pause, resume on a second host, board"""

LESSONS = """Six pre-registered hinges with kill criteria, each passed on a measurement written into the ledger before the pitch. AWS Bedrock was dropped at 10:08 when no account was available; Tinybird was swapped for RawTree at kickoff, which took one client file because RawTree takes events as they are. A 1.2B model on an Intel CPU is a good per-tick distiller (8-25 s per page) and a poor agent: it could not drive a read-then-write loop, so the second host became a fresh headless session and Liquid stayed where it works. The ledger, not the model, decides what is new: repeat ticks deduplicate to "no change". The demo video is generated from a timestamped run, not screen-recorded; the process is in docs/video-process.md."""

LINKS = "\n".join([
    f"{REPO}/blob/main/docs/Ledger-One-Pager.pdf",
    f"{REPO}/blob/main/docs/Ledger-Over-History.pdf",
    f"{REPO}/blob/main/STATUS.md",
    f"{REPO}/blob/main/docs/video-process.md",
])


def description() -> str:
    text = (ROOT / "docs" / "submission.md").read_text()
    match = re.search(r"\*\*Description:\*\*\n(.*?)\n\n\*\*", text, flags=re.S)
    return " ".join(match.group(1).split()) if match else ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default="/tmp/fill-submission.log")
    parser.add_argument("--hold", type=int, default=3600)
    args = parser.parse_args()
    log = open(args.log, "a")

    def say(text: str) -> None:
        print(text, file=log, flush=True)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(Path.home() / ".ledger-keys-browser"), headless=False, viewport={"width": 1280, "height": 1000},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(FORM, wait_until="domcontentloaded")
        page.wait_for_selector("#hackathon-project-name", timeout=600_000)
        say("form found")
        filled, left = [], []

        def fill(selector: str, value: str, label: str) -> None:
            try:
                page.fill(selector, value)
                filled.append(f"{label} <- {value[:70]}")
            except Exception as error:  # noqa: BLE001
                left.append(f"{label}: {error}")

        fill("#hackathon-project-name", "ledger", "project name")
        fill("#hackathon-summary", SUMMARY[:300], "one-sentence description")
        try:
            desc = page.locator("#hackathon-description")
            desc.click()
            page.keyboard.press("Meta+A")
            page.keyboard.type(description()[:1500], delay=2)
            filled.append(f"project description <- {len(description()[:1500])} chars")
        except Exception as error:  # noqa: BLE001
            left.append(f"project description: {error}")
        try:
            page.select_option("#hackathon-team-size", index=0)
            filled.append("team size <- 1 — Just me")
        except Exception as error:  # noqa: BLE001
            left.append(f"team size: {error}")
        for tool in TOOLS_LISTED:
            try:
                page.get_by_role("button", name=tool, exact=True).first.click()
                filled.append(f"tool selected <- {tool}")
            except Exception as error:  # noqa: BLE001
                left.append(f"tool {tool}: {error}")
        for tool in TOOLS_CUSTOM:
            try:
                page.fill("#hackathon-tool-search", tool)
                page.wait_for_timeout(1200)
                candidates = page.get_by_role("button").filter(has_text=re.compile(re.escape(tool), re.I))
                names = [candidates.nth(index).inner_text().strip()[:40] for index in range(min(candidates.count(), 6))]
                say(f"tool search {tool!r}: buttons {names}")
                if candidates.count():
                    candidates.first.click()
                    filled.append(f"tool added <- {tool} (clicked {names[0]!r})")
                else:
                    page.keyboard.press("Enter")
                    filled.append(f"tool typed <- {tool} (Enter; check it stuck)")
                page.wait_for_timeout(600)
            except Exception as error:  # noqa: BLE001
                left.append(f"custom tool {tool}: {error}")
        fill("#hackathon-working-url", REPO, "working project URL")
        fill("#hackathon-video-url", VIDEO, "demo video URL")
        fill("#hackathon-repo-url", REPO, "GitHub repository")
        try:
            page.set_input_files("#hackathon-image-upload", str(ROOT / "docs" / "demo-screenshot.png"))
            filled.append("screenshot <- docs/demo-screenshot.png")
        except Exception as error:  # noqa: BLE001
            left.append(f"screenshot: {error}")
        try:
            toggle = page.get_by_text(re.compile(r"Additional project details", re.I)).first
            toggle.click()
            page.wait_for_timeout(800)
            page.wait_for_selector("#hackathon-architecture", state="visible", timeout=10_000)
            filled.append("expanded the optional section")
        except Exception as error:  # noqa: BLE001
            left.append(f"optional section toggle: {error}")
        fill("#hackathon-architecture", ARCHITECTURE, "architecture")
        fill("#hackathon-setup", SETUP, "setup")
        fill("#hackathon-lessons", LESSONS, "lessons")
        fill("#hackathon-additional-links", LINKS, "additional links")
        try:
            say("tools now selected: " + page.locator("text=/\\d+ selected/").first.inner_text())
        except Exception:  # noqa: BLE001
            pass
        say("FILLED:"); [say("  " + item) for item in filled]
        say("LEFT FOR THE OPERATOR:"); [say("  " + item) for item in left]
        say("not submitting; window stays open")
        time.sleep(args.hold)
        context.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
