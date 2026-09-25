"""The second host. A bare loop: read the brief, act on files through tools, write the ledger, stop.

    python -m hosts.loop [--backend ollama|anthropic|bedrock] [--max-turns N] [--dir .ledger] [--dry-run] [TASK]

The model never sees a transcript from the first host. Its whole context is `ledger resume` plus the task.
Every backend uses native tool calling, so a 1.2B-parameter local model and a frontier API model drive the
same five tools.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import urllib.request
from pathlib import Path

from ledger import brief as brief_module
from ledger import config, events
from ledger.store import Ledger

log = logging.getLogger("hosts.loop")

SYSTEM_TAIL = """
You are a different program resuming the work above from the ledger alone. You have no other memory of it.
Act only by calling tools. Read every file the task names before writing. Call done once the task's file is
written; done is the last call. Keep tool arguments complete: write_file needs path and content.
""".strip()

TOOLS: list[dict] = [
    {"name": "list_files", "description": "List a directory relative to the repo root.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "read_file", "description": "Read a text file relative to the repo root.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Create or overwrite a text file relative to the repo root.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                      "required": ["path", "content"]}},
    {"name": "note", "description": "Append one clock-stamped line to the ledger after a real step.",
     "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
    {"name": "done", "description": "Stop. Call this once, after the task's file is written.",
     "input_schema": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}},
]
TOOL_NAMES = {tool["name"] for tool in TOOLS}


# ---- tools ------------------------------------------------------------------------


def safe_path(root: Path, relative: str) -> Path:
    target = (root / relative).resolve()
    if root.resolve() not in target.parents and target != root.resolve():
        raise ValueError(f"path escapes the repo: {relative}")
    return target


def run_tool(ledger: Ledger, name: str, args: dict) -> str:
    root = ledger.root.parent
    if name == "list_files":
        target = safe_path(root, str(args.get("path") or "."))
        names = sorted(item.name + ("/" if item.is_dir() else "") for item in target.iterdir() if not item.name.startswith("."))
        return "\n".join(names) or "(empty)"
    if name == "read_file":
        return safe_path(root, str(args["path"])).read_text()[:12000]
    if name == "write_file":
        content = str(args.get("content", ""))
        target = safe_path(root, str(args["path"]))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return f"wrote {len(content)} chars to {args['path']}. If the task is complete, call done."
    if name == "note":
        entry = ledger.append(str(args.get("text", "")).strip() or "(empty note)", "- written by hosts/loop.py")
        events.emit(ledger, "note", text=entry.title, model=os.environ.get("LEDGER_MODEL", ""))
        return f"noted at {entry.stamp}"
    raise ValueError(f"unknown tool {name}")


# ---- backends -------------------------------------------------------------------
# Each backend keeps its own message list and exposes:
#   step() -> (calls: list[(call_id, name, args)], text, usage)
#   feed(results: list[(call_id, name, text)])


class OllamaBackend:
    """Liquid LFM2.5 through Ollama's native chat API with tools. No key, no cloud."""

    def __init__(self, system: str, task: str):
        from sponsors import liquid

        self.model = liquid.model_name()
        self.base = liquid.base_url().removesuffix("/v1")
        self.messages = [{"role": "system", "content": system}, {"role": "user", "content": task}]
        self.tools = [{"type": "function", "function": {"name": tool["name"], "description": tool["description"],
                                                         "parameters": tool["input_schema"]}} for tool in TOOLS]

    def step(self):
        body = json.dumps({"model": self.model, "messages": self.messages, "tools": self.tools, "stream": False,
                           "options": {"temperature": 0.0, "num_ctx": 8192}}).encode()
        request = urllib.request.Request(f"{self.base}/api/chat", data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=300) as response:
            payload = json.loads(response.read().decode())
        message = payload["message"]
        self.messages.append(message)
        calls = [(str(index), call["function"]["name"], call["function"].get("arguments") or {})
                 for index, call in enumerate(message.get("tool_calls") or [])]
        usage = {"prompt_tokens": payload.get("prompt_eval_count", 0), "completion_tokens": payload.get("eval_count", 0)}
        return calls, message.get("content", ""), usage

    def feed(self, results):
        for _call_id, name, text in results:
            self.messages.append({"role": "tool", "tool_name": name, "content": text})

    def nudge(self, text: str):
        self.messages.append({"role": "user", "content": text})


class AnthropicBackend:
    """Claude through the Anthropic SDK (or Bedrock Mantle when backend=bedrock)."""

    def __init__(self, system: str, task: str, bedrock: bool = False):
        import anthropic

        if bedrock:
            self.client = anthropic.AnthropicBedrockMantle(aws_region=config.get("AWS_REGION"))
            self.model = config.get("BEDROCK_MODEL_ID") or "anthropic.claude-opus-5"
        else:
            self.client = anthropic.Anthropic()
            self.model = config.get("ANTHROPIC_MODEL") or "claude-opus-5"
        self.system = system
        self.messages = [{"role": "user", "content": task}]

    def step(self):
        response = self.client.messages.create(
            model=self.model, max_tokens=8000, system=self.system, messages=self.messages, tools=TOOLS,
        )
        self.messages.append({"role": "assistant", "content": response.content})
        calls = [(block.id, block.name, dict(block.input)) for block in response.content if block.type == "tool_use"]
        text = "".join(block.text for block in response.content if block.type == "text")
        usage = {"prompt_tokens": response.usage.input_tokens, "completion_tokens": response.usage.output_tokens}
        return calls, text, usage

    def feed(self, results):
        self.messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": call_id, "content": text} for call_id, _name, text in results
        ]})

    def nudge(self, text: str):
        self.messages.append({"role": "user", "content": text})


