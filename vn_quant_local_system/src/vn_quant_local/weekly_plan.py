"""Kế hoạch tích lũy tuần dựa trên C3 và danh mục thực tế.

P1 canonical vẫn dùng Top-10 và buffer Top-20 hai tháng. V44.4 hiểu khoản nhập
hàng tuần là tiền dự kiến nạp thêm, cộng với tiền khả dụng DNSE. Không gửi lệnh
broker.
"""
from __future__ import annotations

from datetime import datetime
import json
import sqlite3
from typing import Mapping, Sequence

from .broker_portfolio import latest_broker_portfolio
from .core import account_snapshot, load_config, paths, state_db, utc_now

POLICY_ID = "P1_TOP10_UNDERWEIGHT_BUFFER20"
PLANNER_VARIANT = "V44_4_DNSE_CASH_PLUS_WEEKLY_CONTRIBUTION"


def capped_inverse_vol_weights(
    rows: Sequence[Mapping[str, object]], *, cap: float = 0.15
) -> dict[str, float]:
    selected = [
        row
        for row in rows[:10]
        if float(row.get("volatility_60") or 0.0) > 0.0
    ]
    if not selected:
        return {}
    raw = {
        str(row["symbol"]): 1.0 / float(row["volatility_60"])
        for row in selected
    }
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


def planned_buying_power(
    current_cash_vnd: float,
    weekly_contribution_vnd: float,
) -> float:
    """Tiền mua dự kiến = tiền DNSE hiện có + khoản sẽ nạp trong tuần.

    ``weekly_contribution_vnd`` phải là khoản chưa nằm trong số dư DNSE. Nếu đã
    nạp tiền trước khi đồng bộ broker thì người dùng đặt contribution bằng 0 để
    tránh tính hai lần.
    """

    cash = float(current_cash_vnd)
    contribution = float(weekly_contribution_vnd)
    if cash < 0.0:
        raise ValueError("Tiền khả dụng DNSE không được âm")
    if contribution < 0.0:
        raise ValueError("Tiền dự kiến nạp tuần không được âm")
    return cash + contribution


