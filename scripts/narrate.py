#!/usr/bin/env python3
"""Mix a spoken narration into a screen recording of demo/run.sh, one clip per step, at the step's real time.

    python scripts/narrate.py --video demo.mov --steps /tmp/ledger-demo/steps.tsv --log demo.log \
        [--offset 1.0] [--voice say|zero] [--out demo-narrated.mp4]

The narration text is the six "Say:" blocks of docs/demo-script.md. Bracketed placeholders such as
"[read the bytes-discarded figure off the screen]" are filled from the run log when --log is given.
--offset is the delay, in seconds, between the recording starting and the script starting (DEMO_WAIT=1
makes that a single key press, so about one second). Clips never overlap: a clip that runs long pushes
the next one later. Voices: `say` (macOS, offline, free) or `zero` (OpenAI TTS through Zero, paid per clip).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_MD = ROOT / "docs" / "demo-script.md"


def narration_blocks(markdown: str) -> list[str]:
    blocks = re.findall(r'Say: "(.*?)"', markdown, flags=re.S)
    return [" ".join(block.split()) for block in blocks]


def values_from_log(log_text: str) -> dict[str, str]:
    values = {}
    bytes_lines = re.findall(r"\[(\d+) bytes discarded", log_text)
    if bytes_lines:
        values["bytes"] = f"{int(bytes_lines[0]):,}"
    persisted = re.search(r"persisted\s+(\d+) bytes", log_text)
    discarded = re.search(r"discarded\s+(\d+) raw bytes over (\d+) ticks", log_text)
    if persisted and discarded:
        values["split"] = (f"{int(persisted[1]):,} bytes persisted in the ledger, "
                           f"{int(discarded[1]):,} raw bytes discarded over {discarded[2]} ticks")
    return values


# Spoken-only respellings for words the voices misread. Docs keep the real spelling.
PRONOUNCE = {
    r"\bpytest\b": "pie-test",
    r"\bRawTree\b": "Raw Tree",
    r"\bslug\.py\b": "slug dot pie",
    r"(?<![A-Za-z])\.ledger\b": "dot-ledger",
}


def speakable(text: str) -> str:
    """Strip Markdown and code marks and apply respellings, so the voice reads words, not punctuation."""
    text = text.replace("`", "").replace("**", "").replace("*", "")
    for pattern, spoken in PRONOUNCE.items():
        text = re.sub(pattern, spoken, text)
    return " ".join(text.split())


def fill_placeholders(text: str, values: dict[str, str]) -> str:
    text = re.sub(r"\[read the bytes-discarded figure off the screen\]", values.get("bytes", "tens of thousands of"), text)
    text = re.sub(r"\[read the persisted and discarded bytes off the screen\]", values.get("split", "a small ledger against a large pile of discarded pages"), text)
    return speakable(re.sub(r"\[[^\]]*\]", "", text))


def tts_say(text: str, out_wav: Path, voice: str = "Samantha", rate: int = 175) -> None:
    aiff = out_wav.with_suffix(".aiff")
    subprocess.run(["say", "-v", voice, "-r", str(rate), "-o", str(aiff), text], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(aiff), "-ar", "44100", "-ac", "2", str(out_wav)], check=True)


def tts_zero(text: str, out_wav: Path, voice: str = "onyx") -> None:
    """OpenAI TTS through Zero. Re-searches for the capability each run, as the Zero skill requires."""
    search = subprocess.run(["zero", "search", "OpenAI text-to-speech", "--json"], capture_output=True, text=True, check=True)
    results = json.loads(search.stdout)
    items = results if isinstance(results, list) else results.get("results", [])
    chosen = next((item for item in items if "openai" in json.dumps(item).lower() and "text-to-speech" in json.dumps(item).lower()), None)
    if not chosen:
        raise RuntimeError("no OpenAI TTS capability found on Zero")
    token = chosen.get("token") or chosen.get("slug")
    detail = json.loads(subprocess.run(["zero", "get", token], capture_output=True, text=True, check=True).stdout)
    url = detail.get("url") or detail.get("endpoint")
    body = {"input": text, "voice": voice, "model": "tts-1", "response_format": "mp3"}
    mp3 = out_wav.with_suffix(".mp3")
    with mp3.open("wb") as handle:
        subprocess.run(["zero", "fetch", url, "--capability", token, "--max-pay", "0.05", "--timeout", "120",
                        "-d", json.dumps(body), "-H", "Content-Type:application/json"], stdout=handle, check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-ar", "44100", "-ac", "2", str(out_wav)], check=True)


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def read_steps(path: Path) -> list[float]:
    times = {}
    for line in path.read_text().splitlines():
        key, _tab, value = line.partition("\t")
        if key.isdigit():
            times[int(key)] = float(value)
    return [times[index] for index in sorted(times)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--video", required=True)
    parser.add_argument("--steps", required=True, help="steps.tsv written by demo/run.sh")
    parser.add_argument("--log", help="the demo's stdout, to fill the numbers in the narration")
    parser.add_argument("--offset", type=float, default=1.0)
    parser.add_argument("--voice", choices=["say", "zero"], default="say")
    parser.add_argument("--say-voice", default="Samantha")
    parser.add_argument("--out", default="demo-narrated.mp4")
    parser.add_argument("--keep-video-audio", action="store_true", help="mix over the recording's own audio")
    args = parser.parse_args()

    blocks = narration_blocks(SCRIPT_MD.read_text())
    steps = read_steps(Path(args.steps))
    if len(blocks) != len(steps):
        print(f"{len(blocks)} narration blocks but {len(steps)} steps in {args.steps}", file=sys.stderr)
        return 2
    values = values_from_log(Path(args.log).read_text()) if args.log else {}
    texts = [fill_placeholders(block, values) for block in blocks]

    work = Path(tempfile.mkdtemp(prefix="narrate-"))
    clips = []
    for index, text in enumerate(texts, start=1):
        wav = work / f"block{index}.wav"
        (tts_zero if args.voice == "zero" else lambda t, o: tts_say(t, o, args.say_voice))(text, wav)
        clips.append((wav, duration(wav)))

    placements = []
    cursor = 0.0
    for (wav, length), step_time in zip(clips, steps):
        start = max(step_time + args.offset, cursor)
        placements.append((wav, start, length))
        cursor = start + length + 0.4
    video_length = duration(Path(args.video))
    print(f"{'step':>4}  {'starts':>7}  {'clip':>6}  {'step at':>7}")
    for index, ((wav, start, length), step_time) in enumerate(zip(placements, steps), start=1):
        flag = "  (late: narration runs past the step)" if start - step_time - args.offset > 2 else ""
        print(f"{index:>4}  {start:>7.1f}  {length:>6.1f}  {step_time + args.offset:>7.1f}{flag}")
    end = placements[-1][1] + placements[-1][2]
    if end > video_length:
        print(f"warning: narration ends at {end:.1f}s but the video is {video_length:.1f}s; trailing audio is cut", file=sys.stderr)

    inputs = ["-i", args.video]
    filters = []
    labels = []
    for index, (wav, start, _length) in enumerate(placements, start=1):
        inputs += ["-i", str(wav)]
        delay = int(start * 1000)
        filters.append(f"[{index}]adelay={delay}|{delay}[n{index}]")
        labels.append(f"[n{index}]")
    if args.keep_video_audio:
        labels.insert(0, "[0:a]")
    filters.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=first[a]" if args.keep_video_audio
                   else "".join(labels) + f"amix=inputs={len(labels)}:normalize=0[a]")
    command = ["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filters),
               "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", args.out]
    subprocess.run(command, check=True)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
