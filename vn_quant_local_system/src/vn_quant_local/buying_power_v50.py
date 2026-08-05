"""V50 authoritative DNSE buying-power integration.

The broker balance endpoint exposes settled/available cash, while DNSE's PPSE
endpoint exposes the amount that can actually be reused for a new order,
including eligible unsettled sell proceeds.  V50 keeps both concepts separate:

* ``available_cash_vnd`` remains the cash field reported by the account balance;
* the planner uses a read-only, non-margin PPSE snapshot when the endpoint is
  available;
* each candidate is additionally capped by DNSE's symbol/price-specific qmax;
* no trading token is accepted and no write/order endpoint is called.

If PPSE cannot be read with the configured OpenAPI credentials, the system falls
back to available cash and records the capability failure explicitly.  It never
estimates sell proceeds from position deltas.
"""
from __future__ import annotations

from datetime import datetime
import json
import math
import re
import sqlite3
from typing import Mapping, Sequence
from uuid import uuid4

from . import broker_portfolio, capital_plan, data_sources, weekly_plan
from .core import paths, state_db, utc_now
from .source_integrity_v49 import (
    V49_VERSION,
    _choose_account,
    _first_present,
    _probe_accounts,
)

V50_VERSION = "V50_DNSE_AUTHORITATIVE_BUYING_POWER"
BUYING_POWER_SOURCE = "DNSE_PPSE_NON_MARGIN_READ_ONLY"
FALLBACK_SOURCE = "AVAILABLE_CASH_FALLBACK"

_LOAN_PACKAGES = re.compile(
    r"^/order-service/v2/accounts/[A-Za-z0-9_-]+/loan-packages$"
)
_PPSE = re.compile(
    r"^/order-service/accounts/[A-Za-z0-9_-]+/ppse$"
)

_ORIGINAL_READER_GET = None
_ORIGINAL_SYNC_BROKER = None
_ORIGINAL_LATEST_BROKER = None
_ORIGINAL_PLANNED_BUYING_POWER = None
_ORIGINAL_ALLOCATE_BUY_ORDERS = None
_ORIGINAL_CREATE_WEEKLY_PLAN = None


def _finite_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _nonnegative_int(value: object, default: int = 0) -> int:
    number = _finite_float(value, float(default))
    if number < 0 or not number.is_integer():
        return default
    return int(number)


def _extract_list(payload: object, *keys: str) -> list[Mapping[str, object]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, Mapping)]
    if not isinstance(payload, Mapping):
        return []
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, Mapping)]
    data = payload.get("data")
    if data is not None and data is not payload:
        rows = _extract_list(data, *keys)
        if rows:
            return rows
    return []


def _find_number(payload: object, names: Sequence[str]) -> float | None:
    wanted = {str(name).lower() for name in names}
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if str(key).lower() in wanted and value is not None:
                number = _finite_float(value, float("nan"))
                if math.isfinite(number):
                    return number
        for value in payload.values():
            found = _find_number(value, names)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = _find_number(value, names)
            if found is not None:
                return found
    return None


def _patched_reader_get(self, path: str, *, params=None):
    """Extend the existing GET allowlist with two read-only order-service APIs."""

    if _LOAN_PACKAGES.fullmatch(path) or _PPSE.fullmatch(path):
        response = self._client.get(path, params=dict(params or {}))
        return response.json()
    assert _ORIGINAL_READER_GET is not None
    return _ORIGINAL_READER_GET(self, path, params=params)


def _package_symbols(raw: Mapping[str, object]) -> set[str]:
    result: set[str] = set()
    direct = raw.get("symbols")
    if isinstance(direct, list):
        result.update(str(value).strip().upper() for value in direct if str(value).strip())
    elif isinstance(direct, str):
        result.update(
            part.strip().upper()
            for part in direct.replace(";", ",").split(",")
            if part.strip()
        )
    for product in _extract_list(raw, "loanProducts", "products"):
        symbol = str(
            _first_present(product, ("symbol", "ticker", "securitySymbol"), "")
            or ""
        ).strip().upper()
        if symbol:
            result.add(symbol)
    return result


