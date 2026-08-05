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

bash "$SYSTEM_DIR/scripts/validate_v49_gitbash.sh"

cd "$SYSTEM_DIR"

echo "===== V50 BUYING POWER ENGINE ====="
"$PYTHON_EXE" - <<'PY'
import sqlite3

from vn_quant_local import broker_portfolio, capital_plan, weekly_plan
from vn_quant_local import buying_power_v50 as v50

assert v50.V50_VERSION == "V50_DNSE_AUTHORITATIVE_BUYING_POWER"
assert broker_portfolio.latest_broker_portfolio is v50.latest_broker_portfolio_v50
assert weekly_plan.latest_broker_portfolio is v50.latest_broker_portfolio_v50
assert capital_plan.latest_broker_portfolio is v50.latest_broker_portfolio_v50
assert weekly_plan.planned_buying_power is v50.planned_buying_power_v50
assert weekly_plan.allocate_buy_orders is v50.allocate_buy_orders_v50
assert capital_plan.create_weekly_plan is v50.create_weekly_plan_v50

package = v50.select_non_margin_package(
    [
        {"id": 9, "type": "M", "loanProducts": [{"symbol": "FPT"}]},
        {"id": 3, "type": "N", "loanProducts": [{"symbol": "FPT"}]},
    ],
    "FPT",
)
assert package is not None
assert package["id"] == "3"
assert package["type"] == "N"

ppse = v50.normalize_ppse_response(
    {"ppse": 72500.0, "qmax": 3, "price": 24000.0},
    symbol="MBB",
    price_vnd=23900.0,
    loan_package_id="3",
)
assert ppse["ppse_vnd"] == 72500.0
assert ppse["qmax"] == 3

original_snapshot = v50._current_effective_buying_power
v50._current_effective_buying_power = lambda: {
    "status": "SUCCESS",
    "conservative_buying_power_vnd": 72000.0,
    "items": [
        {
            "symbol": "FPT",
            "status": "SUCCESS",
            "ppse_vnd": 72000.0,
            "qmax": 2,
            "loan_package_id": "3",
        }
    ],
}
try:
    assert v50.planned_buying_power_v50(945.0, 0.0) == 72000.0
    orders = v50.allocate_buy_orders_v50(
        [
            {
                "symbol": "FPT",
                "rank": 1,
                "price_vnd": 10000.0,
                "budget_ceiling_vnd": 100000.0,
                "underweight_pct": 0.2,
                "target_gap_vnd": 100000.0,
            }
        ],
        budget_vnd=100000.0,
        max_orders=1,
        cost_bps=0.0,
    )
finally:
    v50._current_effective_buying_power = original_snapshot
assert len(orders) == 1
assert orders[0]["quantity"] == 2
assert orders[0]["dnse_qmax"] == 2

db = sqlite3.connect(":memory:")
v50._ensure_schema(db)
tables = {
    row[0]
    for row in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
}
assert "buying_power_snapshots_v50" in tables
assert "buying_power_items_v50" in tables
db.close()

print("V50_NON_MARGIN_PACKAGE=PASS")
print("V50_PPSE_NORMALIZATION=PASS")
print("V50_UNSETTLED_PROCEEDS_BUDGET=PASS")
print("V50_QMAX_GUARD=PASS")
print("V50_RUNTIME_BINDINGS=PASS")
print("V50_SCHEMA=PASS")
PY

echo "===== V50 CONTRACT AND UI ====="
grep -q 'DNSE_NON_MARGIN_PPSE_PLUS_NEW_CAPITAL' src/vn_quant_local/buying_power_v50.py || fail "thieu PPSE planner formula"
grep -q 'DNSE_PPSE_NOT_POSITION_DELTA' src/vn_quant_local/buying_power_v50.py || fail "thieu source rule"
grep -q 'write_endpoint_called.*false' config.json || fail "thieu read-only contract"
grep -q 'margin_allowed.*false' config.json || fail "thieu non-margin contract"
grep -q 'Sức mua planner' web/source_integrity_v49.js || fail "thieu buying power UI"
grep -q 'Tiền bán chờ về tái sử dụng' web/source_integrity_v49.js || fail "thieu unsettled proceeds UI"
grep -q 'V50_DNSE_AUTHORITATIVE_BUYING_POWER' web/source_integrity_v49.js || fail "thieu V50 UI version"

if command -v node >/dev/null 2>&1; then
  node --check web/source_integrity_v49.js
else
  echo "NODE_NOT_FOUND: bo qua node --check"
fi

"$PYTHON_EXE" -m compileall -q src tests

echo "V50_VALIDATION=PASS"
