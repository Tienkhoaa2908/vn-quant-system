"""One-share and odd-lot aware periodic-contribution allocator.

The validated model target remains monthly.  Cash may arrive at any time and is
allocated against the complete current portfolio.  The underlying v17 greedy
optimizer is reused with a default quantity step of one share, then the result
is enriched with round-lot and odd-lot execution instructions.

This module only prepares a plan.  It never submits a live order.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping, Sequence

from . import contribution_portfolio_v17 as v17
from .portfolio_planner import Holding

SCHEMA_VERSION = "contribution_portfolio_v18"
ALLOCATOR_NAME = "cashflow_target_gap_one_share_odd_lot_v3"
ROUND_LOT_SIZE = 100


@dataclass(frozen=True)
class ContributionPlanRequest(v17.ContributionPlanRequest):
    """Contribution request with one-share execution granularity by default."""

    lot_size: int = 1


def _execution_route(quantity: int) -> str:
    if quantity <= 0:
        return "NO_ORDER"
    round_quantity = quantity // ROUND_LOT_SIZE * ROUND_LOT_SIZE
    odd_quantity = quantity % ROUND_LOT_SIZE
    if round_quantity and odd_quantity:
        return "ROUND_LOT_AND_ODD_LOT_SEPARATE_ORDERS"
    if round_quantity:
        return "ROUND_LOT_ORDER"
    return "ODD_LOT_LIMIT_ORDER"


def _decimal(value: object) -> Decimal | None:
    try:
        result = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, AttributeError):
        return None
    return result if result.is_finite() and result > 0 else None


def _cheapest_priced_share_cost(
    *,
    price_vnd: Mapping[str, object],
    allocation_rows: Sequence[Mapping[str, object]],
    request: ContributionPlanRequest,
) -> Decimal:
    multiplier = Decimal("1") + (
        Decimal(str(request.buy_fee_bps)) + Decimal(str(request.slippage_bps))
    ) / Decimal("10000")
    costs: list[Decimal] = []
    for row in allocation_rows:
        symbol = str(row.get("symbol") or row.get("ma") or "").strip().upper()
        price = _decimal(price_vnd.get(symbol)) if symbol else None
        if price is not None:
            costs.append(price * multiplier)
    return min(costs) if costs else Decimal("0")


def build_contribution_plan(
    *,
    holdings: Sequence[Holding],
    price_vnd: Mapping[str, object],
    allocation_rows: Sequence[Mapping[str, object]],
    predictions: Sequence[Mapping[str, object]],
    model: Mapping[str, object],
    request: ContributionPlanRequest,
    sector_by_symbol: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Allocate cash in integer shares without exceeding available cash.

    Quantity step defaults to one.  Recommendations of 1-99 residual shares
    are marked as odd-lot limit orders; quantities of at least 100 are split
    into a round-lot component and an odd-lot residual when required.
    """
    result = v17.build_contribution_plan(
        holdings=holdings,
        price_vnd=price_vnd,
        allocation_rows=allocation_rows,
        predictions=predictions,
        model=model,
        request=request,
        sector_by_symbol=sector_by_symbol,
    )
    rows = result.get("rows", [])
    odd_lot_present = False
    for row in rows:
        if not isinstance(row, dict):
            continue
        quantity = int(row.get("recommended_buy_quantity") or 0)
        round_quantity = quantity // ROUND_LOT_SIZE * ROUND_LOT_SIZE
        odd_quantity = quantity % ROUND_LOT_SIZE
        odd_lot_present = odd_lot_present or odd_quantity > 0
        row["recommended_round_lot_quantity"] = round_quantity
        row["recommended_odd_lot_quantity"] = odd_quantity
        row["execution_route"] = _execution_route(quantity)
        if quantity <= 0 and row.get("status") == "ACCUMULATE_FOR_EXECUTABLE_LOT":
            row["status"] = "WAIT_FOR_ONE_SHARE_OR_RISK_ROOM"

    if (
        result.get("contribution_status") == "ACCUMULATE_CASH_UNTIL_EXECUTABLE_LOT"
    ):
        result["contribution_status"] = (
            "ACCUMULATE_CASH_UNTIL_ONE_SHARE_AFFORDABLE_OR_RISK_ROOM"
        )

    cheapest_share = _cheapest_priced_share_cost(
        price_vnd=price_vnd,
        allocation_rows=allocation_rows,
        request=request,
    )
    remaining = Decimal(str(result.get("remaining_available_cash_vnd") or 0))
    cheapest_shortfall = max(Decimal("0"), cheapest_share - remaining)
    next_valid_share = Decimal(
        str(result.get("next_executable_lot_cost_vnd") or 0)
    )
    valid_shortfall = Decimal(
        str(result.get("cash_shortfall_to_next_lot_vnd") or 0)
    )
    spent = Decimal(str(result.get("estimated_spend_vnd") or 0))
    if spent > 0:
        one_share_blocker = ""
    elif next_valid_share > 0 and valid_shortfall > 0:
        one_share_blocker = "CASH_SHORTFALL_TO_NEXT_TARGET_IMPROVING_SHARE"
    elif cheapest_share > remaining:
        one_share_blocker = "CASH_BELOW_CHEAPEST_PRICED_SHARE"
    else:
        one_share_blocker = "TARGET_OR_RISK_CAP_BLOCKS_ADDITIONAL_SHARE"

    warnings = [str(item) for item in result.get("warnings", [])]
    warnings = [
        item
        for item in warnings
        if item != "EXECUTION_PRICE_IS_ESTIMATE_NOT_GUARANTEED_FILL"
    ]
    warnings.append("EXECUTION_PRICE_IS_ESTIMATE_NOT_GUARANTEED_FILL")
    warnings.append("ODD_LOT_1_TO_99_REQUIRES_SEPARATE_LIMIT_ORDER_BOOK")
    warnings.append("ODD_LOT_PRICE_MAY_DIFFER_FROM_ROUND_LOT_REFERENCE_PRICE")
    if odd_lot_present:
        warnings.append("PLAN_CONTAINS_ODD_LOT_ORDERS")

    result["schema_version"] = SCHEMA_VERSION
    result["allocator"] = ALLOCATOR_NAME
    result["quantity_step"] = request.lot_size
    result["round_lot_size"] = ROUND_LOT_SIZE
    result["odd_lot_supported"] = request.lot_size == 1
    result["next_executable_share_cost_vnd"] = int(next_valid_share)
    result["cash_shortfall_to_next_share_vnd"] = int(valid_shortfall)
    result["cheapest_priced_share_all_in_vnd"] = int(cheapest_share)
    result["cash_shortfall_to_cheapest_priced_share_vnd"] = int(
        cheapest_shortfall
    )
    result["one_share_blocker"] = one_share_blocker
    result["warnings"] = list(dict.fromkeys(warnings))
    result["automatic_live_orders_allowed"] = False
    result["live_capital_approved"] = False
    return result


__all__ = [
    "SCHEMA_VERSION",
    "ALLOCATOR_NAME",
    "ROUND_LOT_SIZE",
    "ContributionPlanRequest",
    "build_contribution_plan",
]
