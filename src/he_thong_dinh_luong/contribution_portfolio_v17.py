"""Cash-flow-aware buy-only allocator for periodic investor contributions.

The model signal is monthly. Contributions may arrive weekly, biweekly or at
irregular dates. This allocator never interprets a T+1 fill as predictive
validation; it only converts the latest frozen target into an executable,
lot-aware purchase plan against the investor's complete current portfolio.

No live order is submitted by this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from math import isfinite
from typing import Mapping, Sequence

from .portfolio_planner import Holding

SCHEMA_VERSION = "contribution_portfolio_v17"
ALLOCATOR_NAME = "cashflow_target_gap_lot_aware_v2"
VN_TZ = timezone(timedelta(hours=7))


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


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


@dataclass(frozen=True)
class ContributionPlanRequest:
    """One external cash-flow event applied to the latest monthly target."""

    extra_cash_vnd: int
    settled_cash_vnd: int = 0
    include_settled_cash: bool = False
    lot_size: int = 100
    buy_fee_bps: Decimal = Decimal("2.7")
    slippage_bps: Decimal = Decimal("5")
    max_symbol_weight: Decimal = Decimal("0.15")
    max_sector_weight: Decimal = Decimal("0.25")
    equity_budget_pct: Decimal | None = None
    allow_sells: bool = False
    require_sector_data: bool = False

    def __post_init__(self) -> None:
        if self.extra_cash_vnd < 0 or self.settled_cash_vnd < 0:
            raise ValueError("CONTRIBUTION_CASH_INVALID")
        if self.lot_size <= 0:
            raise ValueError("CONTRIBUTION_LOT_INVALID")
        for name in ("buy_fee_bps", "slippage_bps"):
            value = _decimal(getattr(self, name), f"CONTRIBUTION_{name.upper()}_INVALID")
            if value < 0 or value >= Decimal("10000"):
                raise ValueError(f"CONTRIBUTION_{name.upper()}_INVALID")
        for name in ("max_symbol_weight", "max_sector_weight"):
            value = _decimal(getattr(self, name), f"CONTRIBUTION_{name.upper()}_INVALID")
            if not Decimal("0") < value <= Decimal("1"):
                raise ValueError(f"CONTRIBUTION_{name.upper()}_INVALID")
        if self.equity_budget_pct is not None:
            budget = _decimal(self.equity_budget_pct, "CONTRIBUTION_EQUITY_BUDGET_INVALID")
            if not Decimal("0") <= budget <= Decimal("1"):
                raise ValueError("CONTRIBUTION_EQUITY_BUDGET_INVALID")
        if self.allow_sells:
            raise ValueError("CONTRIBUTION_LIVE_SELLS_NOT_SUPPORTED")


@dataclass(frozen=True)
class _Target:
    symbol: str
    rank: int
    target_weight: Decimal
    target_value: Decimal
    price: Decimal
    sector: str | None
    above_ma250: object
    score: object


def _equity_budget(
    request: ContributionPlanRequest,
    model: Mapping[str, object],
) -> Decimal:
    if request.equity_budget_pct is not None:
        return _decimal(request.equity_budget_pct, "CONTRIBUTION_EQUITY_BUDGET_INVALID")
    raw = model.get("capital_budget_pct", 100)
    budget = _decimal(raw, "CONTRIBUTION_MODEL_BUDGET_INVALID")
    if budget > 1:
        budget /= Decimal("100")
    return min(Decimal("1"), max(Decimal("0"), budget))


def _rank(raw: Mapping[str, object], prediction: Mapping[str, object]) -> int:
    value = raw.get("rank") or prediction.get("champion_rank") or prediction.get("rank") or 999999
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 999999


def _tracking_error(values: Mapping[str, Decimal], targets: Sequence[_Target], total: Decimal) -> Decimal:
    if total <= 0:
        return Decimal("0")
    return sum(
        ((values.get(item.symbol, Decimal("0")) - item.target_value) / total) ** 2
        for item in targets
    )


def build_contribution_plan(
    *,
    holdings: Sequence[Holding],
    price_vnd: Mapping[str, Decimal],
    allocation_rows: Sequence[Mapping[str, object]],
    predictions: Sequence[Mapping[str, object]],
    model: Mapping[str, object],
    request: ContributionPlanRequest,
    sector_by_symbol: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Allocate one contribution against the complete existing portfolio.

    The discrete greedy step buys the lot that most reduces squared target
    tracking error per dong of all-in cost. It may slightly cross a target only
    when doing so reduces tracking error, but never breaches the hard symbol or
    known-sector caps.
    """
    sectors = {
        str(symbol).strip().upper(): str(sector).strip()
        for symbol, sector in (sector_by_symbol or {}).items()
        if str(symbol).strip() and str(sector).strip()
    }
    holding_by_symbol = {holding.symbol: holding for holding in holdings}
    if len(holding_by_symbol) != len(holdings):
        raise ValueError("CONTRIBUTION_HOLDING_DUPLICATE")

    values: dict[str, Decimal] = {}
    quantities: dict[str, int] = {}
    missing_prices: list[str] = []
    current_market_value = Decimal("0")
    for holding in holdings:
        price = price_vnd.get(holding.symbol)
        if price is None:
            missing_prices.append(holding.symbol)
            continue
        price = _decimal(price, "CONTRIBUTION_PRICE_INVALID")
        if price <= 0:
            raise ValueError(f"CONTRIBUTION_PRICE_INVALID:{holding.symbol}")
        value = price * holding.quantity
        values[holding.symbol] = value
        quantities[holding.symbol] = holding.quantity
        current_market_value += value
    if missing_prices:
        raise ValueError("CONTRIBUTION_PRICE_MISSING:" + ",".join(sorted(missing_prices)))

    settled = Decimal(request.settled_cash_vnd)
    contribution = Decimal(request.extra_cash_vnd)
    all_cash_after_flow = settled + contribution
    total_after_flow = current_market_value + all_cash_after_flow
    if total_after_flow <= 0:
        raise ValueError("CONTRIBUTION_TOTAL_VALUE_INVALID")

    budget = _equity_budget(request, model)
    target_cash_reserve = total_after_flow * (Decimal("1") - budget)
    maximum_deployable_after_reserve = max(
        Decimal("0"),
        all_cash_after_flow - target_cash_reserve,
    )
    requested_pool = contribution + (
        settled if request.include_settled_cash else Decimal("0")
    )
    deployable = min(requested_pool, maximum_deployable_after_reserve)

    prediction_by_symbol = {
        str(row.get("symbol") or row.get("ma") or "").strip().upper(): row
        for row in predictions
        if str(row.get("symbol") or row.get("ma") or "").strip()
    }
    raw_targets: list[dict[str, object]] = []
    missing_sector: set[str] = set()
    for raw in allocation_rows:
        symbol = str(raw.get("symbol") or raw.get("ma") or "").strip().upper()
        if not symbol:
            continue
        price = price_vnd.get(symbol)
        if price is None:
            continue
        price_dec = _decimal(price, "CONTRIBUTION_PRICE_INVALID")
        if price_dec <= 0:
            continue
        prediction = prediction_by_symbol.get(symbol, {})
        weight_pct = _decimal(
            raw.get("target_weight_pct", raw.get("target_weight", 0)),
            "CONTRIBUTION_TARGET_WEIGHT_INVALID",
        )
        weight = weight_pct / Decimal("100") if weight_pct > 1 else weight_pct
        weight = min(max(Decimal("0"), weight), request.max_symbol_weight)
        if weight <= 0:
            continue
        sector = sectors.get(symbol)
        if sector is None:
            missing_sector.add(symbol)
        raw_targets.append({
            "symbol": symbol,
            "rank": _rank(raw, prediction),
            "weight": weight,
            "price": price_dec,
            "sector": sector,
            "above_ma250": prediction.get("above_ma250", raw.get("above_ma250", "")),
            "score": prediction.get("score", raw.get("score", "")),
        })
    if not raw_targets:
        raise ValueError("CONTRIBUTION_TARGETS_EMPTY_OR_UNPRICED")
    if request.require_sector_data and missing_sector:
        raise ValueError(
            "CONTRIBUTION_SECTOR_MISSING:" + ",".join(sorted(missing_sector))
        )

    total_raw_weight = sum(
        (Decimal(str(item["weight"])) for item in raw_targets),
        Decimal("0"),
    )
    scale = min(Decimal("1"), budget / total_raw_weight) if total_raw_weight > 0 else Decimal("0")
    targets = [
        _Target(
            symbol=str(item["symbol"]),
            rank=int(item["rank"]),
            target_weight=Decimal(str(item["weight"])) * scale,
            target_value=total_after_flow * Decimal(str(item["weight"])) * scale,
            price=Decimal(str(item["price"])),
            sector=str(item["sector"]) if item["sector"] else None,
            above_ma250=item["above_ma250"],
            score=item["score"],
        )
        for item in raw_targets
    ]
    targets.sort(key=lambda item: (item.rank, item.symbol))

    symbol_cap_value = total_after_flow * request.max_symbol_weight
    sector_cap_value = total_after_flow * request.max_sector_weight
    sector_values: dict[str, Decimal] = {}
    for symbol, value in values.items():
        sector = sectors.get(symbol)
        if sector:
            sector_values[sector] = sector_values.get(sector, Decimal("0")) + value

    all_in_multiplier = Decimal("1") + (
        request.buy_fee_bps + request.slippage_bps
    ) / Decimal("10000")
    purchases = {target.symbol: 0 for target in targets}
    gross_purchases = {target.symbol: Decimal("0") for target in targets}
    all_in_costs = {target.symbol: Decimal("0") for target in targets}
    tracking_before = _tracking_error(values, targets, total_after_flow)
    remaining = deployable
    spent = Decimal("0")

    while True:
        candidates: list[tuple[Decimal, Decimal, int, str, _Target, Decimal, Decimal]] = []
        for target in targets:
            lot_gross = target.price * request.lot_size
            lot_all_in = lot_gross * all_in_multiplier
            if lot_all_in > remaining:
                continue
            current_value = values.get(target.symbol, Decimal("0"))
            proposed_value = current_value + lot_gross
            if proposed_value > symbol_cap_value:
                continue
            if target.sector:
                proposed_sector = sector_values.get(target.sector, Decimal("0")) + lot_gross
                if proposed_sector > sector_cap_value:
                    continue
            before = (current_value - target.target_value) ** 2
            after = (proposed_value - target.target_value) ** 2
            reduction = before - after
            if reduction <= 0:
                continue
            efficiency = reduction / lot_all_in
            gap = target.target_value - current_value
            candidates.append(
                (efficiency, gap, -target.rank, target.symbol, target, lot_gross, lot_all_in)
            )
        if not candidates:
            break
        _, _, _, _, target, lot_gross, lot_all_in = max(candidates)
        purchases[target.symbol] += request.lot_size
        gross_purchases[target.symbol] += lot_gross
        all_in_costs[target.symbol] += lot_all_in
        quantities[target.symbol] = quantities.get(target.symbol, 0) + request.lot_size
        values[target.symbol] = values.get(target.symbol, Decimal("0")) + lot_gross
        if target.sector:
            sector_values[target.sector] = sector_values.get(target.sector, Decimal("0")) + lot_gross
        remaining -= lot_all_in
        spent += lot_all_in

    rows: list[dict[str, object]] = []
    for target in targets:
        holding = holding_by_symbol.get(target.symbol)
        current_qty = holding.quantity if holding else 0
        current_value = target.price * current_qty
        buy_qty = purchases[target.symbol]
        gross_buy = gross_purchases[target.symbol]
        all_in = all_in_costs[target.symbol]
        post_value = current_value + gross_buy
        gap_before = target.target_value - current_value
        gap_after = target.target_value - post_value
        if buy_qty > 0:
            status = "BUY_WITH_CONTRIBUTION"
            action = "BUY"
        elif current_value > target.target_value:
            status = "OVER_TARGET_NO_ADD"
            action = "HOLD"
        elif current_qty > 0:
            status = "UNDER_TARGET_ACCUMULATE"
            action = "HOLD"
        else:
            status = "ACCUMULATE_FOR_EXECUTABLE_LOT"
            action = "WAIT"
        rows.append({
            "symbol": target.symbol,
            "sector": target.sector or "",
            "rank": target.rank,
            "score": target.score,
            "above_ma250": target.above_ma250,
            "current_quantity": current_qty,
            "current_value_vnd": int(current_value),
            "current_weight_pct": float(current_value / total_after_flow * 100),
            "target_weight_pct": float(target.target_weight * 100),
            "target_value_vnd": int(target.target_value),
            "gap_before_vnd": int(gap_before),
            "recommended_buy_quantity": buy_qty,
            "estimated_price_vnd": int(target.price),
            "estimated_gross_buy_vnd": int(gross_buy),
            "estimated_all_in_cost_vnd": int(all_in),
            "estimated_fee_and_slippage_vnd": int(all_in - gross_buy),
            "post_quantity": current_qty + buy_qty,
            "post_value_vnd": int(post_value),
            "post_weight_pct": float(post_value / total_after_flow * 100),
            "gap_after_vnd": int(gap_after),
            "action": action,
            "status": status,
        })

    target_symbols = {target.symbol for target in targets}
    outside_target: list[dict[str, object]] = []
    for holding in holdings:
        if holding.symbol in target_symbols:
            continue
        value = values[holding.symbol]
        outside_target.append({
            "symbol": holding.symbol,
            "sector": sectors.get(holding.symbol, ""),
            "quantity": holding.quantity,
            "market_value_vnd": int(value),
            "weight_pct": float(value / total_after_flow * 100),
            "status": "OUTSIDE_TARGET_NO_ADD",
        })

    hard_breaches: list[str] = []
    for symbol, value in sorted(values.items()):
        if value / total_after_flow > request.max_symbol_weight:
            hard_breaches.append(f"SYMBOL_CAP:{symbol}")
    for sector, value in sorted(sector_values.items()):
        if value / total_after_flow > request.max_sector_weight:
            hard_breaches.append(f"SECTOR_CAP:{sector}")

    next_lot_costs: list[Decimal] = []
    for target in targets:
        lot_gross = target.price * request.lot_size
        lot_all_in = lot_gross * all_in_multiplier
        current_value = values.get(target.symbol, Decimal("0"))
        proposed = current_value + lot_gross
        if proposed > symbol_cap_value:
            continue
        if target.sector and sector_values.get(target.sector, Decimal("0")) + lot_gross > sector_cap_value:
            continue
        before = (current_value - target.target_value) ** 2
        after = (proposed - target.target_value) ** 2
        if before - after > 0:
            next_lot_costs.append(lot_all_in)
    next_lot = min(next_lot_costs) if next_lot_costs else Decimal("0")
    tracking_after = _tracking_error(values, targets, total_after_flow)
    remaining_available = requested_pool - spent
    total_target_weight = sum((target.target_weight for target in targets), Decimal("0"))

    if spent <= 0 and deployable <= 0:
        contribution_status = "HELD_AS_CASH_BY_REGIME_OR_EXISTING_OVERWEIGHT"
    elif spent <= 0:
        contribution_status = "ACCUMULATE_CASH_UNTIL_EXECUTABLE_LOT"
    elif remaining_available > 0:
        contribution_status = "PARTIALLY_DEPLOYED"
    else:
        contribution_status = "FULLY_DEPLOYED"

    warnings: list[str] = [
        "MONTHLY_MODEL_SIGNAL_USED_FOR_IRREGULAR_CONTRIBUTIONS",
        "BUY_ONLY_NO_AUTOMATIC_SELLS",
        "EXECUTION_PRICE_IS_ESTIMATE_NOT_GUARANTEED_FILL",
        "LIVE_ORDERS_DISABLED",
    ]
    if missing_sector:
        warnings.append("SECTOR_CAP_PARTIAL_MISSING_TRUSTED_SECTOR_DATA")
    if hard_breaches:
        warnings.append("EXISTING_PORTFOLIO_RISK_BREACH_REQUIRES_REVIEW")

    return {
        "schema_version": SCHEMA_VERSION,
        "allocator": ALLOCATOR_NAME,
        "created_at": _now_text(),
        "signal_date": str(model.get("signal_date") or ""),
        "champion_model": str(model.get("champion_model") or model.get("historical_reference_model") or ""),
        "contribution_status": contribution_status,
        "extra_cash_vnd": request.extra_cash_vnd,
        "settled_cash_vnd": request.settled_cash_vnd,
        "include_settled_cash": request.include_settled_cash,
        "requested_available_cash_vnd": int(requested_pool),
        "deployable_cash_vnd": int(deployable),
        "estimated_spend_vnd": int(spent),
        "estimated_remaining_vnd": int(remaining_available),
        "remaining_available_cash_vnd": int(remaining_available),
        "cash_after_plan_vnd": int(all_cash_after_flow - spent),
        "target_cash_reserve_vnd": int(target_cash_reserve),
        "current_market_value_vnd": int(current_market_value),
        "total_after_contribution_vnd": int(total_after_flow),
        "equity_budget_pct": float(budget * 100),
        "target_equity_weight_pct": float(total_target_weight * 100),
        "tracking_error_before": float(tracking_before),
        "tracking_error_after": float(tracking_after),
        "tracking_error_reduction": float(tracking_before - tracking_after),
        "next_executable_lot_cost_vnd": int(next_lot),
        "cash_shortfall_to_next_lot_vnd": int(max(Decimal("0"), next_lot - remaining_available)) if next_lot > 0 else 0,
        "lot_size": request.lot_size,
        "buy_fee_bps": str(request.buy_fee_bps),
        "slippage_bps": str(request.slippage_bps),
        "max_symbol_weight_pct": float(request.max_symbol_weight * 100),
        "max_sector_weight_pct": float(request.max_sector_weight * 100),
        "hard_risk_breaches": hard_breaches,
        "rows": rows,
        "outside_target_holdings": outside_target,
        "warnings": warnings,
        "automatic_live_orders_allowed": False,
        "live_capital_approved": False,
    }
