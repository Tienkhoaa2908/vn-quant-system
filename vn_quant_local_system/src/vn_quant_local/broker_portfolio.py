"""Đồng bộ danh mục DNSE ở chế độ chỉ đọc.

Module không nhận trading token, không đặt lệnh và không lưu số tiểu khoản đầy đủ
trong output trả về trình duyệt. Holdings DNSE sau khi đồng bộ trở thành nguồn
trạng thái danh mục mặc định của workstation.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import json
import math
import sqlite3
from typing import Mapping, Sequence

from .core import account_snapshot, load_config, paths, replace_account, state_db, utc_now
from .data_sources import reader_from_saved_credentials


def _float(value: object, default: float = 0.0) -> float:
    try:
        result = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _int(value: object, default: int = 0) -> int:
    result = _float(value, float(default))
    return int(result) if result >= 0 else default


def _mask_account(value: str) -> str:
    text = str(value or "").strip()
    if len(text) <= 4:
        return "•" * len(text)
    return "•" * max(4, len(text) - 4) + text[-4:]


def _account_id(account: Mapping[str, object]) -> str:
    for key in (
        "id",
        "accountNo",
        "account_no",
        "accountId",
        "investorAccountId",
        "investor_account_id",
    ):
        value = str(account.get(key) or "").strip()
        if value:
            return value
    return ""


def _account_type_text(account: Mapping[str, object]) -> str:
    return " ".join(
        str(account.get(key) or "")
        for key in (
            "accountType",
            "accountTypeName",
            "account_type",
            "account_type_name",
            "type",
            "name",
        )
    ).strip()


def _is_explicit_derivative_account(account: Mapping[str, object]) -> bool:
    """Chỉ loại tài khoản được mô tả rõ là tài khoản phái sinh.

    Trường ``derivativeAccount`` trong payload DNSE biểu thị khách hàng đã đăng
    ký giao dịch phái sinh, không phải bản thân tiểu khoản đang xét là tiểu khoản
    phái sinh. Vì vậy tuyệt đối không dùng boolean đó để loại tài khoản cơ sở.
    """

    text = _account_type_text(account).upper()
    return any(
        marker in text
        for marker in (
            "DERIVATIVE",
            "DERIVATIVES",
            "DERIV",
            "PHÁI SINH",
            "PHAI SINH",
        )
    )


def _candidate_accounts(
    raw_accounts: Sequence[Mapping[str, object]],
) -> tuple[list[Mapping[str, object]], str]:
    identified = [account for account in raw_accounts if _account_id(account)]
    if not identified:
        return [], "NO_IDENTIFIED_ACCOUNT"
    non_derivative = [
        account for account in identified if not _is_explicit_derivative_account(account)
    ]
    if non_derivative:
        return non_derivative, "EXCLUDE_EXPLICIT_DERIVATIVE_TYPES"
    return identified, "FALLBACK_ALL_IDENTIFIED_ACCOUNTS"


def _account_diagnostic(account: Mapping[str, object]) -> dict[str, object]:
    account_no = _account_id(account)
    return {
        "masked_account": _mask_account(account_no),
        "account_type_name": _account_type_text(account) or None,
        "derivative_registration_flag": account.get("derivativeAccount"),
        "explicit_derivative_type": _is_explicit_derivative_account(account),
    }


def _find_number(payload: object, names: Sequence[str]) -> float | None:
    wanted = {name.lower() for name in names}
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if str(key).lower() in wanted:
                result = _float(value, float("nan"))
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


def _normalize_position(raw: Mapping[str, object]) -> dict[str, object] | None:
    symbol = str(
        raw.get("symbol")
        or raw.get("instrument")
        or raw.get("ticker")
        or raw.get("securitySymbol")
        or ""
    ).strip().upper()
    if not symbol:
        return None
    quantity = _int(
        raw.get("openQuantity")
        or raw.get("quantity")
        or raw.get("accumulateQuantity")
        or raw.get("tradeQuantity")
        or raw.get("totalQuantity")
    )
    if quantity <= 0:
        return None
    sellable = _int(
        raw.get("tradeQuantity")
        or raw.get("availableQuantity")
        or raw.get("sellableQuantity")
        or raw.get("available")
        or quantity
    )
    return {
        "symbol": symbol,
        "quantity": quantity,
        "sellable_quantity": min(max(sellable, 0), quantity),
        "average_cost_vnd": _float(
            raw.get("costPrice")
            or raw.get("averagePrice")
            or raw.get("avgPrice")
            or raw.get("breakEvenPrice")
        ),
        "broker_market_price_vnd": _float(
            raw.get("marketPrice")
            or raw.get("currentPrice")
            or raw.get("price")
            or raw.get("closePrice")
        ),
    }


def _price_vnd(raw: float, local_price_vnd: float) -> float:
    if raw <= 0:
        return local_price_vnd
    candidates = (raw, raw * 1000.0)
    if local_price_vnd <= 0:
        return raw * 1000.0 if raw < 1000.0 else raw
    return min(candidates, key=lambda candidate: abs(candidate / local_price_vnd - 1.0))


def _local_prices(symbols: Sequence[str]) -> tuple[str | None, dict[str, float]]:
    p = paths()
    if not p.market_db.is_file():
        return None, {}
    multiplier = float(load_config().get("model", {}).get("price_multiplier", 1000.0))
    db = sqlite3.connect(p.market_db)
    try:
        day_row = db.execute(
            "SELECT MAX(day) FROM bars WHERE upper(asset_type)='INDEX'"
        ).fetchone()
        day = str(day_row[0]) if day_row and day_row[0] else None
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
        return day, prices
    finally:
        db.close()


def _ensure_schema(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS broker_snapshots(
            snapshot_id TEXT PRIMARY KEY,
            captured_at TEXT NOT NULL,
            source TEXT NOT NULL,
            masked_accounts_json TEXT NOT NULL,
            total_cash_vnd REAL NOT NULL,
            available_cash_vnd REAL NOT NULL,
            withdrawable_cash_vnd REAL NOT NULL,
            planner_cash_vnd REAL NOT NULL,
            stock_value_vnd REAL NOT NULL,
            net_asset_value_vnd REAL NOT NULL,
            position_count INTEGER NOT NULL,
            market_day TEXT,
            details_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS broker_positions(
            snapshot_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            sellable_quantity INTEGER NOT NULL,
            average_cost_vnd REAL NOT NULL,
            broker_market_price_vnd REAL NOT NULL,
            local_market_price_vnd REAL NOT NULL,
            valuation_price_vnd REAL NOT NULL,
            market_value_vnd REAL NOT NULL,
            unrealized_pnl_vnd REAL NOT NULL,
            unrealized_pnl_pct REAL NOT NULL,
            account_count INTEGER NOT NULL,
            PRIMARY KEY(snapshot_id,symbol),
            FOREIGN KEY(snapshot_id) REFERENCES broker_snapshots(snapshot_id)
        );
        CREATE INDEX IF NOT EXISTS idx_broker_snapshots_time
        ON broker_snapshots(captured_at DESC);
        """
    )


