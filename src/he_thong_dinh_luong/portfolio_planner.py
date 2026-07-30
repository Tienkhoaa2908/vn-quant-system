"""Danh muc thuc te va ke hoach phan bo tien moi cho web local.

Module nay khong phu thuoc NiceGUI. No chi doc artifact da cong bo va tao ke
hoach ky thuat; khong gui lenh, khong tu dong ban va khong gia lap sector cap
khi chua co sector master tin cay.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN
import json
from pathlib import Path
import sqlite3
from typing import Iterable, Iterator, Mapping, Sequence
import uuid

VN_TZ = timezone(timedelta(hours=7))
SCHEMA_VERSION = "portfolio_planner_v1"
ALLOCATOR_NAME = "target_gap_lot_aware_v1"
MODEL_REGISTRY = (
    {"name": "momentum_baseline", "label": "Momentum 12-1", "role": "baseline/champion eligible"},
    {"name": "lightgbm_ranker", "label": "LightGBM Ranker", "role": "challenger; gate controlled"},
    {"name": "logistic_legacy", "label": "Logistic Regression", "role": "legacy benchmark"},
)
ALLOCATOR_REGISTRY = (
    {
        "name": ALLOCATOR_NAME,
        "label": "Bù khoảng thiếu theo target",
        "description": "Phân tiền mới vào mã còn thiếu so với target, có lot và trần từng mã.",
        "version": "1",
    },
)


def _now_text() -> str:
    return datetime.now(VN_TZ).isoformat(timespec="seconds")


def _decimal(value: object, code: str) -> Decimal:
    try:
        result = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, AttributeError) as exc:
        raise ValueError(code) from exc
    if not result.is_finite():
        raise ValueError(code)
    return result


@dataclass(frozen=True)
class Holding:
    symbol: str
    quantity: int
    average_cost_vnd: Decimal

    def __post_init__(self) -> None:
        symbol = self.symbol.strip().upper()
        if not symbol or not symbol.replace("-", "").isalnum():
            raise ValueError("PORTFOLIO_SYMBOL_INVALID")
        if self.quantity < 0:
            raise ValueError("PORTFOLIO_QUANTITY_INVALID")
        if self.average_cost_vnd < 0:
            raise ValueError("PORTFOLIO_AVERAGE_COST_INVALID")
        object.__setattr__(self, "symbol", symbol)


@dataclass(frozen=True)
class PlanRequest:
    extra_cash_vnd: int
    current_cash_vnd: int = 0
    include_current_cash: bool = False
    lot_size: int = 100
    buy_fee_bps: Decimal = Decimal("15")
    slippage_bps: Decimal = Decimal("10")
    max_symbol_weight: Decimal = Decimal("0.15")

    def __post_init__(self) -> None:
        if self.extra_cash_vnd < 0 or self.current_cash_vnd < 0:
            raise ValueError("PORTFOLIO_CASH_INVALID")
        if self.lot_size <= 0:
            raise ValueError("PORTFOLIO_LOT_INVALID")
        if min(self.buy_fee_bps, self.slippage_bps) < 0:
            raise ValueError("PORTFOLIO_COST_INVALID")
        if not Decimal("0") < self.max_symbol_weight <= Decimal("1"):
            raise ValueError("PORTFOLIO_MAX_WEIGHT_INVALID")


class PortfolioStore:
    """SQLite local cho vi the nguoi dung va lich su ke hoach phan bo."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                connection.execute("PRAGMA foreign_keys=ON")
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS portfolio_positions (
                    symbol TEXT PRIMARY KEY,
                    quantity INTEGER NOT NULL CHECK(quantity >= 0),
                    average_cost_vnd TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS portfolio_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS allocation_plans (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    signal_date TEXT NOT NULL,
                    allocator TEXT NOT NULL,
                    extra_cash_vnd INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_allocation_plans_created
                    ON allocation_plans(created_at DESC);
                """
            )

    def upsert_holding(self, holding: Holding) -> None:
        with self._connection() as connection:
            if holding.quantity == 0:
                connection.execute("DELETE FROM portfolio_positions WHERE symbol=?", (holding.symbol,))
                return
            connection.execute(
                """
                INSERT INTO portfolio_positions(symbol, quantity, average_cost_vnd, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    quantity=excluded.quantity,
                    average_cost_vnd=excluded.average_cost_vnd,
                    updated_at=excluded.updated_at
                """,
                (holding.symbol, holding.quantity, str(holding.average_cost_vnd), _now_text()),
            )

    def delete_holding(self, symbol: str) -> None:
        normalized = symbol.strip().upper()
        with self._connection() as connection:
            connection.execute("DELETE FROM portfolio_positions WHERE symbol=?", (normalized,))

    def list_holdings(self) -> list[Holding]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT symbol, quantity, average_cost_vnd FROM portfolio_positions ORDER BY symbol"
            ).fetchall()
        return [Holding(row["symbol"], int(row["quantity"]), Decimal(row["average_cost_vnd"])) for row in rows]

    def set_current_cash(self, amount_vnd: int) -> None:
        if amount_vnd < 0:
            raise ValueError("PORTFOLIO_CASH_INVALID")
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO portfolio_settings(key, value, updated_at)
                VALUES ('current_cash_vnd', ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """,
                (str(amount_vnd), _now_text()),
            )

    def get_current_cash(self) -> int:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT value FROM portfolio_settings WHERE key='current_cash_vnd'"
            ).fetchone()
        return int(row["value"]) if row is not None else 0

    def record_plan(self, plan: Mapping[str, object]) -> str:
        plan_id = uuid.uuid4().hex
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO allocation_plans(
                    id, created_at, signal_date, allocator, extra_cash_vnd, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    _now_text(),
                    str(plan.get("signal_date", "")),
                    str(plan.get("allocator", ALLOCATOR_NAME)),
                    int(plan.get("extra_cash_vnd", 0)),
                    json.dumps(plan, ensure_ascii=False, sort_keys=True),
                ),
            )
        return plan_id

    def recent_plans(self, limit: int = 20) -> list[dict[str, object]]:
        if limit <= 0:
            raise ValueError("PORTFOLIO_PLAN_LIMIT_INVALID")
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT id, created_at, signal_date, allocator, extra_cash_vnd FROM allocation_plans "
                "ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]