def normalize_loan_package(raw: Mapping[str, object]) -> dict[str, object] | None:
    package_id = _first_present(raw, ("id", "loanPackageId", "loan_package_id"), None)
    if package_id is None or str(package_id).strip() == "":
        return None
    package_type = str(
        _first_present(raw, ("type", "loanType", "loan_type"), "") or ""
    ).strip().upper()
    symbols = _package_symbols(raw)
    return {
        "id": str(package_id),
        "name": str(_first_present(raw, ("name",), "") or ""),
        "type": package_type,
        "symbols": symbols,
        "applies_to_all_symbols": not symbols,
    }


def select_non_margin_package(
    packages: Sequence[Mapping[str, object]], symbol: str
) -> dict[str, object] | None:
    ticker = str(symbol or "").strip().upper()
    normalized = [
        package
        for package in (normalize_loan_package(row) for row in packages)
        if package is not None and str(package["type"]).upper() == "N"
    ]
    applicable = [
        package
        for package in normalized
        if bool(package["applies_to_all_symbols"])
        or ticker in package["symbols"]
    ]
    if not applicable:
        return None
    return sorted(applicable, key=lambda row: (str(row["id"]), str(row["name"])))[0]


def normalize_ppse_response(
    payload: object,
    *,
    symbol: str,
    price_vnd: float,
    loan_package_id: str,
) -> dict[str, object]:
    ppse = _find_number(payload, ("ppse", "purchasingPower", "buyingPower"))
    qmax = _find_number(payload, ("qmax", "maxBuyQuantity", "buyQuantity"))
    response_price = _find_number(payload, ("price",))
    if ppse is None or qmax is None:
        raise ValueError(f"DNSE_PPSE_RESPONSE_INVALID:{symbol}")
    return {
        "symbol": str(symbol).upper(),
        "price_vnd": float(response_price if response_price and response_price > 0 else price_vnd),
        "loan_package_id": str(loan_package_id),
        "ppse_vnd": max(float(ppse), 0.0),
        "qmax": max(int(float(qmax)), 0),
        "status": "SUCCESS",
        "source": BUYING_POWER_SOURCE,
    }


