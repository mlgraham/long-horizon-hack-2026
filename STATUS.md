# STATUS — long-horizon-hack-2026 ledger

Append-only. Every heading is stamped from the clock in the command that writes it. Newest entry last.

## Log

### 2026-09-25 09:48 PDT — workspace created; stub pushed; resume documents written

- Public repo `mlgraham/long-horizon-hack-2026` created and pushed with only `README.md` and `.gitignore`
  (commit `55b7729`, "Initial stub"). **Everything else here is local and unpushed on purpose.**
- Written locally: `CLAUDE.md` (read-first order, public/private rule, carried-over rules), `plans/design.md`
  (the `ledger` CLI with all four sponsors, hinges H1–H6 with times, demo script, day plan, team split),
  `research/event.md` (brief, agenda, submission requirements, prizes, judges, sponsor doc links),
  `docs/Ledger-Over-History.pdf` (9 pages, the judge narrative) with its HTML source, and the two fetched
  event pages as JSON under `research/`.
- Decision pending from the operator: single-sponsor version (Tinybird only, as in the PDF) or the
  four-sponsor version in `plans/design.md`. The PDF's project section describes the Tinybird-first cut;
  the design file describes the full one. Both share the same core and H1.
- **Next:** at 11:00, start H1 (`note`, `pause`, `resume` from files alone, pass by 12:30). Put keys in
  `.env`. Fill the submission form's names and emails when it opens at 11:30.

### ⏸ PAUSED 2026-09-25 09:48 PDT — resume here

1. Read `CLAUDE.md`, then `plans/design.md`.
2. Confirm with the operator: four sponsors or Tinybird-only.
3. Begin H1. Do not start any sponsor integration before H1 passes.
4. First file to read for the pitch: `docs/Ledger-Over-History.pdf`, page 7 onward.

### 2026-09-25 10:00 PDT — decision: four-sponsor version; H1 starts

- Operator chose the four-sponsor version in `plans/design.md` over the Tinybird-only cut.
- Order for a solo build: core (H1) → Tinybird (H2) → Bedrock loop (H3) → Nimble (H4) → Liquid (H5) → FLUX (H6).
- No `.env` yet. Sponsor clients are built to degrade to local fallbacks until keys arrive.
- **Next:** H1. `ledger note`, `pause`, `resume` from files alone; brief under 60 lines; dogfood on this repo.

### 2026-09-25 10:04 PDT — gate H1 registered

- threshold: note, pause, resume work from files alone; resume brief under 60 lines on this repo
- by: 2026-09-25 12:30
- owner: solo
- if it fails: no hackathon entry; stop

### 2026-09-25 10:04 PDT — gate H2 registered

- threshold: a Tinybird endpoint returns the last hour of ledger events
- by: 2026-09-25 13:30
- owner: solo
- if it fails: events stay in .ledger/events.jsonl; drop the Tinybird pitch line

### 2026-09-25 10:04 PDT — gate H3 registered

- threshold: a task killed under Claude Code finishes under the Bedrock loop from ledger resume alone
- by: 2026-09-25 15:00
- owner: solo
- if it fails: demo resume into a fresh Claude Code session instead

### 2026-09-25 10:04 PDT — gate H4 registered

- threshold: three watch ticks on a real topic through Nimble write three deltas and discard the raw pages
- by: 2026-09-25 14:30
- owner: solo
- if it fails: watch reads a local fixture; no Nimble claim

### 2026-09-25 10:04 PDT — gate H5 registered

- threshold: a Liquid model produces a usable 3-line delta from a real page
- by: 2026-09-25 14:30
- owner: solo
- if it fails: distill with the Bedrock model; no Liquid claim

### 2026-09-25 10:04 PDT — gate H6 registered

- threshold: a FLUX cover image lands in .ledger/covers on pause
- by: 2026-09-25 15:30
- owner: solo
- if it fails: skip; say nothing about it

### 2026-09-25 10:04 PDT — gate H1 PASS

