"""The verbs: init, note, gate, obligation, pause, resume, tick, watch, events, sync, board, stats, doctor."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from ledger import brief as brief_module
from ledger import config, events
from ledger.store import Ledger

log = logging.getLogger("ledger")


def _ledger(args: argparse.Namespace) -> Ledger:
    root = Path(args.dir).expanduser().resolve() if args.dir else None
    return Ledger(root)


# ---- verbs ------------------------------------------------------------------


def cmd_init(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    fresh = not ledger.exists()
    ledger.ensure()
    if fresh:
        ledger.append("ledger initialised", f"Host: {config.host_name()}. Files under `{ledger.root}`.")
        events.emit(ledger, "init", text=str(ledger.root))
    print(ledger.root)
    return 0


def cmd_note(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    title = " ".join(args.text).strip()
    body = sys.stdin.read() if args.stdin else (args.body or "")
    if not title:
        log.error("note needs text")
        return 2
    entry = ledger.append(title, body)
    events.emit(ledger, "note", text=title, gate=args.gate or "", model=args.model or "")
    print(f"{entry.stamp} — {entry.title}")
    return 0


def cmd_gate(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    if args.gate_cmd == "list":
        for gate in ledger.gates():
            print(f"{gate['name']}\t{gate.get('status') or 'open'}\t{gate.get('threshold','')}\tby {gate.get('by','')}\t{gate.get('measured','')}")
        return 0
    if args.gate_cmd == "add":
        row = {
            "name": args.name,
            "threshold": args.threshold,
            "by": args.by,
            "owner": args.owner,
            "kill criterion": args.kill,
            "status": "open",
            "measured": "",
        }
        ledger.upsert_gate(row)
        ledger.append(
            f"gate {args.name} registered",
            f"- threshold: {args.threshold}\n- by: {args.by}\n- owner: {args.owner}\n- if it fails: {args.kill}",
        )
        events.emit(ledger, "gate_add", text=args.threshold, gate=args.name)
        print(f"gate {args.name} open, by {args.by}")
        return 0
    gate = ledger.find_gate(args.name)
    if gate is None:
        log.error("no gate named %s", args.name)
        return 1
    if not args.measured:
        log.error("a gate flips only on a measurement: pass --measured")
        return 2
    gate["status"] = args.gate_cmd  # pass or fail
    gate["measured"] = args.measured
    ledger.upsert_gate(gate)
    verdict = "PASS" if args.gate_cmd == "pass" else "FAIL"
    consequence = "" if verdict == "PASS" else f"\n- consequence: {gate.get('kill criterion','')}"
    ledger.append(
        f"gate {args.name} {verdict}",
        f"- threshold: {gate.get('threshold','')}\n- measured: {args.measured}{consequence}",
    )
    events.emit(ledger, f"gate_{args.gate_cmd}", text=args.measured, gate=args.name)
    print(f"gate {args.name} {verdict}: {args.measured}")
    return 0


def cmd_obligation(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    if args.ob_cmd == "list":
        for item in ledger.obligations():
            print(f"{item['name']}\t{item.get('status') or 'open'}\tinhabited={item.get('hypothesis inhabited','')}\tconsumer={item.get('consumer','')}")
        return 0
    if args.ob_cmd == "add":
        row = {
            "name": args.name,
            "hypothesis inhabited": args.hypothesis_inhabited,
            "consumer": args.consumer or "none found",
            "status": "open",
        }
        ledger.upsert_obligation(row)
        ledger.append(
            f"obligation {args.name} recorded",
            f"- hypothesis inhabited: {args.hypothesis_inhabited}\n- consumer: {row['consumer']}",
        )
        events.emit(ledger, "obligation_add", text=f"inhabited={args.hypothesis_inhabited}", gate=args.name)
        print(f"obligation {args.name} open (inhabited: {args.hypothesis_inhabited})")
        return 0
    item = ledger.find_obligation(args.name)
    if item is None:
        log.error("no obligation named %s", args.name)
        return 1
    item["status"] = "closed" if args.ob_cmd == "close" else "open"
    if args.ob_cmd == "close":
        item["hypothesis inhabited"] = "yes"
    ledger.upsert_obligation(item)
    ledger.append(f"obligation {args.name} {item['status']}", f"- how: {args.how or 'not stated'}")
    events.emit(ledger, f"obligation_{args.ob_cmd}", text=args.how or "", gate=args.name)
    print(f"obligation {args.name} {item['status']}")
    return 0


def cmd_pause(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    entries = ledger.entries()
    resume_lines = args.resume or []
    if not resume_lines:
        last = next((entry for entry in reversed(entries) if not entry.paused), None)
        resume_lines = [f"Continue from the last entry: {last.title}" if last else "Start from the plan."]
    open_gates = [gate["name"] for gate in ledger.gates() if (gate.get("status") or "open") == "open"]
    open_obligations = [item["name"] for item in ledger.obligations() if (item.get("status") or "open") == "open"]

    lines = []
    for index, text in enumerate(resume_lines, start=1):
        lines.append(f"{index}. {text}")
    step = len(resume_lines) + 1
    lines.append(f"{step}. Caps: {args.cap or 'none recorded'}")
    step += 1
    rulings = args.ruling or []
    lines.append(f"{step}. Open rulings: " + ("; ".join(rulings) if rulings else "none"))
    step += 1
    lines.append(f"{step}. First file to read: {args.first or 'this ledger, then the plan'}")
    lines.append("")
    lines.append(
        f"Open gates: {', '.join(open_gates) if open_gates else 'none'} · "
        f"open obligations: {', '.join(open_obligations) if open_obligations else 'none'} · "
        f"entries: {len(entries)}"
    )
    if args.note:
        lines.append("")
        lines.append(args.note)
    body = "\n".join(lines)
    entry = ledger.append("resume here", body, paused=True)
    ledger.pause_path.write_text(f"### ⏸ PAUSED {entry.stamp} — resume here\n\n{body}\n")
    events.emit(ledger, "pause", text=resume_lines[0])
    print(f"⏸ {entry.stamp}")

    if args.cover:
        try:
            from sponsors import bfl

            path = bfl.cover_for_pause(ledger, entry)
            if path:
                print(f"cover: {path}")
        except Exception as error:  # noqa: BLE001 - decoration never blocks a pause
            log.warning("cover skipped: %s", error)
    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    text = brief_module.build(ledger, recent=args.recent)
    count = text.count("\n")
    if not args.quiet:
        events.emit(ledger, "resume", text=f"{count} lines", model=args.model or "")
    sys.stdout.write(text)
    if args.check and count > brief_module.MAX_LINES:
        log.error("brief is %d lines; limit is %d", count, brief_module.MAX_LINES)
        return 1
    return 0


def cmd_events(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    for row in events.read_events(ledger, limit=args.limit):
        print(f"{row['ts']}\t{row['kind']}\t{row['host']}\t{row.get('gate','')}\t{row.get('text','')[:80]}")
    return 0


def cmd_tick(args: argparse.Namespace) -> int:
    from ledger import watch

    ledger = _ledger(args)
    try:
        return watch.tick(ledger, topic=args.topic, url=args.url, fixture=args.fixture, distiller=args.distiller)
    except Exception as error:  # noqa: BLE001 - one readable line instead of a traceback (watch does the same)
        log.error("tick failed: %s: %s (ledger doctor shows which component is down)", type(error).__name__, error)
        return 1


def cmd_watch(args: argparse.Namespace) -> int:
    from ledger import watch

    ledger = _ledger(args)
    return watch.loop(
        ledger,
        topic=args.topic,
        url=args.url,
        every=args.every,
        ticks=args.ticks,
        fixture=args.fixture,
        distiller=args.distiller,
    )


def cmd_sync(args: argparse.Namespace) -> int:
    from sponsors import rawtree

    ledger = _ledger(args)
    if not rawtree.configured():
        log.error("RAWTREE_API_KEY is not set: add RAWTREE_API_KEY to .env, then run ledger sync")
        return 1
    try:
        posted = rawtree.sync_local(ledger)
    except Exception as error:  # noqa: BLE001 - report, keep the offset where it stopped
        log.error("sync stopped at line %d: %s", rawtree.read_offset(ledger), error)
        return 1
    print(f"posted {posted} rows to RawTree ({rawtree.read_offset(ledger)} lines mirrored)")
    return 0


def cmd_board(args: argparse.Namespace) -> int:
    from ledger import board as board_module

    ledger = _ledger(args)
    board = board_module.build(ledger, hours=args.hours, recent_hours=args.recent_hours, prefer_remote=not args.local)
    sys.stdout.write(board_module.render_text(board))
    out = Path(args.out).expanduser() if args.out else ledger.root / "board.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(board_module.render_html(board))
    print(f"wrote {out}")
    if args.open:
        import webbrowser

        webbrowser.open(out.resolve().as_uri())
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    from ledger import doctor

    checks = doctor.run_all(_ledger(args))
    for check in checks:
        print(check.line())
    passed = sum(check.ok for check in checks)
    print(f"{passed}/{len(checks)} ok")
    return 0  # a report, not a gate


def cmd_stats(args: argparse.Namespace) -> int:
    import json

    from ledger import stats as stats_module

    ledger = _ledger(args)
    measured = stats_module.measure(ledger)
    if args.json:
        print(json.dumps(measured.as_dict()))
    else:
        sys.stdout.write(stats_module.render_text(measured))
    if args.note:
        line = stats_module.one_line(measured)
        ledger.append(line)
        events.emit(ledger, "stats", text=line)
    return 0


# ---- parser -------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ledger", description=__doc__)
    parser.add_argument("--dir", help="the .ledger directory (default: nearest .ledger or <repo>/.ledger)")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create .ledger/ and the first entry").set_defaults(func=cmd_init)

    note = sub.add_parser("note", help="append a clock-stamped entry")
    note.add_argument("text", nargs="*")
    note.add_argument("--body", help="lines under the heading")
    note.add_argument("--stdin", action="store_true", help="read the body from stdin")
    note.add_argument("--gate", help="gate this note belongs to (event field)")
    note.add_argument("--model", help="model that produced the note (event field)")
    note.set_defaults(func=cmd_note)

    gate = sub.add_parser("gate", help="pre-registered hinges")
    gate_sub = gate.add_subparsers(dest="gate_cmd", required=True)
    gate_add = gate_sub.add_parser("add")
    gate_add.add_argument("name")
    gate_add.add_argument("--threshold", required=True)
    gate_add.add_argument("--by", required=True, help="the date or time the gate is decided")
    gate_add.add_argument("--owner", required=True)
    gate_add.add_argument("--kill", required=True, help="what a failure implies")
    for verdict in ("pass", "fail"):
        flip = gate_sub.add_parser(verdict)
        flip.add_argument("name")
        flip.add_argument("--measured", required=True)
    gate_sub.add_parser("list")
    gate.set_defaults(func=cmd_gate)

    obligation = sub.add_parser("obligation", help="named-but-unproved claims")
    ob_sub = obligation.add_subparsers(dest="ob_cmd", required=True)
    ob_add = ob_sub.add_parser("add")
    ob_add.add_argument("name")
    ob_add.add_argument("--hypothesis-inhabited", choices=["yes", "no", "unknown"], required=True)
    ob_add.add_argument("--consumer", help="what fails without it")
    for change in ("close", "reopen"):
        flip = ob_sub.add_parser(change)
        flip.add_argument("name")
        flip.add_argument("--how")
    ob_sub.add_parser("list")
    obligation.set_defaults(func=cmd_obligation)

    pause = sub.add_parser("pause", help="write the ⏸ entry a fresh session resumes from")
    pause.add_argument("--resume", action="append", help="what to resume (repeatable, numbered)")
    pause.add_argument("--cap", help="caps in force, e.g. 'subagents ≤ 2'")
    pause.add_argument("--ruling", action="append", help="an open ruling not yet acted on (repeatable)")
    pause.add_argument("--first", help="the first file to read")
    pause.add_argument("--note", help="free text under the list")
    pause.add_argument("--cover", action="store_true", help="also render a FLUX cover image")
    pause.set_defaults(func=cmd_pause)

    resume = sub.add_parser("resume", help="print the two-minute brief")
    resume.add_argument("--recent", type=int, default=5)
    resume.add_argument("--check", action="store_true", help=f"exit 1 if over {brief_module.MAX_LINES} lines")
    resume.add_argument("--quiet", action="store_true", help="do not post a resume event")
    resume.add_argument("--model", help="model that will consume the brief (event field)")
    resume.set_defaults(func=cmd_resume)

    ev = sub.add_parser("events", help="print the local event mirror")
    ev.add_argument("--limit", type=int, default=20)
    ev.set_defaults(func=cmd_events)

    sub.add_parser("sync", help="post local events not yet mirrored to RawTree").set_defaults(func=cmd_sync)

    board = sub.add_parser("board", help="print the board and write .ledger/board.html")
    board.add_argument("--hours", type=int, default=24, help="window for the per-kind table (default 24)")
    board.add_argument("--recent-hours", type=int, default=1, help="window for 'what changed' (default 1)")
    board.add_argument("--out", help="HTML path (default .ledger/board.html)")
    board.add_argument("--open", action="store_true", help="open the HTML page in a browser")
    board.add_argument("--local", action="store_true", help="ignore RawTree and read the local mirror")
    board.set_defaults(func=cmd_board)

    stats = sub.add_parser("stats", help="persisted / derived / discarded bytes for this ledger")
    stats.add_argument("--json", action="store_true", help="one JSON object instead of text")
    stats.add_argument("--note", action="store_true", help="also append a ledger entry and emit a stats event")
    stats.set_defaults(func=cmd_stats)

    sub.add_parser("doctor", help="one line per component: ledger files, sponsor keys, binaries").set_defaults(func=cmd_doctor)

    for name, func in (("tick", cmd_tick), ("watch", cmd_watch)):
        loop = sub.add_parser(name, help="fetch → distill → note the delta → discard the raw page")
        loop.add_argument("topic")
        loop.add_argument("--url", help="page to fetch (default: a Nimble search on the topic)")
        loop.add_argument("--fixture", help="local file to read instead of fetching")
        loop.add_argument("--distiller", choices=["liquid", "bedrock", "none"], default=None)
        if name == "watch":
            loop.add_argument("--every", default="10m", help="e.g. 30s, 10m")
            loop.add_argument("--ticks", type=int, default=0, help="stop after N ticks (0 = forever)")
        loop.set_defaults(func=func)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