def allocate_buy_orders(
    candidates: Sequence[Mapping[str, object]],
    *,
    budget_vnd: float,
    max_orders: int,
    cost_bps: float,
) -> list[dict[str, object]]:
    if budget_vnd <= 0.0:
        return []
    if max_orders < 1 or max_orders > 5:
        raise ValueError("maximum_buy_orders_per_week phải nằm trong 1..5")
    multiplier = 1.0 + float(cost_bps) / 10_000.0
    ordered: list[dict[str, object]] = []
    for raw in candidates:
        price = float(raw.get("price_vnd") or 0.0)
        ceiling = float(raw.get("budget_ceiling_vnd") or 0.0)
        if price <= 0.0 or ceiling <= 0.0:
            continue
        one_share = price * multiplier
        if one_share > budget_vnd + 1e-9 or one_share > ceiling + 1e-9:
            continue
        row = dict(raw)
        row["one_share_cost_vnd"] = one_share
        row["priority"] = float(raw.get("underweight_pct") or 0.0)
        ordered.append(row)
    ordered.sort(
        key=lambda row: (
            -float(row["priority"]),
            -float(row.get("target_gap_vnd") or 0.0),
            int(row.get("rank") or 10**9),
        )
    )

    remaining = float(budget_vnd)
    selected: list[dict[str, object]] = []
    for row in ordered:
        if len(selected) >= max_orders:
            break
        one_share = float(row["one_share_cost_vnd"])
        if one_share <= remaining + 1e-9:
            selected.append(
                {**row, "quantity": 1, "estimated_cost_vnd": one_share}
            )
            remaining -= one_share

    while selected:
        best: dict[str, object] | None = None
        best_residual = 0.0
        for row in selected:
            residual = float(row["budget_ceiling_vnd"]) - float(
                row["estimated_cost_vnd"]
            )
            one_share = float(row["one_share_cost_vnd"])
            if residual + 1e-9 >= one_share and remaining + 1e-9 >= one_share:
                score = min(residual, remaining)
                if score > best_residual + 1e-9:
                    best = row
                    best_residual = score
        if best is None:
            break
        one_share = float(best["one_share_cost_vnd"])
        max_extra = int(min(remaining, best_residual) // one_share)
        if max_extra <= 0:
            break
        best["quantity"] = int(best["quantity"]) + max_extra
        extra_cost = max_extra * one_share
        best["estimated_cost_vnd"] = (
            float(best["estimated_cost_vnd"]) + extra_cost
        )
        remaining -= extra_cost

    return [
        {
            "symbol": str(row["symbol"]),
            "rank": int(row["rank"]),
            "quantity": int(row["quantity"]),
            "price_vnd": float(row["price_vnd"]),
            "estimated_cost_vnd": round(
                float(row["estimated_cost_vnd"]), 2
            ),
            "actual_weight": float(row.get("actual_weight") or 0.0),
            "target_weight": float(row.get("target_weight") or 0.0),
            "underweight_pct": float(row.get("underweight_pct") or 0.0),
            "target_gap_vnd": float(row.get("target_gap_vnd") or 0.0),
            "score": float(row.get("score") or 0.0),
            "reason": "TOP10_C3_AND_PORTFOLIO_UNDERWEIGHT",
        }
        for row in selected
    ]


def _latest_two_monthly_rankings() -> list[dict[str, object]]:
    with state_db() as db:
        signal_days = [
            str(row[0])
            for row in db.execute(
                "SELECT DISTINCT signal_day FROM rankings "
                "WHERE signal_kind='MONTHLY_CANONICAL' "
                "ORDER BY signal_day DESC LIMIT 2"
            ).fetchall()
        ]
        result: list[dict[str, object]] = []
        for signal_day in signal_days:
            run = db.execute(
                "SELECT r.run_id,r.finished_at FROM runs r "
                "JOIN rankings k ON k.run_id=r.run_id "
                "WHERE r.status='SUCCESS' "
                "AND k.signal_kind='MONTHLY_CANONICAL' "
                "AND k.signal_day=? ORDER BY r.finished_at DESC LIMIT 1",
                (signal_day,),
            ).fetchone()
            if run is None:
                continue
            rows = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM rankings WHERE run_id=? "
                    "AND signal_kind='MONTHLY_CANONICAL' ORDER BY rank",
                    (run["run_id"],),
                ).fetchall()
            ]
            result.append(
                {
                    "signal_day": signal_day,
                    "run_id": run["run_id"],
                    "rows": rows,
                }
            )
    return result


def _latest_market_prices(
    symbols: Sequence[str],
) -> tuple[str, dict[str, float]]:
    p = paths()
    db = sqlite3.connect(p.market_db)
    try:
        day = str(
            db.execute(
                "SELECT MAX(day) FROM bars WHERE upper(asset_type)='INDEX'"
            ).fetchone()[0]
        )
        prices: dict[str, float] = {}
        multiplier = float(
            load_config().get("model", {}).get("price_multiplier", 1000.0)
        )
        for symbol in sorted(set(symbols)):
            row = db.execute(
                "SELECT close FROM bars WHERE upper(asset_type)='STOCK' "
                "AND symbol=? AND day<=? ORDER BY day DESC LIMIT 1",
                (symbol, day),
            ).fetchone()
            if row is not None:
                prices[symbol] = float(row[0]) * multiplier
    finally:
        db.close()
    return day, prices