- threshold: note, pause, resume work from files alone; resume brief under 60 lines on this repo
- measured: ledger resume on this repo: 30 lines (limit 60); tests/test_core.py: 6 passed; note/pause/resume touch only .ledger/ files

### 2026-09-25 10:04 PDT — H1 passed at 10:04; core CLI installed in .venv; STATUS.md is now written by ledger note

- `ledger/`: clock, config, store, events, brief, cli. `sponsors/tinybird.py` written, untested (no token yet).
- `.ledger/STATUS.md` is a symlink to this file, so the repo dogfoods the tool.
- Next: H2 Tinybird. Datasource + endpoint files first, then ingest once a token is in `.env`.

### 2026-09-25 10:08 PDT — ruling: no AWS account today; second host becomes a bare local loop

- Operator: nothing can be sent to an AWS account. Bedrock is dropped as the second host.
- Replacement for H3: `hosts/loop.py`, a ~100-line loop with pluggable backends: Liquid LFM2.5 via Ollama (no key, no cloud) and the Anthropic API. The Bedrock backend stays as an option only.
- H3 threshold reworded: a task killed under Claude Code finishes under the local loop from `ledger resume` alone.
- The pitch gains a line: resumed on a 1.2B-parameter model on a laptop, from the ledger alone.

### 2026-09-25 10:08 PDT — gate H3 registered

- threshold: a task killed under Claude Code finishes under hosts/loop.py (Liquid via Ollama or Anthropic API) from ledger resume alone
- by: 2026-09-25 15:00
- owner: solo
- if it fails: demo resume into a fresh Claude Code session instead

### 2026-09-25 10:16 PDT — ruling: three of four sponsors is enough for the submission

- Operator: only 3 of 4 sponsors must be used. One may drop if its hinge fails.
- Standing so far: Liquid distiller works locally (LFM2.5-1.2B via Ollama, ~10 s per tick). Tinybird, Nimble and FLUX clients are written and wait for keys.
- H3 dry run: the 1.2B model completes a native tool call but cannot drive a read-then-write task; trying LFM2.5-2.6B next, then other installed hosts.

### 2026-09-25 10:36 PDT — measured: Liquid on this Intel i9 (CPU only, 32 GB): 1.2B distills a 4 KB page in ~10 s; 2.6B tool loop did not finish in 10 min

- LFM2.5-1.2B-Instruct via Ollama: 1640 prompt tokens, 20 completion tokens, 10.0 s and 8.4 s on the fixture; 8-13 s on a live 4 KB page. Usable as the per-tick distiller (H5).
- LFM2.5-2.6B: tool-calling loop on a 3-file task exceeded the 600 s foreground timeout with no completion; killed.
- 1.2B native tool calling works for a single call but not for a read-then-write task.
- Ruling in effect: Liquid stays as the distiller only. Second host for H3 is a fresh headless Claude Code session (`claude -p`) fed by `ledger resume`; OpenCode if it has a provider configured.

### 2026-09-25 10:38 PDT — gate H3 registered

- threshold: a task paused under Claude Code finishes under a second host (hosts/claude_code.sh headless, or hosts/loop.py) from ledger resume alone
- by: 2026-09-25 15:00
- owner: solo
- if it fails: demo resume into a fresh interactive Claude Code session instead

### 2026-09-25 10:38 PDT — gate H3 PASS

- threshold: a task paused under Claude Code finishes under a second host (hosts/claude_code.sh headless, or hosts/loop.py) from ledger resume alone
- measured: dry run 10:36-10:37 PDT in a scratch repo: paused task (write notes/summary.md from 3 files) finished under a fresh headless claude -p session; 24-line brief was its only context; 3 ledger notes written; summary.md 3 lines correct. Liquid 1.2B/2.6B on CPU could not finish the same task.

### 2026-09-25 10:38 PDT — obligation openrouter-key-for-opencode recorded

