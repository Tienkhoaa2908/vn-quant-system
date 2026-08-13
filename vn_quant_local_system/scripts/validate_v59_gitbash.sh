#!/usr/bin/env bash
set -euo pipefail

SYSTEM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$SYSTEM_DIR/.." && pwd)"
PY="$SYSTEM_DIR/.venv/Scripts/python.exe"

fail(){ echo "FAILED: $*" >&2; exit 2; }
[[ -f "$PY" ]] || fail "khong tim thay workstation Python: $PY"
cd "$REPO_ROOT"

export PYTHONPATH="$SYSTEM_DIR/src:$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

"$PY" -m compileall -q \
  "$SYSTEM_DIR/src/vn_quant_local" \
  "$SYSTEM_DIR/tests"

"$PY" -m unittest discover -s "$SYSTEM_DIR/tests" -p 'test_*.py' -v

"$PY" - <<'PY'
import vn_quant_local
from vn_quant_local import broker_portfolio, core, signal_refresh
from vn_quant_local import v59_fast_realtime as v59
from vn_quant_local import v59_market_stream as market
from vn_quant_local import v59_stream_safety as safety
from vn_quant_local import webapp_v59

assert vn_quant_local.__version__ == "0.5.9"
assert broker_portfolio.sync_broker_portfolio is v59.sync_broker_portfolio_v59
assert broker_portfolio.latest_broker_portfolio is v59.latest_broker_portfolio_v59
assert core.workstation_status is v59.workstation_status_v59
assert core.market_coverage is v59.fast_market_coverage_v59
assert getattr(signal_refresh, "_v59_model_cache_applied", False)
assert getattr(v59, "_v59_stream_safety_applied", False)
assert webapp_v59.V59_WEB_VERSION == "V59_FAST_REALTIME_WEB"
assert market.V59_MARKET_VERSION == "V59_DNSE_MARKET_STREAM_READ_ONLY"
rt = v59.realtime_status_v59(include_portfolio=False)
assert rt["automatic_live_orders_allowed"] is False
assert rt["stream_scope_safety_version"] == safety.V59_STREAM_SAFETY_VERSION
status = core.workstation_status()
if status.get("market", {}).get("status") != "MISSING":
    assert status["market"].get("sha256") is None
    assert status["market"].get("sha256_mode") == "DEFERRED_MAINTENANCE_ONLY"
assert status["reference_zip"].get("sha256") is None
print("V59_FAST_STATUS=PASS")
print("V59_SELECTED_ACCOUNT_FASTPATH=PASS")
print("V59_MODEL_CACHE=PASS")
print("V59_STREAM_SCOPE_FAIL_CLOSED=PASS")
print("V59_REALTIME_READ_ONLY=PASS")
PY

if command -v node >/dev/null 2>&1; then
  node --check "$SYSTEM_DIR/web/realtime_v59.js"
fi

grep -q 'DnseTradingStream' "$SYSTEM_DIR/src/vn_quant_local/v59_fast_realtime.py"
grep -q 'subscribe_positions' "$SYSTEM_DIR/src/vn_quant_local/v59_fast_realtime.py"
grep -q 'subscribe_orders' "$SYSTEM_DIR/src/vn_quant_local/v59_fast_realtime.py"
grep -q 'DnseMarketStream' "$SYSTEM_DIR/src/vn_quant_local/v59_market_stream.py"
grep -q 'subscribe_trades' "$SYSTEM_DIR/src/vn_quant_local/v59_market_stream.py"
grep -q 'subscribe_quotes' "$SYSTEM_DIR/src/vn_quant_local/v59_market_stream.py"
grep -q 'UNSCOPED_POSITION_EVENTS_DIAGNOSTIC_ONLY' "$SYSTEM_DIR/src/vn_quant_local/v59_stream_safety.py"
grep -q 'SKIPPED_INTERACTIVE_FAST_PATH' "$SYSTEM_DIR/src/vn_quant_local/webapp_v59.py"
grep -q 'automatic_live_orders_allowed.*False' "$SYSTEM_DIR/src/vn_quant_local/v59_fast_realtime.py"
grep -q 'V59_POLL_MS = 1000' "$SYSTEM_DIR/web/realtime_v59.js"

if grep -REn 'orders\.(place|cancel|update)|place_order|cancel_order|update_order' \
    "$SYSTEM_DIR/src/vn_quant_local/v59_fast_realtime.py" \
    "$SYSTEM_DIR/src/vn_quant_local/v59_market_stream.py" \
    "$SYSTEM_DIR/src/vn_quant_local/v59_stream_safety.py" \
    "$SYSTEM_DIR/src/vn_quant_local/webapp_v59.py"; then
  fail "V59 realtime layer chua endpoint trading mutation"
fi

echo "V59_UI_LOCAL_POLL=PASS"
echo "V59_VALIDATION=PASS"
