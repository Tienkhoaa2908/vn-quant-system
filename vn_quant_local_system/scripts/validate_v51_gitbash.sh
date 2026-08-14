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

echo "===== V51 COMPILE ====="
"$PYTHON_EXE" -m compileall -q src tests

echo "===== V51 FULL UNIT TESTS ====="
"$PYTHON_EXE" -m unittest discover -s tests -p 'test_*.py' -v

echo "===== V51 CASH AND INTENT CONTRACT ====="
"$PYTHON_EXE" - <<'PY'
from vn_quant_local import broker_portfolio, capital_plan, core, performance, weekly_plan
from vn_quant_local import source_integrity_v49
from vn_quant_local import v51_integrity as v51
from vn_quant_local import v51_safety
from vn_quant_local import webapp

assert v51.V51_VERSION == "V51_INTENT_RECONCILIATION_CASH_INTEGRITY"

cash = v51.validate_cash_contract(
    total_cash_vnd=147_123,
    available_cash_vnd=585_945,
    withdrawable_cash_vnd=176_531,
)
assert cash["status"] == "REJECT_AVAILABLE_EXCEEDS_TOTAL_CASH"
assert cash["planner_cash_vnd"] == 147_123
assert cash["validated_available_cash_vnd"] == 147_123
assert cash["uses_ppse"] is False

fields = v51_safety.extract_cash_fields(
    {
        "totalCash": 147_123,
        "availableCash": 140_000,
        "withdrawableCash": 130_000,
        "nested": {"availableCash": 585_945},
    }
)
assert fields["field_source"] == "TOP_LEVEL_DNSE_BALANCE_FIELDS"
assert fields["available_cash_vnd"] == 140_000

plans = [
    {
        "plan_id": "plan-v51",
        "week_key": "CYCLE:cycle-v51",
        "created_at": "2026-08-05T07:03:29+00:00",
        "execution_day": "2026-08-06",
        "status": "SELECTED",
        "planned_contribution_vnd": 0.0,
        "details": {
            "cycle_id": "cycle-v51",
            "buy_orders": [
                {
                    "symbol": "MSB",
                    "quantity": 4,
                    "price_vnd": 16_200,
                    "estimated_cost_vnd": 65_124,
                }
            ],
            "exit_candidates": [],
        },
    }
]
actual = [
    {
        "event_id": "fill-1",
        "event_time": "2026-08-05T07:10:00+00:00",
        "event_day": "2026-08-05",
        "event_type": "ACTUAL_FILL",
        "side": "BUY",
        "symbol": "MSB",
        "quantity": 2,
        "price_vnd": 16_150,
        "fees_vnd": 0.0,
        "taxes_vnd": 0.0,
        "plan_id": "plan-v51",
    },
    {
        "event_id": "fill-2",
        "event_time": "2026-08-05T07:11:00+00:00",
        "event_day": "2026-08-05",
        "event_type": "ACTUAL_FILL",
        "side": "BUY",
        "symbol": "MSB",
        "quantity": 2,
        "price_vnd": 16_200,
        "fees_vnd": 0.0,
        "taxes_vnd": 0.0,
        "plan_id": "plan-v51",
    },
]
rows = v51.reconcile_intents(
    plans=plans,
    shadow_trades=[],
    actual_fills=actual,
    latest_market_day="2026-08-05",
)
assert len(rows) == 1
assert rows[0]["status"] == "MATCHED_COMPLETE_SHADOW_PENDING"
assert rows[0]["actual_quantity"] == 4
assert rows[0]["actual_vwap_vnd"] == 16_175
assert rows[0]["shadow_pending"] is True

catalog = v51.build_cycle_catalog(plans, rows)
assert len(catalog) == 1
assert catalog[0]["newest"] is True
assert catalog[0]["remaining_quantity"] == 0
assert "MỚI NHẤT" in catalog[0]["display_label"]

assert source_integrity_v49._probe_accounts is v51_safety.probe_accounts_safe
assert broker_portfolio.sync_broker_portfolio is v51._sync_broker_v51
assert broker_portfolio.latest_broker_portfolio is v51._latest_broker_v51
assert weekly_plan.latest_broker_portfolio is v51._latest_broker_v51
assert capital_plan.latest_broker_portfolio is v51._latest_broker_v51
assert performance.latest_broker_portfolio is v51._latest_broker_v51
assert performance._reconciliation is v51.reconciliation_v51
assert performance.performance_status is v51.performance_status_v51
assert core.workstation_status is v51_safety.workstation_status_zero_new_capital
assert webapp.latest_broker_portfolio is v51._latest_broker_v51
assert webapp.performance_status is v51.performance_status_v51
assert webapp.Handler.server_version == "VNQuantLocal/2.0"

print("V51_CASH_CONTRACT=PASS")
print("V51_TOP_LEVEL_CASH_FIELDS=PASS")
print("V51_INTENT_BEFORE_SHADOW=PASS")
print("V51_MULTI_FILL_VWAP=PASS")
print("V51_CYCLE_CATALOG=PASS")
print("V51_ZERO_NEW_CAPITAL_DEFAULT=PASS")
print("V51_RUNTIME_BINDINGS=PASS")
PY

echo "===== V51 WEB ASSETS ====="
grep -q 'performance_v51.css' web/index.html || fail "thieu V51 CSS"
grep -q 'performance_v51.js' web/index.html || fail "thieu V51 JS"
grep -q '/performance_v51.js' src/vn_quant_local/webapp.py || fail "thieu V51 JS route"
grep -q '/performance_v51.css' src/vn_quant_local/webapp.py || fail "thieu V51 CSS route"
grep -q 'MATCHED_COMPLETE_SHADOW_PENDING' web/performance_v51.js || fail "thieu shadow pending UI"
grep -q 'MỚI NHẤT' web/performance_v51.js || fail "thieu newest cycle label"
grep -q 'Tiền mới chưa nằm trong DNSE' web/index.html || fail "thieu capital input clarification"
grep -q 'V51_INTENT_RECONCILIATION_CASH_INTEGRITY' src/vn_quant_local/v51_integrity.py || fail "thieu V51 engine"

if grep -q 'buying_power_v50' src/vn_quant_local/__init__.py; then
  fail "V50 PPSE dang duoc kich hoat tren branch V51"
fi

if command -v node >/dev/null 2>&1; then
  node --check web/performance_v51.js
  node --check web/signal_v47.js
  node --check web/source_integrity_v49.js
else
  echo "NODE_NOT_FOUND: bo qua node --check"
fi

echo "V51_VALIDATION=PASS"