- hypothesis inhabited: unknown
- consumer: a third host (OpenCode, model openrouter/kimi-k3) and a hosted Liquid endpoint via OpenRouter

### 2026-09-25 10:38 PDT — state at 10:38: H1 and H3 passed; Liquid distiller works locally; Tinybird, Nimble, FLUX wait on keys

- Tests: 16 passing (core, watch, tinybird). `ledger board` renders from the local mirror; `ledger sync` refuses cleanly without a token.
- Two Opus subagents at work: README + .env.example + docs/submission.md + demo/run.sh; sponsor-client tests + `ledger doctor` + loop --dry-run.
- Blocked on the operator for: TINYBIRD_TOKEN + TINYBIRD_HOST (H2), NIMBLE_API_KEY (H4), BFL_API_KEY (H6). Each is one `.env` line; the hinge test for each is ready to run the moment the line exists.
- docs/Ledger-One-Pager.pdf sent to the operator's phone at 10:35; to be regenerated when the sponsor set is final.

### 2026-09-25 10:39 PDT — ruling: use all four sponsors; three is the minimum

- Operator at 10:39: keep all four. A failed hinge still drops that sponsor; nothing else changes.
- Best-use odds as assessed now: Tinybird first (board and endpoint are the product; Tinybird judges on the panel), Liquid second (local per-tick distiller), Nimble if the live watch runs cleanly, BFL unlikely (decoration).

### 2026-09-25 10:41 PDT — tests 43 passing; ledger doctor added; loop --dry-run added

- `ledger doctor` on this repo: 4/8 ok; Liquid answered a 1-token chat locally.
- Next for the second agent: Tinybird Local in Docker to validate datafiles and the endpoint shape before a cloud token exists.

### 2026-09-25 10:41 PDT — hosts/claude_code.sh verified end to end at 10:41 in the scratch repo

- Packaged script, not the inline command: paused task finished 10:40-10:41 PDT; 3 clock-stamped notes; notes/summary.md 3 correct lines; exit 0.
- The headless session's only context was the 24-line brief plus the task line.

### 2026-09-25 10:42 PDT — gate H5 PASS

- threshold: a Liquid model produces a usable 3-line delta from a real page
- measured: scripts/hinges.sh H5 at 10:42: news.ycombinator.com, 4019 raw bytes discarded, LFM2.5-1.2B via Ollama on CPU returned 3 concrete lines in 20.9 s (8-13 s on earlier runs); earlier repeat ticks deduped to 'no change' by the ledger

### 2026-09-25 10:43 PDT — README, .env.example, docs/submission.md, demo/run.sh written; demo rehearsed without the paid step

- Agent measurement, DEMO_SKIP_HOST=1: three live ticks 17.1 s, 9.6 s, 9.4 s; 4019 raw bytes discarded per tick; pause, brief and board rendered.
- Full rehearsal including hosts/claude_code.sh now running in the background.
- README: 136 lines, one section per sponsor so any can be removed cleanly; quotes only ledger-recorded numbers.

### 2026-09-25 10:44 PDT — demo/run.sh rehearsed in full: 10:43:34 to 10:44:37 PDT, exit 0

- 3 live ticks on news.ycombinator.com through the Liquid distiller: 12057 raw bytes discarded, 4377 tokens in, 370 out.
- Pause under Claude Code; the headless second host read the ledger, wrote notes/hn.md, left 3 notes; board rendered from the local mirror.
- Whole demo about 63 s wall clock without a Nimble key (urllib fetch) and without Tinybird (local mirror).

### 2026-09-25 10:45 PDT — ledger stats, docs/demo-script.md and .github/workflows/tests.yml added; 47 tests pass with sockets blocked

### 2026-09-25 10:52 PDT — review pass: 6 bugs fixed with regression tests, 7 items flagged; 57 tests pass