def latest_price_map(price_rows: Iterable[Mapping[str, object]]) -> tuple[dict[str, Decimal], str]:
    latest_by_symbol: dict[str, tuple[str, Decimal]] = {}
    latest_day = ""
    for row in price_rows:
        symbol = str(row.get("ma") or row.get("symbol") or "").strip().upper()
        day = str(row.get("ngay") or row.get("day") or "").strip()[:10]
        close_raw = row.get("gia_dong_cua") if "gia_dong_cua" in row else row.get("close")
        if not symbol or not day or close_raw in (None, ""):
            continue
        close_thousand = _decimal(close_raw, "PORTFOLIO_CLOSE_INVALID")
        if close_thousand <= 0:
            continue
        close_vnd = close_thousand * Decimal("1000")
        previous = latest_by_symbol.get(symbol)
        if previous is None or day > previous[0]:
            latest_by_symbol[symbol] = (day, close_vnd)
        latest_day = max(latest_day, day)
    return {symbol: value for symbol, (_, value) in latest_by_symbol.items()}, latest_day


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def market_snapshot(
    predictions: Sequence[Mapping[str, object]],
    model: Mapping[str, object],
) -> dict[str, object]:
    valid = [row for row in predictions if row.get("symbol")]
    above_count = sum(_truthy(row.get("above_ma250")) for row in valid)
    selected = [row for row in valid if _truthy(row.get("selected_top_k"))]
    selected_above = sum(_truthy(row.get("above_ma250")) for row in selected)
    momentum = model.get("momentum_validation") if isinstance(model.get("momentum_validation"), Mapping) else {}
    challenger = model.get("lightgbm_validation") if isinstance(model.get("lightgbm_validation"), Mapping) else {}
    return {
        "signal_date": str(model.get("signal_date") or (valid[0].get("signal_date") if valid else "")),
        "market_regime": model.get("market_regime", "UNKNOWN"),
        "capital_budget_pct": model.get("capital_budget_pct", 0),
        "champion_model": model.get("champion_model", ""),
        "candidate_count": len(valid),
        "breadth_above_ma250": (above_count / len(valid)) if valid else None,
        "top_selected_above_ma250": (selected_above / len(selected)) if selected else None,
        "momentum_rank_ic": momentum.get("mean_rank_ic") if isinstance(momentum, Mapping) else None,
        "challenger_rank_ic": challenger.get("mean_rank_ic") if isinstance(challenger, Mapping) else None,
        "research_eligible": bool(model.get("research_eligible", False)),
        "warnings": [
            "TECHNICAL_VALIDATION_ONLY",
            "SECTOR_CAP_NOT_ENFORCED_WITHOUT_TRUSTED_SECTOR_MASTER",
            "NO_AUTOMATIC_SELL_ORDERS",
        ],
    }


