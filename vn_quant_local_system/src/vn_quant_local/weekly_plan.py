"""Weekly cash-flow plan using the frozen P1 policy selected by V43.1.

Policy:
* monthly canonical C3 Top-10;
* buy one most-underweight Top-10 symbol each week;
* sell only after a symbol is outside Top-20 in two consecutive monthly signals;
* odd-lot unit is one share;
* output is research guidance, never a broker order.
"""
from __future__ import annotations

from datetime import datetime
import json
import sqlite3
from typing import Mapping, Sequence

from .core import account_snapshot, load_config, paths, state_db, utc_now

POLICY_ID = "P1_TOP10_UNDERWEIGHT_BUFFER20"


def capped_inverse_vol_weights(rows: Sequence[Mapping[str, object]], *, cap: float = 0.15) -> dict[str, float]:
    selected = [row for row in rows[:10] if float(row.get("volatility_60") or 0.0) > 0.0]
    if not selected:
        return {}
    raw = {str(row["symbol"]): 1.0 / float(row["volatility_60"]) for row in selected}
    weights = {symbol: 0.0 for symbol in raw}
    remaining = set(raw)
    remaining_weight = 1.0
    while remaining and remaining_weight > 1e-12:
        total = sum(raw[symbol] for symbol in remaining)
        if total <= 0.0:
            share = remaining_weight / len(remaining)
            for symbol in remaining:
                weights[symbol] += share
            break
        capped_any = False
        for symbol in list(remaining):
            proposed = remaining_weight * raw[symbol] / total
            available = cap - weights[symbol]
            if proposed >= available - 1e-12:
                allocation = max(available, 0.0)
                weights[symbol] += allocation
                remaining_weight -= allocation
                remaining.remove(symbol)
                capped_any = True
        if not capped_any:
            for symbol in remaining:
                weights[symbol] += remaining_weight * raw[symbol] / total
            remaining_weight = 0.0
    return weights


def _latest_two_monthly_rankings() -> list[dict[str, object]]:
    with state_db() as db:
        signal_days = [
            str(row[0])
            for row in db.execute(
                """
                SELECT DISTINCT signal_day FROM rankings
                WHERE signal_kind='MONTHLY_CANONICAL'
                ORDER BY signal_day DESC LIMIT 2
                """
            ).fetchall()
        ]
        result: list[dict[str, object]] = []
        for signal_day in signal_days:
            run = db.execute(
                """
                SELECT r.run_id,r.finished_at FROM runs r
                JOIN rankings k ON k.run_id=r.run_id
                WHERE r.status='SUCCESS' AND k.signal_kind='MONTHLY_CANONICAL'
                  AND k.signal_day=?
                ORDER BY r.finished_at DESC LIMIT 1
                """,
                (signal_day,),
            ).fetchone()
            if run is None:
                continue
            rows = [dict(row) for row in db.execute(
                "SELECT * FROM rankings WHERE run_id=? AND signal_kind='MONTHLY_CANONICAL' ORDER BY rank",
                (run["run_id"],),
            ).fetchall()]
            result.append({"signal_day": signal_day, "run_id": run["run_id"], "rows": rows})
    return result


def _latest_market_prices(symbols: Sequence[str]) -> tuple[str, dict[str, float]]:
    p = paths()
    db = sqlite3.connect(p.market_db)
    try:
        day = str(db.execute(
            "SELECT MAX(day) FROM bars WHERE upper(asset_type)='INDEX'"
        ).fetchone()[0])
        prices: dict[str, float] = {}
        multiplier = float(load_config().get("model", {}).get("price_multiplier", 1000.0))
        for symbol in sorted(set(symbols)):
            row = db.execute(
                """
                SELECT close FROM bars
                WHERE upper(asset_type)='STOCK' AND symbol=? AND day<=?
                ORDER BY day DESC LIMIT 1
                """,
                (symbol, day),
            ).fetchone()
            if row is not None:
                prices[symbol] = float(row[0]) * multiplier
    finally:
        db.close()
    return day, prices


