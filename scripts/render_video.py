#!/usr/bin/env python3
"""Render a recorded demo run (scripts/record_run.py) as a terminal-style MP4, with the narration mixed in.

    python scripts/render_video.py --run demo/run.jsonl [--audio demo/narration.wav] [--out demo/ledger-demo.mp4]
        [--width 1280 --height 720 --rows 30 --font 17]

One frame per change (a new line or a scroll), held for its real duration, so the video's clock is the run's
clock and the narration track lines up without a screen recording. Needs ffmpeg and Playwright.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
  :root {{ color-scheme: dark; }}
  body {{ margin: 0; background: #141821; color: #E4E7EB; font-family: "SF Mono", Menlo, Consolas, monospace;
          font-size: {font}px; line-height: 1.38; width: {width}px; height: {height}px; overflow: hidden; }}
  .bar {{ height: 34px; background: #1C212B; display: flex; align-items: center; padding: 0 14px; gap: 8px;
          font-size: 13px; color: #A3ACB8; border-bottom: 1px solid #2C333E; }}
  .dot {{ width: 12px; height: 12px; border-radius: 6px; background: #3a4150; }}
  .dot.r {{ background: #E0846F; }} .dot.y {{ background: #d9b45a; }} .dot.g {{ background: #6CBF82; }}
  .title {{ margin-left: 10px; }}
  pre {{ margin: 0; padding: 14px 18px; white-space: pre-wrap; word-break: break-all; }}
  .b {{ color: #73B7BC; font-weight: 700; }}
  .p {{ color: #6CBF82; }} .f {{ color: #E0846F; }} .d {{ color: #A3ACB8; }}
  .cursor {{ display: inline-block; width: 9px; height: 1.1em; background: #E4E7EB; vertical-align: text-bottom; }}
</style></head><body>
<div class="bar"><span class="dot r"></span><span class="dot y"></span><span class="dot g"></span>
<span class="title">ledger — bash demo/run.sh</span></div>
<pre id="t"></pre>
<script>
  window.setLines = (items) => {{
    const pre = document.getElementById('t');
    pre.innerHTML = items.join('\\n') + '<span class="cursor"></span>';
  }};
</script></body></html>"""


def classify(line: str, bold: bool) -> str:
    escaped = html.escape(line)
    if bold or line.startswith("== "):
        return f'<span class="b">{escaped}</span>'
    if "passed" in line and "failed" not in line or "PASS" in line or "cover landed" in line:
        return f'<span class="p">{escaped}</span>'
    if re.search(r"\b\d+ failed\b|\bFAIL\b|^error:|Traceback", line):
        return f'<span class="f">{escaped}</span>'
    if line.startswith("[") and "bytes discarded" in line or line.startswith("-- "):
        return f'<span class="d">{escaped}</span>'
    return escaped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", default="demo/run.jsonl")
    parser.add_argument("--audio", default="demo/narration.wav")
    parser.add_argument("--out", default="demo/ledger-demo.mp4")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--rows", type=int, default=32)
    parser.add_argument("--font", type=int, default=15)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--tail", type=float, default=2.0, help="seconds to hold the final frame")
    parser.add_argument("--no-clear-on-step", dest="clear_on_step", action="store_false",
                        help="scroll continuously instead of clearing the screen at each step heading")
    parser.add_argument("--tempo", type=float, default=1.0, help="play the narration this much faster (pitch preserved), e.g. 1.02")
    args = parser.parse_args()

    events = [json.loads(line) for line in Path(args.run).read_text().splitlines() if line.strip()]
    end_time = next((event["t"] for event in events if event.get("end")), events[-1]["t"])
    events = [event for event in events if not event.get("end")]
    if args.audio and Path(args.audio).exists() and args.tempo != 1.0:
        fast = Path(tempfile.mkdtemp(prefix="tempo-")) / "narration.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", args.audio, "-af", f"atempo={args.tempo}", str(fast)], check=True)
        args.audio = str(fast)
    if args.audio and Path(args.audio).exists():
        # hold the last frame until the narration has finished
        audio_length = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", args.audio],
                                            capture_output=True, text=True, check=True).stdout.strip())
        args.tail = max(args.tail, audio_length - end_time + 0.5)

    from playwright.sync_api import sync_playwright

    work = Path(tempfile.mkdtemp(prefix="render-"))
    page_path = work / "term.html"
    page_path.write_text(PAGE.format(font=args.font, width=args.width, height=args.height))
    frames: list[tuple[Path, float]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": args.width, "height": args.height}, device_scale_factor=1)
        page.goto(page_path.as_uri())
        shown: list[str] = []
        last_t = 0.0
        # frame 0: empty terminal
        page.evaluate("setLines", [])
        frame = work / "f0000.png"
        page.screenshot(path=str(frame))
        frames.append((frame, 0.0))
        for index, event in enumerate(events, start=1):
            if args.clear_on_step and (event["bold"] or event["line"].startswith("== ")):
                shown = []  # each numbered step starts at the top of the terminal
            shown.append(classify(event["line"], event["bold"]))
            visible = shown[-args.rows :]
            page.evaluate("setLines", visible)
            frame = work / f"f{index:04d}.png"
            page.screenshot(path=str(frame))
            frames.append((frame, event["t"]))
        browser.close()

    concat = work / "frames.txt"
    with concat.open("w") as handle:
        for (frame, start), (_next, next_start) in zip(frames, frames[1:] + [(None, end_time + args.tail)]):
            hold = max(next_start - start, 1 / args.fps)
            handle.write(f"file '{frame}'\nduration {hold:.3f}\n")
        handle.write(f"file '{frames[-1][0]}'\n")
    video = work / "video.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat),
                    "-vf", f"fps={args.fps}", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "20",
                    "-t", f"{end_time + args.tail:.3f}", str(video)], check=True)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.audio and Path(args.audio).exists():
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", args.audio,
                        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", str(out)], check=True)
    else:
        video.replace(out)
    length = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
                            capture_output=True, text=True).stdout.strip()
    print(f"{len(frames)} frames, run {end_time:.1f}s -> {out} ({float(length):.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
