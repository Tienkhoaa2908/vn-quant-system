"""V57 research-only loss-aware NO-ADD study for C3/P1.

Unlike V56 hard exits, NO-ADD never sells a losing position. It only prevents
additional purchases in that symbol until the next canonical monthly signal.
The purpose is to reduce single-name tail amplification without crystallising
losses or missing rebounds.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from statistics import median
from typing import Mapping, Sequence
import argparse
import bisect
import json
from hashlib import sha256
from zipfile import ZIP_DEFLATED, ZipFile

from . import weekly_micro_capital_v43 as base
from . import weekly_micro_capital_v43_1 as v43_1

SCHEMA_VERSION = "tail_noadd_v57"
BASE_POLICY = "P1_TOP10_UNDERWEIGHT_BUFFER20"
DEFAULT_ANALYSIS_END = date(2026, 7, 31)
DEFAULT_HOLDOUT_START = date(2022, 1, 1)


@dataclass(frozen=True)
class NoAddSpec:
    variant_id: str
    nav_loss_budget: float | None = None
    symbol_cap: float = 0.15
    rank_loss_exit: bool = False


VARIANTS: tuple[NoAddSpec, ...] = (
    NoAddSpec("BASELINE"),
    NoAddSpec("NOADD_075", nav_loss_budget=0.0075),
    NoAddSpec("NOADD_100", nav_loss_budget=0.0100),
    NoAddSpec("NOADD_125", nav_loss_budget=0.0125),
    NoAddSpec("CAP125", symbol_cap=0.125),
    NoAddSpec("CAP100", symbol_cap=0.10),
    NoAddSpec("NOADD_100_CAP125", nav_loss_budget=0.0100, symbol_cap=0.125),
    NoAddSpec("RANKLOSS_EXIT_100", nav_loss_budget=0.0100, rank_loss_exit=True),
)


def _position_loss_nav(symbol: str, qty: int, avg_cost: float, *, prices: base.PriceStore,
                       day: date, nav: float) -> float:
    mark = prices.latest_close(symbol, day)
    if mark is None or mark <= 0 or qty <= 0 or avg_cost <= 0 or nav <= 0:
        return 0.0
    return (float(mark) - avg_cost) * qty / nav


def simulate(*, spec: NoAddSpec, contribution: int, scenario: str,
             snapshots: Sequence[base.SignalSnapshot], prices: base.PriceStore,
             weekly_days: Sequence[date], analysis_end: date) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    policy = dict(v43_1.POLICIES[BASE_POLICY])
    policy["symbol_cap"] = spec.symbol_cap
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
    unit_price = peak = 1.0
    max_dd = 0.0
    contributions_total = fees_total = 0.0
    buy_count = sell_count = noadd_events = rankloss_exits = 0
    ledger: list[dict[str, object]] = []
    trades: list[dict[str, object]] = []
    cashflows: list[tuple[date, float]] = []
    benchmark_units = 0.0
    benchmark_cashflows: list[tuple[date, float]] = []

    for week_no, day in enumerate(weekly, start=1):
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
            sell_symbols = base.compute_exit_symbols(holdings, ranks, outside_counts,
                                                     exit_rank=int(policy["exit_rank"]),
                                                     exit_months=int(policy["exit_months"]))
            if spec.rank_loss_exit and spec.nav_loss_budget is not None:
                nav_open, _ = base._account_value(cash, holdings, prices, day, use_open=True)
                for symbol, qty in list(holdings.items()):
                    rank = ranks.get(symbol, 10**9)
                    loss_nav = _position_loss_nav(symbol, qty, average_cost.get(symbol, 0.0),
                                                  prices=prices, day=day, nav=nav_open)
                    if qty > 0 and rank > 10 and loss_nav <= -spec.nav_loss_budget:
                        sell_symbols.append(symbol)
                        rankloss_exits += 1
            for symbol in sorted(set(sell_symbols)):
                qty = holdings.get(symbol, 0)
                raw = prices.opens.get((symbol, day))
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
                trades.append({"day":day.isoformat(),"side":"SELL","symbol":symbol,"quantity":qty,
                               "reason":"RANKLOSS_OR_MONTHLY_EXIT","cash_effect_vnd":proceeds})

        # Evaluate NO-ADD using information known by the prior weekly close. Block lasts
        # only within the same canonical signal month and automatically releases when
        # current_signal_index advances.
        nav_mark, _ = base._account_value(cash, holdings, prices, day, use_open=False)
        if spec.nav_loss_budget is not None and not spec.rank_loss_exit:
            for symbol, qty in holdings.items():
                if qty <= 0:
                    continue
                loss_nav = _position_loss_nav(symbol, qty, average_cost.get(symbol, 0.0),
                                              prices=prices, day=day, nav=nav_mark)
                if loss_nav <= -spec.nav_loss_budget and blocked_signal_index.get(symbol) != current_signal_index:
                    blocked_signal_index[symbol] = current_signal_index
                    noadd_events += 1

        target_count = int(policy["target_count"])
        target_symbols = list(current_snapshot.ranking[:target_count])
        target_weights = base.capped_inverse_vol_weights(current_snapshot.ranking, current_snapshot.volatility,
                                                         target_count=target_count, symbol_cap=spec.symbol_cap)
        eligible = [s for s in target_symbols if blocked_signal_index.get(s, -10**9) < current_signal_index]
        account_open, _ = base._account_value(cash, holdings, prices, day, use_open=True)
        deployable = v43_1.deployable_cash(policy_id=BASE_POLICY, cash=cash, contribution=contribution,
                                           risk_on=current_snapshot.risk_on)
        buy_symbol, round_robin_pointer, buy_budget, _, _ = v43_1._buy_candidates(
            rule=str(policy["buy_rule"]), target_symbols=eligible, target_weights=target_weights,
            holdings=holdings, prices=prices, day=day, account_value=account_open,
            deployable=deployable, contribution=contribution, target_count=target_count,
            base_symbol_cap=spec.symbol_cap, slippage_bps=slippage_bps,
            round_robin_pointer=round_robin_pointer,
        )
        if buy_symbol is not None:
            raw = float(prices.opens[(buy_symbol, day)])
            qty = base.affordable_quantity(buy_budget, raw, slippage_bps)
            cost = base._buy_total(raw, qty, slippage_bps)
            while qty > 0 and cost > cash + 1e-8:
                qty -= 1; cost = base._buy_total(raw, qty, slippage_bps)
            if qty > 0:
                old_qty = holdings.get(buy_symbol, 0)
                old_basis = average_cost.get(buy_symbol, 0.0) * old_qty
                new_qty = old_qty + qty
                average_cost[buy_symbol] = (old_basis + cost) / new_qty
                holdings[buy_symbol] = new_qty
                cash -= cost
                fees_total += cost - raw * qty
                buy_count += 1
                trades.append({"day":day.isoformat(),"side":"BUY","symbol":buy_symbol,"quantity":qty,
                               "cash_effect_vnd":-cost,"blocked":False})

        end_value, _ = base._account_value(cash, holdings, prices, day, use_open=False)
        unit_price = end_value / fund_units if fund_units > 0 else 1.0
        peak = max(peak, unit_price); max_dd = min(max_dd, unit_price / peak - 1.0)
        worst_loss = 0.0; largest = 0.0
        if end_value > 0:
            for symbol, qty in holdings.items():
                if qty <= 0: continue
                worst_loss = min(worst_loss, _position_loss_nav(symbol, qty, average_cost.get(symbol,0.0),
                                                                 prices=prices, day=day, nav=end_value))
                mark = prices.latest_close(symbol, day)
                if mark is not None: largest=max(largest, qty*float(mark)/end_value)
        ledger.append({"variant":spec.variant_id,"contribution":contribution,"scenario":scenario,
                       "week":week_no,"day":day.isoformat(),"unit_price":unit_price,
                       "portfolio_value_vnd":end_value,"cash_vnd":cash,"worst_position_loss_nav":worst_loss,
                       "largest_symbol_weight":largest})

    if not ledger: raise ValueError("V57_NOADD_NO_LEDGER")
    final_day=date.fromisoformat(str(ledger[-1]["day"])); final_value=float(ledger[-1]["portfolio_value_vnd"])
    cashflows.append((final_day,final_value)); idx_close=prices.index_close.get(final_day)
    benchmark_final=benchmark_units*float(idx_close) if idx_close else 0.0; benchmark_cashflows.append((final_day,benchmark_final))
    xirr=base.xirr(cashflows); bench=base.xirr(benchmark_cashflows)
    return {"schema_version":SCHEMA_VERSION,"variant":spec.variant_id,"contribution":contribution,"scenario":scenario,
            "final_value_vnd":final_value,"xirr":xirr,"benchmark_xirr":bench,
            "xirr_excess":xirr-bench if xirr is not None and bench is not None else None,
            "max_drawdown":max_dd,"worst_position_loss_nav":min(float(r["worst_position_loss_nav"]) for r in ledger),
            "max_largest_symbol_weight":max(float(r["largest_symbol_weight"]) for r in ledger),
            "noadd_event_count":noadd_events,"rankloss_exit_count":rankloss_exits,
            "buy_order_count":buy_count,"sell_order_count":sell_count,"estimated_total_cost_vnd":fees_total,
            "live_model_change_authorized":False}, ledger, trades


def _segment(rows: Sequence[Mapping[str, object]], start: date | None, end: date) -> dict[str, object]:
    sel=[r for r in rows if (start is None or date.fromisoformat(str(r["day"]))>=start) and date.fromisoformat(str(r["day"]))<=end]
    if len(sel)<2: return {"day_count":len(sel),"annualized_return":None,"max_drawdown":None,"worst_position_loss_nav":None}
    first,last=sel[0],sel[-1]; d0=date.fromisoformat(str(first["day"])); d1=date.fromisoformat(str(last["day"])); years=max((d1-d0).days/365.25,1/365.25)
    ann=(float(last["unit_price"])/float(first["unit_price"]))**(1/years)-1; peak=float(first["unit_price"]); dd=0.0
    for r in sel:
        u=float(r["unit_price"]); peak=max(peak,u); dd=min(dd,u/peak-1.0)
    return {"day_count":len(sel),"annualized_return":ann,"max_drawdown":dd,
            "worst_position_loss_nav":min(float(r["worst_position_loss_nav"]) for r in sel),
            "max_largest_symbol_weight":max(float(r["largest_symbol_weight"]) for r in sel)}


def run_study(*, input_zip: Path, store_path: Path, output_dir: Path, output_zip: Path,
              contributions: Sequence[int]=base.CONTRIBUTIONS, price_multiplier: float=base.PRICE_MULTIPLIER,
              analysis_end: date=DEFAULT_ANALYSIS_END, holdout_start: date=DEFAULT_HOLDOUT_START) -> dict[str, object]:
    rows,_=base._load_research_rows(input_zip); snapshots,_,_=base.build_signal_snapshots(rows); prices=base._load_prices(store_path,price_multiplier=price_multiplier)
    effective_end=min(analysis_end,snapshots[-1].day,prices.calendar[-1]); weekly_days=base._weekly_days(prices.calendar,start=snapshots[0].day,end=effective_end)
    calibration_end=date.fromordinal(holdout_start.toordinal()-1); summaries=[]; ledgers=[]; trades=[]
    for contribution in sorted(set(int(x) for x in contributions)):
        for scenario in base.SCENARIOS:
            for spec in VARIANTS:
                summary,ledger,tr=simulate(spec=spec,contribution=contribution,scenario=scenario,snapshots=snapshots,prices=prices,weekly_days=weekly_days,analysis_end=effective_end)
                summary["calibration"]=_segment(ledger,None,calibration_end); summary["holdout"]=_segment(ledger,holdout_start,effective_end)
                summaries.append(summary); ledgers.extend(ledger); trades.extend({"variant":spec.variant_id,"contribution":contribution,"scenario":scenario,**r} for r in tr)
    report={"schema_version":SCHEMA_VERSION,"status":"SUCCESS","effective_analysis_end":effective_end.isoformat(),"holdout_start":holdout_start.isoformat(),
            "variant_count":len(VARIANTS),"simulation_count":len(summaries),"summary_rows":summaries,
            "permissions":{"research_only":True,"live_model_change_authorized":False}}
    flat=[]
    for r in summaries:
        row={k:v for k,v in r.items() if k not in {"calibration","holdout"}}
        row.update({f"calibration_{k}":v for k,v in r["calibration"].items()}); row.update({f"holdout_{k}":v for k,v in r["holdout"].items()}); flat.append(row)
    files={"tail_noadd_summary_v57.csv":base._csv_bytes(flat),"tail_noadd_ledger_v57.csv":base._csv_bytes(ledgers),
           "tail_noadd_trades_v57.csv":base._csv_bytes(trades),"tail_noadd_report_v57.json":base._json_bytes(report)}
    files["manifest.json"]=base._json_bytes({"schema_version":SCHEMA_VERSION,"files":{n:{"sha256":base._sha(p),"size_bytes":len(p)} for n,p in files.items()}})
    output_dir.mkdir(parents=True,exist_ok=False)
    for n,p in files.items():(output_dir/n).write_bytes(p)
    with ZipFile(output_zip,"w",ZIP_DEFLATED) as z:
        for n,p in files.items():z.writestr(n,p)
    return {"status":"SUCCESS","output_zip":str(output_zip.resolve()),"output_zip_sha256":sha256(output_zip.read_bytes()).hexdigest(),
            "simulation_count":len(summaries),"live_model_change_authorized":False}


def _parser():
    p=argparse.ArgumentParser(); p.add_argument("--input-zip",type=Path,required=True); p.add_argument("--store",type=Path,required=True); p.add_argument("--output-dir",type=Path,required=True); p.add_argument("--output-zip",type=Path,required=True)
    p.add_argument("--contribution",type=int,action="append",dest="contributions"); p.add_argument("--price-multiplier",type=float,default=base.PRICE_MULTIPLIER); p.add_argument("--analysis-end",type=date.fromisoformat,default=DEFAULT_ANALYSIS_END); p.add_argument("--holdout-start",type=date.fromisoformat,default=DEFAULT_HOLDOUT_START); return p


def main(argv=None):
    a=_parser().parse_args(argv)
    try: result=run_study(input_zip=a.input_zip,store_path=a.store,output_dir=a.output_dir,output_zip=a.output_zip,contributions=a.contributions or base.CONTRIBUTIONS,price_multiplier=a.price_multiplier,analysis_end=a.analysis_end,holdout_start=a.holdout_start)
    except Exception as exc: print(json.dumps({"status":"FAILED","error":f"{type(exc).__name__}:{exc}"},sort_keys=True)); return 2
    print(json.dumps(result,indent=2,sort_keys=True)); return 0

if __name__=="__main__": raise SystemExit(main())
