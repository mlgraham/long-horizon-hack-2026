#!/usr/bin/env python3
"""Build one continuous narration track for the demo, then pace the demo to it.

    python scripts/narration_track.py --steps /tmp/ledger-demo/steps.tsv --log /tmp/demo.log \
        [--voice zero-elevenlabs|zero-openai|say] [--slack 5] [--out demo/narration]

Writes <out>.wav (the whole narration with silence between blocks), <out>-cues.tsv (when each block starts,
in seconds from the start of the track) and <out>-texts.txt (what was spoken). Block k starts no earlier than
the moment step k started in the timed rehearsal (steps.tsv) plus --slack seconds, and never before the
previous block has finished. Then run the demo paced to the track:

    DEMO_WAIT=1 DEMO_CUES=demo/narration-cues.tsv DEMO_AUDIO=demo/narration.wav bash demo/run.sh

and mix the recording with scripts/mix.sh. Zero voices are paid per block (about two cents each).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from narrate import SCRIPT_MD, duration, fill_placeholders, narration_blocks, read_steps, tts_say, values_from_log  # noqa: E402

import re


def bridge_lines(markdown: str) -> list[tuple[int, float, str]]:
    """`- N +S: "text"` entries under the Bridges heading: (step, seconds into the step, text)."""
    section = markdown.split("## Bridges", 1)[1] if "## Bridges" in markdown else ""
    found = re.findall(r'^- (\d+) \+(\d+(?:\.\d+)?): "(.*?)"$', section, flags=re.M | re.S)
    return [(int(step), float(offset), " ".join(text.split())) for step, offset, text in found]

ZERO_VOICES = {
    # search query, substring to match in a result, request body builder, known slug (fallback when search JSON differs)
    "zero-elevenlabs": ("ElevenLabs text to speech", "x402engine",
                        lambda text: {"input": text, "text": text, "voice_id": "21m00Tcm4TlvDq8ikWAM"},
                        "x402engine-elevenlabs-text-to-speech-6db68b62"),
    "zero-openai": ("OpenAI text-to-speech", "openai",
                    lambda text: {"input": text, "voice": "onyx", "model": "tts-1-hd", "response_format": "mp3"}, None),
}


def _find(obj, needle: str):
    """Depth-first search for a dict mentioning the needle that carries a token or slug."""
    if isinstance(obj, dict):
        if needle in json.dumps(obj).lower() and (obj.get("token") or obj.get("slug")):
            return obj
        for value in obj.values():
            found = _find(value, needle)
            if found:
                return found
    if isinstance(obj, list):
        for item in obj:
            found = _find(item, needle)
            if found:
                return found
    return None


def zero_pick(query: str, needle: str, fallback_slug: str | None) -> tuple[str, dict]:
    token = None
    try:
        search = subprocess.run(["zero", "search", query, "--json"], capture_output=True, text=True, check=True)
        hit = _find(json.loads(search.stdout), needle)
        token = (hit or {}).get("token") or (hit or {}).get("slug")
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        token = None
    token = token or fallback_slug
    if not token:
        raise RuntimeError(f"no capability matching {needle!r} on Zero")
    detail = json.loads(subprocess.run(["zero", "get", token], capture_output=True, text=True, check=True).stdout)
    return token, detail


def _find_url(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in ("url", "endpoint") and isinstance(value, str) and value.startswith("http"):
                return value
            found = _find_url(value)
            if found:
                return found
    if isinstance(obj, list):
        for item in obj:
            found = _find_url(item)
            if found:
                return found
    return None


def _audio_from_payload(payload) -> bytes | None:
    """The reply may carry the audio as a URL, as base64 (any key), or nested. Return the bytes."""
    import base64
    import re

    if isinstance(payload, dict):
        for value in payload.values():
            found = _audio_from_payload(value)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _audio_from_payload(item)
            if found:
                return found
    elif isinstance(payload, str):
        if payload.startswith("http") and len(payload) < 2000:
            return subprocess.run(["curl", "-sSL", payload], capture_output=True, check=True).stdout
        if len(payload) > 2000 and re.fullmatch(r"[A-Za-z0-9+/=\s]+", payload[:4000]):
            try:
                return base64.b64decode(payload, validate=False)
            except ValueError:
                return None
    return None


def looks_like_audio(data: bytes) -> bool:
    return data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2") or data[:4] == b"RIFF" or data[:4] == b"fLaC"


def zero_speak(token: str, detail: dict, body: dict, out_mp3: Path) -> None:
    """One paid call, fetched straight to disk. Existing valid audio at out_mp3 is reused, never re-bought."""
    if out_mp3.exists() and looks_like_audio(out_mp3.read_bytes()[:8]):
        print(f"  reusing {out_mp3.name}", file=sys.stderr)
        return
    url = detail.get("url") or detail.get("endpoint") or (detail.get("capability") or {}).get("url") or _find_url(detail)
    if not url:
        raise RuntimeError("could not find the capability URL in zero get output")
    raw_path = out_mp3.with_suffix(".reply")
    with raw_path.open("wb") as handle:
        subprocess.run(["zero", "fetch", url, "--capability", token, "--max-pay", "0.06", "--timeout", "180",
                        "-d", json.dumps(body), "-H", "Content-Type:application/json"], stdout=handle, check=True)
    data = raw_path.read_bytes()
    if not looks_like_audio(data):
        payload = json.loads(data.decode())
        data = _audio_from_payload(payload) or b""
    if not looks_like_audio(data):
        raise RuntimeError(f"no audio in reply ({len(data)} bytes)")
    out_mp3.write_bytes(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--steps", required=True)
    parser.add_argument("--log")
    parser.add_argument("--voice", choices=["say", *ZERO_VOICES], default="zero-elevenlabs")
    parser.add_argument("--slack", type=float, default=5.0, help="seconds after a step starts before its block begins")
    parser.add_argument("--gap", type=float, default=0.8, help="minimum silence between blocks")
    parser.add_argument("--out", default="demo/narration")
    parser.add_argument("--work", default="demo/.track", help="where block audio is kept; existing blocks are reused")
    parser.add_argument("--bridge-scale", default="{}", help='JSON {"step": factor}: multiply bridge offsets, used after trimming a run')
    args = parser.parse_args()

    blocks = narration_blocks(SCRIPT_MD.read_text())
    steps = read_steps(Path(args.steps))
    if len(blocks) != len(steps):
        print(f"{len(blocks)} blocks but {len(steps)} steps", file=sys.stderr)
        return 2
    values = values_from_log(Path(args.log).read_text()) if args.log else {}
    texts = [fill_placeholders(block, values) for block in blocks]
    bridges = [(step, offset, fill_placeholders(text, values)) for step, offset, text in bridge_lines(SCRIPT_MD.read_text())]
    # every spoken item with its anchor time: main block k at step k (+slack, block 1 at 0.3 s), bridges at step + offset
    items: list[tuple[float, str, int | None]] = []
    for index, (text, step_time) in enumerate(zip(texts, steps), start=1):
        anchor = 0.3 if index == 1 else step_time + args.slack
        items.append((anchor, text, index))
    scale = {int(key): float(value) for key, value in json.loads(args.bridge_scale).items()}
    for step, offset, text in bridges:
        if 1 <= step <= len(steps):
            anchor = steps[step - 1] + offset * scale.get(step, 1.0)
            next_start = steps[step] if step < len(steps) else float("inf")
            if anchor >= next_start:
                print(f"bridge for step {step} at +{offset:.0f}s dropped: step ends before it", file=sys.stderr)
                continue
            items.append((anchor, text, None))
    items.sort(key=lambda item: item[0])
    Path(f"{args.out}-texts.txt").write_text("\n\n".join(f"[{anchor:.1f}s] {text}" for anchor, text, _ in items) + "\n")

    work = Path(args.work) if args.work else Path(tempfile.mkdtemp(prefix="track-"))
    work.mkdir(parents=True, exist_ok=True)
    clips: list[Path] = []
    token = detail = None
    if args.voice in ZERO_VOICES:
        query, needle, _build, slug = ZERO_VOICES[args.voice]
        token, detail = zero_pick(query, needle, slug)
        print(f"voice: {args.voice} via {token}", file=sys.stderr)
    import hashlib

    for anchor, text, step_index in items:
        # cache by text hash, so re-laying or re-wording one line never re-buys the others
        key = hashlib.sha1(f"{args.voice}:{text}".encode()).hexdigest()[:12]
        wav = work / f"clip-{key}.wav"
        if not wav.exists():
            if args.voice == "say":
                tts_say(text, wav)
            else:
                mp3 = work / f"clip-{key}.mp3"
                zero_speak(token, detail, ZERO_VOICES[args.voice][2](text), mp3)
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-ar", "44100", "-ac", "2", str(wav)], check=True)
        clips.append(wav)
        label = f"block {step_index}" if step_index else "bridge"
        print(f"{label:>8} @{anchor:6.1f}s: {duration(wav):.1f}s", file=sys.stderr)

    starts = []
    cursor = 0.0
    for wav, (anchor, _text, _step) in zip(clips, items):
        start = max(anchor, cursor)
        starts.append(start)
        cursor = start + duration(wav) + args.gap
    total = cursor
    cues = [start for start, (_a, _t, step_index) in zip(starts, items) if step_index]
    filters = []
    labels = []
    inputs = []
    for index, (wav, start) in enumerate(zip(clips, starts)):
        inputs += ["-i", str(wav)]
        delay = int(start * 1000)
        filters.append(f"[{index}]adelay={delay}|{delay}[n{index}]")
        labels.append(f"[n{index}]")
    filters.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0,apad=whole_dur={total:.2f}[a]")
    out_wav = Path(f"{args.out}.wav")
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filters), "-map", "[a]", str(out_wav)], check=True)
    with Path(f"{args.out}-cues.tsv").open("w") as handle:
        for index, start in enumerate(cues, start=1):
            handle.write(f"{index}\t{start:.2f}\n")
        handle.write(f"end\t{total:.2f}\n")
    print(f"{'item':>8}  {'starts':>7}  {'ends':>7}  {'anchor':>7}")
    for wav, start, (anchor, _text, step_index) in zip(clips, starts, items):
        label = f"block {step_index}" if step_index else "bridge"
        print(f"{label:>8}  {start:>7.1f}  {start + duration(wav):>7.1f}  {anchor:>7.1f}")
    gaps = [(b_start - (a_start + duration(a_wav))) for (a_wav, a_start), (_b, b_start) in zip(zip(clips, starts), zip(clips[1:], starts[1:]))]
    if gaps:
        print(f"longest silence between items: {max(gaps):.1f}s")
    print(f"wrote {out_wav} ({total:.1f}s), {args.out}-cues.tsv, {args.out}-texts.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
