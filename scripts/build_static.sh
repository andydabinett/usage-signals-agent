#!/usr/bin/env bash
# Build the read-only static site from the FROZEN snapshot. Offline: no network, no API key, no LLM calls.
#   site/index.html       live (real) view of snapshot/warehouse.duckdb
#   site/demo/index.html  labeled SYNTHETIC demo scenario (one synthetic post on samsara)
set -euo pipefail
cd "$(dirname "$0")/.."
env -u OPENROUTER_API_KEY -u CONTACT_EMAIL -u SEC_USER_AGENT bash -c '
  rm -rf site && mkdir -p site/demo
  uv run signals web --db snapshot/warehouse.duckdb --out site/index.html
  uv run signals demo samsara --db snapshot/warehouse.duckdb --out data/demo-static.duckdb
  uv run signals web --db data/demo-static.duckdb --out site/demo/index.html
'
if grep -q SYNTHETIC site/index.html; then echo "live page contains SYNTHETIC" >&2; exit 1; fi
grep -q SYNTHETIC site/demo/index.html || { echo "demo page missing SYNTHETIC banner" >&2; exit 1; }
if P='sk''-or-'; grep -rIl -E "${P}[A-Za-z0-9]|@gmail\.com" site; then echo "secret/email in site" >&2; exit 1; fi
echo "built site/ (live at /, SYNTHETIC demo at /demo)"
