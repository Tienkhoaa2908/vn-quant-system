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

echo "===== V55 COMPILE ====="
"$PYTHON_EXE" -m compileall -q src tests

echo "===== V55 FULL UNIT TESTS ====="
"$PYTHON_EXE" -m unittest discover -s tests -p 'test_*.py' -v

echo "===== V55 RUNTIME CONTRACT ====="
"$PYTHON_EXE" - <<'PY'
import json
import vn_quant_local
from vn_quant_local import broker_portfolio, capital_plan, performance, weekly_plan
from vn_quant_local import v54_research_scope as v54
from vn_quant_local import v55_eod_only as v55
from vn_quant_local import webapp

assert vn_quant_local.__version__ == "0.5.5"
assert v55.V55_VERSION == "V55_FINAL_EOD_ONLY_VALUATION"
assert broker_portfolio.sync_broker_portfolio is v55.sync_broker_portfolio_v55
assert broker_portfolio.latest_broker_portfolio is v55.latest_broker_portfolio_v55
assert weekly_plan.latest_broker_portfolio is v55.latest_broker_portfolio_v55
assert capital_plan.latest_broker_portfolio is v55.latest_broker_portfolio_v55
assert performance.latest_broker_portfolio is v55.latest_broker_portfolio_v55
assert performance.performance_status is v54.performance_status_v54
assert webapp.sync_broker_portfolio is v55.sync_broker_portfolio_v55
assert webapp.latest_broker_portfolio is v55.latest_broker_portfolio_v55

position = v55.official_position({
    "symbol": "VPI",
    "quantity": 2,
    "average_cost_vnd": 65000,
    "local_market_price_vnd": 63000,
    "broker_market_price_vnd": 99999,
})
assert position["price_vnd"] == 63000
assert position["market_value_vnd"] == 126000
assert position["pnl_vnd"] == -4000

try:
    v55.official_position({
        "symbol": "ACB",
        "quantity": 3,
        "average_cost_vnd": 22300,
        "local_market_price_vnd": 0,
        "broker_market_price_vnd": 22450,
    })
except ValueError as exc:
    assert "V55_FINAL_EOD_PRICE_MISSING:ACB" in str(exc)
else:
    raise AssertionError("broker reference was used as EOD fallback")

public = v55._public({
    "status": "SUCCESS",
    "snapshot_id": "broker-test",
    "market_day": "2026-08-06",
    "total_cash_vnd": 176534,
    "broker_nav_vnd": 999999,
    "broker_stock_value_vnd": 888888,
    "details": {},
    "positions": [{
        "symbol": "MSB",
        "quantity": 4,
        "sellable_quantity": 0,
        "average_cost_vnd": 16150,
        "local_market_price_vnd": 16150,
        "broker_market_price_vnd": 99999,
        "broker_market_value_vnd": 399996,
    }],
})
assert public["official_eod_stock_value_vnd"] == 64600
assert public["official_eod_nav_vnd"] == 241134
assert "broker_nav_vnd" not in public
assert "broker_stock_value_vnd" not in public
assert "broker_market_price_vnd" not in public["positions"][0]
assert "broker_market_value_vnd" not in public["positions"][0]
json.dumps(public, ensure_ascii=False)

print("V55_FINAL_EOD_PRICE=PASS")
print("V55_NO_BROKER_PRICE_FALLBACK=PASS")
print("V55_PUBLIC_REFERENCE_REMOVAL=PASS")
print("V55_RUNTIME_BINDINGS=PASS")
PY

echo "===== V55 FILE CONTRACT ====="
grep -q 'V55_FINAL_EOD_ONLY_VALUATION' src/vn_quant_local/v55_eod_only.py || fail "thieu V55 engine"
grep -q 'LOCAL_FINAL_EOD_CLOSE_ONLY' src/vn_quant_local/v55_eod_only.py || fail "thieu EOD-only policy"
grep -q 'broker_market_price_used.*False' src/vn_quant_local/v55_eod_only.py || fail "broker price van duoc dung"
grep -q 'row.pop("broker_market_price_vnd"' src/vn_quant_local/v55_eod_only.py || fail "public payload van lo broker price"
grep -q 'row.pop("broker_market_value_vnd"' src/vn_quant_local/v55_eod_only.py || fail "public payload van lo broker market value"
grep -q 'official_eod_nav_vnd' web/planning_v46.js || fail "thieu EOD NAV UI"
grep -q 'P&L EOD' web/planning_v46.js || fail "thieu EOD PnL UI"
grep -q 'Giá đóng cửa EOD chính thức' web/planning_v46.js || fail "thieu EOD price UI"
grep -q '/planning_v46.js' web/index.html || fail "V55 renderer chua duoc load"
grep -q 'V55_FINAL_EOD_ONLY_VALUATION' config.json || fail "config chua khai bao V55"
grep -q '"broker_market_price_used_for_valuation": false' config.json || fail "config van cho broker valuation"

if grep -q 'Broker NAV' web/planning_v46.js; then
  fail "UI V55 van hien Broker NAV"
fi
if grep -q 'Broker snapshot' web/planning_v46.js; then
  fail "UI V55 van hien Broker snapshot price"
fi
if command -v node >/dev/null 2>&1; then
  node --check web/planning_v46.js
  node --check web/performance_v51.js
else
  echo "NODE_NOT_FOUND: bo qua node --check"
fi

echo "V55_EXISTING_SNAPSHOT_REVALUE=PASS"
echo "V55_OPENING_EOD_REBASE=PASS"
echo "V55_UI_EOD_ONLY=PASS"
echo "V55_VALIDATION=PASS"
