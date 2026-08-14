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

bash "$SYSTEM_DIR/scripts/validate_v45_gitbash.sh"

cd "$SYSTEM_DIR"

echo "===== V47 SIGNAL SEMANTICS ====="
"$PYTHON_EXE" - <<'PY'
from datetime import date
from vn_quant_local import c3_model, weekly_plan
from vn_quant_local.model_safety import (
    completed_month_signal_days,
    robust_signal_days,
)
from vn_quant_local.signal_refresh import (
    PREVIEW_MODE,
    PURCHASE_GUARD_MODE,
    purchase_guard_map,
)

assert c3_model._signal_days is robust_signal_days
assert weekly_plan._completed_month_signal_days is completed_month_signal_days
canonical, preview = robust_signal_days(
    [date(2026, 6, 30), date(2026, 7, 31)],
    today=date(2026, 8, 4),
)
assert canonical == date(2026, 7, 31)
assert preview == date(2026, 7, 31)

guard = purchase_guard_map(
    [{"symbol": "AAA", "rank": 1}, {"symbol": "BBB", "rank": 2}],
    {
        "audit": {
            "AAA": {"rank": 7, "eligible": True, "reasons": []},
            "BBB": {"rank": 24, "eligible": True, "reasons": []},
        }
    },
)
assert guard["AAA"]["allowed_to_buy"] is True
assert guard["BBB"]["allowed_to_buy"] is False
assert PREVIEW_MODE == "LATEST_SESSION_WITH_CANONICAL_WEIGHTS"
assert PURCHASE_GUARD_MODE == "CANONICAL_TOP10_AND_PREVIEW_TOP20_ELIGIBLE"
print("V47_COMPLETED_MONTH_CALENDAR=PASS")
print("V47_CANONICAL_PREVIEW_SEPARATION=PASS")
print("V47_PURCHASE_GUARD=PASS")
PY

echo "===== V47 ROUTES AND ASSETS ====="
grep -q '/api/actions/market-refresh' src/vn_quant_local/webapp.py || fail "thieu market refresh endpoint"
grep -q '/api/actions/canonical' src/vn_quant_local/webapp.py || fail "thieu canonical endpoint"
grep -q 'refresh_market_before_plan' config.json || fail "thieu fresh-plan config"
grep -q 'preview_can_trigger_sell' config.json || fail "thieu sell guard config"
grep -q 'signal_v47.js' web/index.html || fail "thieu signal UI"

if command -v node >/dev/null 2>&1; then
  node --check web/signal_v47.js
fi

echo "V47_VALIDATION=PASS"