def _position_reviews(
    *,
    holdings: Mapping[str, int],
    sellable: Mapping[str, int],
    prices: Mapping[str, float],
    current_rank: Mapping[str, int],
    previous_rank: Mapping[str, int],
    target_weights: Mapping[str, float],
    account_value: float,
    have_two_months: bool,
) -> list[dict[str, object]]:
    reviews: list[dict[str, object]] = []
    for symbol in sorted(holdings):
        quantity = int(holdings[symbol])
        value = quantity * float(prices.get(symbol, 0.0))
        actual_weight = value / account_value if account_value > 0 else 0.0
        target_weight = float(target_weights.get(symbol, 0.0))
        rank_now = int(current_rank.get(symbol, 10**9))
        rank_prev = int(previous_rank.get(symbol, 10**9))
        action = "HOLD"
        reason = "STILL_INSIDE_BUFFER_OR_TARGET"
        if have_two_months and rank_now > 20 and rank_prev > 20:
            action = (
                "EXIT_CANDIDATE"
                if int(sellable.get(symbol, quantity)) > 0
                else "WAIT_SELLABLE"
            )
            reason = "OUTSIDE_TOP20_TWO_CONSECUTIVE_MONTHS"
        elif rank_now > 20:
            action = "WATCH"
            reason = "OUTSIDE_TOP20_ONE_MONTH_ONLY"
        elif rank_now > 10:
            action = "HOLD_NO_ADD"
            reason = "INSIDE_TOP20_BUFFER_BUT_OUTSIDE_TOP10"
        if (
            action in {"HOLD", "HOLD_NO_ADD"}
            and target_weight > 0.0
            and actual_weight > max(0.20, target_weight * 1.50)
        ):
            action = "REVIEW_TRIM"
            reason = "POSITION_MATERIALLY_ABOVE_TARGET"
        reviews.append(
            {
                "symbol": symbol,
                "quantity": quantity,
                "sellable_quantity": int(sellable.get(symbol, quantity)),
                "market_value_vnd": value,
                "actual_weight": actual_weight,
                "target_weight": target_weight,
                "current_rank": None if rank_now >= 10**9 else rank_now,
                "previous_rank": None if rank_prev >= 10**9 else rank_prev,
                "action": action,
                "reason": reason,
            }
        )
    return reviews


