#!/usr/bin/env bash
set -euo pipefail

SYSTEM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="$(cd "$SYSTEM_DIR/.." && pwd)"
PYTHON_EXE="$SYSTEM_DIR/.venv/Scripts/python.exe"

fail() {
  echo "FAILED: $*" >&2
  exit 2
}

[[ -f "$PYTHON_EXE" ]] || fail "khong tim thay $PYTHON_EXE"

export PYTHONPATH="$SYSTEM_DIR/src:$REPO_DIR/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

cd "$SYSTEM_DIR"

echo "===== V45 COMPILE ====="
"$PYTHON_EXE" -m compileall -q src tests

echo "===== V45 UNIT TESTS ====="
"$PYTHON_EXE" -m unittest discover -s tests -p 'test_*.py' -v

echo "===== V45 DATABASE MIGRATION SMOKE ====="
"$PYTHON_EXE" - <<'PY'
import sqlite3
from vn_quant_local.performance import _ensure_schema, _event_hash, _week_key

db = sqlite3.connect(":memory:")
_ensure_schema(db)
_ensure_schema(db)
tables = {
    row[0]
    for row in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
}
required = {
    "performance_config",
    "performance_opening_positions",
    "performance_events",
    "performance_shadow_plans",
    "performance_shadow_trades",
    "performance_nav",
}
missing = sorted(required - tables)
if missing:
    raise SystemExit("MISSING_TABLES=" + ",".join(missing))
assert _week_key("2026-08-04T09:00:00+07:00") == "2026-W32"
assert _event_hash({"a": 1, "b": 2}) == _event_hash({"b": 2, "a": 1})
print("V45_SCHEMA=PASS")
print("V45_EVENT_LEDGER=PASS")
print("V45_WEEK_SELECTION=PASS")
PY

echo "===== V45 WEB ASSETS ====="
grep -q 'performance_v45.css' web/index.html || fail "index thieu CSS V45"
grep -q 'performance_v45.js' web/index.html || fail "index thieu JavaScript V45"
grep -q '/api/performance' src/vn_quant_local/webapp.py || fail "backend thieu API V45"

if command -v node >/dev/null 2>&1; then
  node --check web/app.js
  node --check web/sell_review_v44_5.js
  node --check web/performance_v45.js
else
  echo "NODE_NOT_FOUND: bo qua node --check; Python/web smoke van chay"
fi

echo "===== V45 IMPORT SMOKE ====="
"$PYTHON_EXE" - <<'PY'
from vn_quant_local.performance import (
    OBSERVATORY_VERSION,
    performance_status,
)
from vn_quant_local.webapp import Handler

status = performance_status()
assert status["status"] in {"NOT_STARTED", "ACTIVE"}
assert OBSERVATORY_VERSION == "V45_LIVE_PERFORMANCE_OBSERVATORY"
assert Handler.server_version == "VNQuantLocal/1.6"
print("V45_IMPORT=PASS")
print("V45_CURRENT_STATUS=" + status["status"])
PY

echo "V45_VALIDATION=PASS"