def make_backend(name: str, system: str, task: str):
    if name == "ollama":
        return OllamaBackend(system, task)
    return AnthropicBackend(system, task, bedrock=(name == "bedrock"))


# ---- the loop -------------------------------------------------------------------


def resolve_task(ledger: Ledger, task: str | None) -> str:
    """The explicit task, else step 1 of the last pause entry."""
    if task:
        return task
    pause = ledger.last_pause()
    first = next((line for line in (pause.body.splitlines() if pause else []) if line.startswith("1. ")), "")
    return first[3:] or "Continue the work described in the ledger."


def build_system(ledger: Ledger) -> str:
    """The whole context the second host gets: the resume brief (without its rules section) plus the tail."""
    brief_text = brief_module.build(ledger).split("\n## Rules")[0].rstrip()
    return brief_text + "\n\n" + SYSTEM_TAIL


def run(ledger: Ledger, task: str | None, backend_name: str, max_turns: int) -> int:
    task = resolve_task(ledger, task)
    system = build_system(ledger)
    backend = make_backend(backend_name, system, f"Task: {task}")
    os.environ["LEDGER_HOST"] = f"loop-{backend_name}"
    os.environ["LEDGER_MODEL"] = backend.model

    ledger.append(f"resumed under {os.environ['LEDGER_HOST']}", f"- model: {backend.model}\n- task: {task}")
    events.emit(ledger, "resume", text=task, model=backend.model)

    tokens_in = tokens_out = 0
    writes = 0
    for turn in range(1, max_turns + 1):
        calls, text, usage = backend.step()
        tokens_in += int(usage.get("prompt_tokens", 0) or 0)
        tokens_out += int(usage.get("completion_tokens", 0) or 0)
        events.emit(ledger, "turn", text="; ".join(f"{name} {json.dumps(args)[:120]}" for _id, name, args in calls) or text[:200],
                    model=backend.model, tokens_in=int(usage.get("prompt_tokens", 0) or 0),
                    tokens_out=int(usage.get("completion_tokens", 0) or 0))
        if not calls:
            log.warning("turn %d: no tool call; text=%r", turn, text[:120])
            backend.nudge("Use a tool. Call done only when the task's file is written.")
            continue
        results = []
        for call_id, name, args in calls:
            print(f"[{turn}] {name} {json.dumps(args)[:110]}")
            if name == "done":
                if not writes:
                    results.append((call_id, name, "Nothing has been written yet. Use write_file first, then done."))
                    continue
                summary = str(args.get("summary", "")).strip() or "done"
                ledger.append(f"done under {os.environ['LEDGER_HOST']}: {summary[:90]}",
                              f"- {summary}\n- turns: {turn}; tokens in {tokens_in}, out {tokens_out}")
                events.emit(ledger, "done", text=summary, model=backend.model, tokens_in=tokens_in, tokens_out=tokens_out)
                print(f"done after {turn} turns: {summary}")
                return 0
            if name not in TOOL_NAMES:
                results.append((call_id, name, f"unknown tool {name}; use one of {sorted(TOOL_NAMES)}"))
                continue
            try:
                output = run_tool(ledger, name, args)
                writes += name == "write_file"
            except Exception as error:  # noqa: BLE001 - the model gets the error back and continues
                output = f"error: {error}"
            results.append((call_id, name, output[:6000]))
        backend.feed(results)
    ledger.append(f"stopped under {os.environ['LEDGER_HOST']}: turn cap {max_turns} reached",
                  f"- tokens in {tokens_in}, out {tokens_out}")
    events.emit(ledger, "stopped", text="turn cap", model=backend.model, tokens_in=tokens_in, tokens_out=tokens_out)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hosts.loop", description=__doc__)
    parser.add_argument("task", nargs="?")
    parser.add_argument("--backend", choices=["ollama", "anthropic", "bedrock"], default=config.get("LOOP_BACKEND") or "ollama")
    parser.add_argument("--max-turns", type=int, default=12)
    parser.add_argument("--dir")
    parser.add_argument("--dry-run", action="store_true", help="print the system prompt and task, call no backend")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING, stream=sys.stderr)
    ledger = Ledger(Path(args.dir).expanduser().resolve() if args.dir else None)
    if args.dry_run:
        print(build_system(ledger))
        print(f"\n---\nTask: {resolve_task(ledger, args.task)}")
        return 0
    return run(ledger, args.task, args.backend, args.max_turns)


if __name__ == "__main__":
    sys.exit(main())
