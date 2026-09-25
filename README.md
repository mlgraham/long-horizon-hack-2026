# ledger

The agent's history is disposable. The ledger is the state. A long-horizon agent does not need its transcript
back after a crash, a context reset or a change of host. It needs a short, dated, falsifiable record of what
was decided, what is still open and what to do next. `ledger` keeps that record as plain Markdown under
`.ledger/` in whatever repo it runs in. Any host that can run a shell command can write it, and any other host
can pick the work up from `ledger resume` alone. Raw observations are distilled into a few lines and thrown
away. Every verb also emits one event, so the whole run can be queried.

## Install

```sh
uv venv .venv && uv pip install -e '.[dev]'
source .venv/bin/activate
ledger init
```

The per-tick distiller runs locally on a Liquid model through Ollama:

```sh
ollama pull hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF
```

Copy `.env.example` to `.env` and fill in only the keys you have. Every sponsor integration is optional; the
core runs on the standard library with no keys at all.

## Verbs

Every heading `ledger` writes is stamped from the clock, never from an argument.

```sh
ledger note "switched the distiller to LFM2.5-1.2B" --body "- 8-13 s per tick on CPU"
ledger gate add H2 --threshold "endpoint returns the last hour" --by 13:30 --owner solo --kill "keep events local"
ledger gate pass H2 --measured "<what you measured>"  # a gate flips only on a measurement
ledger obligation add nimble-key --hypothesis-inhabited unknown --consumer watch
ledger pause --resume "finish notes/summary.md from the three input files" --first plans/design.md
ledger resume                                          # the brief a fresh session starts from
ledger tick "hacker news" --url https://news.ycombinator.com --distiller liquid
ledger watch "hacker news" --url https://news.ycombinator.com --every 10m --ticks 6
ledger sync                                            # backfill events to RawTree
ledger board --open                                    # two tables, printed and written to .ledger/board.html
ledger doctor                                          # one line per component: ledger files, each sponsor, claude, ollama
ledger stats                                           # persisted / derived / discarded bytes for this ledger
```

`ledger events` prints the local event mirror. `ledger gate list` and `ledger obligation list` print the tables.

## Files

```
.ledger/
  STATUS.md         append-only log; every heading is "### YYYY-MM-DD HH:MM TZ — title"
  gates.md          pre-registered hinges: threshold, date, owner, kill criterion, status, measurement
  obligations.md    named-but-unproved claims, with "hypothesis inhabited" yes / no / unknown
  pause.md          the latest ⏸ resume-here entry
  events.jsonl      one JSON row per verb (the local mirror)
  board.html        written by `ledger board`
  covers/           FLUX images from `ledger pause --cover`
```

Nothing else holds state. Delete the transcript, keep `.ledger/`, and the work survives.

## Kill and resume across hosts

1. Plan under Claude Code: write the spec as a gate (`ledger gate add build --threshold "pytest passes"`), the
   tests that measure it, and `ledger note` after each real step.
2. Stop mid-task with a pause entry:
   `ledger pause --resume "fix slug.py until pytest passes, then ledger gate pass build --measured ..."`.
3. Kill the session. Then start a second host whose only context is the brief:

```sh
hosts/claude_code.sh .ledger          # a fresh headless Claude Code session fed by `ledger resume`
python -m hosts.loop --backend anthropic   # alternative: a bare tool-calling loop (Ollama or Anthropic API)
```

The `anthropic` backend needs the SDK: `uv pip install -e '.[loop]'`. The `ollama` backend needs only Ollama.

The second host reads the brief, acts, runs the tests, self-corrects until they pass, and flips the gate with
the exact line it measured. Plan, act, observe, self-correct, across a build cycle, with no transcript carried
over. `demo/run.sh` runs the whole sequence in a scratch repo.

## The video

`demo/ledger-demo.mp4` is generated, not screen-recorded: a real run of `demo/run.sh` with every line
timestamped, rendered as a terminal, with a narration laid on the step times. The process, reusable for any
scripted demo, is in `docs/video-process.md`; the narration text is `docs/demo-script.md`.

## Sponsors

Each integration is switched on by one environment variable. Without it, the verb still works.

