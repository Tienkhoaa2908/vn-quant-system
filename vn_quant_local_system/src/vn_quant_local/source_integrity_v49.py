"""V49 DNSE source-integrity layer.

This module fixes two source-boundary defects without changing C3, planner,
sell policy, shadow execution, or the append-only performance ledger:

* recent OHLC sessions are fetched on every refresh and are never hidden by a
  stale ``fetched_ranges`` interval;
* broker state is read from one explicit sub-account and current quantities
  preserve zero-valued DNSE fields instead of falling back to cumulative
  historical quantities.

The module is applied from :mod:`vn_quant_local.__init__` before the web app
imports the patched functions.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from hashlib import sha256
import json
import math
from typing import Mapping, Sequence
from uuid import uuid4
from zoneinfo import ZoneInfo
import sqlite3

from . import broker_portfolio, data_sources
from .core import SYSTEM_ROOT, account_snapshot, load_config, paths, replace_account, state_db, utc_now

V49_VERSION = "V49_DNSE_SOURCE_INTEGRITY"
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
ACCOUNT_SELECTION_PATH = SYSTEM_ROOT / "data" / "state" / "dnse_account_selection.json"
RECENT_MUTABLE_DAYS = 10
DEFAULT_REFRESH_LOOKBACK_DAYS = 14
EOD_READY_TIME = time(15, 30)
MIN_SESSION_COVERAGE_RATIO = 0.75

_ORIGINAL_LATEST_BROKER = None
_ORIGINAL_CREDENTIAL_STATUS = None


def _finite_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _nonnegative_int(value: object, default: int = 0) -> int:
    number = _finite_float(value, float(default))
    if number < 0 or not float(number).is_integer():
        return default
    return int(number)


def _first_present(
    payload: Mapping[str, object],
    names: Sequence[str],
    default: object = None,
) -> object:
    """Return the first present non-None field while preserving zero values."""

    for name in names:
        if name in payload and payload[name] is not None:
            return payload[name]
    lowered = {str(key).lower(): value for key, value in payload.items()}
    for name in names:
        value = lowered.get(name.lower(), None)
        if value is not None:
            return value
    return default


def _find_number(payload: object, names: Sequence[str]) -> float | None:
    wanted = {name.lower() for name in names}
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if str(key).lower() in wanted and value is not None:
                result = _finite_float(value, float("nan"))
                if math.isfinite(result):
                    return result
        for value in payload.values():
            result = _find_number(value, names)
            if result is not None:
                return result
    if isinstance(payload, list):
        for value in payload:
            result = _find_number(value, names)
            if result is not None:
                return result
    return None


def _mask_account(value: str) -> str:
    text = str(value or "").strip()
    if len(text) <= 4:
        return "•" * len(text)
    return "•" * max(4, len(text) - 4) + text[-4:]


def _account_id(account: Mapping[str, object]) -> str:
    value = _first_present(
        account,
        (
            "id",
            "accountNo",
            "account_no",
            "accountId",
            "investorAccountId",
            "investor_account_id",
        ),
        "",
    )
    return str(value or "").strip()


def _account_token(account_no: str) -> str:
    return sha256(str(account_no).encode("utf-8")).hexdigest()[:20]


def _read_account_selection() -> str | None:
    try:
        payload = json.loads(ACCOUNT_SELECTION_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, Mapping):
        return None
    token = str(payload.get("selection_token") or "").strip()
    return token or None


def _write_account_selection(token: str) -> None:
    ACCOUNT_SELECTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "selection_token": str(token),
        "saved_at": utc_now(),
        "stores_full_account_number": False,
    }
    temporary = ACCOUNT_SELECTION_PATH.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    try:
        temporary.chmod(0o600)
    except OSError:
        pass
    temporary.replace(ACCOUNT_SELECTION_PATH)


def normalize_position_v49(raw: Mapping[str, object]) -> dict[str, object] | None:
    """Normalize a current DNSE position without treating ``0`` as missing."""

    symbol = str(
        _first_present(
            raw,
            ("symbol", "instrument", "ticker", "securitySymbol"),
            "",
        )
        or ""
    ).strip().upper()
    if not symbol:
        return None

    status = str(_first_present(raw, ("status",), "") or "").strip().upper()
    open_raw = _first_present(raw, ("openQuantity", "open_quantity"), None)
    quantity_raw = _first_present(
        raw,
        ("quantity", "totalQuantity", "total_quantity"),
        None,
    )
    if open_raw is not None:
        quantity = _nonnegative_int(open_raw)
    elif quantity_raw is not None:
        quantity = _nonnegative_int(quantity_raw)
    else:
        accumulated = _nonnegative_int(
            _first_present(
                raw,
                ("accumulateQuantity", "accumulate_quantity"),
                0,
            )
        )
        closed = _nonnegative_int(
            _first_present(raw, ("closedQuantity", "closed_quantity"), 0)
        )
        quantity = max(accumulated - closed, 0)

    if quantity <= 0 or status in {"CLOSED", "CLOSE", "DONE", "SETTLED"}:
        return None

    sellable_raw = _first_present(
        raw,
        (
            "tradeQuantity",
            "trade_quantity",
            "availableQuantity",
            "available_quantity",
            "sellableQuantity",
            "sellable_quantity",
            "available",
        ),
        None,
    )
    sellable = quantity if sellable_raw is None else _nonnegative_int(sellable_raw)

    return {
        "symbol": symbol,
        "quantity": quantity,
        "sellable_quantity": min(max(sellable, 0), quantity),
        "average_cost_raw": _finite_float(
            _first_present(
                raw,
                (
                    "costPrice",
                    "cost_price",
                    "averageCostPrice",
                    "average_cost_price",
                    "averagePrice",
                    "average_price",
                    "avgPrice",
                    "breakEvenPrice",
                    "break_even_price",
                ),
                0.0,
            )
        ),
        "broker_market_price_raw": _finite_float(
            _first_present(
                raw,
                (
                    "marketPrice",
                    "market_price",
                    "currentPrice",
                    "current_price",
                    "price",
                    "closePrice",
                    "close_price",
                ),
                0.0,
            )
        ),
        "status": status or "OPEN",
        "modified_at": str(
            _first_present(raw, ("modifiedDate", "modified_date"), "") or ""
        )
        or None,
        "source_fields": sorted(str(key) for key in raw.keys()),
    }


def _price_vnd(raw: float, reference_vnd: float) -> float:
    if raw <= 0:
        return 0.0
    candidates = (raw, raw * 1000.0)
    if reference_vnd <= 0:
        return raw * 1000.0 if raw < 1000.0 else raw
    return min(candidates, key=lambda candidate: abs(candidate / reference_vnd - 1.0))


def _local_prices(symbols: Sequence[str]) -> tuple[str | None, dict[str, float]]:
    market_db = paths().market_db
    if not market_db.is_file():
        return None, {}
    multiplier = float(load_config().get("model", {}).get("price_multiplier", 1000.0))
    with sqlite3.connect(market_db) as db:
        day_row = db.execute(
            "SELECT MAX(day) FROM bars WHERE upper(asset_type)='INDEX'"
        ).fetchone()
        market_day = str(day_row[0]) if day_row and day_row[0] else None
        prices: dict[str, float] = {}
        for symbol in sorted(set(symbols)):
            row = db.execute(
                """
                SELECT close FROM bars
                WHERE upper(asset_type)='STOCK' AND symbol=?
                ORDER BY day DESC LIMIT 1
                """,
                (symbol,),
            ).fetchone()
            if row is not None:
                prices[symbol] = float(row[0]) * multiplier
        return market_day, prices


def _patched_reader_positions(self, account_no: str) -> list[Mapping[str, object]]:
    """Accept both documented ``positions`` and SDK ``deals`` response keys."""

    module = __import__(
        "he_thong_dinh_luong.dnse_portfolio",
        fromlist=["_extract_list"],
    )
    payload = self.get(
        f"/accounts/{account_no}/positions",
        params={"marketType": "STOCK", "pageSize": 1000},
    )
    return module._extract_list(payload, "positions", "deals")


def _probe_accounts(reader) -> list[dict[str, object]]:
    raw_accounts = list(reader.accounts())
    result: list[dict[str, object]] = []
    selected_token = _read_account_selection()
    for account in raw_accounts:
        account_no = _account_id(account)
        if not account_no:
            continue
        token = _account_token(account_no)
        balance: object = {}
        positions_payload: list[Mapping[str, object]] = []
        balance_error = None
        positions_error = None
        try:
            balance = reader.balances(account_no)
        except Exception as exc:
            balance_error = f"{type(exc).__name__}:{exc}"
        try:
            positions_payload = list(reader.positions(account_no))
        except Exception as exc:
            positions_error = f"{type(exc).__name__}:{exc}"

        normalized = [
            row
            for row in (normalize_position_v49(item) for item in positions_payload)
            if row is not None
        ]
        available = _find_number(balance, ("availableCash", "available_cash"))
        withdrawable = _find_number(
            balance,
            ("withdrawableCash", "withdrawable_cash"),
        )
        total_cash = _find_number(balance, ("totalCash", "total_cash"))
        stock_balance_present = any(
            value is not None for value in (available, withdrawable, total_cash)
        )
        readable = bool(
            (balance_error is None and stock_balance_present)
            or (positions_error is None and normalized)
        )
        result.append(
            {
                "account_no": account_no,
                "selection_token": token,
                "masked_account": _mask_account(account_no),
                "selected": token == selected_token,
                "readable": readable,
                "balance_ok": balance_error is None and stock_balance_present,
                "positions_ok": positions_error is None,
                "balance_error": balance_error,
                "positions_error": positions_error,
                "balance": balance,
                "positions_payload": positions_payload,
                "normalized_positions": normalized,
                "available_cash_vnd": max(available or 0.0, 0.0),
                "withdrawable_cash_vnd": max(withdrawable or 0.0, 0.0),
                "total_cash_vnd": max(total_cash or 0.0, 0.0),
                "raw_position_count": len(positions_payload),
                "open_position_count": len(normalized),
                "stock_balance_present": stock_balance_present,
                "account_fields": sorted(str(key) for key in account.keys()),
                "balance_fields": (
                    sorted(str(key) for key in balance.keys())
                    if isinstance(balance, Mapping)
                    else []
                ),
            }
        )
    return result


def _safe_account_option(row: Mapping[str, object]) -> dict[str, object]:
    return {
        key: row.get(key)
        for key in (
            "selection_token",
            "masked_account",
            "selected",
            "readable",
            "balance_ok",
            "positions_ok",
            "available_cash_vnd",
            "withdrawable_cash_vnd",
            "total_cash_vnd",
            "raw_position_count",
            "open_position_count",
            "stock_balance_present",
            "account_fields",
            "balance_fields",
        )
    }


def broker_account_options() -> dict[str, object]:
    reader, credential_source = data_sources.reader_from_saved_credentials()
    try:
        rows = _probe_accounts(reader)
    finally:
        reader.close()
    return {
        "status": "SUCCESS",
        "credential_source": credential_source,
        "selection_required": len([row for row in rows if row["readable"]]) > 1
        and not any(row["selected"] for row in rows),
        "accounts": [_safe_account_option(row) for row in rows],
        "stores_full_account_number": False,
    }


def select_broker_account(selection_token: str) -> dict[str, object]:
    token = str(selection_token or "").strip()
    if not token:
        raise ValueError("DNSE_ACCOUNT_SELECTION_TOKEN_REQUIRED")
    reader, _ = data_sources.reader_from_saved_credentials()
    try:
        rows = _probe_accounts(reader)
    finally:
        reader.close()
    selected = next(
        (row for row in rows if row["selection_token"] == token and row["readable"]),
        None,
    )
    if selected is None:
        raise ValueError("DNSE_ACCOUNT_SELECTION_INVALID")
    _write_account_selection(token)
    return {
        "status": "SUCCESS",
        "selection_token": token,
        "masked_account": selected["masked_account"],
        "message": f"Đã chọn tiểu khoản {selected['masked_account']}.",
        "stores_full_account_number": False,
    }


def _choose_account(rows: Sequence[Mapping[str, object]]) -> Mapping[str, object]:
    readable = [row for row in rows if row.get("readable")]
    if not readable:
        raise ValueError("DNSE_ACCOUNT_READ_FAILED")
    selected_token = _read_account_selection()
    if selected_token:
        selected = next(
            (row for row in readable if row.get("selection_token") == selected_token),
            None,
        )
        if selected is not None:
            return selected
    if len(readable) == 1:
        _write_account_selection(str(readable[0]["selection_token"]))
        return readable[0]

    with_positions = [
        row for row in readable if int(row.get("open_position_count") or 0) > 0
    ]
    if len(with_positions) == 1:
        _write_account_selection(str(with_positions[0]["selection_token"]))
        return with_positions[0]
    raise ValueError(
        "DNSE_ACCOUNT_SELECTION_REQUIRED:"
        + json.dumps(
            [_safe_account_option(row) for row in readable],
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def _ensure_broker_schema_v49(db: sqlite3.Connection) -> None:
    broker_portfolio._ensure_schema(db)
    existing_snapshot = {
        str(row[1]) for row in db.execute("PRAGMA table_info(broker_snapshots)").fetchall()
    }
    snapshot_columns = {
        "selected_account_token": "TEXT",
        "broker_stock_value_vnd": "REAL NOT NULL DEFAULT 0",
        "broker_nav_vnd": "REAL NOT NULL DEFAULT 0",
        "research_eod_stock_value_vnd": "REAL NOT NULL DEFAULT 0",
        "research_eod_nav_vnd": "REAL NOT NULL DEFAULT 0",
        "source_freshness": "TEXT",
    }
    for name, definition in snapshot_columns.items():
        if name not in existing_snapshot:
            db.execute(f"ALTER TABLE broker_snapshots ADD COLUMN {name} {definition}")

    existing_position = {
        str(row[1]) for row in db.execute("PRAGMA table_info(broker_positions)").fetchall()
    }
    position_columns = {
        "broker_market_value_vnd": "REAL NOT NULL DEFAULT 0",
        "research_eod_market_value_vnd": "REAL NOT NULL DEFAULT 0",
        "research_eod_unrealized_pnl_vnd": "REAL NOT NULL DEFAULT 0",
        "research_eod_unrealized_pnl_pct": "REAL NOT NULL DEFAULT 0",
        "position_status": "TEXT",
        "broker_modified_at": "TEXT",
    }
    for name, definition in position_columns.items():
        if name not in existing_position:
            db.execute(f"ALTER TABLE broker_positions ADD COLUMN {name} {definition}")


def sync_broker_portfolio_v49() -> dict[str, object]:
    reader, credential_source = data_sources.reader_from_saved_credentials()
    try:
        probed = _probe_accounts(reader)
        selected = _choose_account(probed)
    finally:
        reader.close()

    positions_payload = list(selected["normalized_positions"])
    market_day, local_prices = _local_prices([str(row["symbol"]) for row in positions_payload])
    positions: list[dict[str, object]] = []
    for raw in positions_payload:
        symbol = str(raw["symbol"])
        quantity = int(raw["quantity"])
        local_price = float(local_prices.get(symbol, 0.0))
        broker_price = _price_vnd(float(raw["broker_market_price_raw"]), local_price)
        average_cost = _price_vnd(
            float(raw["average_cost_raw"]), broker_price or local_price
        )
        valuation_price = broker_price or local_price
        broker_market_value = broker_price * quantity if broker_price > 0 else 0.0
        research_market_value = local_price * quantity if local_price > 0 else 0.0
        market_value = valuation_price * quantity
        pnl = market_value - average_cost * quantity
        pnl_pct = pnl / (average_cost * quantity) if average_cost > 0 else 0.0
        research_pnl = research_market_value - average_cost * quantity
        research_pnl_pct = (
            research_pnl / (average_cost * quantity) if average_cost > 0 else 0.0
        )
        positions.append(
            {
                "symbol": symbol,
                "quantity": quantity,
                "sellable_quantity": int(raw["sellable_quantity"]),
                "average_cost_vnd": round(average_cost, 2),
                "broker_market_price_vnd": round(broker_price, 2),
                "local_market_price_vnd": round(local_price, 2),
                "valuation_price_vnd": round(valuation_price, 2),
                "market_value_vnd": round(market_value, 2),
                "unrealized_pnl_vnd": round(pnl, 2),
                "unrealized_pnl_pct": pnl_pct,
                "account_count": 1,
                "broker_market_value_vnd": round(broker_market_value, 2),
                "research_eod_market_value_vnd": round(research_market_value, 2),
                "research_eod_unrealized_pnl_vnd": round(research_pnl, 2),
                "research_eod_unrealized_pnl_pct": research_pnl_pct,
                "position_status": raw["status"],
                "broker_modified_at": raw["modified_at"],
            }
        )

    available_cash = float(selected["available_cash_vnd"])
    withdrawable_cash = float(selected["withdrawable_cash_vnd"])
    total_cash = float(selected["total_cash_vnd"])
    planner_cash = (
        available_cash
        if selected["balance_ok"]
        else withdrawable_cash
        if withdrawable_cash > 0
        else total_cash
    )
    broker_stock_value = sum(float(row["broker_market_value_vnd"]) for row in positions)
    research_stock_value = sum(
        float(row["research_eod_market_value_vnd"]) for row in positions
    )
    broker_nav = total_cash + broker_stock_value
    research_nav = total_cash + research_stock_value
    snapshot_id = "broker-" + datetime.now(VN_TZ).strftime("%Y%m%d-%H%M%S-%f")
    captured_at = utc_now()
    masked = str(selected["masked_account"])
    account_options = [_safe_account_option(row) for row in probed]
    details = {
        "version": V49_VERSION,
        "credential_source": credential_source,
        "selected_masked_account": masked,
        "selected_account_token": selected["selection_token"],
        "account_selection_mode": "PERSISTED_OR_AUTO_SINGLE_CURRENT_ACCOUNT",
        "account_options": account_options,
        "raw_account_count": len(probed),
        "readable_account_count": sum(bool(row["readable"]) for row in probed),
        "selected_raw_position_count": selected["raw_position_count"],
        "selected_open_position_count": selected["open_position_count"],
        "selected_account_fields": selected["account_fields"],
        "selected_balance_fields": selected["balance_fields"],
        "quantity_rule": "OPEN_QUANTITY_PRESERVE_ZERO",
        "sellable_rule": "TRADE_QUANTITY_PRESERVE_ZERO",
        "planner_cash_source": (
            "AVAILABLE_CASH"
            if selected["balance_ok"]
            else "WITHDRAWABLE_OR_TOTAL_FALLBACK"
        ),
        "valuation_source": "BROKER_MARKET_PRICE_FALLBACK_RESEARCH_EOD",
        "research_valuation_source": "LOCAL_EOD_CLOSE",
        "read_only": True,
        "full_account_number_persisted": False,
    }

    with state_db() as db:
        _ensure_broker_schema_v49(db)
        db.execute(
            """
            INSERT INTO broker_snapshots(
                snapshot_id,captured_at,source,masked_accounts_json,
                total_cash_vnd,available_cash_vnd,withdrawable_cash_vnd,
                planner_cash_vnd,stock_value_vnd,net_asset_value_vnd,
                position_count,market_day,details_json,
                selected_account_token,broker_stock_value_vnd,broker_nav_vnd,
                research_eod_stock_value_vnd,research_eod_nav_vnd,
                source_freshness
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                snapshot_id,
                captured_at,
                "DNSE_OPENAPI_READ_ONLY_V49",
                json.dumps([masked], ensure_ascii=False),
                total_cash,
                available_cash,
                withdrawable_cash,
                planner_cash,
                broker_stock_value,
                broker_nav,
                len(positions),
                market_day,
                json.dumps(details, ensure_ascii=False, sort_keys=True),
                selected["selection_token"],
                broker_stock_value,
                broker_nav,
                research_stock_value,
                research_nav,
                "BROKER_SNAPSHOT_AT_REQUEST_TIME",
            ),
        )
        db.executemany(
            """
            INSERT INTO broker_positions(
                snapshot_id,symbol,quantity,sellable_quantity,
                average_cost_vnd,broker_market_price_vnd,
                local_market_price_vnd,valuation_price_vnd,
                market_value_vnd,unrealized_pnl_vnd,unrealized_pnl_pct,
                account_count,broker_market_value_vnd,
                research_eod_market_value_vnd,
                research_eod_unrealized_pnl_vnd,
                research_eod_unrealized_pnl_pct,
                position_status,broker_modified_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    snapshot_id,
                    row["symbol"],
                    row["quantity"],
                    row["sellable_quantity"],
                    row["average_cost_vnd"],
                    row["broker_market_price_vnd"],
                    row["local_market_price_vnd"],
                    row["valuation_price_vnd"],
                    row["market_value_vnd"],
                    row["unrealized_pnl_vnd"],
                    row["unrealized_pnl_pct"],
                    1,
                    row["broker_market_value_vnd"],
                    row["research_eod_market_value_vnd"],
                    row["research_eod_unrealized_pnl_vnd"],
                    row["research_eod_unrealized_pnl_pct"],
                    row["position_status"],
                    row["broker_modified_at"],
                )
                for row in positions
            ],
        )

    current = account_snapshot()
    replace_account(
        cash_vnd=max(planner_cash, 0.0),
        weekly_contribution_vnd=float(current["account"]["weekly_contribution_vnd"]),
        holdings=[
            {
                "symbol": row["symbol"],
                "quantity": row["quantity"],
                "average_cost": row["average_cost_vnd"],
            }
            for row in positions
        ],
    )
    result = latest_broker_portfolio_v49()
    if result is None:
        raise RuntimeError("DNSE_BROKER_SNAPSHOT_READBACK_FAILED")
    return result


def latest_broker_portfolio_v49() -> dict[str, object] | None:
    with state_db() as db:
        _ensure_broker_schema_v49(db)
        snapshot = db.execute(
            "SELECT * FROM broker_snapshots ORDER BY captured_at DESC LIMIT 1"
        ).fetchone()
        if snapshot is None:
            return None
        positions = [
            dict(row)
            for row in db.execute(
                """
                SELECT * FROM broker_positions
                WHERE snapshot_id=?
                ORDER BY market_value_vnd DESC,symbol
                """,
                (snapshot["snapshot_id"],),
            ).fetchall()
        ]
    result = dict(snapshot)
    result["masked_accounts"] = json.loads(str(result.pop("masked_accounts_json")))
    result["details"] = json.loads(str(result.pop("details_json")))
    result["positions"] = positions
    result["status"] = "SUCCESS"
    selected_masked = result["details"].get("selected_masked_account") or (
        result["masked_accounts"][0] if result["masked_accounts"] else "—"
    )
    result["message"] = (
        f"Đã đồng bộ {result['position_count']} mã từ tiểu khoản {selected_masked}."
    )
    result["version"] = result["details"].get("version") or "LEGACY"
    result["research_only"] = True
    result["automatic_live_orders_allowed"] = False
    return result


def _extract_iso_dates(payload: object) -> set[date]:
    result: set[date] = set()
    if isinstance(payload, Mapping):
        for value in payload.values():
            result.update(_extract_iso_dates(value))
    elif isinstance(payload, list):
        for value in payload:
            result.update(_extract_iso_dates(value))
    elif isinstance(payload, str):
        try:
            result.add(date.fromisoformat(payload[:10]))
        except ValueError:
            pass
    return result


def _working_dates(source, today: date) -> tuple[list[date], str | None]:
    try:
        response = source._client().get("/market/working-dates")
        dates = sorted(day for day in _extract_iso_dates(response.json()) if day <= today)
        if dates:
            return dates, None
        return [], "DNSE_WORKING_DATES_EMPTY"
    except Exception as exc:
        return [], f"{type(exc).__name__}:{exc}"


def expected_final_session(
    *,
    now_vn: datetime,
    working_dates: Sequence[date],
) -> date | None:
    eligible = sorted(day for day in working_dates if day <= now_vn.date())
    if not eligible:
        return None
    latest = eligible[-1]
    if latest < now_vn.date() or now_vn.time() >= EOD_READY_TIME:
        return latest
    previous = [day for day in eligible if day < now_vn.date()]
    return previous[-1] if previous else None


def _bar_digest(row) -> str:
    payload = (
        row.symbol,
        row.day.isoformat(),
        float(row.open),
        float(row.high),
        float(row.low),
        float(row.close),
        int(row.volume),
    )
    return sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _ensure_market_schema_v49(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS market_source_revisions_v49(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_type TEXT NOT NULL,
            symbol TEXT NOT NULL,
            day TEXT NOT NULL,
            old_json TEXT NOT NULL,
            new_json TEXT NOT NULL,
            detected_at TEXT NOT NULL,
            policy TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS market_sync_runs_v49(
            run_id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            requested_start TEXT NOT NULL,
            requested_end TEXT NOT NULL,
            expected_final_session TEXT,
            latest_index_day TEXT,
            latest_stock_day TEXT,
            source_freshness TEXT NOT NULL,
            details_json TEXT NOT NULL
        );
        """
    )


