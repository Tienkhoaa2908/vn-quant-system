#!/usr/bin/env bash
set -euo pipefail

SYSTEM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$SYSTEM_DIR/.." && pwd)"
ROOT_PY="$REPO_ROOT/.venv/Scripts/python.exe"
LOCAL_PY="$SYSTEM_DIR/.venv/Scripts/python.exe"
SERVE_SCRIPT="$SYSTEM_DIR/scripts/serve_web_gitbash.sh"

fail() { echo "FAILED: $*" >&2; exit 2; }

[[ -f "$ROOT_PY" ]] || fail "Không tìm thấy Python 3.12 của repository: $ROOT_PY"
[[ -f "$SERVE_SCRIPT" ]] || fail "Không tìm thấy web runner: $SERVE_SCRIPT"

if [[ ! -f "$LOCAL_PY" ]]; then
  echo "===== TẠO MÔI TRƯỜNG RIÊNG ====="
  "$ROOT_PY" -m venv "$SYSTEM_DIR/.venv"
fi

export PYTHONPATH="$SYSTEM_DIR/src:$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

cd "$SYSTEM_DIR"

echo "===== KIỂM TRA CODE ====="
bash -n "$SERVE_SCRIPT"
"$LOCAL_PY" -m compileall -q src tests
"$LOCAL_PY" -m unittest discover -s tests -v

echo "===== BOOTSTRAP KHO LOCAL ====="
"$LOCAL_PY" -m vn_quant_local.pipeline bootstrap

echo "===== MỞ WEB LOCAL ====="
bash "$SERVE_SCRIPT"
