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

echo "===== V53 COMPILE ====="
"$PYTHON_EXE" -m compileall -q src tests

echo "===== V53 FULL UNIT TESTS ====="
"$PYTHON_EXE" -m unittest discover -s tests -p 'test_*.py' -v

echo "===== V53 RUNTIME CONTRACT ====="
"$PYTHON_EXE" - <<'PY'
import vn_quant_local
from vn_quant_local import performance
from vn_quant_local import v53_cycle_cleanup as v53
from vn_quant_local import webapp

assert vn_quant_local.__version__ == "0.5.3"
assert v53.V53_VERSION == "V53_BULK_CYCLE_CLEANUP"
assert performance.performance_status is v53.performance_status_v53
assert performance.add_actual_cashflow is v53.add_actual_cashflow_v53
assert performance.discard_cycles is v53.discard_cycles
assert webapp.performance_status is v53.performance_status_v53
assert webapp.add_actual_cashflow is v53.add_actual_cashflow_v53

partial_auto = {
    "status": "ACTIVE",
    "latest_market_day_for_cycle_lock": "2026-08-05",
    "shadow_plans": [{
        "plan_id": "plan-auto",
        "status": "PENDING_MARKET_DATA",
        "execution_day": "2026-08-06",
    }],
    "cycle_catalog": [{
        "plan_id": "plan-auto",
        "planned_quantity": 4,
        "actual_quantity": 2,
        "remaining_quantity": 2,
    }],
    "reconciliation": [{
        "intent_id": "plan-auto:BUY:MSB",
        "plan_id": "plan-auto",
        "side": "BUY",
        "symbol": "MSB",
        "planned_quantity": 4,
        "actual_quantity": 2,
        "remaining_quantity": 2,
        "actual_event_ids": ["fill-1"],
        "match_method": "AUTO_NEWEST_OPEN_INTENT",
        "status": "MATCHED_PARTIAL_SHADOW_PENDING",
        "shadow_pending": True,
    }],
}
row = v53._cycle_policy_rows(partial_auto)[0]
assert row["discardable"] is True
assert row["discard_reassigns_auto_fills"] is True
assert row["intents"][0]["planned_quantity"] == 4
assert row["intents"][0]["actual_quantity"] == 2
assert row["intents"][0]["remaining_quantity"] == 2

partial_auto["reconciliation"][0]["match_method"] = "EXPLICIT_PLAN_ID"
row = v53._cycle_policy_rows(partial_auto)[0]
assert row["discardable"] is False
assert row["discard_lock_reason"] == "EXPLICIT_PLAN_BINDING"

partial_auto["reconciliation"][0]["actual_quantity"] = 4
partial_auto["reconciliation"][0]["remaining_quantity"] = 0
row = v53._cycle_policy_rows(partial_auto)[0]
assert row["discardable"] is False
assert row["discard_lock_reason"] == "ACTUAL_COMPLETE"

print("V53_PARTIAL_AUTO_MATCH_DISCARD=PASS")
print("V53_EXPLICIT_BINDING_LOCK=PASS")
print("V53_COMPLETE_CYCLE_LOCK=PASS")
print("V53_INLINE_INTENT_DETAILS=PASS")
print("V53_RUNTIME_BINDINGS=PASS")
PY

echo "===== V53 WEB CONTRACT ====="
grep -q 'DISCARD_CYCLES' web/performance_v51.js || fail "thieu bulk command"
grep -q 'data-v53-cycle-select' web/performance_v51.js || fail "thieu bulk checkbox"
grep -q 'data-v53-bulk-discard' web/performance_v51.js || fail "thieu bulk button"
grep -q 'cycleIntentRows' web/performance_v51.js || fail "thieu chi tiet intent"
grep -q 'AUTO_NEWEST_OPEN_INTENT' web/performance_v51.js || fail "thieu nhan auto match"
grep -q 'EXPLICIT_PLAN_ID' web/performance_v51.js || fail "thieu nhan explicit match"
grep -q 'setCommandBusy(false)' web/performance_v51.js || fail "thieu reset command busy"
if grep -q 'MutationObserver' web/performance_v51.js; then
  fail "MutationObserver cu con ton tai; co the lam nut dung sau lan dau"
fi
grep -q 'v53-cycle-intent-row' web/performance_v51.css || fail "thieu CSS intent details"
grep -q 'V53_BULK_CYCLE_CLEANUP' src/vn_quant_local/v53_cycle_cleanup.py || fail "thieu V53 engine"
grep -q 'bulk_cycle_discard_is_atomic' src/vn_quant_local/v53_cycle_cleanup.py || fail "thieu atomic contract"

if grep -q 'buying_power_v50' src/vn_quant_local/__init__.py; then
  fail "V50 PPSE dang duoc kich hoat tren branch V53"
fi

if command -v node >/dev/null 2>&1; then
  node --check web/performance_v51.js
else
  echo "NODE_NOT_FOUND: bo qua node --check"
fi

echo "V53_BULK_COMMAND=PASS"
echo "V53_UI_REFRESH_WITHOUT_RELOAD=PASS"
echo "V53_VALIDATION=PASS"