def _ensure_schema(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS buying_power_snapshots_v50(
            snapshot_id TEXT PRIMARY KEY,
            broker_snapshot_id TEXT NOT NULL,
            captured_at TEXT NOT NULL,
            status TEXT NOT NULL,
            source TEXT NOT NULL,
            available_cash_vnd REAL NOT NULL,
            conservative_buying_power_vnd REAL NOT NULL,
            reusable_unsettled_vnd REAL NOT NULL,
            candidate_count INTEGER NOT NULL,
            successful_candidate_count INTEGER NOT NULL,
            details_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS buying_power_items_v50(
            snapshot_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            price_vnd REAL NOT NULL,
            loan_package_id TEXT,
            ppse_vnd REAL NOT NULL,
            qmax INTEGER NOT NULL,
            status TEXT NOT NULL,
            error TEXT,
            PRIMARY KEY(snapshot_id,symbol),
            FOREIGN KEY(snapshot_id) REFERENCES buying_power_snapshots_v50(snapshot_id)
        );
        CREATE INDEX IF NOT EXISTS idx_buying_power_broker_v50
        ON buying_power_snapshots_v50(broker_snapshot_id,captured_at DESC);
        """
    )


def _candidate_prices() -> tuple[str | None, list[dict[str, object]]]:
    try:
        ranking = weekly_plan._latest_canonical_ranking()
        rows = list(ranking.get("rows") or [])[:10]
    except Exception:
        return None, []
    symbols = [str(row.get("symbol") or "").upper() for row in rows]
    symbols = [symbol for symbol in symbols if symbol]
    if not symbols:
        return str(ranking.get("signal_day") or "") or None, []
    market_day, prices = weekly_plan._latest_market_prices(symbols)
    candidates = [
        {
            "symbol": symbol,
            "price_vnd": float(prices.get(symbol) or 0.0),
        }
        for symbol in symbols
        if float(prices.get(symbol) or 0.0) > 0.0
    ]
    return market_day, candidates


def _persist_snapshot(
    *,
    broker: Mapping[str, object],
    status: str,
    source: str,
    items: Sequence[Mapping[str, object]],
    details: Mapping[str, object],
) -> dict[str, object]:
    broker_snapshot_id = str(broker.get("snapshot_id") or "")
    if not broker_snapshot_id:
        raise ValueError("DNSE_BUYING_POWER_REQUIRES_BROKER_SNAPSHOT")
    available_cash = max(_finite_float(broker.get("available_cash_vnd")), 0.0)
    successful = [
        row
        for row in items
        if row.get("status") == "SUCCESS" and _finite_float(row.get("ppse_vnd")) >= 0.0
    ]
    if status == "SUCCESS" and successful:
        positive = [
            _finite_float(row.get("ppse_vnd"))
            for row in successful
            if _finite_float(row.get("ppse_vnd")) > 0.0
        ]
        authoritative = min(positive) if positive else 0.0
        conservative = max(authoritative, available_cash)
        effective_source = source
    else:
        conservative = available_cash
        effective_source = FALLBACK_SOURCE
    reusable = max(conservative - available_cash, 0.0)
    snapshot_id = "bp-v50-" + uuid4().hex
    captured_at = utc_now()
    payload = {
        "version": V50_VERSION,
        "snapshot_id": snapshot_id,
        "broker_snapshot_id": broker_snapshot_id,
        "captured_at": captured_at,
        "status": status,
        "source": effective_source,
        "available_cash_vnd": available_cash,
        "conservative_buying_power_vnd": conservative,
        "reusable_unsettled_vnd": reusable,
        "candidate_count": len(items),
        "successful_candidate_count": len(successful),
        "details": dict(details),
        "items": [dict(row) for row in items],
    }
    with state_db() as db:
        _ensure_schema(db)
        db.execute(
            """
            INSERT INTO buying_power_snapshots_v50(
                snapshot_id,broker_snapshot_id,captured_at,status,source,
                available_cash_vnd,conservative_buying_power_vnd,
                reusable_unsettled_vnd,candidate_count,
                successful_candidate_count,details_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                snapshot_id,
                broker_snapshot_id,
                captured_at,
                status,
                effective_source,
                available_cash,
                conservative,
                reusable,
                len(items),
                len(successful),
                json.dumps(dict(details), ensure_ascii=False, sort_keys=True),
            ),
        )
        db.executemany(
            """
            INSERT INTO buying_power_items_v50(
                snapshot_id,symbol,price_vnd,loan_package_id,
                ppse_vnd,qmax,status,error
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            [
                (
                    snapshot_id,
                    str(row.get("symbol") or ""),
                    _finite_float(row.get("price_vnd")),
                    str(row.get("loan_package_id") or "") or None,
                    _finite_float(row.get("ppse_vnd")),
                    _nonnegative_int(row.get("qmax")),
                    str(row.get("status") or "FAILED"),
                    str(row.get("error") or "") or None,
                )
                for row in items
            ],
        )
    return payload


def refresh_buying_power_snapshot(
    broker: Mapping[str, object] | None = None,
) -> dict[str, object]:
    if broker is None:
        assert _ORIGINAL_LATEST_BROKER is not None
        broker = _ORIGINAL_LATEST_BROKER()
    if not broker:
        raise ValueError("DNSE_BUYING_POWER_REQUIRES_BROKER_SNAPSHOT")

    market_day, candidates = _candidate_prices()
    if not candidates:
        return _persist_snapshot(
            broker=broker,
            status="UNAVAILABLE",
            source=FALLBACK_SOURCE,
            items=[],
            details={
                "version": V50_VERSION,
                "reason": "NO_CANONICAL_CANDIDATE_PRICE",
                "market_day": market_day,
                "read_only": True,
            },
        )

    reader, credential_source = data_sources.reader_from_saved_credentials()
    items: list[dict[str, object]] = []
    endpoint_error = None
    try:
        probed = _probe_accounts(reader)
        selected = _choose_account(probed)
        account_no = str(selected["account_no"])
        packages_payload = reader.get(
            f"/order-service/v2/accounts/{account_no}/loan-packages"
        )
        packages = _extract_list(packages_payload, "loanPackages", "packages")
        for candidate in candidates:
            symbol = str(candidate["symbol"])
            price_vnd = float(candidate["price_vnd"])
            package = select_non_margin_package(packages, symbol)
            if package is None:
                items.append(
                    {
                        "symbol": symbol,
                        "price_vnd": price_vnd,
                        "loan_package_id": None,
                        "ppse_vnd": 0.0,
                        "qmax": 0,
                        "status": "NO_NON_MARGIN_PACKAGE",
                        "error": "NO_APPLICABLE_TYPE_N_LOAN_PACKAGE",
                    }
                )
                continue
            try:
                payload = reader.get(
                    f"/order-service/accounts/{account_no}/ppse",
                    params={
                        "symbol": symbol,
                        "price": int(round(price_vnd)),
                        "loanPackageId": package["id"],
                    },
                )
                items.append(
                    normalize_ppse_response(
                        payload,
                        symbol=symbol,
                        price_vnd=price_vnd,
                        loan_package_id=str(package["id"]),
                    )
                )
            except Exception as exc:
                items.append(
                    {
                        "symbol": symbol,
                        "price_vnd": price_vnd,
                        "loan_package_id": str(package["id"]),
                        "ppse_vnd": 0.0,
                        "qmax": 0,
                        "status": "FAILED",
                        "error": f"{type(exc).__name__}:{exc}",
                    }
                )
    except Exception as exc:
        endpoint_error = f"{type(exc).__name__}:{exc}"
    finally:
        reader.close()

    success_count = sum(row.get("status") == "SUCCESS" for row in items)
    status = "SUCCESS" if success_count > 0 else "UNAVAILABLE"
    return _persist_snapshot(
        broker=broker,
        status=status,
        source=BUYING_POWER_SOURCE,
        items=items,
        details={
            "version": V50_VERSION,
            "credential_source": credential_source,
            "market_day": market_day,
            "candidate_symbols": [str(row["symbol"]) for row in candidates],
            "endpoint_error": endpoint_error,
            "non_margin_only": True,
            "margin_buying_power_allowed": False,
            "trading_token_used": False,
            "write_endpoint_called": False,
            "read_only": True,
            "conservative_rule": "MIN_POSITIVE_PPSE_ACROSS_SUCCESSFUL_TOP10_PROBES",
            "fallback_rule": "AVAILABLE_CASH_ONLY_WHEN_PPSE_UNAVAILABLE",
        },
    )


def latest_buying_power_snapshot(
    broker_snapshot_id: str | None = None,
) -> dict[str, object] | None:
    with state_db() as db:
        _ensure_schema(db)
        if broker_snapshot_id:
            row = db.execute(
                """
                SELECT * FROM buying_power_snapshots_v50
                WHERE broker_snapshot_id=?
                ORDER BY captured_at DESC LIMIT 1
                """,
                (str(broker_snapshot_id),),
            ).fetchone()
        else:
            row = db.execute(
                """
                SELECT * FROM buying_power_snapshots_v50
                ORDER BY captured_at DESC LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        items = [
            dict(item)
            for item in db.execute(
                """
                SELECT * FROM buying_power_items_v50
                WHERE snapshot_id=? ORDER BY symbol
                """,
                (row["snapshot_id"],),
            ).fetchall()
        ]
    result = dict(row)
    result["details"] = json.loads(str(result.pop("details_json")))
    result["items"] = items
    result["version"] = V50_VERSION
    return result


def _attach_buying_power(broker: dict[str, object] | None) -> dict[str, object] | None:
    if broker is None:
        return None
    result = dict(broker)
    snapshot = latest_buying_power_snapshot(str(result.get("snapshot_id") or ""))
    if snapshot is None:
        return result
    result["buying_power"] = snapshot
    result["planning_buying_power_vnd"] = float(
        snapshot.get("conservative_buying_power_vnd") or 0.0
    )
    result["reusable_unsettled_vnd"] = float(
        snapshot.get("reusable_unsettled_vnd") or 0.0
    )
    result["planner_cash_vnd"] = result["planning_buying_power_vnd"]
    details = dict(result.get("details") or {})
    details["planner_cash_source"] = str(snapshot.get("source") or FALLBACK_SOURCE)
    details["buying_power_snapshot_id"] = snapshot.get("snapshot_id")
    details["buying_power_status"] = snapshot.get("status")
    result["details"] = details
    return result


def sync_broker_portfolio_v50() -> dict[str, object]:
    assert _ORIGINAL_SYNC_BROKER is not None
    broker = _ORIGINAL_SYNC_BROKER()
    try:
        refresh_buying_power_snapshot(broker)
    except Exception as exc:
        _persist_snapshot(
            broker=broker,
            status="UNAVAILABLE",
            source=FALLBACK_SOURCE,
            items=[],
            details={
                "version": V50_VERSION,
                "reason": "BUYING_POWER_REFRESH_EXCEPTION",
                "error": f"{type(exc).__name__}:{exc}",
                "read_only": True,
            },
        )
    return _attach_buying_power(dict(broker)) or dict(broker)


def latest_broker_portfolio_v50() -> dict[str, object] | None:
    assert _ORIGINAL_LATEST_BROKER is not None
    broker = _ORIGINAL_LATEST_BROKER()
    return _attach_buying_power(dict(broker)) if broker else None


def _current_effective_buying_power() -> dict[str, object] | None:
    broker = latest_broker_portfolio_v50()
    if not broker:
        return None
    snapshot = broker.get("buying_power")
    return dict(snapshot) if isinstance(snapshot, Mapping) else None


def planned_buying_power_v50(
    current_cash_vnd: float,
    weekly_contribution_vnd: float,
) -> float:
    cash = float(current_cash_vnd)
    contribution = float(weekly_contribution_vnd)
    if cash < 0.0:
        raise ValueError("Tiền khả dụng DNSE không được âm")
    if contribution < 0.0:
        raise ValueError("Tiền mới cho planning cycle không được âm")
    snapshot = _current_effective_buying_power()
    base = cash
    if snapshot and snapshot.get("status") == "SUCCESS":
        base = max(
            cash,
            _finite_float(snapshot.get("conservative_buying_power_vnd")),
        )
    return base + contribution


def allocate_buy_orders_v50(
    candidates: Sequence[Mapping[str, object]],
    *,
    budget_vnd: float,
    max_orders: int,
    cost_bps: float,
) -> list[dict[str, object]]:
    assert _ORIGINAL_ALLOCATE_BUY_ORDERS is not None
    snapshot = _current_effective_buying_power()
    item_by_symbol = {
        str(row.get("symbol") or ""): row
        for row in (snapshot or {}).get("items", [])
        if isinstance(row, Mapping)
    }
    authoritative = bool(snapshot and snapshot.get("status") == "SUCCESS")
    adjusted: list[dict[str, object]] = []
    for raw in candidates:
        row = dict(raw)
        symbol = str(row.get("symbol") or "")
        item = item_by_symbol.get(symbol)
        if authoritative:
            if not item or item.get("status") != "SUCCESS":
                row["budget_ceiling_vnd"] = 0.0
                row["buying_power_guard"] = "BLOCKED_NO_AUTHORITATIVE_QMAX"
            else:
                qmax = _nonnegative_int(item.get("qmax"))
                one_share = float(row.get("price_vnd") or 0.0) * (
                    1.0 + float(cost_bps) / 10_000.0
                )
                qmax_ceiling = qmax * one_share
                row["budget_ceiling_vnd"] = min(
                    float(row.get("budget_ceiling_vnd") or 0.0),
                    qmax_ceiling,
                )
                row["dnse_qmax"] = qmax
                row["dnse_ppse_vnd"] = _finite_float(item.get("ppse_vnd"))
                row["dnse_loan_package_id"] = item.get("loan_package_id")
                row["buying_power_guard"] = "DNSE_PPSE_QMAX_NON_MARGIN"
        adjusted.append(row)
    orders = _ORIGINAL_ALLOCATE_BUY_ORDERS(
        adjusted,
        budget_vnd=budget_vnd,
        max_orders=max_orders,
        cost_bps=cost_bps,
    )
    for order in orders:
        item = item_by_symbol.get(str(order.get("symbol") or ""))
        if item and item.get("status") == "SUCCESS":
            order["dnse_qmax"] = _nonnegative_int(item.get("qmax"))
            order["dnse_ppse_vnd"] = _finite_float(item.get("ppse_vnd"))
            order["dnse_loan_package_id"] = item.get("loan_package_id")
            order["buying_power_source"] = BUYING_POWER_SOURCE
    return orders


def create_weekly_plan_v50(*, weekly_budget_vnd=None, maximum_buy_orders=None):
    assert _ORIGINAL_CREATE_WEEKLY_PLAN is not None
    plan = _ORIGINAL_CREATE_WEEKLY_PLAN(
        weekly_budget_vnd=weekly_budget_vnd,
        maximum_buy_orders=maximum_buy_orders,
    )
    snapshot = _current_effective_buying_power()
    if snapshot:
        plan["dnse_buying_power_vnd"] = _finite_float(
            snapshot.get("conservative_buying_power_vnd")
        )
        plan["reusable_unsettled_proceeds_vnd"] = _finite_float(
            snapshot.get("reusable_unsettled_vnd")
        )
        plan["buying_power_snapshot_id"] = snapshot.get("snapshot_id")
        plan["buying_power_status"] = snapshot.get("status")
        plan["buying_power_source"] = snapshot.get("source")
        rationale = dict(plan.get("rationale") or {})
        rationale.update(
            {
                "buying_power_snapshot_id": snapshot.get("snapshot_id"),
                "buying_power_status": snapshot.get("status"),
                "buying_power_source": snapshot.get("source"),
                "dnse_available_cash_vnd": snapshot.get("available_cash_vnd"),
                "dnse_buying_power_vnd": snapshot.get(
                    "conservative_buying_power_vnd"
                ),
                "reusable_unsettled_proceeds_vnd": snapshot.get(
                    "reusable_unsettled_vnd"
                ),
                "buying_power_formula": (
                    "DNSE_NON_MARGIN_PPSE_PLUS_NEW_CAPITAL"
                    if snapshot.get("status") == "SUCCESS"
                    else "AVAILABLE_CASH_FALLBACK_PLUS_NEW_CAPITAL"
                ),
                "candidate_qmax_enforced": snapshot.get("status") == "SUCCESS",
                "margin_buying_power_allowed": False,
                "sell_proceeds_reuse_source": "DNSE_PPSE_NOT_POSITION_DELTA",
            }
        )
        plan["rationale"] = rationale
        with state_db() as db:
            db.execute(
                "UPDATE weekly_plans SET rationale_json=? WHERE plan_id=?",
                (
                    json.dumps(rationale, ensure_ascii=False, sort_keys=True),
                    str(plan.get("plan_id") or ""),
                ),
            )
        output = paths().outputs / f"{plan['plan_id']}.json"
        output.write_text(
            json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return plan


def apply() -> None:
    if getattr(data_sources, "_v50_buying_power_applied", False):
        return
    global _ORIGINAL_READER_GET
    global _ORIGINAL_SYNC_BROKER, _ORIGINAL_LATEST_BROKER
    global _ORIGINAL_PLANNED_BUYING_POWER, _ORIGINAL_ALLOCATE_BUY_ORDERS
    global _ORIGINAL_CREATE_WEEKLY_PLAN

    portfolio_module = __import__(
        "he_thong_dinh_luong.dnse_portfolio",
        fromlist=["DnseReadOnlyClient"],
    )
    reader_class = portfolio_module.DnseReadOnlyClient
    _ORIGINAL_READER_GET = reader_class.get
    _ORIGINAL_SYNC_BROKER = broker_portfolio.sync_broker_portfolio
    _ORIGINAL_LATEST_BROKER = broker_portfolio.latest_broker_portfolio
    _ORIGINAL_PLANNED_BUYING_POWER = weekly_plan.planned_buying_power
    _ORIGINAL_ALLOCATE_BUY_ORDERS = weekly_plan.allocate_buy_orders
    _ORIGINAL_CREATE_WEEKLY_PLAN = weekly_plan.create_weekly_plan

    reader_class.get = _patched_reader_get
    broker_portfolio.sync_broker_portfolio = sync_broker_portfolio_v50
    broker_portfolio.latest_broker_portfolio = latest_broker_portfolio_v50
    weekly_plan.planned_buying_power = planned_buying_power_v50
    weekly_plan.allocate_buy_orders = allocate_buy_orders_v50
    weekly_plan.create_weekly_plan = create_weekly_plan_v50
    capital_plan.create_weekly_plan = create_weekly_plan_v50

    data_sources.refresh_buying_power_snapshot = refresh_buying_power_snapshot
    data_sources.latest_buying_power_snapshot = latest_buying_power_snapshot
    data_sources.V50_VERSION = V50_VERSION
    data_sources._v50_buying_power_applied = True
