# Submission form text

**Project name:** ledger

**Description:**
ledger is a host-agnostic command-line tool that keeps a long-horizon agent's state as dated, falsifiable
Markdown under `.ledger/`, so the work survives a crash, a context reset or a change of host. The agent's
history is disposable; the ledger is the state. Every heading is stamped from the clock, gates flip only on a
measurement, and `ledger resume` prints a short brief that a completely fresh session can finish the task
from. In the demo the plan is a gate with a threshold and the tests are its measurement: a task paused under
Claude Code with failing tests is finished by a new headless Claude Code session whose only context is that
brief; it fixes the code, runs the tests, iterates until green and flips the gate with the exact line it
measured. Plan, act, observe, self-correct, across a build cycle, without the history. A `watch` loop fetches a page through Nimble, a Liquid LFM2.5-1.2B model running
locally through Ollama distills it into at most three new lines, and the raw page is discarded. Every verb
emits one event to RawTree, where two SQL queries, what changed in the last hour and the board, answer "what
happened" as a query. On pause, Black Forest Labs FLUX renders a cover image from the day's entries.
Built with Python 3.11 (standard library only in the core), Claude Code, RawTree, Nimble, Liquid AI and
Black Forest Labs.

**Demo video:** https://github.com/mlgraham/long-horizon-hack-2026/raw/main/demo/ledger-demo.mp4 (also playable from the repo page; narrated, 2:59)

**Team name:** <TEAM NAME>

**Contact email:** <EMAIL>

**Repository:** https://github.com/mlgraham/long-horizon-hack-2026

**One-sentence description:** A host-agnostic CLI that keeps a long-horizon agent's state as dated, falsifiable Markdown, so a task killed under one agent host finishes under another from a two-minute brief.

**Team size:** 1. **Tools selected:** Liquid AI, Nimble, Black Forest Labs, RawTree, Claude Code.

**Working project URL:** https://github.com/mlgraham/long-horizon-hack-2026. **Screenshot:** `docs/demo-screenshot.png` (the RawTree board frame from the video).

## Additional project details (optional section of the form)

**Architecture**

Plain Markdown under .ledger/ is the only state: STATUS.md (append-only, every heading stamped from the clock), gates.md (pre-registered thresholds that flip only on a measurement), obligations.md, pause.md (the resume-here entry). `ledger resume` rebuilds a brief of under 60 lines from those files; that brief is the whole context a second host gets.

Every verb emits one event (ts, kind, host, model, gate, text, tokens, bytes_discarded) to a local mirror and to one RawTree table; "what changed in the last hour" and the board are two SQL queries. `ledger tick`/`watch` observe a live topic through Nimble search, distill it with Liquid LFM2.5-1.2B running locally through Ollama into at most three new lines, deduplicate against the ledger, and discard the raw page. `ledger pause --cover` renders a FLUX image from the day's headlines. The second host is a fresh headless Claude Code session (hosts/claude_code.sh) or a bare tool-calling loop (hosts/loop.py). Core is Python 3.11 standard library only; 55 tests.

**Setup**

```sh
uv venv .venv && uv pip install -e '.[dev,video]'
ollama pull hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF
cp .env.example .env   # RAWTREE_API_KEY, NIMBLE_API_KEY, BFL_API_KEY; every key is optional, each verb degrades to a local fallback
ledger doctor          # one line per component
bash demo/run.sh       # the 3-minute demo: observe, plan (spec as a gate), pause, resume on a second host, board
```

**Lessons**

Six pre-registered hinges with kill criteria, each passed on a measurement written into the ledger before the pitch. AWS Bedrock was dropped at 10:08 when no account was available; Tinybird was swapped for RawTree at kickoff, which took one client file because RawTree takes events as they are. A 1.2B model on an Intel CPU is a good per-tick distiller (8-25 s per page) and a poor agent: it could not drive a read-then-write loop, so the second host became a fresh headless session and Liquid stayed where it works. The ledger, not the model, decides what is new: repeat ticks deduplicate to "no change". The demo video is generated from a timestamped run, not screen-recorded; the process is in docs/video-process.md.

**Additional links**

https://github.com/mlgraham/long-horizon-hack-2026/blob/main/docs/Ledger-One-Pager.pdf
https://github.com/mlgraham/long-horizon-hack-2026/blob/main/docs/Ledger-Over-History.pdf
https://github.com/mlgraham/long-horizon-hack-2026/blob/main/STATUS.md
https://github.com/mlgraham/long-horizon-hack-2026/blob/main/docs/video-process.md