def create_weekly_plan() -> dict[str, object]:
    rankings = _latest_two_monthly_rankings()
    if not rankings:
        raise ValueError("Chưa có MONTHLY_CANONICAL ranking; hãy chạy model trước")
    latest = rankings[0]
    current_rows = list(latest["rows"])
    current_rank = {str(row["symbol"]): int(row["rank"]) for row in current_rows}
    previous_rank = (
        {str(row["symbol"]): int(row["rank"]) for row in rankings[1]["rows"]}
        if len(rankings) > 1
        else {}
    )

    account = account_snapshot()
    holdings = {
        str(row["symbol"]): int(row["quantity"])
        for row in account["holdings"]
        if int(row["quantity"]) > 0
    }
    account_row = account["account"]
    cash = float(account_row["cash_vnd"])
    contribution = float(account_row["weekly_contribution_vnd"])

    symbols = set(holdings) | {str(row["symbol"]) for row in current_rows[:20]}
    market_day, prices = _latest_market_prices(sorted(symbols))

    sell_symbols = (
        sorted(
            symbol
            for symbol in holdings
            if current_rank.get(symbol, 10**9) > 20
            and previous_rank.get(symbol, 10**9) > 20
        )
        if len(rankings) >= 2
        else []
    )
    estimated_sell_proceeds = sum(
        holdings[symbol] * prices.get(symbol, 0.0) for symbol in sell_symbols
    )
    available = cash + contribution + estimated_sell_proceeds

    live_holdings = {
        symbol: quantity
        for symbol, quantity in holdings.items()
        if symbol not in sell_symbols
    }
    holdings_value = sum(
        quantity * prices.get(symbol, 0.0)
        for symbol, quantity in live_holdings.items()
    )
    account_value = available + holdings_value

    target_rows = current_rows[:10]
    weights = capped_inverse_vol_weights(target_rows, cap=0.15)
    established = sum(1 for row in target_rows if live_holdings.get(str(row["symbol"]), 0) > 0)
    config = load_config()
    planning_cost_bps = float(config.get("weekly_policy", {}).get("planning_cost_bps", 50.0))

    candidates: list[dict[str, object]] = []
    for row in target_rows:
        symbol = str(row["symbol"])
        price = prices.get(symbol)
        if price is None or price <= 0.0:
            continue
        quantity = live_holdings.get(symbol, 0)
        actual_value = quantity * price
        target_value = float(weights.get(symbol, 0.0)) * account_value
        target_gap = max(target_value - actual_value, 0.0)
        resulting_count = max(established + (0 if quantity > 0 else 1), 1)
        effective_cap = max(0.15, 1.0 / min(resulting_count, 10))
        cap_gap = max(effective_cap * account_value - actual_value, 0.0)
        one_share_cost = price * (1.0 + planning_cost_bps / 10_000.0)
        desired_budget = min(
            available,
            cap_gap,
            max(target_gap, min(contribution, available), one_share_cost),
        )
        affordable = int(desired_budget // one_share_cost)
        candidates.append(
            {
                "symbol": symbol,
                "rank": int(row["rank"]),
                "price_vnd": price,
                "actual_value_vnd": actual_value,
                "target_weight": float(weights.get(symbol, 0.0)),
                "target_value_vnd": target_value,
                "target_gap_vnd": target_gap,
                "effective_cap": effective_cap,
                "budget_vnd": desired_budget,
                "affordable_quantity": affordable,
            }
        )
    candidates.sort(key=lambda row: (-float(row["target_gap_vnd"]), int(row["rank"])))
    selected = next((row for row in candidates if int(row["affordable_quantity"]) >= 1), None)
    buy_symbol = str(selected["symbol"]) if selected else None
    buy_quantity = int(selected["affordable_quantity"]) if selected else 0
    estimated_buy = (
        buy_quantity * float(selected["price_vnd"]) * (1.0 + planning_cost_bps / 10_000.0)
        if selected else 0.0
    )

    plan_id = "plan-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    rationale = {
        "policy": POLICY_ID,
        "market_day": market_day,
        "monthly_signal_day": latest["signal_day"],
        "monthly_ranking_run_id": latest["run_id"],
        "cash_before_contribution_vnd": cash,
        "weekly_contribution_vnd": contribution,
        "estimated_sell_proceeds_vnd": estimated_sell_proceeds,
        "available_after_contribution_and_sells_vnd": available,
        "weights": weights,
        "buy_candidates": candidates,
        "buffer_rule": "SELL_IF_OUTSIDE_TOP20_TWO_CONSECUTIVE_MONTHLY_SIGNALS",
        "one_buy_order_per_week": True,
        "odd_lot_share_unit": 1,
    }
    plan = {
        "status": "SUCCESS",
        "plan_id": plan_id,
        "created_at": utc_now(),
        "policy": POLICY_ID,
        "ranking_run_id": latest["run_id"],
        "signal_day": latest["signal_day"],
        "market_day": market_day,
        "sell_symbols": sell_symbols,
        "estimated_sell_proceeds_vnd": estimated_sell_proceeds,
        "buy_symbol": buy_symbol,
        "buy_quantity": buy_quantity,
        "estimated_buy_value_vnd": estimated_buy,
        "available_cash_vnd": available,
        "rationale": rationale,
        "research_only": True,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }
    with state_db() as db:
        db.execute(
            """
            INSERT INTO weekly_plans(
                plan_id,created_at,ranking_run_id,contribution_vnd,
                available_cash_vnd,buy_symbol,buy_quantity,
                estimated_buy_value_vnd,sell_symbols_json,rationale_json,research_only
            ) VALUES(?,?,?,?,?,?,?,?,?,?,1)
            """,
            (
                plan_id,
                plan["created_at"],
                latest["run_id"],
                contribution,
                available,
                buy_symbol,
                buy_quantity,
                estimated_buy,
                json.dumps(sell_symbols),
                json.dumps(rationale, sort_keys=True),
            ),
        )
    output = paths().outputs / f"{plan_id}.json"
    output.write_text(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return plan


def latest_weekly_plan() -> dict[str, object] | None:
    with state_db() as db:
        row = db.execute("SELECT * FROM weekly_plans ORDER BY created_at DESC LIMIT 1").fetchone()
    if row is None:
        return None
    result = dict(row)
    result["sell_symbols"] = json.loads(str(result.pop("sell_symbols_json")))
    result["rationale"] = json.loads(str(result.pop("rationale_json")))
    return result
