# CLAUDE.md — long-horizon-hack-2026

Workspace for the **Long Horizon Agents Hackathon**, Friday 2026-09-25, AWS Builder Loft, San Francisco.
Kickoff 11:00, submission window 11:30–16:30 PT, finalist demos 17:00, awards 19:00.

## Read first, in this order

1. `STATUS.md` — the ledger. The last entry says where things stand and what to do next.
2. `plans/design.md` — what we are building (`ledger`, a host-agnostic resumable-state CLI, with all four
   sponsors in the loop) and the hour-by-hour plan with pre-registered hinges.
3. `research/event.md` — prizes, submission requirements, judges, sponsor docs links.
4. `docs/Ledger-Over-History.pdf` — the narrative for the judges. Its HTML source is beside it.

This project was prepared on the morning of 2026-09-25, before the event, from an earlier private repository whose
ledgers, gates, memory files and status board the PDF narrative draws on.

## What is public and what is not

- The GitHub repo `mlgraham/long-horizon-hack-2026` is **public** and holds only the stub README until the
  operator says to push. Everything else in this directory is local and unpushed on purpose.
- Push only when the operator says so, and then push the whole working tree (the submission needs a public
  repo with the real code and README).
- Keys go in `.env` (gitignored). Never commit a key. Needed today: Nimble, RawTree (replaced Tinybird at kickoff), Liquid AI (or a local
  model from Hugging Face), Black Forest Labs. AWS Bedrock was dropped: no account was available.

## Rules carried over from the earlier repository

- **Ledger timestamps come from the clock.** Every `STATUS.md` heading is written with `$(date "+%Y-%m-%d %H:%M %Z")`
  in the same command. Never type a time.
- **Never cite a number you have not run.** Line counts, timings, event counts: measure, then write.
- **"Shipped" means the judge can run it.** A commit is not a demo. The video is not the submission until the form is sent.
- **Test the hinge before building on it.** Each sponsor integration has a pass/fail hinge and a time in
  `plans/design.md`. A failed hinge drops that sponsor, never the core.
- **Commit messages carry no AI attribution.** No "Generated with" footers, no Co-Authored-By model lines.
- **Web fetches go through Playwright** (installed in this repo's `.venv` by the `video` extra). Bare `curl` fails
  silently on many sites.

## Conventions

- Python 3.11, type hints, no single-letter variable names, `logging` not `print` inside the library.
- CLI code in `ledger/`, host adapters in `hosts/`, sponsor clients in `sponsors/`, tests in `tests/`.
- The ledger files the tool manages live under `.ledger/` in whatever repo it runs in. This repo dogfoods it:
  once the CLI exists, `STATUS.md` entries are written with `ledger note`.
