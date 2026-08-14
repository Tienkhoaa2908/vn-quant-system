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

bash "$SYSTEM_DIR/scripts/validate_v47_gitbash.sh"

cd "$SYSTEM_DIR"

echo "===== V48 CORRECTION ENGINE ====="
"$PYTHON_EXE" - <<'PY'
from vn_quant_local import performance
from vn_quant_local.performance_corrections import (
    CORRECTIONS_VERSION,
    _effective_event_rows_from,
    correction_index,
    effective_actual_events,
    normalize_fill_price,
    performance_status_v48,
    reconciliation_v48,
)

assert CORRECTIONS_VERSION == "V48_AUDITABLE_EVENT_CORRECTIONS"
assert performance._actual_events is effective_actual_events
assert performance._reconciliation is reconciliation_v48
assert performance.performance_status is performance_status_v48
assert normalize_fill_price(72, "THOUSAND_VND") == 72_000

old = {
    "event_id": "old",
    "event_time": "2026-08-04T01:00:00+00:00",
    "event_day": "2026-08-04",
    "event_type": "ACTUAL_CASHFLOW",
    "source": "USER_CONFIRMED",
    "amount_vnd": 250000,
    "details_json": "{}",
}
void = {
    "event_id": "void",
    "event_time": "2026-08-04T02:00:00+00:00",
    "event_day": "2026-08-04",
    "event_type": "EVENT_VOID",
    "source": "USER_CORRECTION",
    "details_json": '{"target_event_id":"old","reason":"test"}',
}
assert correction_index([old, void])["old"]["status"] == "VOIDED"
assert _effective_event_rows_from(
    [old, void], market_days=["2026-08-04"]
) == []
print("V48_APPEND_ONLY_CORRECTION=PASS")
print("V48_EFFECTIVE_LEDGER=PASS")
print("V48_PRICE_UNIT_GUARD=PASS")
print("V48_RUNTIME_PATCH=PASS")
PY

echo "===== V48 UI ====="
grep -q 'Sửa có audit' web/signal_v47.js || fail "thieu nut sua V48"
grep -q 'Hủy có audit' web/signal_v47.js || fail "thieu nut huy V48"
grep -q 'PENDING_VALUATION' web/signal_v47.js || fail "thieu pending valuation UI"
grep -q 'THOUSAND_VND' web/signal_v47.js || fail "thieu price unit UI"
grep -q 'V48_AUDITABLE_EVENT_CORRECTIONS' src/vn_quant_local/performance_corrections.py || fail "thieu correction engine"

if command -v node >/dev/null 2>&1; then
  node --check web/signal_v47.js
fi

echo "V48_VALIDATION=PASS"
