#!/usr/bin/env python3
"""Run demo/run.sh and record every output line with its elapsed time, for scripts/render_video.py.

    python scripts/record_run.py --out demo/run.jsonl [-- extra env like DEMO_PAUSE=8 DEMO_CUES=...]

Writes one JSON object per line: {"t": seconds since start, "line": text with ANSI codes stripped, "bold": bool}.
The clock starts when the script starts (DEMO_WAIT is not used here; the video has no recording to sync to).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="demo/run.jsonl")
    parser.add_argument("env", nargs="*", help="KEY=VALUE pairs for the demo")
    args = parser.parse_args()
    env = dict(os.environ)
    for pair in args.env:
        key, _eq, value = pair.partition("=")
        env[key] = value
    env["PYTHONUNBUFFERED"] = "1"
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    start = time.time()
    process = subprocess.Popen(["bash", str(ROOT / "demo" / "run.sh")], cwd=ROOT, env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    count = 0
    with out.open("w") as handle:
        assert process.stdout is not None
        for raw in process.stdout:
            elapsed = time.time() - start
            bold = "\x1b[1m" in raw
            line = ANSI.sub("", raw.rstrip("\n"))
            handle.write(json.dumps({"t": round(elapsed, 2), "line": line, "bold": bold}, ensure_ascii=False) + "\n")
            handle.flush()
            count += 1
            print(f"{elapsed:7.2f}  {line[:100]}", file=sys.stderr)
    code = process.wait()
    with out.open("a") as handle:
        handle.write(json.dumps({"t": round(time.time() - start, 2), "line": "", "bold": False, "end": True}) + "\n")
    print(f"{count} lines, exit {code}, {time.time() - start:.1f}s -> {out}", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