- Fixed: numeric-offset timezones broke heading parsing; tests could leak to a real Tinybird workspace; torn events.jsonl lines crashed four verbs; previous_state dropped delta lines containing 'raw '; FLUX cover link path; tick traceback when the distiller is down.
- Fixed by the orchestrator now: hosts/claude_code.sh exports the source repo's .env so the headless host mirrors events live; `loop` extra adds the anthropic SDK.
- In progress: a `ledger` column so one Tinybird datasource never mixes two ledgers on the board.
- Left as is: tick events carry the topic in the gate field; the cover line sits under the pause entry; concurrent verbs may double-post; no Windows encoding handling.

### 2026-09-25 10:56 PDT — kickoff slide: judges want plan/act/observe/self-correct across a full build cycle; 3+ sponsor tools

- Verbatim in research/event.md. Implication: the resume demo must be a build cycle, not a summary file: spec as a gate, failing test, second host implements, runs tests, iterates, flips the gate on the measured pytest line.
- Both Opus subagents were stopped by the operator at ~10:55; solo from here.

### 2026-09-25 10:59 PDT — ruling: last-minute event change, Tinybird is out, RawTree is in

- Operator at 10:59: do not use Tinybird; use RawTree. The prize page's docs link was rawtree.com/docs all along (research/event.md).
- Gate H2 is re-registered against RawTree. tinybird/ project files and sponsors/tinybird.py become the pattern for sponsors/rawtree.py; the board and sync verbs re-target.
- Key catcher (scripts/catch_key.py) started for Nimble and BFL while the RawTree docs are read.

### 2026-09-25 10:59 PDT — gate H2 registered

- threshold: a RawTree query returns the last hour of ledger events posted by the verbs
- by: 2026-09-25 13:30
- owner: solo
- if it fails: events stay in .ledger/events.jsonl; drop the RawTree pitch line

### 2026-09-25 11:01 PDT — demo/run.sh build-cycle rehearsal passed at 10:59 PDT: 3 failed before, 3 passed after, gate build flipped by the second host

- Second host (headless Claude Code) read tests/test_slug.py, fixed slug.py, ran pytest, ran 'ledger gate pass build --measured "3 passed in 0.01s"', wrote a done note.
- ledger stats on the demo ledger: persisted 3656 bytes over 10 entries; brief 27 lines; discarded 12060 raw bytes over 3 ticks; ratio 3.299.
- This is the plan / act / observe / self-correct cycle the kickoff slide asks for, with no transcript carried across hosts.

### 2026-09-25 11:03 PDT — RawTree swap done: sponsors/rawtree.py, ledger sync/board/doctor re-pointed, tinybird/ removed, docs/rawtree.md written

- RawTree API (from rawtree.com/docs): POST /v1/tables/{table} with a JSON array, POST /v1/query with {sql}; Bearer rt_ key; table created on first insert. No datafiles, no deploy.
- Board and last-hour query scoped by a `ledger` column so two ledgers on one key never mix.
- Hinge H2 now: scripts/hinges.sh H2 syncs the local mirror and queries the last hour back.

### 2026-09-25 11:04 PDT — judging criteria slide: autonomy on real-time web data, idea, technical implementation, 3+ sponsor tools, 3-minute demo

- Verbatim table in research/event.md.
- Mapping: autonomy = the watch loop on live pages through Nimble plus an unattended demo/run.sh (no human between the pause and the passing gate); tool use = RawTree, Nimble, Liquid, FLUX; presentation = demo/run.sh in about a minute plus narration.

### 2026-09-25 11:18 PDT — gate H4 PASS

- threshold: three watch ticks on a real topic through Nimble write three deltas and discard the raw pages
- measured: scripts/hinges.sh H4 at 11:16-11:18 PDT: three ticks on 'AI agents news today' through Nimble search (full_content); 44897 raw bytes discarded per tick, 134691 total; ledger STATUS.md 1093 bytes; tick 1 wrote 3 lines, ticks 2 and 3 wrote 'no change' (same live results within two minutes); 23.6-25.3 s per tick on CPU