def sync_broker_portfolio() -> dict[str, object]:
    reader, credential_source = reader_from_saved_credentials()
    try:
        raw_accounts = reader.accounts()
        accounts, account_selection_mode = _candidate_accounts(raw_accounts)
        if not accounts:
            raise ValueError("DNSE_ACCOUNT_LIST_EMPTY")

        raw_by_symbol: dict[str, list[dict[str, object]]] = defaultdict(list)
        masked_accounts: list[str] = []
        total_cash_values: list[float] = []
        available_cash_values: list[float] = []
        withdrawable_values: list[float] = []
        stock_values: list[float] = []
        nav_values: list[float] = []
        account_diagnostics: list[dict[str, object]] = []
        readable_account_count = 0

        for account in accounts:
            account_no = _account_id(account)
            diagnostic = _account_diagnostic(account)
            balance: object = {}
            positions_payload: list[Mapping[str, object]] = []
            balance_ok = False
            positions_ok = False

            try:
                balance = reader.balances(account_no)
                balance_ok = True
            except Exception as exc:
                diagnostic["balance_error"] = f"{type(exc).__name__}:{exc}"

            try:
                positions_payload = reader.positions(account_no)
                positions_ok = True
            except Exception as exc:
                diagnostic["positions_error"] = f"{type(exc).__name__}:{exc}"

            diagnostic["balance_ok"] = balance_ok
            diagnostic["positions_ok"] = positions_ok
            diagnostic["position_payload_count"] = len(positions_payload)
            account_diagnostics.append(diagnostic)

            if not (balance_ok or positions_ok):
                continue

            readable_account_count += 1
            masked_accounts.append(_mask_account(account_no))

            if balance_ok:
                total_cash_values.append(_find_number(balance, ("totalCash",)) or 0.0)
                available_value = _find_number(balance, ("availableCash",))
                withdrawable_value = _find_number(balance, ("withdrawableCash",))
                if available_value is not None:
                    available_cash_values.append(max(available_value, 0.0))
                if withdrawable_value is not None:
                    withdrawable_values.append(max(withdrawable_value, 0.0))
                stock_values.append(_find_number(balance, ("stockValue",)) or 0.0)
                nav_values.append(_find_number(balance, ("netAssetValue",)) or 0.0)

            if positions_ok:
                for raw in positions_payload:
                    normalized = _normalize_position(raw)
                    if normalized is not None:
                        normalized["masked_account"] = _mask_account(account_no)
                        raw_by_symbol[str(normalized["symbol"])].append(normalized)
    finally:
        reader.close()

    if readable_account_count <= 0:
        raise ValueError(
            "DNSE_ACCOUNT_READ_FAILED:"
            + json.dumps(account_diagnostics, ensure_ascii=False, sort_keys=True)
        )

    market_day, local_prices = _local_prices(list(raw_by_symbol))
    positions: list[dict[str, object]] = []
    for symbol in sorted(raw_by_symbol):
        parts = raw_by_symbol[symbol]
        quantity = sum(int(part["quantity"]) for part in parts)
        sellable = sum(int(part["sellable_quantity"]) for part in parts)
        local_price = local_prices.get(symbol, 0.0)
        cost_total = 0.0
        broker_market_values: list[float] = []
        for part in parts:
            raw_cost = _price_vnd(float(part["average_cost_vnd"]), local_price)
            cost_total += raw_cost * int(part["quantity"])
            broker_price = _price_vnd(float(part["broker_market_price_vnd"]), local_price)
            if broker_price > 0:
                broker_market_values.append(broker_price)
        average_cost = cost_total / quantity if quantity > 0 else 0.0
        broker_price = broker_market_values[-1] if broker_market_values else 0.0
        valuation_price = local_price or broker_price
        market_value = valuation_price * quantity
        pnl = market_value - average_cost * quantity
        pnl_pct = pnl / (average_cost * quantity) if average_cost > 0 and quantity > 0 else 0.0
        positions.append(
            {
                "symbol": symbol,
                "quantity": quantity,
                "sellable_quantity": min(sellable, quantity),
                "average_cost_vnd": round(average_cost, 2),
                "broker_market_price_vnd": round(broker_price, 2),
                "local_market_price_vnd": round(local_price, 2),
                "valuation_price_vnd": round(valuation_price, 2),
                "market_value_vnd": round(market_value, 2),
                "unrealized_pnl_vnd": round(pnl, 2),
                "unrealized_pnl_pct": pnl_pct,
                "account_count": len({str(part["masked_account"]) for part in parts}),
            }
        )

    total_cash = sum(total_cash_values)
    available_cash = sum(available_cash_values)
    withdrawable_cash = sum(withdrawable_values)
    if available_cash_values and withdrawable_values:
        planner_cash = min(available_cash, withdrawable_cash)
    elif available_cash_values:
        planner_cash = available_cash
    elif withdrawable_values:
        planner_cash = withdrawable_cash
    else:
        planner_cash = max(total_cash, 0.0)
    stock_value = sum(float(row["market_value_vnd"]) for row in positions)
    broker_stock_value = sum(stock_values)
    nav = sum(nav_values) or (planner_cash + stock_value)

    snapshot_id = "broker-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    captured_at = utc_now()
    details = {
        "credential_source": credential_source,
        "raw_account_count": len(raw_accounts),
        "candidate_account_count": len(accounts),
        "readable_account_count": readable_account_count,
        "account_selection_mode": account_selection_mode,
        "masked_accounts": sorted(set(masked_accounts)),
        "account_diagnostics": account_diagnostics,
        "broker_reported_stock_value_vnd": broker_stock_value,
        "valuation_source": "LOCAL_EOD_CLOSE_FALLBACK_BROKER_PRICE",
        "derivative_registration_flag_is_not_account_type": True,
        "read_only": True,
    }
    with state_db() as db:
        _ensure_schema(db)
        db.execute(
            "INSERT INTO broker_snapshots VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                snapshot_id,
                captured_at,
                "DNSE_OPENAPI_READ_ONLY",
                json.dumps(sorted(set(masked_accounts)), ensure_ascii=False),
                total_cash,
                available_cash,
                withdrawable_cash,
                planner_cash,
                stock_value,
                nav,
                len(positions),
                market_day,
                json.dumps(details, ensure_ascii=False, sort_keys=True),
            ),
        )
        db.executemany(
            "INSERT INTO broker_positions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
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
                    row["account_count"],
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
    return latest_broker_portfolio() or {
        "status": "FAILED",
        "message": "Không đọc lại được snapshot vừa lưu.",
    }


def latest_broker_portfolio() -> dict[str, object] | None:
    with state_db() as db:
        _ensure_schema(db)
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
    result["message"] = (
        f"Đã đồng bộ {result['position_count']} mã từ "
        f"{result['details'].get('readable_account_count', 0)} tiểu khoản đọc được."
    )
    result["research_only"] = True
    result["automatic_live_orders_allowed"] = False
    return result
