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

echo "===== V46 COMPILE ====="
"$PYTHON_EXE" -m compileall -q src tests

echo "===== V46 UNIT TESTS ====="
"$PYTHON_EXE" -m unittest discover -s tests -p 'test_*.py' -v

echo "===== V46 DATABASE MIGRATION SMOKE ====="
"$PYTHON_EXE" - <<'PY'
from datetime import date
import sqlite3
from vn_quant_local import performance
from vn_quant_local.capital_plan import _ensure_schema as ensure_capital_schema
from vn_quant_local.performance import _ensure_schema, _event_hash, _week_key, _xirr
from vn_quant_local.performance_safety import (
    append_unique_event,
    safe_xirr,
    select_plans_after_opening,
)

db = sqlite3.connect(":memory:")
_ensure_schema(db)
ensure_capital_schema(db)
required = {
    "performance_config",
    "performance_opening_positions",
    "performance_events",
    "performance_shadow_plans",
    "performance_shadow_trades",
    "performance_nav",
    "capital_plans",
}
tables = {
    row[0]
    for row in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
}
missing = sorted(required - tables)
if missing:
    raise SystemExit("MISSING_TABLES=" + ",".join(missing))
assert _week_key("2026-08-04T09:00:00+07:00") == "2026-W32"
assert _event_hash({"a": 1, "b": 2}) == _event_hash({"b": 2, "a": 1})
assert performance._xirr is safe_xirr
assert performance._append_event is append_unique_event
assert performance._sync_shadow_plan_selection is select_plans_after_opening
assert _xirr([
    (date(2026, 8, 4), -100.0),
    (date(2026, 8, 4), 100.0),
]) is None
print("V46_SCHEMA=PASS")
print("V46_EVENT_LEDGER=PASS")
print("V46_EVENT_CYCLE_SELECTION=PASS")
print("V46_XIRR_GUARD=PASS")
PY

echo "===== V46 WEB ASSETS ====="
grep -q 'READ-ONLY MARKET OVERVIEW' web/sell_review_v44_5.js || fail "thieu tab thi truong V46"
grep -q 'EVENT_DRIVEN_CAPITAL_CYCLE' src/vn_quant_local/capital_plan.py || fail "thieu event planner V46"
grep -q '/api/market-overview' src/vn_quant_local/webapp.py || fail "backend thieu market overview"
grep -q '/api/actions/plan' src/vn_quant_local/webapp.py || fail "backend thieu plan endpoint"

if command -v node >/dev/null 2>&1; then
  node --check web/app.js
  node --check web/sell_review_v44_5.js
  node --check web/performance_v45.js
else
  echo "NODE_NOT_FOUND: bo qua node --check"
fi

echo "===== V46 IMPORT SMOKE ====="
"$PYTHON_EXE" - <<'PY'
from vn_quant_local.capital_plan import PLANNING_MODE
from vn_quant_local.market_overview import market_overview
from vn_quant_local.performance import performance_status
from vn_quant_local.webapp import Handler

status = performance_status()
assert status["status"] in {"NOT_STARTED", "ACTIVE"}
assert PLANNING_MODE == "EVENT_DRIVEN_CAPITAL_CYCLE"
assert Handler.server_version == "VNQuantLocal/1.7"
assert callable(market_overview)
print("V46_IMPORT=PASS")
print("V46_CURRENT_STATUS=" + status["status"])
PY

echo "V46_VALIDATION=PASS"
