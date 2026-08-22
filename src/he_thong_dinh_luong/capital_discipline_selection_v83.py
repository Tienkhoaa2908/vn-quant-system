"""Pre-2026-only selection view for V83 capital discipline.

V83 was conceived after observing 2026 forward behavior, so 2026 must not be
used to select a capital-discipline rule. This module reuses the fixed V83 rules
but truncates the market calendar and causal signal inputs at 2025-12-31.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from . import capital_discipline_audit_v83 as v83
from . import deep_portfolio_backtest_v70 as v70
from . import weekly_overlay_backtest_v72 as v72


def _truncate_market(market: v70.Market) -> v70.Market:
    cal=[d for d in market.cal if d<=v83.PRIMARY_SELECTION_END]
    return v70.Market(cal,market.io,market.ic,market.so,market.sc,market.vol)


def analyze(*,v68_output:Path,v70_output:Path,store:Path,output_dir:Path,initial_capital:float=v83.INITIAL_CAPITAL_VND)->dict[str,object]:
    report70=json.loads((Path(v70_output)/"v70_report.json").read_text(encoding="utf-8-sig"))
    if report70.get("status")!="SUCCESS" or report70.get("champion_model")!=v83.CHAMPION_MODEL:
        raise ValueError("V83_SELECTION_V70_CONTRACT_INVALID")
    variants_root=Path(v68_output)/"variants"
    inputs={};symbols=set()
    for variant_dir in sorted(p for p in variants_root.iterdir() if p.is_dir()):
        monthly=variant_dir/"v67_c3_monthly_rankings.csv.gz";weekly_path=variant_dir/"v67_weekly_signal_states.csv.gz"
        if not monthly.is_file() or not weekly_path.is_file():continue
        snaps=v70.load_snaps(monthly);weekly,weekly_symbols=v72.load_weekly_signals(weekly_path)
        snaps=[s for s in snaps if s.day<=v83.PRIMARY_SELECTION_END]
        weekly=[s for s in weekly if s.evaluation_day<=v83.PRIMARY_SELECTION_END and s.canonical_day<=v83.PRIMARY_SELECTION_END]
        if len(snaps)<3:continue
        inputs[variant_dir.name]=(snaps,weekly);symbols.update(weekly_symbols)
        for snap in snaps:symbols.update(snap.symbols)
    if not inputs:raise ValueError("V83_SELECTION_NO_VARIANTS")
    market=_truncate_market(v70.load_market(Path(store),symbols))
    primary="GAP18_CLEAN" if "GAP18_CLEAN" in inputs else sorted(inputs)[0]
    snaps,weekly=inputs[primary]
    rows=[]
    base=None
    for policy in v83.POLICIES:
        result=v83._simulate(market,snaps,weekly,policy,v70.COSTS[1],initial_capital)
        row={k:v for k,v in result.items() if k not in {"events","ledger","missing"}}
        if policy.policy_id=="C3_BASE":base=row
        if base is not None:
            row["incremental_nav_vs_c3_vnd"]=v83._f(row["ending_nav_vnd"])-v83._f(base["ending_nav_vnd"])
            row["total_return_uplift_vs_c3"]=v83._f(row["total_return"])-v83._f(base["total_return"])
            row["cagr_uplift_vs_c3"]=v83._f(row.get("cagr"))-v83._f(base.get("cagr"))
            row["mdd_improvement_vs_c3"]=v83._f(row.get("max_drawdown"))-v83._f(base.get("max_drawdown"))
        row["sample_scope"]="PRE2026_SELECTION"
        rows.append(row)
    entry_rows=v83._entry_timing_rows(market,snaps,primary)
    entry=v83._entry_summary(entry_rows,primary,"ALL")
    report={
        "schema_version":"capital_discipline_selection_v83",
        "status":"SUCCESS",
        "primary_variant":primary,
        "selection_end":v83.PRIMARY_SELECTION_END.isoformat(),
        "primary_base_dnse_pre2026":rows,
        "entry_timing_pre2026":entry,
        "year_2026_used_to_select":False,
        "historical_threshold_search_reopened":False,
        "new_leader_research_reopened":False,
        "promotion_authorized":False,
        "live_orders_allowed":False,
    }
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    (out/"v83_selection_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return report


def main(argv:Sequence[str]|None=None)->int:
    p=argparse.ArgumentParser();p.add_argument("--v68-output",type=Path,required=True);p.add_argument("--v70-output",type=Path,required=True);p.add_argument("--store",type=Path,required=True);p.add_argument("--output-dir",type=Path,required=True);p.add_argument("--initial-capital",type=float,default=v83.INITIAL_CAPITAL_VND)
    a=p.parse_args(argv)
    try:r=analyze(v68_output=a.v68_output,v70_output=a.v70_output,store=a.store,output_dir=a.output_dir,initial_capital=a.initial_capital)
    except Exception as exc:
        print(json.dumps({"status":"FAILED","error":f"{type(exc).__name__}:{exc}"},ensure_ascii=False));return 2
    print(json.dumps(r,ensure_ascii=False,sort_keys=True));return 0


if __name__=="__main__":raise SystemExit(main())
