#!/usr/bin/env bash
set -euo pipefail
SYSTEM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$SYSTEM_DIR/.." && pwd)"
PY="$SYSTEM_DIR/.venv/Scripts/python.exe"
[[ -f "$PY" ]] || { echo "Chưa setup. Chạy scripts/setup_and_run_gitbash.sh trước." >&2; exit 2; }
export PYTHONPATH="$SYSTEM_DIR/src:$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
cd "$SYSTEM_DIR"
cmd.exe /c start "" "http://127.0.0.1:8787"
"$PY" -m vn_quant_local.webapp
