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

echo "===== V54 COMPILE ====="
"$PYTHON_EXE" -m compileall -q src tests

echo "===== V54 FULL UNIT TESTS ====="
"$PYTHON_EXE" -m unittest discover -s tests -p 'test_*.py' -v

echo "===== V54 RUNTIME CONTRACT ====="
"$PYTHON_EXE" - <<'PY'
import json
import vn_quant_local
from vn_quant_local import performance
from vn_quant_local import v51_integrity as v51
from vn_quant_local import v52_cycle_management as v52
from vn_quant_local import v54_research_scope as v54
from vn_quant_local import v54_safety
from vn_quant_local import webapp

assert vn_quant_local.__version__ == "0.5.4"
assert v54.V54_VERSION == "V54_RESEARCH_SCOPE_SELLABILITY"
assert performance.performance_status is v54.performance_status_v54
assert performance.add_actual_cashflow is v54.add_actual_cashflow_v54
assert performance.mark_research_only is v54.mark_research_only
assert performance.restore_operational is v54.restore_operational
assert v52.discarded_plan_ids is v54.operationally_excluded_plan_ids
assert v52._active_shadow_plans is v54._active_shadow_plans_v54
assert v51.extract_plan_intents is v54.extract_plan_intents_v54
assert v54._snapshot_sellable_map is v54_safety.snapshot_sellable_map_safe
assert v54._sellability is v54_safety.sellability_zero_first
assert webapp.performance_status is v54.performance_status_v54
assert webapp.add_actual_cashflow is v54.add_actual_cashflow_v54

requested, executable, source = v54._sellability(
    {"quantity": 15, "sellable_quantity": 0},
    snapshot_sellable=15,
)
assert requested == 15
assert executable == 0
assert source == "PLAN_EXPLICIT_SELLABLE_QUANTITY"

requested, executable, source = v54._sellability(
    {"quantity": 15, "sellable_quantity": 15, "action": "WAIT_SELLABLE"},
    snapshot_sellable=15,
)
assert requested == 15
assert executable == 0
assert source == "PLAN_CLASSIFIED_WAIT_SELLABLE"

original_status = v54._ORIGINAL_PERFORMANCE_STATUS
v54._ORIGINAL_PERFORMANCE_STATUS = lambda: {
    "status": "ACTIVE",
    "latest_market_day_for_cycle_lock": "2026-08-05",
    "cycle_catalog": [{
        "plan_id": "plan-observed-incomplete",
        "execution_day": "2026-08-05",
        "shadow_status": "EXECUTED",
        "planned_quantity": 9,
        "actual_quantity": 2,
        "remaining_quantity": 7,
        "actual_complete": False,
        "intents": [],
    }],
    "limitations": {},
}
original_all_plans = v54._all_plan_rows
original_sell_rows = v54._sell_rows_for_plan
original_research_catalog = v54._research_catalog
original_research_ids = v54.research_only_plan_ids
original_actions = v54._scope_action_rows
try:
    v54._all_plan_rows = lambda: [{
        "plan_id": "plan-observed-incomplete",
        "details_json": "{}",
    }]
    v54._sell_rows_for_plan = lambda plan: ([], [{
        "side": "SELL",
        "symbol": "MBB",
        "planned_quantity": 15,
        "actual_quantity": 0,
        "remaining_quantity": 0,
        "status": "WAIT_SELLABLE_AT_PLAN",
        "compliance_eligible": False,
        "excluded_from_compliance": True,
    }])
    v54._research_catalog = lambda: []
    v54.research_only_plan_ids = lambda: set()
    v54._scope_action_rows = lambda: []
    status = v54.performance_status_v54()
finally:
    v54._ORIGINAL_PERFORMANCE_STATUS = original_status
    v54._all_plan_rows = original_all_plans
    v54._sell_rows_for_plan = original_sell_rows
    v54._research_catalog = original_research_catalog
    v54.research_only_plan_ids = original_research_ids
    v54._scope_action_rows = original_actions

cycle = status["cycle_catalog"][0]
assert cycle["research_scope_eligible"] is True
assert cycle["research_scope_retroactive"] is True
assert cycle["wait_sellable_quantity"] == 15
assert cycle["compliance_planned_quantity"] == 9
json.dumps(status, ensure_ascii=False)

print("V54_EXPLICIT_ZERO_SELLABLE=PASS")
print("V54_WAIT_SELLABLE_COMPLIANCE=PASS")
print("V54_RETROACTIVE_RESEARCH_SCOPE=PASS")
print("V54_RUNTIME_BINDINGS=PASS")
PY

echo "===== V54 WEB CONTRACT ====="
grep -q 'MARK_RESEARCH_ONLY_BULK' web/performance_v51.js || fail "thieu bulk research command"
grep -q 'data-v54-cycle-select' web/performance_v51.js || fail "thieu cycle scope checkbox"
grep -q 'data-v54-research' web/performance_v51.js || fail "thieu research-only button"
grep -q 'WAIT_SELLABLE_AT_PLAN' web/performance_v51.js || fail "thieu wait sellable UI"
grep -q 'operational_scope_curated' web/performance_v51.js || fail "thieu hindsight warning"
grep -q 'setCommandBusy(false)' web/performance_v51.js || fail "thieu command busy reset"
if grep -q 'MutationObserver' web/performance_v51.js; then
  fail "MutationObserver khong duoc phep quay lai"
fi
grep -q 'v54-wait-sellable' web/performance_v51.css || fail "thieu wait-sellable CSS"
grep -q 'V54_RESEARCH_SCOPE_SELLABILITY' src/vn_quant_local/v54_research_scope.py || fail "thieu V54 engine"
grep -q 'retroactive_after_shadow_observation' src/vn_quant_local/v54_research_scope.py || fail "thieu hindsight audit"
grep -q 'explicit_zero_is_preserved' src/vn_quant_local/v54_research_scope.py || fail "thieu zero sellable contract"
grep -q 'sellability_zero_first' src/vn_quant_local/v54_safety.py || fail "thieu zero-first safety"

if grep -q 'buying_power_v50' src/vn_quant_local/__init__.py; then
  fail "V50 PPSE dang duoc kich hoat tren branch V54"
fi

if command -v node >/dev/null 2>&1; then
  node --check web/performance_v51.js
else
  echo "NODE_NOT_FOUND: bo qua node --check"
fi

echo "V54_RESEARCH_SCOPE_ACTIONS=PASS"
echo "V54_SELLABILITY_SHADOW_GUARD=PASS"
echo "V54_UI_REFRESH_WITHOUT_RELOAD=PASS"
echo "V54_VALIDATION=PASS"