def _upsert_market_row(
    db: sqlite3.Connection,
    *,
    asset_type: str,
    row,
    mutable_from: date,
    fetched_at: str,
) -> str:
    existing = db.execute(
        """
        SELECT open,high,low,close,volume FROM bars
        WHERE asset_type=? AND symbol=? AND day=?
        """,
        (asset_type, row.symbol, row.day.isoformat()),
    ).fetchone()
    incoming = {
        "open": float(row.open),
        "high": float(row.high),
        "low": float(row.low),
        "close": float(row.close),
        "volume": int(row.volume),
    }
    if existing is None:
        db.execute(
            """
            INSERT INTO bars(
                asset_type,symbol,day,open,high,low,close,volume,
                source,source_version,price_basis,normalized_sha256,fetched_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                asset_type,
                row.symbol,
                row.day.isoformat(),
                incoming["open"],
                incoming["high"],
                incoming["low"],
                incoming["close"],
                incoming["volume"],
                row.source,
                row.version,
                "CHUA_XAC_NHAN",
                _bar_digest(row),
                fetched_at,
            ),
        )
        return "INSERTED"

    previous = {
        "open": float(existing[0]),
        "high": float(existing[1]),
        "low": float(existing[2]),
        "close": float(existing[3]),
        "volume": int(existing[4]),
    }
    if previous == incoming:
        return "IDENTICAL"
    if row.day < mutable_from:
        raise ValueError(f"DNSE_STORE_HISTORICAL_CONFLICT:{row.symbol}:{row.day}")
    db.execute(
        """
        INSERT INTO market_source_revisions_v49(
            asset_type,symbol,day,old_json,new_json,detected_at,policy
        ) VALUES(?,?,?,?,?,?,?)
        """,
        (
            asset_type,
            row.symbol,
            row.day.isoformat(),
            json.dumps(previous, sort_keys=True),
            json.dumps(incoming, sort_keys=True),
            fetched_at,
            "RECENT_SESSION_SOURCE_REVISION_ALLOWED",
        ),
    )
    db.execute(
        """
        UPDATE bars
        SET open=?,high=?,low=?,close=?,volume=?,source=?,
            source_version=?,normalized_sha256=?,fetched_at=?
        WHERE asset_type=? AND symbol=? AND day=?
        """,
        (
            incoming["open"],
            incoming["high"],
            incoming["low"],
            incoming["close"],
            incoming["volume"],
            row.source,
            row.version,
            _bar_digest(row),
            fetched_at,
            asset_type,
            row.symbol,
            row.day.isoformat(),
        ),
    )
    return "REVISED"


def _quarantine_rows_after_expected(
    db: sqlite3.Connection,
    *,
    expected: date | None,
    detected_at: str,
) -> int:
    if expected is None:
        return 0
    rows = db.execute(
        """
        SELECT asset_type,symbol,day,open,high,low,close,volume
        FROM bars WHERE day>? ORDER BY day,symbol
        """,
        (expected.isoformat(),),
    ).fetchall()
    for row in rows:
        previous = {
            "open": float(row[3]),
            "high": float(row[4]),
            "low": float(row[5]),
            "close": float(row[6]),
            "volume": int(row[7]),
        }
        db.execute(
            """
            INSERT INTO market_source_revisions_v49(
                asset_type,symbol,day,old_json,new_json,detected_at,policy
            ) VALUES(?,?,?,?,?,?,?)
            """,
            (
                str(row[0]),
                str(row[1]),
                str(row[2]),
                json.dumps(previous, sort_keys=True),
                json.dumps({"quarantined": True}, sort_keys=True),
                detected_at,
                "INCOMPLETE_SESSION_QUARANTINED",
            ),
        )
    if rows:
        db.execute("DELETE FROM bars WHERE day>?", (expected.isoformat(),))
    return len(rows)


def _latest_market_rows(db: sqlite3.Connection) -> tuple[str | None, str | None]:
    index = db.execute(
        "SELECT MAX(day) FROM bars WHERE upper(asset_type)='INDEX'"
    ).fetchone()[0]
    stock = db.execute(
        "SELECT MAX(day) FROM bars WHERE upper(asset_type)='STOCK'"
    ).fetchone()[0]
    return str(index) if index else None, str(stock) if stock else None


def market_source_integrity_status() -> dict[str, object]:
    market_db = paths().market_db
    last_sync = None
    with state_db() as db:
        row = db.execute(
            "SELECT value,updated_at FROM metadata WHERE key='last_market_sync'"
        ).fetchone()
        if row is not None:
            try:
                last_sync = json.loads(str(row["value"]))
            except (TypeError, ValueError, json.JSONDecodeError):
                last_sync = None
    latest_index = None
    latest_stock = None
    if market_db.is_file():
        with sqlite3.connect(market_db) as db:
            latest_index, latest_stock = _latest_market_rows(db)
    return {
        "status": "SUCCESS",
        "version": V49_VERSION,
        "latest_index_day": latest_index,
        "latest_stock_day": latest_stock,
        "last_sync": last_sync,
    }


def sync_incremental_market_data_local_v49(
    *,
    end: date | None = None,
    lookback_days: int = DEFAULT_REFRESH_LOOKBACK_DAYS,
) -> dict[str, object]:
    market_db = paths().market_db
    if not market_db.is_file():
        raise FileNotFoundError("Chưa bootstrap market database local")
    now_vn = datetime.now(VN_TZ)
    final_end = end or now_vn.date()
    with sqlite3.connect(market_db) as db:
        symbols = [
            str(row[0])
            for row in db.execute(
                """
                SELECT DISTINCT symbol FROM bars
                WHERE upper(asset_type)='STOCK' ORDER BY symbol
                """
            ).fetchall()
        ]
        last_index, last_stock = _latest_market_rows(db)
    if not symbols:
        raise ValueError("Local market store không có dữ liệu STOCK")

    latest_known = max(
        [date.fromisoformat(day) for day in (last_index, last_stock) if day],
        default=final_end,
    )
    requested_start = min(latest_known + timedelta(days=1), final_end)
    requested_start -= timedelta(days=max(int(lookback_days), RECENT_MUTABLE_DAYS))
    mutable_from = requested_start

    source, credential_source = data_sources.source_from_saved_credentials()
    started_at = utc_now()
    try:
        working_dates, working_error = _working_dates(source, final_end)
        if not working_dates:
            working_dates = [
                requested_start + timedelta(days=offset)
                for offset in range((final_end - requested_start).days + 1)
                if (requested_start + timedelta(days=offset)).weekday() < 5
            ]
        expected = expected_final_session(
            now_vn=(
                now_vn
                if end is None
                else datetime.combine(final_end, EOD_READY_TIME, VN_TZ)
            ),
            working_dates=working_dates,
        )

        fetched: list[tuple[str, object]] = []
        index_rows = tuple(
            source.fetch("VNINDEX", requested_start, final_end, is_index=True)
        )
        fetched.extend(
            ("INDEX", row)
            for row in index_rows
            if expected is None or row.day <= expected
        )
        per_symbol_latest: dict[str, str | None] = {}
        errors: dict[str, str] = {}
        for symbol in symbols:
            try:
                rows = tuple(source.fetch(symbol, requested_start, final_end))
            except Exception as exc:
                errors[symbol] = f"{type(exc).__name__}:{exc}"
                continue
            eligible_rows = [
                row for row in rows if expected is None or row.day <= expected
            ]
            fetched.extend(("STOCK", row) for row in eligible_rows)
            per_symbol_latest[symbol] = (
                eligible_rows[-1].day.isoformat() if eligible_rows else None
            )
    finally:
        source.close()

    counts = {"INSERTED": 0, "IDENTICAL": 0, "REVISED": 0}
    fetched_at = utc_now()
    with sqlite3.connect(market_db) as db:
        _ensure_market_schema_v49(db)
        db.execute("BEGIN IMMEDIATE")
        try:
            quarantined_row_count = _quarantine_rows_after_expected(
                db,
                expected=expected,
                detected_at=fetched_at,
            )
            for asset_type, row in fetched:
                action = _upsert_market_row(
                    db,
                    asset_type=asset_type,
                    row=row,
                    mutable_from=mutable_from,
                    fetched_at=fetched_at,
                )
                counts[action] += 1
            latest_index, latest_stock = _latest_market_rows(db)
            expected_text = expected.isoformat() if expected else None
            coverage_count = (
                int(
                    db.execute(
                        """
                        SELECT COUNT(DISTINCT symbol) FROM bars
                        WHERE upper(asset_type)='STOCK' AND day=?
                        """,
                        (expected_text,),
                    ).fetchone()[0]
                )
                if expected_text
                else 0
            )
            coverage_ratio = coverage_count / max(len(symbols), 1)
            if expected_text is None:
                freshness = "EXPECTED_SESSION_UNKNOWN"
            elif latest_index == expected_text and coverage_ratio >= MIN_SESSION_COVERAGE_RATIO:
                freshness = "CURRENT_FINAL_EOD"
            elif latest_index == expected_text:
                freshness = "PARTIAL_STOCK_COVERAGE"
            else:
                freshness = "SOURCE_LAGGING_OR_EMPTY"
            run_id = "market-v49-" + uuid4().hex
            details = {
                "version": V49_VERSION,
                "credential_source": credential_source,
                "working_dates_error": working_error,
                "working_dates_source": (
                    "DNSE_/market/working-dates"
                    if working_error is None
                    else "WEEKDAY_FALLBACK"
                ),
                "requested_symbol_count": len(symbols),
                "symbol_error_count": len(errors),
                "symbol_errors": errors,
                "expected_session_stock_count": coverage_count,
                "expected_session_coverage_ratio": coverage_ratio,
                "actions": counts,
                "quarantined_incomplete_row_count": quarantined_row_count,
                "stale_fetched_ranges_ignored": True,
                "recent_sessions_refetched_every_run": True,
                "recent_source_revisions_allowed_from": mutable_from.isoformat(),
                "per_symbol_latest": per_symbol_latest,
            }
            db.execute(
                """
                INSERT INTO market_sync_runs_v49(
                    run_id,started_at,requested_start,requested_end,
                    expected_final_session,latest_index_day,latest_stock_day,
                    source_freshness,details_json
                ) VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    run_id,
                    started_at,
                    requested_start.isoformat(),
                    final_end.isoformat(),
                    expected_text,
                    latest_index,
                    latest_stock,
                    freshness,
                    json.dumps(details, ensure_ascii=False, sort_keys=True),
                ),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

    result = {
        "status": "SUCCESS",
        "message": (
            f"Đồng bộ EOD xong: kỳ vọng {expected_text or 'không xác định'}, "
            f"VNINDEX mới nhất {latest_index or 'chưa có'}."
        ),
        "version": V49_VERSION,
        "credential_source": credential_source,
        "requested_start": requested_start.isoformat(),
        "requested_end": final_end.isoformat(),
        "expected_final_session": expected_text,
        "latest_index_day": latest_index,
        "latest_stock_day": latest_stock,
        "source_freshness": freshness,
        "expected_session_stock_count": coverage_count,
        "expected_session_stock_coverage_ratio": coverage_ratio,
        "inserted_row_count": counts["INSERTED"],
        "identical_row_count": counts["IDENTICAL"],
        "revised_row_count": counts["REVISED"],
        "quarantined_incomplete_row_count": quarantined_row_count,
        "symbol_error_count": len(errors),
        "stale_fetched_ranges_ignored": True,
    }
    with state_db() as state:
        state.execute(
            """
            INSERT INTO metadata(key,value,updated_at)
            VALUES(?,?,?)
            ON CONFLICT(key) DO UPDATE
            SET value=excluded.value,updated_at=excluded.updated_at
            """,
            ("last_market_sync", json.dumps(result, sort_keys=True), utc_now()),
        )
    return result