### 2026-09-25 11:25 PDT — H6 attempt at 11:25 PDT: BFL key valid, API answered 402 Payment Required; no cover; gate H6 stays open

- The organization has no credits (1 credit = $0.01). Needs a sponsor promo code or a top-up under API → Credits at dashboard.bfl.ai, then `scripts/hinges.sh H6` again.
- scripts/hinges.sh H6 now exits 1 when no cover file lands.

### 2026-09-25 11:44 PDT — gate H2 PASS

- threshold: a RawTree query returns the last hour of ledger events posted by the verbs
- measured: scripts/hinges.sh H2 at 11:44 PDT: ledger sync posted 32 rows to RawTree table ledger_events_mlgraham on the shared hackathon cluster; what_changed(1h) returned 5 rows after casting ts via toString (RawTree infers ts as Dynamic DateTime); ledger board renders from RawTree; SELECT 1 in 0.2 s

### 2026-09-25 11:44 PDT — all three keys in .env (Nimble, BFL, RawTree); RawTree key created through the signed-in UI by Playwright

- RawTree: org tokensand, shared cluster long-horizon-agents-hack, other teams' tables visible in the default database; we write to RAWTREE_TABLE=ledger_events_mlgraham.
- BFL: key valid, no credits yet (402); a background poll retries H6 every 5 minutes.

### 2026-09-25 11:45 PDT — gate H6 PASS

- threshold: a FLUX cover image lands in .ledger/covers on pause
- measured: scripts/hinges.sh H6 at 11:44-11:45 PDT: flux-2-pro-preview returned Ready; two covers landed (344258 and 174133 bytes) in the scratch ledger's covers/, the pause entry links the image; first attempt after the account was funded

### 2026-09-25 11:45 PDT — all six gates passed by 11:45 PDT: H1 core, H2 RawTree, H3 second host, H4 Nimble, H5 Liquid, H6 FLUX

- Measurements are in gates.md. Sponsors in the loop: RawTree (event mirror + two SQL questions), Nimble (live search on every tick), Liquid (local distiller), Black Forest Labs (cover on pause).
- Remaining before submission: full live rehearsal (running), demo/run.sh pause --cover, README measured section, record the video, push public, submit the form.

### 2026-09-25 11:47 PDT — full live rehearsal passed 11:45-11:47 PDT with Nimble, Liquid and RawTree; exit 0

- 3 Nimble ticks: 44897 raw bytes each, 134691 total; tokens in 11702, out 171; ratio 37.592 discarded bytes per persisted byte (3583 persisted, 10 entries).
- 3 failed -> headless host rewrote slugify -> 3 passed -> gate build flipped with the measured line; its events reached RawTree live (host claude-code-headless).
- Board source: RawTree. Next: add --cover to the pause step and rehearse once more.

### 2026-09-25 11:48 PDT — final demo rehearsal with the FLUX cover passed 11:47-11:48 PDT, exit 0; all four sponsors in one run

- Cover 204604 bytes linked from the pause entry; cover event mirrored to RawTree; ratio 35.529 discarded bytes per persisted byte.
- Wrinkle: /tmp/ledger-demo/.ledger is recreated at the same path, so the RawTree scope (by path) shows the previous rehearsal's rows too. Fix: a unique ledger id written at init.

### 2026-09-25 11:49 PDT — ledger identity: .ledger/id written at init (<repo>-<12 hex>); RawTree scope uses it, so a demo ledger recreated at the same path never shows an earlier rehearsal

- This repo's id is pinned to its old path form so the 32 rows already in RawTree still belong to it.
- Tinybird Local container, its 7.23 GB image and the tb CLI removed from the laptop; RawTree needs nothing local.

### 2026-09-25 12:00 PDT — narration pipeline: demo/run.sh writes steps.tsv (DEMO_WAIT, DEMO_PAUSE); scripts/narrate.py speaks the six blocks and mixes them at the step times

