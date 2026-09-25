"""RawTree: the event mirror. Every verb's event lands in one table; the board and the judges' questions are SQL.

RawTree takes events as they are (a table is created on first insert) and answers read-only ClickHouse SQL.
API: POST /v1/tables/{table} to insert, POST /v1/query {"sql": ...} to read. Bearer key `rt_...`.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from pathlib import Path

from ledger import config

log = logging.getLogger(__name__)

DEFAULT_TABLE = "ledger_events"
BASE = "https://api.rawtree.com"
COLUMNS = "ts, kind, host, model, gate, text, tokens_in, tokens_out, bytes_discarded, ledger"


def configured() -> bool:
    return bool(config.get("RAWTREE_API_KEY"))


def table() -> str:
    """The event table. Set RAWTREE_TABLE on a shared cluster so teams never share a table."""
    return config.get("RAWTREE_TABLE") or DEFAULT_TABLE


def base_url() -> str:
    return (config.get("RAWTREE_BASE_URL") or BASE).rstrip("/")


def _headers() -> dict:
    key = config.get("RAWTREE_API_KEY")
    if not key:
        raise RuntimeError("RAWTREE_API_KEY not set")
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "accept": "application/json"}
    database = config.get("RAWTREE_DATABASE")
    if database:
        headers["x-rawtree-database"] = database
    return headers


def _call(method: str, path: str, body: object | None = None, timeout: float = 15.0) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    request = urllib.request.Request(f"{base_url()}{path}", data=data, method=method, headers=_headers())
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode() or "{}"
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")[:500]
        raise RuntimeError(f"rawtree {method} {path} -> {error.code}: {detail}") from error
    return json.loads(text)


def post_events(rows: list[dict], timeout: float = 15.0) -> int:
    """Insert rows as they are. Returns the inserted count RawTree reports."""
    if not rows:
        return 0
    payload = _call("POST", f"/v1/tables/{table()}", rows, timeout=timeout)
    inserted = payload.get("inserted")
    log.debug("rawtree inserted %s", inserted)
    return int(inserted) if inserted is not None else len(rows)


def query(sql: str, timeout: float = 30.0) -> list[dict]:
    """Read-only SQL. Returns the data rows of RawTree's JSON response."""
    return _call("POST", "/v1/query", {"sql": sql}, timeout=timeout).get("data", [])


def health(timeout: float = 5.0) -> bool:
    try:
        with urllib.request.urlopen(f"{base_url()}/health", timeout=timeout) as response:
            return json.loads(response.read().decode()).get("status") == "ok"
    except (urllib.error.URLError, OSError, ValueError):
        return False


# ---- the local mirror -> RawTree, idempotent -------------------------------------


def _offset_path(ledger) -> Path:
    return ledger.root / ".rawtree_offset"


def read_offset(ledger) -> int:
    try:
        return int(_offset_path(ledger).read_text().strip() or 0)
    except (FileNotFoundError, ValueError):
        return 0


def sync_local(ledger, batch: int = 500, timeout: float = 15.0) -> int:
    """Post every events.jsonl row not yet mirrored. The offset file advances only after RawTree accepts a batch."""
    if not ledger.events_path.exists():
        return 0
    lines = ledger.events_path.read_text().splitlines()
    offset = read_offset(ledger)
    posted = 0
    while offset < len(lines):
        chunk = lines[offset : offset + batch]
        rows = []
        for line in chunk:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                log.warning("skipping a torn events.jsonl line at offset %d", offset)
                continue
            row.setdefault("ledger", ledger.identity())
            rows.append(row)
        post_events(rows, timeout=timeout)
        offset += len(chunk)
        posted += len(rows)
        _offset_path(ledger).write_text(f"{offset}\n")
    return posted


# ---- the two questions the board asks ---------------------------------------------


def _scope(ledger_root: str | None) -> str:
    return f" AND ledger = '{ledger_root}'" if ledger_root else ""


def what_changed(hours: int = 1, limit: int = 200, ledger_root: str | None = None) -> list[dict]:
    sql = (
        f"SELECT {COLUMNS} FROM {table()} "
        f"WHERE parseDateTimeBestEffort(toString(ts)) >= now() - INTERVAL {int(hours)} HOUR{_scope(ledger_root)} "
        f"ORDER BY ts DESC LIMIT {int(limit)}"
    )
    return query(sql)


def board(hours: int = 24, ledger_root: str | None = None) -> list[dict]:
    sql = (
        f"SELECT kind, host, count() AS events, sum(bytes_discarded) AS bytes_discarded, "
        f"sum(tokens_in) AS tokens_in, sum(tokens_out) AS tokens_out, max(ts) AS last_ts FROM {table()} "
        f"WHERE parseDateTimeBestEffort(toString(ts)) >= now() - INTERVAL {int(hours)} HOUR{_scope(ledger_root)} "
        f"GROUP BY kind, host ORDER BY last_ts DESC"
    )
    return query(sql)