def build_incremental_plan(
    *,
    holdings: Sequence[Holding],
    price_vnd: Mapping[str, Decimal],
    allocation_rows: Sequence[Mapping[str, object]],
    predictions: Sequence[Mapping[str, object]],
    model: Mapping[str, object],
    request: PlanRequest,
) -> dict[str, object]:
    """Phan tien moi vao cac khoang thieu so voi target, co lot va chi phi."""
    holding_by_symbol = {item.symbol: item for item in holdings}
    if len(holding_by_symbol) != len(holdings):
        raise ValueError("PORTFOLIO_HOLDING_DUPLICATE")

    current_market_value = Decimal("0")
    holding_values: dict[str, Decimal] = {}
    missing_price: list[str] = []
    for holding in holdings:
        price = price_vnd.get(holding.symbol)
        if price is None:
            missing_price.append(holding.symbol)
            continue
        value = price * holding.quantity
        holding_values[holding.symbol] = value
        current_market_value += value
    if missing_price:
        raise ValueError("PORTFOLIO_PRICE_MISSING:" + ",".join(sorted(missing_price)))

    current_cash = Decimal(request.current_cash_vnd)
    extra_cash = Decimal(request.extra_cash_vnd)
    total_after_deposit = current_market_value + current_cash + extra_cash
    available_cash = extra_cash + (current_cash if request.include_current_cash else Decimal("0"))
    if total_after_deposit <= 0:
        raise ValueError("PORTFOLIO_TOTAL_VALUE_INVALID")

    prediction_by_symbol = {
        str(row.get("symbol", "")).strip().upper(): row for row in predictions if row.get("symbol")
    }
    targets: list[dict[str, object]] = []
    for raw in allocation_rows:
        symbol = str(raw.get("symbol", "")).strip().upper()
        if not symbol:
            continue
        price = price_vnd.get(symbol)
        if price is None:
            continue
        weight_pct = _decimal(raw.get("target_weight_pct", "0"), "PORTFOLIO_TARGET_WEIGHT_INVALID")
        target_weight = min(weight_pct / Decimal("100"), request.max_symbol_weight)
        if target_weight <= 0:
            continue
        current_value = holding_values.get(symbol, Decimal("0"))
        target_value = total_after_deposit * target_weight
        gap = max(Decimal("0"), target_value - current_value)
        prediction = prediction_by_symbol.get(symbol, {})
        rank_text = raw.get("rank") or prediction.get("champion_rank") or "999999"
        try:
            rank = int(str(rank_text))
        except ValueError:
            rank = 999999
        targets.append({
            "symbol": symbol,
            "rank": rank,
            "price_vnd": price,
            "target_weight": target_weight,
            "current_value": current_value,
            "target_value": target_value,
            "gap": gap,
            "momentum_12_1": prediction.get("momentum_12_1", ""),
            "above_ma250": prediction.get("above_ma250", ""),
        })
    targets.sort(key=lambda row: (int(row["rank"]), str(row["symbol"])))
    if not targets:
        raise ValueError("PORTFOLIO_ALLOCATION_EMPTY_OR_UNPRICED")
    total_gap = sum((Decimal(row["gap"]) for row in targets), Decimal("0"))
    deployable = min(available_cash, total_gap)
    all_in_cost_multiplier = Decimal("1") + (
        request.buy_fee_bps + request.slippage_bps
    ) / Decimal("10000")

    plan_rows: list[dict[str, object]] = []
    spent = Decimal("0")
    for row in targets:
        gap = Decimal(row["gap"])
        proportional = deployable * gap / total_gap if total_gap > 0 else Decimal("0")
        price = Decimal(row["price_vnd"])
        lot_cost = price * request.lot_size * all_in_cost_multiplier
        lots = (min(proportional, gap) / lot_cost).to_integral_value(rounding=ROUND_DOWN)
        quantity = int(lots) * request.lot_size
        estimated_cost = price * quantity * all_in_cost_multiplier
        spent += estimated_cost
        holding = holding_by_symbol.get(str(row["symbol"]))
        current_qty = holding.quantity if holding else 0
        post_value = Decimal(row["current_value"]) + price * quantity
        plan_rows.append({
            "symbol": row["symbol"],
            "rank": row["rank"],
            "above_ma250": row["above_ma250"],
            "momentum_12_1": row["momentum_12_1"],
            "current_quantity": current_qty,
            "current_value_vnd": int(Decimal(row["current_value"])),
            "current_weight_pct": float(Decimal(row["current_value"]) / total_after_deposit * 100),
            "target_weight_pct": float(Decimal(row["target_weight"]) * 100),
            "target_value_vnd": int(Decimal(row["target_value"])),
            "gap_before_vnd": int(gap),
            "recommended_buy_quantity": quantity,
            "estimated_price_vnd": int(price),
            "estimated_all_in_cost_vnd": int(estimated_cost),
            "post_quantity": current_qty + quantity,
            "post_value_vnd": int(post_value),
            "post_weight_pct": float(post_value / total_after_deposit * 100),
            "action": "BUY" if quantity > 0 else ("HOLD" if current_qty else "WAIT"),
            "status": (
                "OVER_TARGET_REVIEW" if Decimal(row["current_value"]) > Decimal(row["target_value"])
                else ("BUY_TO_TARGET" if quantity > 0 else "NO_EXECUTABLE_LOT")
            ),
        })

    remaining = deployable - spent
    if remaining > 0:
        by_symbol = {str(row["symbol"]): row for row in plan_rows}
        changed = True
        while changed:
            changed = False
            for target in targets:
                symbol = str(target["symbol"])
                output = by_symbol[symbol]
                price = Decimal(target["price_vnd"])
                lot_cost = price * request.lot_size * all_in_cost_multiplier
                post_value = Decimal(output["post_value_vnd"])
                if remaining >= lot_cost and post_value + price * request.lot_size <= Decimal(target["target_value"]):
                    output["recommended_buy_quantity"] = int(output["recommended_buy_quantity"]) + request.lot_size
                    output["estimated_all_in_cost_vnd"] = int(Decimal(output["estimated_all_in_cost_vnd"]) + lot_cost)
                    output["post_quantity"] = int(output["post_quantity"]) + request.lot_size
                    output["post_value_vnd"] = int(post_value + price * request.lot_size)
                    output["post_weight_pct"] = float(Decimal(output["post_value_vnd"]) / total_after_deposit * 100)
                    output["action"] = "BUY"
                    remaining -= lot_cost
                    spent += lot_cost
                    changed = True

    target_symbols = {str(row["symbol"]) for row in targets}
    other_holdings: list[dict[str, object]] = []
    for holding in holdings:
        if holding.symbol in target_symbols:
            continue
        value = holding_values[holding.symbol]
        other_holdings.append({
            "symbol": holding.symbol,
            "quantity": holding.quantity,
            "market_value_vnd": int(value),
            "weight_pct": float(value / total_after_deposit * 100),
            "status": "OUTSIDE_CURRENT_TARGET_NO_ADD",
        })

    snapshot = market_snapshot(predictions, model)
    target_budget_pct = sum((Decimal(str(row["target_weight_pct"])) for row in plan_rows), Decimal("0"))
    return {
        "schema_version": SCHEMA_VERSION,
        "allocator": ALLOCATOR_NAME,
        "created_at": _now_text(),
        "signal_date": snapshot.get("signal_date", ""),
        "market": snapshot,
        "extra_cash_vnd": request.extra_cash_vnd,
        "current_cash_vnd": request.current_cash_vnd,
        "include_current_cash": request.include_current_cash,
        "available_cash_vnd": int(available_cash),
        "deployable_cash_vnd": int(deployable),
        "estimated_spend_vnd": int(spent),
        "estimated_remaining_vnd": int(available_cash - spent),
        "target_gap_unfilled_vnd": int(max(Decimal("0"), total_gap - spent)),
        "current_market_value_vnd": int(current_market_value),
        "total_after_deposit_vnd": int(total_after_deposit),
        "target_budget_pct": float(target_budget_pct),
        "lot_size": request.lot_size,
        "buy_fee_bps": str(request.buy_fee_bps),
        "slippage_bps": str(request.slippage_bps),
        "max_symbol_weight_pct": float(request.max_symbol_weight * 100),
        "rows": plan_rows,
        "outside_target_holdings": other_holdings,
        "limitations": [
            "technical_validation_only",
            "sector_cap_not_enforced_without_trusted_sector_master",
            "no_automatic_sell_orders",
            "execution_price_is_latest_close_estimate_not_guaranteed_fill",
        ],
    }


def holdings_as_rows(holdings: Sequence[Holding], price_vnd: Mapping[str, Decimal]) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for holding in holdings:
        price = price_vnd.get(holding.symbol)
        market_value = price * holding.quantity if price is not None else None
        pnl = (
            (price - holding.average_cost_vnd) * holding.quantity
            if price is not None and holding.average_cost_vnd > 0 else None
        )
        output.append({
            "symbol": holding.symbol,
            "quantity": holding.quantity,
            "average_cost_vnd": int(holding.average_cost_vnd),
            "latest_price_vnd": int(price) if price is not None else "",
            "market_value_vnd": int(market_value) if market_value is not None else "",
            "unrealized_pnl_vnd": int(pnl) if pnl is not None else "",
        })
    return output
