"""Monthly fallback and weekly protection actions for V63."""
from __future__ import annotations

from datetime import date
import math

from . import c3_adaptive_portfolio_v61 as v61
from . import weekly_micro_capital_v43 as v43
from ._v63_contract import Policy, protection_decision
from ._v63_state import SimState, sell_position


def monthly_p1_exits(
    *,
    state: SimState,
    policy: Policy,
    contribution: int,
    scenario: str,
    snapshot: v43.SignalSnapshot,
    preview: v61.PreviewState | None,
    preview_valid: bool,
    trade_day: date,
    prices: v43.PriceStore,
    slippage_bps: float,
    signal_changed: bool,
) -> set[str]:
    if not signal_changed:
        return set()
    rank_by_symbol = {symbol: rank for rank, symbol in enumerate(snapshot.ranking, start=1)}
    exits = v43.compute_exit_symbols(
        state.holdings,
        rank_by_symbol,
        state.outside_counts,
        exit_rank=20,
        exit_months=2,
    )
    blocked: set[str] = set()
    for symbol in exits:
        quantity = state.holdings.get(symbol, 0)
        if quantity <= 0:
            continue
        result = sell_position(
            state=state, policy_id=policy.policy_id, contribution=contribution,
            scenario=scenario, symbol=symbol, quantity=quantity, trade_day=trade_day,
            prices=prices, slippage_bps=slippage_bps, side="SELL_P1",
            metadata={"preview_rank": v61._preview_rank(preview, symbol) if preview_valid else ""},
        )
        if result is None:
            continue
        state.opportunity_lots.pop(symbol, None)
        state.outside_counts[symbol] = 0
        state.protection_hits[symbol] = 0
        state.protection_locked[symbol] = False
        blocked.add(symbol)
    return blocked


def weekly_protection(
    *,
    state: SimState,
    policy: Policy,
    contribution: int,
    scenario: str,
    snapshot: v43.SignalSnapshot,
    preview: v61.PreviewState | None,
    preview_valid: bool,
    trade_day: date,
    prices: v43.PriceStore,
    slippage_bps: float,
) -> set[str]:
    blocked: set[str] = set()
    if not policy.protection_enabled:
        return blocked
    # A protection lock survives weeks without a causally matched preview.
    # Missing/invalid evidence may not silently re-enable core buys.
    if not preview_valid or preview is None:
        for symbol, locked in state.protection_locked.items():
            if locked:
                blocked.add(symbol)
                state.protection_locked_symbol_weeks += 1
        return blocked
    for symbol in snapshot.ranking[:10]:
        if state.holdings.get(symbol, 0) <= 0 and not state.protection_locked.get(symbol, False):
            continue
        decision = protection_decision(
            preview=preview,
            snapshot=snapshot,
            symbol=symbol,
            prior_hits=state.protection_hits.get(symbol, 0),
            currently_locked=state.protection_locked.get(symbol, False),
        )
        state.protection_hits[symbol] = decision.breakdown_hits
        state.protection_locked[symbol] = decision.locked
        if decision.action == "RECOVER":
            state.protection_recovery_count += 1
            state.trade_rows.append({
                "policy": policy.policy_id, "contribution": contribution, "scenario": scenario,
                "trade_day": trade_day.isoformat(), "side": "PROTECTION_RECOVER",
                "symbol": symbol, "quantity": state.holdings.get(symbol, 0),
                "gross_reference_vnd": 0.0, "cash_effect_vnd": 0.0,
                "preview_rank": v61._preview_rank(preview, symbol), "reason": decision.reason,
            })
            continue
        if decision.action not in {"SOFT_TRIM", "FULL_EXIT"}:
            continue
        held = state.holdings.get(symbol, 0)
        if held <= 0:
            continue
        quantity = held if decision.action == "FULL_EXIT" else int(math.floor(held * decision.fraction))
        if quantity <= 0:
            continue
        result = sell_position(
            state=state, policy_id=policy.policy_id, contribution=contribution,
            scenario=scenario, symbol=symbol, quantity=quantity, trade_day=trade_day,
            prices=prices, slippage_bps=slippage_bps,
            side="SELL_PROTECTION_FULL" if decision.action == "FULL_EXIT" else "SELL_PROTECTION_50",
            metadata={
                "preview_rank": v61._preview_rank(preview, symbol),
                "return_5": preview.return_5.get(symbol, 0.0),
                "distance_ma20": preview.distance_ma20.get(symbol, 0.0),
                "breakdown_hits": decision.breakdown_hits,
                "reason": decision.reason,
            },
        )
        if result is None:
            continue
        if decision.action == "FULL_EXIT":
            state.protection_full_exit_count += 1
        else:
            state.protection_soft_trim_count += 1
        blocked.add(symbol)
    for symbol, locked in state.protection_locked.items():
        if locked:
            blocked.add(symbol)
            state.protection_locked_symbol_weeks += 1
    return blocked