- Voices: macOS Samantha (free, offline) or OpenAI TTS through Zero ($0.02 per clip, six clips).
- Dry run on a synthetic 130 s video: clips 7.0, 12.0, 10.9, 13.8, 15.2, 18.7 s; placed without overlap; MP4 with h264 video and AAC audio.
- No service auto-paces a script to a video; this uses the script's own step timestamps instead.

### 2026-09-25 12:03 PDT — timed rehearsal with DEMO_PAUSE=8: 2 min 46 s end to end; all six narration clips fit their steps

- steps.tsv: step 3 at 76.4 s, 4 at 86.5 s, 5 at 108.8 s, 6 at 141.2 s, end 165.9 s.
- Narration placed at 1.1, 8.4, 77.4, 88.6, 109.8, 142.2 s; clips 7.0-18.7 s; no overlaps; ends before the script does.
- Under the 3-minute demo limit with the holds included.

### 2026-09-25 12:30 PDT — narration track built with ElevenLabs through Zero: six blocks, 168.7 s, cues for a paced demo run

- Blocks 7.3, 13.2, 12.7, 16.2, 19.2, 21.7 s; cues 5.1, 13.2, 81.4, 94.9, 113.8, 146.2 s; $0.12 total, one block salvaged from a mis-parsed reply.
- Video plan: scripts/record_run.py timestamps every demo line; scripts/render_video.py renders a terminal-style MP4 and mixes the track. No screen recording needed.

### 2026-09-25 12:35 PDT — demo video generated without a screen recording: demo/ledger-demo.mp4, 170.3 s, 1280x720 h264 + aac, 7.07 MB

- Paced run recorded 12:31-12:34 PDT with every line timestamped (demo/run.jsonl, 128 frames rendered by Playwright); narration re-laid on the run's real step times (blocks at 6.6, 14.8, 92.7, 106.2, 123.2, 147.8 s).
- Step 2's live ticks ran 10 s longer than the rehearsal, so blocks 4 and 5 trail their steps by about 10 s; step 3-5 content stays on screen long enough.

### 2026-09-25 12:36 PDT — final demo video: demo/ledger-demo.mp4 at 12:36 PDT, 6.25 MB, font 15 so the RawTree board fits

- Assets kept for the public repo: ledger-demo.mp4, narration.mp3, narration-cues.tsv, narration-texts.txt, run.jsonl. narration.wav and .track/ are ignored.
- A shareable link for the form: the raw file URL in the public repo after the push, or an upload to YouTube/Drive by the operator.

### 2026-09-25 12:48 PDT — video v2 in progress: docs/video-process.md written; narration gains an opening line at 0.3 s and six bridge lines for the waits

- Operator's rule: audio in the first second; never a silent stretch over a still screen; explain each pause as it happens.
- Bridges anchored N +S seconds into step N; clips cached by text hash so re-wording one line re-buys only that line.
- Chain running: track v2 -> paced run -> re-lay on real step times -> render.

### 2026-09-25 12:55 PDT — video v3: opening line at 0.3 s, six bridges, 'resume' reworded in speech, last frame held until the narration ends

- Paced run v2 at 12:41-12:44 PDT: steps at 0.4, 21.8, 97.0, 106.3, 123.3, 158.4 s; run 175.3 s.
- Longest silence between spoken items 10.4 s (end of the ticks, screen still updating). First cut ran 184.4 s, over the 3-minute limit; closing line shortened and gaps tightened to bring it under.

### 2026-09-25 12:56 PDT — video v3 delivered at 12:56 PDT: 179.5 s, tempo 1.02, 7.46 MB

- Fits the 3-minute limit; voice starts at 0.3 s; longest silence between spoken items 10.4 s, during ticks while the screen updates.
- docs/video-process.md updated with the time-budget and pronunciation lessons.

### 2026-09-25 13:31 PDT — pre-push scrub at 13:31 PDT: earlier private repository no longer named; home paths removed; ledger id relabelled

