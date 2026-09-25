"""Every test runs without the operator's .env or shell keys, so no test can post to a real sponsor account."""

import pytest

from ledger import config

SPONSOR_VARIABLES = (
    "RAWTREE_API_KEY", "RAWTREE_DATABASE", "RAWTREE_BASE_URL", "RAWTREE_TABLE", "NIMBLE_API_KEY", "LIQUID_MODEL", "LIQUID_BASE_URL", "LIQUID_API_KEY",
    "BFL_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "LOOP_BACKEND", "LEDGER_DIR",
    "AWS_REGION", "AWS_ACCESS_KEY_ID", "AWS_PROFILE", "BEDROCK_MODEL_ID",
)


@pytest.fixture(autouse=True)
def no_real_keys(monkeypatch):
    monkeypatch.setattr(config, "_loaded", True)  # never read .env from the working directory
    for name in SPONSOR_VARIABLES:
        monkeypatch.delenv(name, raising=False)