### RawTree

Every verb mirrors its event row to one RawTree table, `ledger_events`, as it is: no schema step, the table is
created on the first insert. Two SQL queries answer the judges' questions, "what changed in the last hour" and
the board (events, bytes discarded and tokens per kind and host); `ledger board` runs them and falls back to the
local mirror without a key. `ledger sync` backfills and never sends a row twice. Details: `docs/rawtree.md`.
Enabled by `RAWTREE_API_KEY` (optionally `RAWTREE_DATABASE`).

### Nimble

`ledger tick` and `ledger watch` fetch their observation through the Nimble API: an extract of `--url`, or a
live web search on the topic when no URL is given. The raw page is distilled and then discarded; the entry
records how many bytes were thrown away. Enabled by `NIMBLE_API_KEY`. Without it, `--url` is fetched directly.

### Liquid AI

A Liquid LFM2.5 model is the distiller on every tick: previous state plus fresh page in, at most three new
lines out. The large model never sees the raw page. It runs locally through Ollama by default, or against any
OpenAI-compatible host. Enabled by a local Ollama with the model pulled, or by `LIQUID_BASE_URL` and
`LIQUID_API_KEY`. `LIQUID_MODEL` overrides the model name.

### Black Forest Labs

`ledger pause --cover` renders one FLUX image from the day's entry headings into `.ledger/covers/` and links
it under the pause entry. Enabled by `BFL_API_KEY`.

## Environment

| Variable | What it does |
|---|---|
| `RAWTREE_API_KEY` | RawTree key (`rt_...`); enables the event mirror, `ledger sync` and the RawTree board |
| `RAWTREE_DATABASE` | RawTree database name (default: the key's default database) |
| `NIMBLE_API_KEY` | Nimble key; `tick` and `watch` observe through Nimble |
| `LIQUID_MODEL` | distiller model name (default `hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF`) |
| `LIQUID_BASE_URL` | OpenAI-compatible base URL for the distiller (default local Ollama) |
| `LIQUID_API_KEY` | key for a hosted Liquid endpoint |
| `BFL_API_KEY` | Black Forest Labs key; enables `pause --cover` |
| `ANTHROPIC_API_KEY` | key for `hosts/loop.py --backend anthropic` |
| `LEDGER_HOST` | host name written on every event (default: detected) |
| `LEDGER_DIR` | the `.ledger` directory (default: nearest `.ledger` walking up) |

## What is measured

Only numbers recorded in gate and measurement entries of this repo's own ledger (`.ledger/gates.md`, `STATUS.md`).
All six pre-registered gates passed on 2026-09-25:

- **H1, core.** `ledger resume` on this repo: 30 lines, against a limit of 60. `tests/test_core.py`: 6 passed.
  Note, pause and resume touch only `.ledger/` files.
- **H2, RawTree.** `ledger sync` posted 32 rows to the shared hackathon cluster; the last-hour query returned
  5 rows; `ledger board` rendered from RawTree; `SELECT 1` answered in 0.2 s.
- **H3, second host.** A task paused under Claude Code finished under a fresh headless `claude -p` session.
  The 24-line brief was its only context. It wrote 3 ledger notes and a correct 3-line file. Liquid 1.2B and
  2.6B on CPU could not finish the same task. The build-cycle rehearsal: 3 tests failed before, 3 passed after,
  gate flipped by the second host with the measured pytest line.
- **H4, Nimble.** Three ticks on a live topic through Nimble search: 44,897 raw bytes discarded per tick,
  134,691 in total, ledger 1,093 bytes; one 3-line delta, then two honest "no change" entries; 23.6-25.3 s per
  tick on CPU.
- **H5, Liquid.** LFM2.5-1.2B via Ollama on an Intel i9, CPU only: 10.0 s and 8.4 s on the fixture, 8-13 s on
  a live 4 KB page, 20.9 s on the hinge run; repeat ticks deduplicated to "no change" by the ledger.
- **H6, FLUX.** `pause --cover` produced a 344 KB cover through `flux-2-pro-preview` on the first attempt after
  the account was funded; the pause entry links it.

## Tests

```sh
.venv/bin/python -m pytest -q
```
