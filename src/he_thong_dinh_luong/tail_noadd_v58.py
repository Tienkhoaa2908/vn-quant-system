"""V58 research-only causal loss-aware NO-ADD study for C3/P1.

V57 tail results are intentionally superseded. Every loss-aware decision in
this module observes only the close of a session strictly before the execution
session. A decision first affects the next weekly/session open.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path
from statistics import median
from typing import Mapping, Sequence
from zipfile import ZIP_DEFLATED, ZipFile
import argparse
import bisect
import json

from . import weekly_micro_capital_v43 as base
from . import weekly_micro_capital_v43_1 as v43_1

SCHEMA_VERSION = "tail_noadd_v58_causal"
BASE_POLICY = "P1_TOP10_UNDERWEIGHT_BUFFER20"
DEFAULT_ANALYSIS_END = date(2026, 7, 31)
DEFAULT_HOLDOUT_START = date(2022, 1, 1)
LOSS_DECISION_TIMING = "PREVIOUS_SESSION_CLOSE_TO_CURRENT_OPEN"


@dataclass(frozen=True)
class NoAddSpec:
    variant_id: str
    nav_loss_budget: float | None = None
    rank_loss_exit: bool = False


VARIANTS: tuple[NoAddSpec, ...] = (
    NoAddSpec("BASELINE"),
    NoAddSpec("NOADD_075", nav_loss_budget=0.0075),
    NoAddSpec("NOADD_100", nav_loss_budget=0.0100),
    NoAddSpec("NOADD_125", nav_loss_budget=0.0125),
    NoAddSpec("RANKLOSS_EXIT_100", nav_loss_budget=0.0100, rank_loss_exit=True),
)


def previous_session_day(
    calendar: Sequence[date], execution_day: date
) -> date | None:
    """Return the latest market session strictly before ``execution_day``."""

    index = bisect.bisect_left(calendar, execution_day) - 1
    if index < 0:
        return None
    observed = calendar[index]
    if observed >= execution_day:
        raise AssertionError("V58_CAUSALITY_GUARD_FAILED")
    return observed


def _position_loss_nav(
    symbol: str,
    qty: int,
    avg_cost: float,
    *,
    prices: base.PriceStore,
    observation_day: date,
    nav: float,
) -> float:
    mark = prices.latest_close(symbol, observation_day)
    if mark is None or mark <= 0 or qty <= 0 or avg_cost <= 0 or nav <= 0:
        return 0.0
    return (float(mark) - avg_cost) * qty / nav


def causal_loss_observation(
    symbol: str,
    qty: int,
    avg_cost: float,
    *,
    prices: base.PriceStore,
    calendar: Sequence[date],
    execution_day: date,
    nav: float,
) -> tuple[date | None, float]:
    """Observe loss using only information available before execution open."""

    observation_day = previous_session_day(calendar, execution_day)
    if observation_day is None:
        return None, 0.0
    return (
        observation_day,
        _position_loss_nav(
            symbol,
            qty,
            avg_cost,
            prices=prices,
            observation_day=observation_day,
            nav=nav,
        ),
    )


def simulate(
    *,
    spec: NoAddSpec,
    contribution: int,
    scenario: str,
    snapshots: Sequence[base.SignalSnapshot],
    prices: base.PriceStore,
    weekly_days: Sequence[date],
    analysis_end: date,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    policy = dict(v43_1.POLICIES[BASE_POLICY])
    slippage_bps = float(base.SCENARIOS[scenario]["slippage_bps"])
    signal_days = [snapshot.day for snapshot in snapshots]
    weekly = [day for day in weekly_days if day <= analysis_end]

    cash = 0.0
    holdings: dict[str, int] = {}
    average_cost: dict[str, float] = {}
    outside_counts: dict[str, int] = {}
    blocked_signal_index: dict[str, int] = {}
    current_signal_index = -1
    current_snapshot: base.SignalSnapshot | None = None
    round_robin_pointer = 0

    fund_units = 0.0
    unit_price = 1.0
    peak = 1.0
    max_drawdown = 0.0
    fees_total = 0.0
    buy_count = 0
    sell_count = 0
    noadd_events = 0
    rankloss_exits = 0

    ledger: list[dict[str, object]] = []
    trades: list[dict[str, object]] = []
    cashflows: list[tuple[date, float]] = []
    benchmark_units = 0.0
    benchmark_cashflows: list[tuple[date, float]] = []

    for week_number, execution_day in enumerate(weekly, start=1):
        snapshot_index = bisect.bisect_left(signal_days, execution_day) - 1
        if snapshot_index < 0:
            continue
        signal_changed = snapshot_index != current_signal_index
        if signal_changed:
            current_signal_index = snapshot_index
            current_snapshot = snapshots[snapshot_index]
        assert current_snapshot is not None

        observation_day = previous_session_day(prices.calendar, execution_day)
        if observation_day is not None:
            prior_nav, _ = base._account_value(
                cash,
                holdings,
                prices,
                observation_day,
                use_open=False,
            )
        else:
            prior_nav = 0.0

        # Causal NO-ADD state is decided before current-session contribution and open.
        if (
            spec.nav_loss_budget is not None
            and not spec.rank_loss_exit
            and observation_day is not None
            and prior_nav > 0
        ):
            for symbol, qty in holdings.items():
                if qty <= 0:
                    continue
                loss_nav = _position_loss_nav(
                    symbol,
                    qty,
                    average_cost.get(symbol, 0.0),
                    prices=prices,
                    observation_day=observation_day,
                    nav=prior_nav,
                )
                if (
                    loss_nav <= -spec.nav_loss_budget
                    and blocked_signal_index.get(symbol) != current_signal_index
                ):
                    blocked_signal_index[symbol] = current_signal_index
                    noadd_events += 1
                    trades.append(
                        {
                            "day": execution_day.isoformat(),
                            "observation_day": observation_day.isoformat(),
                            "side": "NO_ADD_BLOCK",
                            "symbol": symbol,
                            "quantity": 0,
                            "loss_nav": loss_nav,
                            "cash_effect_vnd": 0.0,
                            "reason": "PREVIOUS_SESSION_CLOSE_NAV_LOSS_BUDGET",
                        }
                    )

        value_before, _ = base._account_value(
            cash,
            holdings,
            prices,
            execution_day,
            use_open=True,
        )
        if fund_units > 0:
            unit_price = value_before / fund_units
        fund_units += contribution / max(unit_price, 1e-12)
        cash += contribution
        cashflows.append((execution_day, -float(contribution)))

        index_open = prices.index_open.get(execution_day)
        if index_open and index_open > 0:
            benchmark_units += contribution / float(index_open)
            benchmark_cashflows.append((execution_day, -float(contribution)))

        if signal_changed:
            ranks = {
                symbol: rank
                for rank, symbol in enumerate(current_snapshot.ranking, start=1)
            }
            sell_symbols = base.compute_exit_symbols(
                holdings,
                ranks,
                outside_counts,
                exit_rank=int(policy["exit_rank"]),
                exit_months=int(policy["exit_months"]),
            )

            if (
                spec.rank_loss_exit
                and spec.nav_loss_budget is not None
                and observation_day is not None
                and prior_nav > 0
            ):
                for symbol, qty in holdings.items():
                    if qty <= 0 or ranks.get(symbol, 10**9) <= 10:
                        continue
                    loss_nav = _position_loss_nav(
                        symbol,
                        qty,
                        average_cost.get(symbol, 0.0),
                        prices=prices,
                        observation_day=observation_day,
                        nav=prior_nav,
                    )
                    if loss_nav <= -spec.nav_loss_budget:
                        sell_symbols.append(symbol)
                        rankloss_exits += 1

            for symbol in sorted(set(sell_symbols)):
                qty = holdings.get(symbol, 0)
                raw = prices.opens.get((symbol, execution_day))
                if qty <= 0 or raw is None:
                    continue
                gross = float(raw) * qty
                proceeds = base._sell_proceeds(float(raw), qty, slippage_bps)
                fees_total += gross - proceeds
                cash += proceeds
                holdings[symbol] = 0
                average_cost.pop(symbol, None)
                outside_counts[symbol] = 0
                sell_count += 1
                trades.append(
                    {
                        "day": execution_day.isoformat(),
                        "observation_day": (
                            observation_day.isoformat()
                            if observation_day is not None
                            else None
                        ),
                        "side": "SELL",
                        "symbol": symbol,
                        "quantity": qty,
                        "cash_effect_vnd": proceeds,
                        "reason": "MONTHLY_EXIT_OR_CAUSAL_RANKLOSS",
                    }
                )

        target_count = int(policy["target_count"])
        target_symbols = list(current_snapshot.ranking[:target_count])
        target_weights = base.capped_inverse_vol_weights(
            current_snapshot.ranking,
            current_snapshot.volatility,
            target_count=target_count,
            symbol_cap=float(policy["symbol_cap"]),
        )
        eligible = [
            symbol
            for symbol in target_symbols
            if blocked_signal_index.get(symbol, -10**9) < current_signal_index
        ]

        account_open, _ = base._account_value(
            cash,
            holdings,
            prices,
            execution_day,
            use_open=True,
        )
        deployable = v43_1.deployable_cash(
            policy_id=BASE_POLICY,
            cash=cash,
            contribution=contribution,
            risk_on=current_snapshot.risk_on,
        )
        (
            buy_symbol,
            round_robin_pointer,
            buy_budget,
            _,
            _,
        ) = v43_1._buy_candidates(
            rule=str(policy["buy_rule"]),
            target_symbols=eligible,
            target_weights=target_weights,
            holdings=holdings,
            prices=prices,
            day=execution_day,
            account_value=account_open,
            deployable=deployable,
            contribution=contribution,
            target_count=target_count,
            base_symbol_cap=float(policy["symbol_cap"]),
            slippage_bps=slippage_bps,
            round_robin_pointer=round_robin_pointer,
        )

        if buy_symbol is not None:
            raw = float(prices.opens[(buy_symbol, execution_day)])
            qty = base.affordable_quantity(buy_budget, raw, slippage_bps)
            cost = base._buy_total(raw, qty, slippage_bps)
            while qty > 0 and cost > cash + 1e-8:
                qty -= 1
                cost = base._buy_total(raw, qty, slippage_bps)
            if qty > 0:
                old_qty = holdings.get(buy_symbol, 0)
                old_basis = average_cost.get(buy_symbol, 0.0) * old_qty
                new_qty = old_qty + qty
                average_cost[buy_symbol] = (old_basis + cost) / new_qty
                holdings[buy_symbol] = new_qty
                cash -= cost
                fees_total += cost - raw * qty
                buy_count += 1
                trades.append(
                    {
                        "day": execution_day.isoformat(),
                        "observation_day": (
                            observation_day.isoformat()
                            if observation_day is not None
                            else None
                        ),
                        "side": "BUY",
                        "symbol": buy_symbol,
                        "quantity": qty,
                        "cash_effect_vnd": -cost,
                        "blocked": False,
                    }
                )

        end_value, _ = base._account_value(
            cash,
            holdings,
            prices,
            execution_day,
            use_open=False,
        )
        unit_price = end_value / fund_units if fund_units > 0 else 1.0
        peak = max(peak, unit_price)
        max_drawdown = min(max_drawdown, unit_price / peak - 1.0)

        worst_loss = 0.0
        largest_weight = 0.0
        if end_value > 0:
            for symbol, qty in holdings.items():
                if qty <= 0:
                    continue
                worst_loss = min(
                    worst_loss,
                    _position_loss_nav(
                        symbol,
                        qty,
                        average_cost.get(symbol, 0.0),
                        prices=prices,
                        observation_day=execution_day,
                        nav=end_value,
                    ),
                )
                mark = prices.latest_close(symbol, execution_day)
                if mark is not None:
                    largest_weight = max(
                        largest_weight,
                        qty * float(mark) / end_value,
                    )

        ledger.append(
            {
                "variant": spec.variant_id,
                "contribution": contribution,
                "scenario": scenario,
                "week": week_number,
                "day": execution_day.isoformat(),
                "decision_observation_day": (
                    observation_day.isoformat()
                    if observation_day is not None
                    else None
                ),
                "unit_price": unit_price,
                "portfolio_value_vnd": end_value,
                "cash_vnd": cash,
                "worst_position_loss_nav": worst_loss,
                "largest_symbol_weight": largest_weight,
            }
        )

    if not ledger:
        raise ValueError("V58_NOADD_NO_LEDGER")

    final_day = date.fromisoformat(str(ledger[-1]["day"]))
    final_value = float(ledger[-1]["portfolio_value_vnd"])
    cashflows.append((final_day, final_value))
    index_close = prices.index_close.get(final_day)
    benchmark_final = (
        benchmark_units * float(index_close) if index_close else 0.0
    )
    benchmark_cashflows.append((final_day, benchmark_final))
    xirr = base.xirr(cashflows)
    benchmark_xirr = base.xirr(benchmark_cashflows)

    return (
        {
            "schema_version": SCHEMA_VERSION,
            "variant": spec.variant_id,
            "contribution": contribution,
            "scenario": scenario,
            "final_value_vnd": final_value,
            "xirr": xirr,
            "benchmark_xirr": benchmark_xirr,
            "xirr_excess": (
                xirr - benchmark_xirr
                if xirr is not None and benchmark_xirr is not None
                else None
            ),
            "max_drawdown": max_drawdown,
            "worst_position_loss_nav": min(
                float(row["worst_position_loss_nav"]) for row in ledger
            ),
            "max_largest_symbol_weight": max(
                float(row["largest_symbol_weight"]) for row in ledger
            ),
            "noadd_event_count": noadd_events,
            "rankloss_exit_count": rankloss_exits,
            "buy_order_count": buy_count,
            "sell_order_count": sell_count,
            "estimated_total_cost_vnd": fees_total,
            "loss_decision_timing": LOSS_DECISION_TIMING,
            "lookahead_guard": True,
            "live_model_change_authorized": False,
        },
        ledger,
        trades,
    )


def _segment(
    rows: Sequence[Mapping[str, object]],
    start: date | None,
    end: date,
) -> dict[str, object]:
    selected = [
        row
        for row in rows
        if (
            start is None
            or date.fromisoformat(str(row["day"])) >= start
        )
        and date.fromisoformat(str(row["day"])) <= end
    ]
    if len(selected) < 2:
        return {
            "day_count": len(selected),
            "annualized_return": None,
            "max_drawdown": None,
            "worst_position_loss_nav": None,
            "max_largest_symbol_weight": None,
        }

    first = selected[0]
    last = selected[-1]
    first_day = date.fromisoformat(str(first["day"]))
    last_day = date.fromisoformat(str(last["day"]))
    years = max((last_day - first_day).days / 365.25, 1 / 365.25)
    annualized = (
        float(last["unit_price"]) / float(first["unit_price"])
    ) ** (1 / years) - 1

    peak = float(first["unit_price"])
    drawdown = 0.0
    for row in selected:
        unit = float(row["unit_price"])
        peak = max(peak, unit)
        drawdown = min(drawdown, unit / peak - 1.0)

    return {
        "day_count": len(selected),
        "annualized_return": annualized,
        "max_drawdown": drawdown,
        "worst_position_loss_nav": min(
            float(row["worst_position_loss_nav"]) for row in selected
        ),
        "max_largest_symbol_weight": max(
            float(row["largest_symbol_weight"]) for row in selected
        ),
    }


def run_study(
    *,
    input_zip: Path,
    store_path: Path,
    output_dir: Path,
    output_zip: Path,
    contributions: Sequence[int] = base.CONTRIBUTIONS,
    price_multiplier: float = base.PRICE_MULTIPLIER,
    analysis_end: date = DEFAULT_ANALYSIS_END,
    holdout_start: date = DEFAULT_HOLDOUT_START,
) -> dict[str, object]:
    rows, _ = base._load_research_rows(input_zip)
    snapshots, _, _ = base.build_signal_snapshots(rows)
    prices = base._load_prices(store_path, price_multiplier=price_multiplier)
    effective_end = min(analysis_end, snapshots[-1].day, prices.calendar[-1])
    weekly_days = base._weekly_days(
        prices.calendar,
        start=snapshots[0].day,
        end=effective_end,
    )
    calibration_end = date.fromordinal(holdout_start.toordinal() - 1)

    summaries: list[dict[str, object]] = []
    ledgers: list[dict[str, object]] = []
    trades: list[dict[str, object]] = []

    for contribution in sorted(set(int(value) for value in contributions)):
        for scenario in base.SCENARIOS:
            for spec in VARIANTS:
                summary, ledger, trade_rows = simulate(
                    spec=spec,
                    contribution=contribution,
                    scenario=scenario,
                    snapshots=snapshots,
                    prices=prices,
                    weekly_days=weekly_days,
                    analysis_end=effective_end,
                )
                summary["calibration"] = _segment(
                    ledger,
                    None,
                    calibration_end,
                )
                summary["holdout"] = _segment(
                    ledger,
                    holdout_start,
                    effective_end,
                )
                summaries.append(summary)
                ledgers.extend(ledger)
                trades.extend(
                    {
                        "variant": spec.variant_id,
                        "contribution": contribution,
                        "scenario": scenario,
                        **dict(row),
                    }
                    for row in trade_rows
                )

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "effective_analysis_end": effective_end.isoformat(),
        "holdout_start": holdout_start.isoformat(),
        "variant_count": len(VARIANTS),
        "simulation_count": len(summaries),
        "loss_decision_timing": LOSS_DECISION_TIMING,
        "v57_tail_results_superseded": True,
        "summary_rows": summaries,
        "permissions": {
            "research_only": True,
            "live_model_change_authorized": False,
        },
    }

    flat_rows: list[dict[str, object]] = []
    for row in summaries:
        flat = {
            key: value
            for key, value in row.items()
            if key not in {"calibration", "holdout"}
        }
        flat.update(
            {
                f"calibration_{key}": value
                for key, value in dict(row["calibration"]).items()
            }
        )
        flat.update(
            {
                f"holdout_{key}": value
                for key, value in dict(row["holdout"]).items()
            }
        )
        flat_rows.append(flat)

    files = {
        "tail_noadd_summary_v58.csv": base._csv_bytes(flat_rows),
        "tail_noadd_ledger_v58.csv": base._csv_bytes(ledgers),
        "tail_noadd_trades_v58.csv": base._csv_bytes(trades),
        "tail_noadd_report_v58.json": base._json_bytes(report),
    }
    files["manifest.json"] = base._json_bytes(
        {
            "schema_version": SCHEMA_VERSION,
            "files": {
                name: {
                    "sha256": base._sha(payload),
                    "size_bytes": len(payload),
                }
                for name, payload in files.items()
            },
        }
    )

    output_dir.mkdir(parents=True, exist_ok=False)
    for name, payload in files.items():
        (output_dir / name).write_bytes(payload)
    with ZipFile(output_zip, "w", ZIP_DEFLATED) as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)

    return {
        "status": "SUCCESS",
        "output_zip": str(output_zip.resolve()),
        "output_zip_sha256": sha256(output_zip.read_bytes()).hexdigest(),
        "simulation_count": len(summaries),
        "loss_decision_timing": LOSS_DECISION_TIMING,
        "live_model_change_authorized": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-zip", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output-zip", type=Path, required=True)
    parser.add_argument(
        "--contribution",
        type=int,
        action="append",
        dest="contributions",
    )
    parser.add_argument(
        "--price-multiplier",
        type=float,
        default=base.PRICE_MULTIPLIER,
    )
    parser.add_argument(
        "--analysis-end",
        type=date.fromisoformat,
        default=DEFAULT_ANALYSIS_END,
    )
    parser.add_argument(
        "--holdout-start",
        type=date.fromisoformat,
        default=DEFAULT_HOLDOUT_START,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_study(
            input_zip=args.input_zip,
            store_path=args.store,
            output_dir=args.output_dir,
            output_zip=args.output_zip,
            contributions=args.contributions or base.CONTRIBUTIONS,
            price_multiplier=args.price_multiplier,
            analysis_end=args.analysis_end,
            holdout_start=args.holdout_start,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "error": f"{type(exc).__name__}:{exc}",
                },
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
