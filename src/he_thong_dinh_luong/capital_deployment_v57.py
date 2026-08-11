"""V57 research-only staged capital deployment study for C3/P1.

This module compares the frozen V43.1 one-order P1 baseline with multi-order
capital deployment variants. It does not change workstation/live behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from statistics import fmean, median
from typing import Mapping, Sequence
import argparse
import bisect
import json
from hashlib import sha256
from zipfile import ZIP_DEFLATED, ZipFile

from . import weekly_micro_capital_v43 as base
from . import weekly_micro_capital_v43_1 as v43_1

SCHEMA_VERSION = "capital_deployment_v57"
BASE_POLICY = "P1_TOP10_UNDERWEIGHT_BUFFER20"
DEFAULT_ANALYSIS_END = date(2026, 7, 31)
DEFAULT_HOLDOUT_START = date(2022, 1, 1)


@dataclass(frozen=True)
class DeploymentSpec:
    variant_id: str
    max_orders: int
    staged_full_deployment: bool
    symbol_cap: float = 0.15


VARIANTS: tuple[DeploymentSpec, ...] = (
    DeploymentSpec("BASELINE_ONE_ORDER", 1, False, 0.15),
    DeploymentSpec("TARGET_GAP_3", 3, False, 0.15),
    DeploymentSpec("STAGED_FULL_3", 3, True, 0.15),
    DeploymentSpec("STAGED_FULL_5", 5, True, 0.15),
    DeploymentSpec("STAGED_FULL_5_CAP125", 5, True, 0.125),
    DeploymentSpec("STAGED_FULL_5_CAP100", 5, True, 0.10),
)


def _effective_cap(base_cap: float, target_count: int, established: int, held: bool) -> float:
    resulting = max(established + (0 if held else 1), 1)
    ramp = 1.0 / min(resulting, max(target_count, 1))
    return min(1.0, max(float(base_cap), ramp))


def _candidate_rows(*, snapshot: base.SignalSnapshot, holdings: Mapping[str, int], prices: base.PriceStore,
                    day: date, account_value: float, contribution: int, cash: float,
                    symbol_cap: float, slippage_bps: float) -> list[dict[str, object]]:
    target_count = 10
    target_symbols = list(snapshot.ranking[:target_count])
    weights = base.capped_inverse_vol_weights(
        snapshot.ranking, snapshot.volatility, target_count=target_count, symbol_cap=symbol_cap
    )
    established = sum(1 for symbol in target_symbols if holdings.get(symbol, 0) > 0)
    rows: list[dict[str, object]] = []
    for rank, symbol in enumerate(target_symbols, start=1):
        raw_price = prices.opens.get((symbol, day))
        if raw_price is None or raw_price <= 0:
            continue
        price = float(raw_price)
        actual_value = holdings.get(symbol, 0) * price
        target_weight = float(weights.get(symbol, 0.0))
        target_gap = max(target_weight * account_value - actual_value, 0.0)
        cap = _effective_cap(symbol_cap, target_count, established, holdings.get(symbol, 0) > 0)
        cap_gap = max(cap * account_value - actual_value, 0.0)
        one_share = base._buy_total(price, 1, slippage_bps)
        if cap_gap + 1e-9 < one_share or cash + 1e-9 < one_share:
            continue
        rows.append({
            "symbol": symbol,
            "rank": rank,
            "price": price,
            "one_share": one_share,
            "target_weight": target_weight,
            "actual_weight": actual_value / account_value if account_value > 0 else 0.0,
            "target_gap": target_gap,
            "cap_gap": cap_gap,
        })
    rows.sort(key=lambda r: (-float(r["target_gap"]), int(r["rank"])))
    return rows


def _allocate(*, rows: Sequence[Mapping[str, object]], budget: float, max_orders: int,
              staged: bool) -> tuple[list[dict[str, object]], float]:
    remaining = float(budget)
    selected: list[dict[str, object]] = []
    # First pass: buy one share of the most underweight names, up to max_orders.
    for raw in rows:
        if len(selected) >= max_orders:
            break
        one = float(raw["one_share"])
        target_ceiling = max(float(raw["target_gap"]), one)
        ceiling = float(raw["cap_gap"]) if staged else min(float(raw["cap_gap"]), target_ceiling)
        if one <= remaining + 1e-9 and one <= ceiling + 1e-9:
            selected.append({**dict(raw), "quantity": 1, "cost": one, "ceiling": ceiling})
            remaining -= one

    # Fill target gaps first.
    while True:
        best = None
        best_key = None
        for row in selected:
            one = float(row["one_share"])
            target_remaining = max(float(row["target_gap"]) - float(row["cost"]), 0.0)
            allowed_remaining = min(target_remaining, float(row["ceiling"]) - float(row["cost"]))
            if one <= remaining + 1e-9 and one <= allowed_remaining + 1e-9:
                key = (target_remaining, -int(row["rank"]))
                if best_key is None or key > best_key:
                    best, best_key = row, key
        if best is None:
            break
        one = float(best["one_share"])
        max_extra = int(min(remaining, float(best["target_gap"]) - float(best["cost"]), float(best["ceiling"]) - float(best["cost"])) // one)
        if max_extra <= 0:
            break
        best["quantity"] = int(best["quantity"]) + max_extra
        add = max_extra * one
        best["cost"] = float(best["cost"]) + add
        remaining -= add

    # Second pass: staged redeployment. Once target gaps are filled, direct residual
    # to the strongest selected C3 names while staying under their effective cap.
    if staged:
        while True:
            candidates = [
                row for row in selected
                if float(row["one_share"]) <= remaining + 1e-9
                and float(row["one_share"]) <= float(row["ceiling"]) - float(row["cost"]) + 1e-9
            ]
            if not candidates:
                break
            candidates.sort(key=lambda r: (int(r["rank"]), -float(r["target_gap"])))
            best = candidates[0]
            one = float(best["one_share"])
            max_extra = int(min(remaining, float(best["ceiling"]) - float(best["cost"])) // one)
            if max_extra <= 0:
                break
            best["quantity"] = int(best["quantity"]) + max_extra
            add = max_extra * one
            best["cost"] = float(best["cost"]) + add
            remaining -= add

    orders = [
        {"symbol": str(row["symbol"]), "rank": int(row["rank"]), "quantity": int(row["quantity"]),
         "estimated_cost_vnd": float(row["cost"]), "target_gap_vnd": float(row["target_gap"]),
         "cap_gap_vnd": float(row["cap_gap"])}
        for row in selected
    ]
    return orders, remaining


def simulate(*, spec: DeploymentSpec, contribution: int, scenario: str,
             snapshots: Sequence[base.SignalSnapshot], prices: base.PriceStore,
             weekly_days: Sequence[date], analysis_end: date) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    policy = v43_1.POLICIES[BASE_POLICY]
    slippage_bps = float(base.SCENARIOS[scenario]["slippage_bps"])
    signal_days = [snapshot.day for snapshot in snapshots]
    cash = 0.0
    holdings: dict[str, int] = {}
    outside_counts: dict[str, int] = {}
    current_signal_index = -1
    current_snapshot: base.SignalSnapshot | None = None
    fund_units = 0.0
    unit_price = peak_unit = 1.0
    max_drawdown = 0.0
    contributions_total = fees_total = 0.0
    buy_count = sell_count = 0
    ledger: list[dict[str, object]] = []
    trades: list[dict[str, object]] = []
    cashflows: list[tuple[date, float]] = []
    benchmark_units = 0.0
    benchmark_cashflows: list[tuple[date, float]] = []
    deployment_ratios: list[float] = []
    idle_despite_affordable = 0

    for week_number, day in enumerate([d for d in weekly_days if d <= analysis_end], start=1):
        snapshot_index = bisect.bisect_left(signal_days, day) - 1
        if snapshot_index < 0:
            continue
        signal_changed = snapshot_index != current_signal_index
        if signal_changed:
            current_signal_index = snapshot_index
            current_snapshot = snapshots[snapshot_index]
        assert current_snapshot is not None

        value_before, _ = base._account_value(cash, holdings, prices, day, use_open=True)
        if fund_units > 0:
            unit_price = value_before / fund_units
        fund_units += contribution / max(unit_price, 1e-12)
        cash += contribution
        contributions_total += contribution
        cashflows.append((day, -float(contribution)))
        idx_open = prices.index_open.get(day)
        if idx_open and idx_open > 0:
            benchmark_units += contribution / float(idx_open)
            benchmark_cashflows.append((day, -float(contribution)))

        if signal_changed:
            ranks = {symbol: rank for rank, symbol in enumerate(current_snapshot.ranking, start=1)}
            for symbol in base.compute_exit_symbols(holdings, ranks, outside_counts,
                                                   exit_rank=int(policy["exit_rank"]),
                                                   exit_months=int(policy["exit_months"])):
                qty = holdings.get(symbol, 0)
                raw = prices.opens.get((symbol, day))
                if qty <= 0 or raw is None:
                    continue
                gross = float(raw) * qty
                proceeds = base._sell_proceeds(float(raw), qty, slippage_bps)
                fees_total += gross - proceeds
                cash += proceeds
                holdings[symbol] = 0
                outside_counts[symbol] = 0
                sell_count += 1
                trades.append({"day": day.isoformat(), "side": "SELL", "symbol": symbol, "quantity": qty, "cash_effect_vnd": proceeds})

        account_open, _ = base._account_value(cash, holdings, prices, day, use_open=True)
        deployable = v43_1.deployable_cash(policy_id=BASE_POLICY, cash=cash,
                                           contribution=contribution, risk_on=current_snapshot.risk_on)
        rows = _candidate_rows(snapshot=current_snapshot, holdings=holdings, prices=prices, day=day,
                               account_value=account_open, contribution=contribution, cash=deployable,
                               symbol_cap=spec.symbol_cap, slippage_bps=slippage_bps)
        before = cash
        orders, residual = _allocate(rows=rows, budget=deployable, max_orders=spec.max_orders,
                                     staged=spec.staged_full_deployment)
        for order in orders:
            symbol = str(order["symbol"])
            qty = int(order["quantity"])
            raw = float(prices.opens[(symbol, day)])
            cost = base._buy_total(raw, qty, slippage_bps)
            while qty > 0 and cost > cash + 1e-8:
                qty -= 1
                cost = base._buy_total(raw, qty, slippage_bps)
            if qty <= 0:
                continue
            gross = raw * qty
            fees_total += cost - gross
            cash -= cost
            holdings[symbol] = holdings.get(symbol, 0) + qty
            buy_count += 1
            trades.append({"day": day.isoformat(), "side": "BUY", "symbol": symbol, "quantity": qty, "cash_effect_vnd": -cost})

        deployed = max(before - cash, 0.0)
        ratio = deployed / deployable if deployable > 0 else 1.0
        deployment_ratios.append(ratio)
        # Diagnose avoidable idle cash after all planned orders.
        cheapest = min((float(r["one_share"]) for r in rows), default=float("inf"))
        if residual > 0.20 * max(deployable, 1.0) and residual + 1e-9 >= cheapest:
            idle_despite_affordable += 1

        end_value, _ = base._account_value(cash, holdings, prices, day, use_open=False)
        unit_price = end_value / fund_units if fund_units > 0 else 1.0
        peak_unit = max(peak_unit, unit_price)
        max_drawdown = min(max_drawdown, unit_price / peak_unit - 1.0)
        largest = 0.0
        if end_value > 0:
            for symbol, qty in holdings.items():
                if qty <= 0:
                    continue
                mark = prices.latest_close(symbol, day)
                if mark is not None:
                    largest = max(largest, qty * float(mark) / end_value)
        ledger.append({"variant": spec.variant_id, "contribution": contribution, "scenario": scenario,
                       "week": week_number, "day": day.isoformat(), "unit_price": unit_price,
                       "portfolio_value_vnd": end_value, "cash_vnd": cash,
                       "deployment_ratio": ratio, "largest_symbol_weight": largest})

    if not ledger:
        raise ValueError("V57_NO_LEDGER")
    final_day = date.fromisoformat(str(ledger[-1]["day"]))
    final_value = float(ledger[-1]["portfolio_value_vnd"])
    cashflows.append((final_day, final_value))
    idx_close = prices.index_close.get(final_day)
    benchmark_final = benchmark_units * float(idx_close) if idx_close else 0.0
    benchmark_cashflows.append((final_day, benchmark_final))
    xirr = base.xirr(cashflows)
    benchmark_xirr = base.xirr(benchmark_cashflows)
    sorted_ratios = sorted(deployment_ratios)
    p10 = sorted_ratios[max(int(len(sorted_ratios) * 0.10) - 1, 0)] if sorted_ratios else None
    return {
        "schema_version": SCHEMA_VERSION, "variant": spec.variant_id,
        "contribution": contribution, "scenario": scenario,
        "final_value_vnd": final_value, "xirr": xirr, "benchmark_xirr": benchmark_xirr,
        "xirr_excess": xirr - benchmark_xirr if xirr is not None and benchmark_xirr is not None else None,
        "max_drawdown": max_drawdown, "median_deployment_ratio": median(deployment_ratios),
        "p10_deployment_ratio": p10, "mean_deployment_ratio": fmean(deployment_ratios),
        "idle_affordable_week_count": idle_despite_affordable,
        "buy_order_count": buy_count, "sell_order_count": sell_count,
        "estimated_total_cost_vnd": fees_total,
        "ending_cash_vnd": cash, "ending_cash_ratio": cash / final_value if final_value > 0 else 0.0,
        "live_model_change_authorized": False,
    }, ledger, trades


def _segment(rows: Sequence[Mapping[str, object]], start: date | None, end: date) -> dict[str, object]:
    sel = [r for r in rows if (start is None or date.fromisoformat(str(r["day"])) >= start)
           and date.fromisoformat(str(r["day"])) <= end]
    if len(sel) < 2:
        return {"day_count": len(sel), "annualized_return": None, "max_drawdown": None,
                "median_deployment_ratio": None, "p10_deployment_ratio": None,
                "max_largest_symbol_weight": None}
    first, last = sel[0], sel[-1]
    first_day, last_day = date.fromisoformat(str(first["day"])), date.fromisoformat(str(last["day"]))
    years = max((last_day - first_day).days / 365.25, 1/365.25)
    annualized = (float(last["unit_price"]) / float(first["unit_price"])) ** (1 / years) - 1
    peak = float(first["unit_price"]); dd = 0.0
    for row in sel:
        u = float(row["unit_price"]); peak = max(peak, u); dd = min(dd, u / peak - 1.0)
    ratios = [float(r["deployment_ratio"]) for r in sel]
    sr = sorted(ratios); p10 = sr[max(int(len(sr)*0.10)-1,0)]
    return {"day_count": len(sel), "annualized_return": annualized, "max_drawdown": dd,
            "median_deployment_ratio": median(ratios), "p10_deployment_ratio": p10,
            "max_largest_symbol_weight": max(float(r["largest_symbol_weight"]) for r in sel)}


def run_study(*, input_zip: Path, store_path: Path, output_dir: Path, output_zip: Path,
              contributions: Sequence[int] = base.CONTRIBUTIONS,
              price_multiplier: float = base.PRICE_MULTIPLIER,
              analysis_end: date = DEFAULT_ANALYSIS_END,
              holdout_start: date = DEFAULT_HOLDOUT_START) -> dict[str, object]:
    rows, _ = base._load_research_rows(input_zip)
    snapshots, _, _ = base.build_signal_snapshots(rows)
    prices = base._load_prices(store_path, price_multiplier=price_multiplier)
    effective_end = min(analysis_end, snapshots[-1].day, prices.calendar[-1])
    weekly_days = base._weekly_days(prices.calendar, start=snapshots[0].day, end=effective_end)
    calibration_end = date.fromordinal(holdout_start.toordinal()-1)
    summaries=[]; ledgers=[]; trades=[]
    for contribution in sorted(set(int(x) for x in contributions)):
        for scenario in base.SCENARIOS:
            for spec in VARIANTS:
                summary, ledger, tr = simulate(spec=spec, contribution=contribution, scenario=scenario,
                                               snapshots=snapshots, prices=prices, weekly_days=weekly_days,
                                               analysis_end=effective_end)
                summary["calibration"] = _segment(ledger, None, calibration_end)
                summary["holdout"] = _segment(ledger, holdout_start, effective_end)
                summaries.append(summary); ledgers.extend(ledger)
                trades.extend({"variant":spec.variant_id,"contribution":contribution,"scenario":scenario,**row} for row in tr)
    report={"schema_version":SCHEMA_VERSION,"status":"SUCCESS","effective_analysis_end":effective_end.isoformat(),
            "holdout_start":holdout_start.isoformat(),"variant_count":len(VARIANTS),"simulation_count":len(summaries),
            "summary_rows":summaries,"permissions":{"research_only":True,"live_model_change_authorized":False}}
    files={
        "capital_deployment_summary_v57.csv": base._csv_bytes([{**{k:v for k,v in r.items() if k not in {"calibration","holdout"}},
            **{f"calibration_{k}":v for k,v in r["calibration"].items()}, **{f"holdout_{k}":v for k,v in r["holdout"].items()}} for r in summaries]),
        "capital_deployment_ledger_v57.csv": base._csv_bytes(ledgers),
        "capital_deployment_trades_v57.csv": base._csv_bytes(trades),
        "capital_deployment_report_v57.json": base._json_bytes(report),
    }
    files["manifest.json"] = base._json_bytes({"schema_version":SCHEMA_VERSION,"files":{n:{"sha256":base._sha(p),"size_bytes":len(p)} for n,p in files.items()}})
    output_dir.mkdir(parents=True, exist_ok=False)
    for n,payload in files.items(): (output_dir/n).write_bytes(payload)
    with ZipFile(output_zip,"w",ZIP_DEFLATED) as z:
        for n,payload in files.items(): z.writestr(n,payload)
    return {"status":"SUCCESS","output_zip":str(output_zip.resolve()),"output_zip_sha256":sha256(output_zip.read_bytes()).hexdigest(),
            "simulation_count":len(summaries),"live_model_change_authorized":False}


def _parser():
    p=argparse.ArgumentParser(); p.add_argument("--input-zip",type=Path,required=True); p.add_argument("--store",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True); p.add_argument("--output-zip",type=Path,required=True)
    p.add_argument("--contribution",type=int,action="append",dest="contributions"); p.add_argument("--price-multiplier",type=float,default=base.PRICE_MULTIPLIER)
    p.add_argument("--analysis-end",type=date.fromisoformat,default=DEFAULT_ANALYSIS_END); p.add_argument("--holdout-start",type=date.fromisoformat,default=DEFAULT_HOLDOUT_START)
    return p


def main(argv=None):
    a=_parser().parse_args(argv)
    try:
        result=run_study(input_zip=a.input_zip,store_path=a.store,output_dir=a.output_dir,output_zip=a.output_zip,
                         contributions=a.contributions or base.CONTRIBUTIONS,price_multiplier=a.price_multiplier,
                         analysis_end=a.analysis_end,holdout_start=a.holdout_start)
    except Exception as exc:
        print(json.dumps({"status":"FAILED","error":f"{type(exc).__name__}:{exc}"},sort_keys=True)); return 2
    print(json.dumps(result,indent=2,sort_keys=True)); return 0

if __name__ == "__main__": raise SystemExit(main())
