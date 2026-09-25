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
