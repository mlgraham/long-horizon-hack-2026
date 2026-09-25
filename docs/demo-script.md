# Demo narration (3 minutes)

Six blocks, one per numbered step of `demo/run.sh`. The video is generated, not screen-recorded:

```sh
source .venv/bin/activate
DEMO_PAUSE=8 bash demo/run.sh | tee /tmp/demo.log                      # a timed rehearsal: writes /tmp/ledger-demo/steps.tsv
python scripts/narration_track.py --steps /tmp/ledger-demo/steps.tsv --log /tmp/demo.log \
    --voice zero-elevenlabs --out demo/narration                          # six TTS blocks (about $0.12) -> narration.wav + cues
python scripts/record_run.py --out demo/run.jsonl DEMO_CUES=demo/narration-cues.tsv   # the real run, paced to the cues, every line timestamped
python scripts/retime_run.py --run demo/run.jsonl --steps /tmp/ledger-demo/steps.tsv --max-gap 14 \
    --narration-args "--log /tmp/demo.log --voice zero-elevenlabs --slack 1.5 --gap 0.5 --out demo/narration"
                                                                          # trim waits, hold each step for its block, re-lay (no new cost)
python scripts/render_video.py --run demo/run.retimed.jsonl --audio demo/narration.wav --out demo/ledger-demo.mp4
```

`--voice say` uses the free macOS voice instead. To narrate a screen recording of your own instead, use
`scripts/narrate.py` (per-step clips mixed at the step times) or `scripts/mix.sh` (one track, one offset).

Numbers said aloud come from two places only: the gate entries in `STATUS.md`, or the terminal while it runs.
Read the live ones off the screen. Do not say a number from a rehearsal.

## The judges' five criteria, and where each one shows

| Criterion | Where it shows in the run |
|---|---|
| Autonomy | Steps 2 and 5: live pages through Nimble, distilled without a human; nobody touches the keyboard between the pause and the passing gate. |
| Idea | The thesis: the history is disposable, the ledger is the state, and it survives a change of host. |
| Technical implementation | Plain Markdown plus one event per verb; clock-stamped, gated on measurement, tested (see the suite). |
| Tool use | RawTree (step 6), Nimble (step 2), Liquid (step 2), Black Forest Labs (the cover on pause). |
| Presentation | Six steps in about a minute of runtime; the narration fills three. |

## 0:00 to 0:30 · Step 1, a scratch repo and a fresh ledger

On screen:

```sh
git -C /tmp/ledger-demo init -q
ledger --dir /tmp/ledger-demo/.ledger init
```

Say: "An agent's transcript is disposable, so we start with nothing but an empty repo and a `.ledger` folder
of plain Markdown."

## 0:30 to 1:00 · Step 2, three ticks on a live page

On screen:

```sh
ledger --dir /tmp/ledger-demo/.ledger tick "AI agents news today" --url https://news.ycombinator.com --distiller liquid
```

Say: "Each tick pulls live web results for the topic through Nimble, a Liquid model on this laptop keeps at
most three new lines, and the raw pages, [read the bytes-discarded figure off the screen] bytes of them, are
thrown away."

## 1:00 to 1:30 · Step 3, plan: the spec is a gate

On screen:

```sh
ledger --dir /tmp/ledger-demo/.ledger gate add build --threshold "python -m pytest -q tests passes all 3 tests" ...
python -m pytest -q tests        # 3 failed
```

Say: "The plan is not a paragraph in a transcript. The spec is a gate with a threshold, the tests are its
measurement, and the first implementation is wrong on purpose. Three failures, recorded."

## 1:30 to 2:00 · Step 4, pause, then the brief

On screen:

```sh
ledger --dir /tmp/ledger-demo/.ledger pause --resume "Fix slug.py so that pytest passes; then ledger gate pass build --measured ..." --first tests/test_slug.py --cover
ledger --dir /tmp/ledger-demo/.ledger resume --quiet
```

Say: "We stop mid-task. What survives is one pause entry saying where to pick up, with a FLUX cover drawn from the day's
headlines, and this brief: the pause, the open gate, the last entries and the rules, under sixty lines. The
transcript is gone."

## 2:00 to 2:30 · Step 5, act, observe, self-correct on a different host

On screen:

```sh
bash hosts/claude_code.sh /tmp/ledger-demo/.ledger
python -m pytest -q tests        # 3 passed
ledger --dir /tmp/ledger-demo/.ledger gate list
```

Say: "A brand-new headless session gets that brief and nothing else. It reads the tests, fixes the code, runs
pytest, and flips the gate with the exact line it measured. Nobody touched the keyboard. In our gate run, a
24-line brief was its only context."

## 2:30 to 3:00 · Step 6, what persisted, what was discarded, the board

On screen:

```sh
ledger --dir /tmp/ledger-demo/.ledger stats
ledger --dir /tmp/ledger-demo/.ledger board
```

Say: "Here is the split the brief asks for: [read the persisted and discarded bytes off the screen]. Every verb
was one event, so what happened is a query, read back here from RawTree. The history is not the agent.
The ledger is."

## Bridges

Lines spoken during waits, so the screen is never still and silent. `- N +S:` plays S seconds into step N,
after any earlier block has finished. Numbers come from the run; say none that are not on screen.

- 1 +0: "This is ledger. Nothing you see is a transcript: the whole state of the work lives in a few Markdown files. We will kill the agent and pick the work up somewhere else."
- 2 +14: "Each tick takes about twenty-five seconds on this laptop, trimmed here: Nimble fetches live results for the topic, then a one-point-two-billion-parameter Liquid model reads forty-five kilobytes and writes at most three lines."
- 2 +33: "The second and third ticks come back as no change. That is the ledger deciding, not the model: a line already in the state is dropped before it is written."
- 2 +52: "Nothing raw is kept. The page is gone the moment the delta is written; only the byte count survives, as an event."
- 2 +63: "One more tick, and then we stop the agent mid-task."
- 5 +21: "It is running pytest now. When the tests pass, it flips the gate itself, with the exact line it measured, and writes its own notes."
