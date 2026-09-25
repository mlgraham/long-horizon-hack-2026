# `ledger` — resumable agent state that survives a change of host

> **Pre-kickoff plan, kept as written.** What changed on the day (see `STATUS.md`): Tinybird was replaced by
> RawTree at kickoff, so the event mirror is one RawTree table and two SQL queries (`sponsors/rawtree.py`); AWS
> Bedrock was dropped because no account was available, and the second host became a fresh headless Claude Code
> session (`hosts/claude_code.sh`) with `hosts/loop.py` as the bare-loop alternative; Liquid stayed as the
> per-tick distiller only; the demo became a build cycle (spec as a gate, failing tests, second host fixes and
> flips the gate). All six hinges passed.

**One sentence:** a small CLI that keeps an agent's long-horizon state as dated, falsifiable Markdown in the
repo, so a task can be killed under one host and resumed under another, with every observation flowing
through Nimble, every event landing in Tinybird, the per-tick distillation on a Liquid model, the resume on
AWS Bedrock, and a FLUX cover image on each pause entry.

The thesis is in `docs/Ledger-Over-History.pdf`: the agent's history is disposable; the state that matters is
a ledger that any fresh session can read in two minutes.

## The verbs

| Verb | Writes | Notes |
|---|---|---|
| `ledger note "<text>"` | appends `### <clock> — <text>` to `.ledger/STATUS.md` | time from the system clock, never an argument |
| `ledger gate add <name> --threshold --by --owner --kill` | a row in `.ledger/gates.md` | pre-registered; `ledger gate pass/fail <name> --measured "<value>"` flips it |
| `ledger obligation add <name> --hypothesis-inhabited yes/no/unknown` | a row in `.ledger/obligations.md` | "an obligation nobody can satisfy reads as closed" |
| `ledger pause` | a `⏸` entry: what to resume, caps, open rulings, first file to read | also triggers the FLUX cover image (optional) |
| `ledger resume` | prints the two-minute brief to stdout | the only thing a new host needs in context |
| `ledger watch <topic> --every 10m` | a loop: Nimble fetch → Liquid distill → `note` the delta → discard raw | the long-horizon demo |
| `ledger tick` | one iteration of `watch` plus an event post | used by cron or a host's scheduler |

Every verb also posts one event to Tinybird (`events` datasource):
`ts, kind, host, model, gate, text, tokens_in, tokens_out, bytes_discarded`.

## Storage format (plain Markdown, host-agnostic)

```
.ledger/
  STATUS.md        append-only log, one heading per entry, clock-stamped
  gates.md         table: name | threshold | by | owner | kill criterion | status | measured
  obligations.md   table: name | hypothesis inhabited? | consumer | status
  pause.md         the latest ⏸ entry (also appended to STATUS.md)
  covers/          optional FLUX images, one per pause
```

No database is required to run. Tinybird is the *event mirror* for the board and for the judges' queries.

## Sponsors, and the hinge for each

| Sponsor | Role in the loop | Hinge (pass by) | If it fails |
|---|---|---|---|
| **AWS Bedrock** | the second host: a ~80-line Python loop that calls `ledger resume`, puts the brief in the system prompt, and continues the task | H3, 15:00: a task killed under Claude Code finishes under the Bedrock loop | demo resume Claude Code → Claude Code fresh session instead |
| **Tinybird** ($2,000 / $1,000 / $500 gift cards) | every event mirrored; a pipe/endpoint `what_changed_last_hour`; the board is a query | H2, 13:30: an endpoint returns the last hour's events | keep events local in `.ledger/events.jsonl`; drop the pitch line |
| **Nimble** ($1,000 cash + credits) | `watch` pulls the topic through the Nimble MCP server or SDK every tick | H4, 14:30: three ticks on a real topic write three deltas and discard the raw pages | `watch` reads a local fixture; no Nimble claim |
| **Liquid AI** (Edge kit + $250) | the distiller on every tick: raw page + last state → ≤ 3-line delta; the big model runs only on `resume` | H5, 14:30: a Liquid model (API or local LFM from Hugging Face) produces a usable delta on a real page | distill with the Bedrock model; no Liquid claim |
| **Black Forest Labs** (credits) | on `pause`, a FLUX image from the day's digest saved to `.ledger/covers/`, shown on the board | H6, 15:30, only if H1–H3 passed | skip; say nothing about it |

The core has its own hinge first: **H1, 12:30 — `note`, `pause`, `resume` work from files alone, and the
resume brief is under 60 lines for the demo repo.** Nothing else starts until H1 passes.

## The demo (3 minutes, record at 15:45)

1. Show `.ledger/STATUS.md` being written by `ledger watch` on a live topic through Nimble, the Liquid delta
   appearing, the raw page byte count discarded.
2. Kill the agent mid-task under Claude Code. Show the `⏸` pause entry (and its FLUX cover if done).
3. `ledger resume` on the Bedrock loop. It picks up and finishes the task.
4. Open the Tinybird endpoint: "what changed in the last hour" as one query. Show the board rendered from it.
5. One slide: the persist / derived / discarded split from the PDF, then the 9,121-line ledger from the earlier private repository as
   proof the pattern survives weeks.

## The day

| Time | Do |
|---|---|
| 11:00 | Repo skeleton, `ledger note/pause/resume`, dogfood: this file's ledger is written by the tool |
| 11:30 | Submission form opens: fill names/emails now; README first draft in the ledger's own format |
| 12:30 | **H1.** Then Tinybird: datasource, ingest from every verb, endpoint |
| 13:30 | **H2.** Lunch. Then Nimble `watch` + Liquid distiller in parallel if two people |
| 14:30 | **H4, H5.** Then the Bedrock loop |
| 15:00 | **H3.** FLUX cover if time |
| 15:45 | Record the video. Push everything public. |
| 16:15 | Submit: repo, video link, description naming all tools, names, emails |
| 16:30 | Deadline. Find the Tinybird and Nimble judges before demos. |

## Team split (up to four)

- **P1:** the CLI core and the Bedrock resume loop.
- **P2:** Nimble `watch` and the Liquid distiller.
- **P3:** Tinybird ingest, endpoint, and the one-page board.
- **P4:** README, video, submission, and the pitch to the sponsor judges.
- **Solo:** core → Tinybird → Bedrock → Nimble → Liquid → FLUX, stopping wherever 15:45 arrives.

## Kill rule for the day

A hinge that fails at its time drops that sponsor from the pitch and the README. It never delays H1–H3.
Record the measurement in `STATUS.md` either way.
