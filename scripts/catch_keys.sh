#!/usr/bin/env bash
# Walk the sponsor dashboards one at a time and catch each key from the clipboard. See catch_key.py.
cd "$(dirname "$0")/.."
PY=.venv/bin/python
$PY scripts/catch_key.py RAWTREE_API_KEY "https://rawtree.com/login" "$@"
$PY scripts/catch_key.py NIMBLE_API_KEY "https://online.nimbleway.com/" "$@"
$PY scripts/catch_key.py BFL_API_KEY "https://dashboard.bfl.ai/" "$@"
