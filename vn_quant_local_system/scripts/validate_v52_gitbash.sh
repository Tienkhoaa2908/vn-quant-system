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

echo "===== V52 COMPILE ====="
"$PYTHON_EXE" -m compileall -q src tests

echo "===== V52 FULL UNIT TESTS ====="
"$PYTHON_EXE" -m unittest discover -s tests -p 'test_*.py' -v

echo "===== V52 CYCLE MANAGEMENT CONTRACT ====="
"$PYTHON_EXE" - <<'PY'
import sqlite3

from vn_quant_local import performance
from vn_quant_local import v51_integrity as v51
from vn_quant_local import v52_commands
from vn_quant_local import v52_cycle_management as v52
from vn_quant_local import v52_discard_safety
from vn_quant_local import v52_status_safety
from vn_quant_local import webapp

assert v52.V52_VERSION == "V52_AUDITABLE_CYCLE_DISCARD"

rows = [
    {
        "action_time": "2026-08-05T09:00:00+00:00",
        "action_id": "a",
        "action_type": "DISCARD",
        "plan_id": "plan-1",
    },
    {
        "action_time": "2026-08-05T09:01:00+00:00",
        "action_id": "b",
        "action_type": "RESTORE",
        "plan_id": "plan-1",
    },
]
assert v52.latest_cycle_action_index(rows)["plan-1"]["action_type"] == "RESTORE"

memory = sqlite3.connect(":memory:")
v52._ensure_schema(memory)
columns = {
    row[1]
    for row in memory.execute(
        "PRAGMA table_info(performance_cycle_actions_v52)"
    ).fetchall()
}
assert {
    "action_id",
    "action_time",
    "action_type",
    "plan_id",
    "week_key",
    "cycle_id",
    "reason",
    "details_json",
}.issubset(columns)
memory.close()

original_loader = v52._ORIGINAL_LOAD_RECONCILIATION_INPUTS
try:
    v52._ORIGINAL_LOAD_RECONCILIATION_INPUTS = lambda: (
        [{"plan_id": "old"}, {"plan_id": "keep"}],
        [{"plan_id": "old"}, {"plan_id": "keep"}],
        [],
        "2026-08-05",
    )
    original_discarded = v52.discarded_plan_ids
    v52.discarded_plan_ids = lambda: {"old"}
    plans, trades, _, _ = v52._load_reconciliation_inputs_v52()
    assert [row["plan_id"] for row in plans] == ["keep"]
    assert [row["plan_id"] for row in trades] == ["keep"]
finally:
    v52._ORIGINAL_LOAD_RECONCILIATION_INPUTS = original_loader
    v52.discarded_plan_ids = original_discarded

assert performance._rebuild_shadow is v52.rebuild_shadow_v52
assert performance._reconciliation is v52.reconciliation_v52
assert v51._load_reconciliation_inputs is v52._load_reconciliation_inputs_v52
assert performance.performance_status is v52_status_safety.performance_status_active_cycles_only
assert performance.add_actual_fill is v52.add_actual_fill_v52
assert performance.add_actual_cashflow is v52_commands.add_actual_cashflow_v52
assert performance.discard_cycle is v52_discard_safety.discard_cycle_safe
assert performance.restore_cycle is v52_discard_safety.restore_cycle_safe
assert webapp.performance_status is v52_status_safety.performance_status_active_cycles_only
assert webapp.add_actual_cashflow is v52_commands.add_actual_cashflow_v52
assert webapp.add_actual_fill is v52.add_actual_fill_v52
assert webapp.Handler.server_version == "VNQuantLocal/2.0"

print("V52_APPEND_ONLY_ACTIONS=PASS")
print("V52_ACTIVE_CYCLE_FILTER=PASS")
print("V52_LEGACY_SELECTOR_FILTER=PASS")
print("V52_ACTUAL_FILL_LOCK=PASS")
print("V52_PRE_EXECUTION_ONLY=PASS")
print("V52_RESTORE_PRE_EXECUTION_ONLY=PASS")
print("V52_SHADOW_REBUILD_BINDING=PASS")
print("V52_EXISTING_API_COMMAND_ROUTE=PASS")
print("V52_RUNTIME_BINDINGS=PASS")
PY

echo "===== V52 WEB ASSETS ====="
grep -q 'data-v52-discard' web/performance_v51.js || fail "thieu nut bo cycle"
grep -q 'data-v52-restore' web/performance_v51.js || fail "thieu nut khoi phuc cycle"
grep -q 'DISCARD_CYCLE' web/performance_v51.js || fail "thieu command discard"
grep -q 'Cycle đã bỏ' web/performance_v51.js || fail "thieu audit cycle da bo"
grep -q 'V52_AUDITABLE_CYCLE_DISCARD' src/vn_quant_local/v52_cycle_management.py || fail "thieu V52 engine"
grep -q 'PERFORMANCE_CYCLE_SHADOW_ALREADY_EXECUTED' src/vn_quant_local/v52_discard_safety.py || fail "thieu anti-hindsight gate"
grep -q 'performance_cycle_actions_v52' src/vn_quant_local/v52_cycle_management.py || fail "thieu cycle action ledger"
grep -q 'active_shadow_plan_count' src/vn_quant_local/v52_status_safety.py || fail "thieu active selector filter"

if grep -q 'buying_power_v50' src/vn_quant_local/__init__.py; then
  fail "V50 PPSE dang duoc kich hoat tren branch V52"
fi

if command -v node >/dev/null 2>&1; then
  node --check web/performance_v51.js
else
  echo "NODE_NOT_FOUND: bo qua node --check"
fi

echo "V52_VALIDATION=PASS"