def credential_status_v49(
    secret_path=data_sources.SECRET_PATH,
) -> dict[str, object]:
    assert _ORIGINAL_CREDENTIAL_STATUS is not None
    result = dict(_ORIGINAL_CREDENTIAL_STATUS(secret_path))
    result["source_integrity"] = market_source_integrity_status()
    result["source_integrity_version"] = V49_VERSION
    return result


def apply() -> None:
    if getattr(data_sources, "_v49_source_integrity_applied", False):
        return
    global _ORIGINAL_LATEST_BROKER, _ORIGINAL_CREDENTIAL_STATUS
    _ORIGINAL_LATEST_BROKER = broker_portfolio.latest_broker_portfolio
    _ORIGINAL_CREDENTIAL_STATUS = data_sources.credential_status

    portfolio_module = __import__(
        "he_thong_dinh_luong.dnse_portfolio",
        fromlist=["DnseReadOnlyClient"],
    )
    portfolio_module.DnseReadOnlyClient.positions = _patched_reader_positions

    data_sources.sync_incremental_market_data_local = sync_incremental_market_data_local_v49
    data_sources.credential_status = credential_status_v49
    broker_portfolio.sync_broker_portfolio = sync_broker_portfolio_v49
    broker_portfolio.latest_broker_portfolio = latest_broker_portfolio_v49
    broker_portfolio.broker_account_options = broker_account_options
    broker_portfolio.select_broker_account = select_broker_account
    data_sources.market_source_integrity_status = market_source_integrity_status
    data_sources.V49_VERSION = V49_VERSION
    data_sources._v49_source_integrity_applied = True