- CLAUDE.md, plans/design.md (with a 'what changed on the day' note), scripts, the narrative byline and two historical STATUS.md lines now say 'the earlier private repository'. The narrative PDF re-rendered.
- .ledger/id is now long-horizon-hack-2026-main; 23 rows in events.jsonl relabelled. Rows already in RawTree keep the old path id, so this repo's RawTree-scoped board starts fresh from here.
- Playwright and pypdf installed in this repo's .venv (extra 'video'); no script depends on another repository.
- Video v4: '.ledger' spoken as dot-ledger, 'pytest' as pie-test, backticks stripped from speech; 179.5 s.

### 2026-09-25 14:03 PDT — video v5 in progress: step 5 now streams the second host's ledger entries live; renderer clears the screen at each step

- Operator: section 5 was not visible enough at 2:10. Cause: the headless session prints nothing for 30 s and the heading sat at the bottom under the brief.
- hosts/claude_code.sh reads stdin from /dev/null (no warning line); demo/run.sh tails STATUS.md during step 5 and shows the closing words trimmed.

### 2026-09-25 14:14 PDT — video v8 delivered at 14:14 PDT: 161.4 s; scripts/retime_run.py trims waits to 14 s and holds each step for its narration block

- Paced run v3 recorded 14:02-14:05 PDT (183.2 s live); re-timed to 148.8 s; narration 161.4 s; each block starts 1.5 s after its step.
- Step 5 streams the second host's ledger entries live; the renderer clears the screen at each step heading.
- Bridges scale with each step's trimmed length; one bridge text says the waits are trimmed.

### 2026-09-25 14:22 PDT — pushing the whole tree to the public repo at 14:22 PDT on the operator's instruction

- 69 files, about 8 MB; tests 55 passed; secret and path scans clean; .env, the WAV, the TTS cache and derived board files are ignored.
- Video: demo/ledger-demo.mp4 (161.4 s). Submission text: docs/submission.md.

### 2026-09-25 14:23 PDT — pushed: commit bce8cb1 on main at 14:23 PDT; remote head matches local

- First attempt failed with 'remote end hung up' on the 8 MB push; succeeded after raising http.postBuffer.
- Public: https://github.com/mlgraham/long-horizon-hack-2026 ; video: https://github.com/mlgraham/long-horizon-hack-2026/raw/main/demo/ledger-demo.mp4
- Next: the operator submits the form (docs/submission.md) before 16:30.

### 2026-09-25 14:33 PDT — submission form filled at 14:33 PDT, not submitted; the operator presses the button

- Filled: project name, one-sentence description, 1357-char description, team size 1, tools (Liquid AI, Nimble, Black Forest Labs, RawTree, Claude Code: '5 selected'), working URL, video URL, repo URL, screenshot, architecture, setup, lessons, additional links.
- docs/submission.md records the same text. Deadline on the form: 4:30 PM PT.

### 2026-09-25 14:41 PDT — submitted at 14:41 PDT by the operator; the day's build is done

- Public repo, narrated video, one-pager and narrative PDFs, all six gates passed on measurement.
- Sponsors in the loop: RawTree (event mirror + two SQL questions), Nimble (live search on every tick), Liquid (local distiller), Black Forest Labs (cover on pause). Claude Code was both hosts.

### ⏸ PAUSED 2026-09-25 14:41 PDT — resume here

1. Finalist demos at 17:00 PT: run 'source .venv/bin/activate && bash demo/run.sh' live if asked (about 3 min with the holds), or play demo/ledger-demo.mp4; awards at 19:00
2. Find the RawTree and Nimble judges before demos; lead with the July failure story from the narrative PDF and the persist/derived/discarded split
3. Caps: no code changes before demos; nothing else to push
4. Open rulings: the tick events carry the topic in the gate column (left as is); old RawTree rows keep the path-form ledger id (left as is)
5. First file to read: docs/Ledger-One-Pager.pdf, then STATUS.md from 'kickoff slide' onward

Open gates: none · open obligations: openrouter-key-for-opencode · entries: 57
