"""Configuration from the environment and a gitignored .env, nothing else."""

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

_loaded = False


def load_dotenv(start: Path | None = None) -> None:
    """Read KEY=VALUE lines from the nearest .env walking up from start. Existing env wins."""
    global _loaded
    if _loaded:
        return
    _loaded = True
    here = (start or Path.cwd()).resolve()
    for directory in [here, *here.parents]:
        candidate = directory / ".env"
        if candidate.is_file():
            for raw in candidate.read_text().splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ.setdefault(key, value)
            log.debug("loaded %s", candidate)
            return


def get(name: str, default: str | None = None) -> str | None:
    load_dotenv()
    return os.environ.get(name, default)


def host_name() -> str:
    """Which host is running the tool. Explicit LEDGER_HOST wins; otherwise sniff."""
    explicit = get("LEDGER_HOST")
    if explicit:
        return explicit
    if os.environ.get("CLAUDECODE") or os.environ.get("CLAUDE_CODE_ENTRYPOINT"):
        return "claude-code"
    if os.environ.get("OPENCODE"):
        return "opencode"
    if os.environ.get("CODEX_SANDBOX") or os.environ.get("CODEX"):
        return "codex"
    return "shell"
