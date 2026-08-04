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

bash "$SYSTEM_DIR/scripts/validate_v48_gitbash.sh"

cd "$SYSTEM_DIR"

echo "===== V49 SOURCE INTEGRITY ENGINE ====="
"$PYTHON_EXE" - <<'PY'
from datetime import date, datetime
from types import SimpleNamespace
import sqlite3

from vn_quant_local import broker_portfolio, data_sources
from vn_quant_local.source_integrity_v49 import (
    V49_VERSION,
    _ensure_broker_schema_v49,
    _ensure_market_schema_v49,
    _first_present,
    _upsert_market_row,
    expected_final_session,
    latest_broker_portfolio_v49,
    normalize_position_v49,
    sync_broker_portfolio_v49,
    sync_incremental_market_data_local_v49,
)

assert V49_VERSION == "V49_DNSE_SOURCE_INTEGRITY"
assert data_sources.sync_incremental_market_data_local is sync_incremental_market_data_local_v49
assert broker_portfolio.sync_broker_portfolio is sync_broker_portfolio_v49
assert broker_portfolio.latest_broker_portfolio is latest_broker_portfolio_v49

assert _first_present(
    {"openQuantity": 0, "accumulateQuantity": 15},
    ("openQuantity", "accumulateQuantity"),
) == 0
assert normalize_position_v49(
    {
        "symbol": "FPT",
        "status": "OPEN",
        "openQuantity": 0,
        "accumulateQuantity": 15,
        "closedQuantity": 15,
        "tradeQuantity": 0,
    }
) is None
position = normalize_position_v49(
    {
        "symbol": "FPT",
        "status": "OPEN",
        "openQuantity": 4,
        "accumulateQuantity": 4,
        "tradeQuantity": 0,
        "costPrice": 72,
        "marketPrice": 73,
    }
)
assert position is not None
assert position["quantity"] == 4
assert position["sellable_quantity"] == 0

sessions = [date(2026, 8, 3), date(2026, 8, 4)]
assert expected_final_session(
    now_vn=datetime.fromisoformat("2026-08-04T14:00:00+07:00"),
    working_dates=sessions,
) == date(2026, 8, 3)
assert expected_final_session(
    now_vn=datetime.fromisoformat("2026-08-04T16:00:00+07:00"),
    working_dates=sessions,
) == date(2026, 8, 4)

market = sqlite3.connect(":memory:")
market.execute(
    """
    CREATE TABLE bars(
        asset_type TEXT NOT NULL,
        symbol TEXT NOT NULL,
        day TEXT NOT NULL,
        open REAL NOT NULL,
        high REAL NOT NULL,
        low REAL NOT NULL,
        close REAL NOT NULL,
        volume INTEGER NOT NULL,
        source TEXT NOT NULL,
        source_version TEXT NOT NULL,
        price_basis TEXT NOT NULL,
        normalized_sha256 TEXT NOT NULL,
        fetched_at TEXT NOT NULL,
        PRIMARY KEY(asset_type,symbol,day)
    )
    """
)
_ensure_market_schema_v49(market)
first = SimpleNamespace(
    symbol="VNINDEX",
    day=date(2026, 8, 4),
    open=1600.0,
    high=1610.0,
    low=1590.0,
    close=1605.0,
    volume=100,
    source="dnse_openapi",
    version="0.5.0",
)
revised = SimpleNamespace(**{**first.__dict__, "close": 1607.0, "volume": 120})
assert _upsert_market_row(
    market,
    asset_type="INDEX",
    row=first,
    mutable_from=date(2026, 7, 20),
    fetched_at="2026-08-04T09:00:00Z",
) == "INSERTED"
assert _upsert_market_row(
    market,
    asset_type="INDEX",
    row=revised,
    mutable_from=date(2026, 7, 20),
    fetched_at="2026-08-04T09:01:00Z",
) == "REVISED"
assert market.execute(
    "SELECT close FROM bars WHERE symbol='VNINDEX'"
).fetchone()[0] == 1607.0
assert market.execute(
    "SELECT COUNT(*) FROM market_source_revisions_v49"
).fetchone()[0] == 1
market.close()

broker = sqlite3.connect(":memory:")
_ensure_broker_schema_v49(broker)
snapshot_columns = {
    row[1] for row in broker.execute("PRAGMA table_info(broker_snapshots)")
}
position_columns = {
    row[1] for row in broker.execute("PRAGMA table_info(broker_positions)")
}
assert "selected_account_token" in snapshot_columns
assert "broker_nav_vnd" in snapshot_columns
assert "research_eod_nav_vnd" in snapshot_columns
assert "broker_market_value_vnd" in position_columns
assert "research_eod_market_value_vnd" in position_columns
broker.close()

print("V49_ZERO_FIELD_PARSER=PASS")
print("V49_RECENT_EOD_REFETCH=PASS")
print("V49_SOURCE_REVISION_AUDIT=PASS")
print("V49_BROKER_RESEARCH_NAV_SPLIT=PASS")
print("V49_RUNTIME_PATCH=PASS")
PY

echo "===== V49 ROUTES AND ASSETS ====="
grep -q '/api/source-integrity' src/vn_quant_local/webapp.py || fail "thieu source integrity endpoint"
grep -q '/api/broker/accounts' src/vn_quant_local/webapp.py || fail "thieu account options endpoint"
grep -q '/api/broker/select-account' src/vn_quant_local/webapp.py || fail "thieu account selection endpoint"
grep -q 'source_integrity_v49.css' web/index.html || fail "thieu V49 CSS"
grep -q 'source_integrity_v49.js' web/index.html || fail "thieu V49 JS"
grep -q 'CURRENT_FINAL_EOD' web/source_integrity_v49.js || fail "thieu freshness UI"
grep -q 'ONE_EXPLICIT_SUBACCOUNT' config.json || fail "thieu account policy"
grep -q 'OPEN_QUANTITY_PRESERVE_ZERO' config.json || fail "thieu quantity policy"
grep -q 'V49_DNSE_SOURCE_INTEGRITY' src/vn_quant_local/source_integrity_v49.py || fail "thieu V49 engine"

if command -v node >/dev/null 2>&1; then
  node --check web/source_integrity_v49.js
fi

"$PYTHON_EXE" -m compileall -q src tests

echo "V49_VALIDATION=PASS"