def create_weekly_plan(
    *,
    weekly_budget_vnd: float | None = None,
    maximum_buy_orders: int | None = None,
) -> dict[str, object]:
    rankings = _latest_two_monthly_rankings()
    if not rankings:
        raise ValueError(
            "Chưa có MONTHLY_CANONICAL ranking; hãy chạy model trước"
        )
    latest = rankings[0]
    current_rows = list(latest["rows"])
    current_rank = {
        str(row["symbol"]): int(row["rank"]) for row in current_rows
    }
    previous_rank = (
        {
            str(row["symbol"]): int(row["rank"])
            for row in rankings[1]["rows"]
        }
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
    current_cash = max(float(account_row["cash_vnd"]), 0.0)
    configured_contribution = float(account_row["weekly_contribution_vnd"])
    planned_contribution = (
        configured_contribution
        if weekly_budget_vnd is None
        else float(weekly_budget_vnd)
    )
    buying_power = planned_buying_power(current_cash, planned_contribution)

    config = load_config()
    policy = config.get("weekly_policy", {})
    planning_cost_bps = float(policy.get("planning_cost_bps", 50.0))
    default_max_orders = int(policy.get("maximum_buy_orders_per_week", 3))
    max_orders = (
        default_max_orders
        if maximum_buy_orders is None
        else int(maximum_buy_orders)
    )
    if max_orders < 1 or max_orders > 5:
        raise ValueError("Số lệnh mua tối đa phải nằm trong 1..5")

    broker = latest_broker_portfolio()
    broker_positions = {
        str(row["symbol"]): row
        for row in (broker or {}).get("positions", [])
    }
    sellable = {
        symbol: int(row.get("sellable_quantity") or holdings.get(symbol, 0))
        for symbol, row in broker_positions.items()
    }

    symbols = set(holdings) | {
        str(row["symbol"]) for row in current_rows[:20]
    }
    market_day, prices = _latest_market_prices(sorted(symbols))
    holdings_value = sum(
        quantity * prices.get(symbol, 0.0)
        for symbol, quantity in holdings.items()
    )
    projected_account_value = holdings_value + buying_power

    target_rows = current_rows[:10]
    weights = capped_inverse_vol_weights(target_rows, cap=0.15)
    established = sum(
        1
        for row in target_rows
        if holdings.get(str(row["symbol"]), 0) > 0
    )

    candidates: list[dict[str, object]] = []
    for row in target_rows:
        symbol = str(row["symbol"])
        price = prices.get(symbol)
        if price is None or price <= 0.0:
            continue
        quantity = holdings.get(symbol, 0)
        actual_value = quantity * price
        actual_weight = (
            actual_value / projected_account_value
            if projected_account_value > 0
            else 0.0
        )
        target_weight = float(weights.get(symbol, 0.0))
        target_value = target_weight * projected_account_value
        target_gap = max(target_value - actual_value, 0.0)
        resulting_count = max(
            established + (0 if quantity > 0 else 1), 1
        )
        effective_cap = max(0.15, 1.0 / min(resulting_count, 10))
        cap_gap = max(
            effective_cap * projected_account_value - actual_value, 0.0
        )
        one_share_cost = price * (1.0 + planning_cost_bps / 10_000.0)
        budget_ceiling = min(cap_gap, max(target_gap, one_share_cost))
        candidates.append(
            {
                "symbol": symbol,
                "rank": int(row["rank"]),
                "score": float(row.get("score") or 0.0),
                "price_vnd": price,
                "quantity_owned": quantity,
                "actual_value_vnd": actual_value,
                "actual_weight": actual_weight,
                "target_weight": target_weight,
                "target_value_vnd": target_value,
                "target_gap_vnd": target_gap,
                "underweight_pct": max(
                    target_weight - actual_weight, 0.0
                ),
                "effective_cap": effective_cap,
                "budget_ceiling_vnd": budget_ceiling,
                "volatility_60": float(
                    row.get("volatility_60") or 0.0
                ),
                "low_volatility_pct": float(
                    row.get("low_volatility_pct") or 0.0
                ),
                "relative_strength_120_pct": float(
                    row.get("relative_strength_120_pct") or 0.0
                ),
                "high_52_week_pct": float(
                    row.get("high_52_week_pct") or 0.0
                ),
            }
        )
    candidates.sort(
        key=lambda row: (
            -float(row["underweight_pct"]),
            -float(row["target_gap_vnd"]),
            int(row["rank"]),
        )
    )

    buy_orders = allocate_buy_orders(
        candidates,
        budget_vnd=buying_power,
        max_orders=max_orders,
        cost_bps=planning_cost_bps,
    )
    single_order = allocate_buy_orders(
        candidates,
        budget_vnd=buying_power,
        max_orders=1,
        cost_bps=planning_cost_bps,
    )
    total_buy = sum(
        float(row["estimated_cost_vnd"]) for row in buy_orders
    )
    reviews = _position_reviews(
        holdings=holdings,
        sellable=sellable,
        prices=prices,
        current_rank=current_rank,
        previous_rank=previous_rank,
        target_weights=weights,
        account_value=projected_account_value,
        have_two_months=len(rankings) >= 2,
    )
    exit_candidates = [
        row for row in reviews if row["action"] == "EXIT_CANDIDATE"
    ]

    plan_id = "plan-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    rationale = {
        "policy": POLICY_ID,
        "planner_variant": PLANNER_VARIANT,
        "market_day": market_day,
        "monthly_signal_day": latest["signal_day"],
        "monthly_ranking_run_id": latest["run_id"],
        "portfolio_source": (
            "DNSE_BROKER_SNAPSHOT" if broker else "MANUAL_LOCAL_ACCOUNT"
        ),
        "broker_snapshot_id": (broker or {}).get("snapshot_id"),
        "broker_snapshot_time": (broker or {}).get("captured_at"),
        "broker_safe_cash_vnd": current_cash,
        "planned_weekly_contribution_vnd": planned_contribution,
        "requested_weekly_budget_vnd": planned_contribution,
        "spendable_budget_vnd": buying_power,
        "projected_account_value_vnd": projected_account_value,
        "cash_semantics": (
            "SPENDABLE_EQUALS_BROKER_AVAILABLE_CASH_PLUS_"
            "PLANNED_WEEKLY_CONTRIBUTION"
        ),
        "maximum_buy_orders": max_orders,
        "planning_cost_bps": planning_cost_bps,
        "weights": weights,
        "buy_candidates": candidates,
        "buy_orders": buy_orders,
        "single_order_baseline": single_order,
        "position_reviews": reviews,
        "buffer_rule": (
            "EXIT_CANDIDATE_ONLY_IF_OUTSIDE_TOP20_TWO_"
            "CONSECUTIVE_MONTHLY_SIGNALS"
        ),
        "sell_proceeds_reused_only_after_actual_broker_sync": True,
        "odd_lot_share_unit": 1,
        "multi_buy_research_status": (
            "IMPLEMENTED_NOT_YET_HISTORICALLY_REVALIDATED"
        ),
    }
    first_buy = buy_orders[0] if buy_orders else None
    plan = {
        "status": "SUCCESS",
        "plan_id": plan_id,
        "created_at": utc_now(),
        "policy": POLICY_ID,
        "planner_variant": PLANNER_VARIANT,
        "ranking_run_id": latest["run_id"],
        "signal_day": latest["signal_day"],
        "market_day": market_day,
        "portfolio_source": rationale["portfolio_source"],
        "weekly_contribution_vnd": planned_contribution,
        "weekly_budget_vnd": planned_contribution,
        "available_cash_vnd": current_cash,
        "spendable_budget_vnd": buying_power,
        "projected_account_value_vnd": projected_account_value,
        "remaining_budget_vnd": max(buying_power - total_buy, 0.0),
        "buy_orders": buy_orders,
        "single_order_baseline": single_order,
        "position_reviews": reviews,
        "exit_candidates": exit_candidates,
        "buy_symbol": str(first_buy["symbol"]) if first_buy else None,
        "buy_quantity": int(first_buy["quantity"]) if first_buy else 0,
        "estimated_buy_value_vnd": total_buy,
        "rationale": rationale,
        "research_only": True,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }
    with state_db() as db:
        db.execute(
            "INSERT INTO weekly_plans("
            "plan_id,created_at,ranking_run_id,contribution_vnd,"
            "available_cash_vnd,buy_symbol,buy_quantity,"
            "estimated_buy_value_vnd,sell_symbols_json,rationale_json,"
            "research_only) VALUES(?,?,?,?,?,?,?,?,?,?,1)",
            (
                plan_id,
                plan["created_at"],
                latest["run_id"],
                planned_contribution,
                current_cash,
                plan["buy_symbol"],
                plan["buy_quantity"],
                total_buy,
                json.dumps([row["symbol"] for row in exit_candidates]),
                json.dumps(rationale, ensure_ascii=False, sort_keys=True),
            ),
        )
    output = paths().outputs / f"{plan_id}.json"
    output.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return plan


