#!/usr/bin/env python3
"""Re-time a recorded run so idle stretches are trimmed and the screen never runs ahead of the narration.

    python scripts/retime_run.py --run demo/run.jsonl --steps /tmp/ledger-demo/steps.tsv --max-gap 8 \
        --narration-args "--log demo.log --voice zero-elevenlabs --slack 1.5 --gap 0.5 --out demo/narration"

Two passes over the timestamps, both monotone (order and content never change, only waiting time):
1. Any silence longer than --max-gap seconds between two output lines is shortened to --max-gap.
2. The narration is laid on the shortened step times; where narration block k would start after step k,
   the run is held before step k so the step appears exactly when its block begins. This is what the
   paced live run does with cues, applied after the fact.
Writes <run>.retimed.jsonl and <steps>.retimed.tsv, and leaves the narration files rebuilt on the new times.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path


def read_run(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def step_starts(events: list[dict]) -> dict[int, float]:
    starts = {}
    for event in events:
        line = event["line"]
        if event.get("bold") and line.startswith("== ") and line[3].isdigit():
            starts[int(line[3])] = event["t"]
    return starts


def compress(events: list[dict], max_gap: float) -> list[dict]:
    out, previous_old, previous_new = [], 0.0, 0.0
    for event in events:
        gap = min(event["t"] - previous_old, max_gap)
        new_t = previous_new + max(gap, 0.0)
        out.append({**event, "t": round(new_t, 2)})
        previous_old, previous_new = event["t"], new_t
    return out


def read_cues(path: Path) -> dict[int, float]:
    cues = {}
    for line in path.read_text().splitlines():
        key, _tab, value = line.partition("\t")
        if key.isdigit():
            cues[int(key)] = float(value)
    return cues


def write_steps(events: list[dict], path: Path) -> None:
    starts = step_starts(events)
    end = max(event["t"] for event in events)
    with path.open("w") as handle:
        for step in sorted(starts):
            handle.write(f"{step}\t{starts[step]:.2f}\n")
        handle.write(f"end\t{end:.2f}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", default="demo/run.jsonl")
    parser.add_argument("--steps", default="/tmp/ledger-demo/steps.tsv")
    parser.add_argument("--max-gap", type=float, default=8.0)
    parser.add_argument("--slack", type=float, default=1.5, help="must match the narration's --slack")
    parser.add_argument("--narration-args", default="--voice say --out demo/narration")
    args = parser.parse_args()

    original = read_run(Path(args.run))
    events = compress(original, args.max_gap)
    old_starts, new_starts = step_starts(original), step_starts(events)
    old_end, new_end = original[-1]["t"], events[-1]["t"]
    scale = {}
    for step in sorted(old_starts):
        old_len = (old_starts.get(step + 1, old_end) - old_starts[step]) or 1.0
        new_len = new_starts.get(step + 1, new_end) - new_starts[step]
        scale[step] = round(new_len / old_len, 3)
    print("bridge scale per step:", scale, file=sys.stderr)
    out_run = Path(args.run).with_suffix(".retimed.jsonl")
    out_steps = Path(args.steps).with_suffix(".retimed.tsv")
    narration = ["python3", str(Path(__file__).with_name("narration_track.py")), "--steps", str(out_steps),
                 "--bridge-scale", json.dumps(scale), *shlex.split(args.narration_args)]
    cues_path = Path(next((value for flag, value in zip(shlex.split(args.narration_args), shlex.split(args.narration_args)[1:]) if flag == "--out"), "demo/narration") + "-cues.tsv")

    for _pass in range(20):
        write_steps(events, out_steps)
        subprocess.run(narration, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cues = read_cues(cues_path)
        starts = step_starts(events)
        shifted = False
        for step in sorted(starts):
            wanted = cues.get(step, 0.0) - args.slack
            if wanted > starts[step] + 0.05:
                delta = wanted - starts[step]
                for event in events:
                    if event["t"] >= starts[step]:
                        event["t"] = round(event["t"] + delta, 2)
                shifted = True
                break  # re-lay from scratch after each shift; later steps move with it
        if not shifted:
            break
    write_steps(events, out_steps)
    subprocess.run(narration, check=True)
    end_marker = [event for event in events if event.get("end")]
    out_run.write_text("\n".join(json.dumps(event, ensure_ascii=False) for event in events) + "\n")
    print(f"retimed run: {events[-1]['t']:.1f}s (was {read_run(Path(args.run))[-1]['t']:.1f}s) -> {out_run}, steps -> {out_steps}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
