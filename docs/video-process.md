# Making a narrated demo video without a screen recording

A repeatable process for turning a scripted terminal demo into a narrated MP4. Everything is generated:
the terminal frames are rendered from a timestamped transcript of a real run, and the narration is
text-to-speech placed at the moments the screen changes. There is no screen capture, no video editor, and
no manual alignment. First used for the `ledger` demo on 2026-09-25; the tools live in `scripts/` and
`demo/` of that repo and are generic enough to lift into another project.

## The idea

A demo script that prints numbered step headings is already a timeline. Record when each line appears,
render those lines as a terminal, and the video's clock is the run's clock. Narration then only needs to
know *when each step started*, which the run itself reports. The two mistakes to avoid are silence at the
start (the viewer wonders whether the audio works) and silence over a still screen (the viewer wonders
whether the video stalled). So: the voice starts in the first second, and every wait is narrated as it
happens.

## Pieces

| Piece | What it does | In this repo |
|---|---|---|
| The demo script | Prints `== N. heading ==` per step; writes `steps.tsv` (step, seconds since start); optional holds and cue-pacing | `demo/run.sh` |
| The narration source | A Markdown file with one `Say: "..."` block per step plus `- N +S: "..."` bridge lines that play S seconds into step N | `docs/demo-script.md` |
| The track builder | Speaks each block (TTS), lays them on the step times without overlaps, writes one WAV plus `cues.tsv` | `scripts/narration_track.py` |
| The recorder | Runs the demo, timestamps every output line into `run.jsonl`; `DEMO_CUES` paces each step to the narration | `scripts/record_run.py` |
| The renderer | Renders `run.jsonl` as terminal frames with Playwright (one frame per change), encodes with ffmpeg, mixes the WAV | `scripts/render_video.py` |
| Voices | `say` (macOS, free) or ElevenLabs / OpenAI through Zero (paid per block, about two cents) | `--voice` flag |

Requirements: Python 3.11, ffmpeg and ffprobe on PATH, Playwright with Chromium (any virtualenv), and for a
paid voice the `zero` CLI signed in.

## The process, in order

1. **Write the script so it narrates itself.** Each step prints a heading. Steps that wait (a model call,
   a network fetch) should print progress lines, so the screen moves. Add `DEMO_PAUSE` style holds only
   where the narration needs more time than the step takes.
2. **Write the narration next to the steps.** One `Say:` block per step, thirty seconds or less each.
   Put numbers in square brackets ("[read the bytes-discarded figure off the screen]") and let the builder
   fill them from the run log, so no number is invented. Add bridge lines for any wait longer than about
   ten seconds: what is happening, how long it takes, what to watch for.
3. **Timed rehearsal.** `bash demo/run.sh | tee /tmp/demo.log` writes `steps.tsv`. This is the first
   estimate of where each step lands.
4. **Build the track.** `python scripts/narration_track.py --steps steps.tsv --log /tmp/demo.log
   --voice zero-elevenlabs --out demo/narration`. It speaks every block once (blocks are cached in
   `demo/.track/` and never bought twice), lays them out (block k no earlier than step k plus slack, never
   before the previous block ends), and writes `narration.wav` and `narration-cues.tsv`.
5. **The real run, paced to the cues.** `python scripts/record_run.py --out demo/run.jsonl
   DEMO_CUES=demo/narration-cues.tsv`. Each step waits for its cue, so the screen never runs ahead of the
   voice. Live steps can still run *longer* than rehearsed; that is why the next step exists.
6. **Re-lay the track on the real step times.** Run step 4 again with the new `steps.tsv` and a small
   `--slack`. No TTS is repeated, so this is free and instant. Now the audio matches the screen exactly.
7. **Re-time (optional, usually wanted).** `python scripts/retime_run.py --run demo/run.jsonl --steps
   steps.tsv --max-gap 14 --narration-args "..."` trims any silence longer than 14 s between output lines,
   scales each step's bridge offsets by how much it shrank, drops a bridge that would fall after its step,
   and holds each step until its narration block begins. Order and content never change; only waiting time.
   It writes `run.retimed.jsonl`, `steps.retimed.tsv` and rebuilds the narration on the new times.
8. **Render.** `python scripts/render_video.py --run demo/run.jsonl --audio demo/narration.wav
   --out demo/ledger-demo.mp4`. One frame per output line, held for its real duration; 1280x720, H.264,
   AAC. Check three frames with `ffmpeg -ss <t> -frames:v 1` before sending.

Total cost for a six-block, three-bridge narration on ElevenLabs: about eighteen cents. Total time after
the rehearsal: the length of the demo plus about two minutes of rendering. Expect two or three rounds of
watching, re-wording and re-laying; only re-worded lines cost anything.

## Checks before publishing

- Voice starts within one second (block 1 anchored at zero, not at step 1 plus slack).
- No gap over about eight seconds without narration while the screen is still.
- Every number spoken appears on screen or in the run log.
- The narration never describes something the screen has not shown yet: re-lay on the real step times.
- The last block finishes before the video ends; set `--tail` on the renderer if it needs a beat.
- The MP4 plays in QuickTime and a browser (H.264 + AAC, yuv420p).
- The total fits the time limit. The narration always ends a few seconds after the screen does, because
  blocks that start late push the next ones later. If the cut runs over: shorten the longest block, tighten
  `--gap`, and as a last resort render with `--tempo 1.02` (pitch preserved, inaudible, 2% shorter).
- Each step starts at the top of the screen (the renderer clears on every `== N.` heading), so the viewer
  never has to find the current section at the bottom of a scrolled page.
- A step that works silently (a model call, a headless session) prints something while it works. In this
  demo, step 5 tails the ledger and prints each entry the second host writes, as it writes it; thirty seconds
  of a still heading is the same problem as thirty seconds of silence.
- Speech gets Markdown and code marks stripped, and a small respelling table for words the voice misreads
  (`pytest` → "pie-test", `.ledger` → "dot-ledger"). Docs keep the real spelling.
- Words with no good respelling are reworded: "resume" came out as "résumé" on ElevenLabs, so the
  narration says "pick up" instead. Only the changed line is re-spoken, because clips are cached by text.

## Adapting to another project

Keep the contract, swap the content: headings of the form `== N. text ==`, a `steps.tsv` writer in the
script, a Markdown file with `Say:` blocks and bridge lines, and the three scripts unchanged. If the demo
is not a terminal, replace the renderer's HTML template with whatever the steps show (screenshots taken
at each step also work: one frame per change is all the renderer needs).