def latest_weekly_plan() -> dict[str, object] | None:
    with state_db() as db:
        row = db.execute(
            "SELECT * FROM weekly_plans ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["sell_symbols"] = json.loads(
        str(result.pop("sell_symbols_json"))
    )
    result["rationale"] = json.loads(str(result.pop("rationale_json")))
    result["buy_orders"] = result["rationale"].get("buy_orders", [])
    result["single_order_baseline"] = result["rationale"].get(
        "single_order_baseline", []
    )
    result["position_reviews"] = result["rationale"].get(
        "position_reviews", []
    )
    result["exit_candidates"] = [
        row
        for row in result["position_reviews"]
        if row.get("action") == "EXIT_CANDIDATE"
    ]
    contribution = float(result["contribution_vnd"])
    available_cash = float(result["available_cash_vnd"])
    spendable = float(
        result["rationale"].get(
            "spendable_budget_vnd",
            planned_buying_power(available_cash, contribution),
        )
    )
    result["weekly_contribution_vnd"] = contribution
    result["weekly_budget_vnd"] = contribution
    result["spendable_budget_vnd"] = spendable
    result["projected_account_value_vnd"] = result["rationale"].get(
        "projected_account_value_vnd"
    )
    result["remaining_budget_vnd"] = max(
        spendable
        - sum(
            float(item.get("estimated_cost_vnd") or 0.0)
            for item in result["buy_orders"]
        ),
        0.0,
    )
    return result
