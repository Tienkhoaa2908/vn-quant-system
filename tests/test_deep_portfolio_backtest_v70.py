from __future__ import annotations

from datetime import date, timedelta
import csv
import gzip
import math
from pathlib import Path
import sqlite3
import tempfile
import unittest

from he_thong_dinh_luong import deep_portfolio_backtest_v70 as v70


def weekdays(start: date, count: int) -> list[date]:
    result=[]; current=start
    while len(result)<count:
        if current.weekday()<5: result.append(current)
        current+=timedelta(days=1)
    return result


def month_ends(days):
    by={}
    for day in days: by[(day.year,day.month)]=day
    return [by[k] for k in sorted(by)]


def build_fixture(root: Path):
    days=weekdays(date(2021,1,4),1450); symbols=[f"S{i:02d}" for i in range(12)]
    store=root/"market.sqlite3"; db=sqlite3.connect(store)
    try:
        db.execute("CREATE TABLE bars(asset_type TEXT,symbol TEXT,day TEXT,open REAL,close REAL,volume INTEGER)")
        for i,day in enumerate(days):
            shock=-60.0 if day.year==2026 and day.month in {3,4} else 0.0
            idx=1000.0+0.12*i+5.0*math.sin(i/35.0)+shock
            db.execute("INSERT INTO bars VALUES(?,?,?,?,?,?)",("INDEX","VNINDEX",day.isoformat(),idx*.999,idx,0))
            for j,symbol in enumerate(symbols):
                base=24.0+j*2.0+(0.012+j*0.0018)*i+0.8*math.sin(i/(13.0+j))
                db.execute("INSERT INTO bars VALUES(?,?,?,?,?,?)",("STOCK",symbol,day.isoformat(),base*.998,base,500_000+j*25_000))
        db.commit()
    finally: db.close()
    v68=root/"v68"; signals=[d for d in month_ends(days) if d>=date(2022,6,1)]
    for variant in ("BROAD_PROVISIONAL","SEAM_CLEAN","GAP18_CLEAN"):
        target=v68/"variants"/variant; target.mkdir(parents=True)
        with gzip.open(target/"v67_c3_monthly_rankings.csv.gz","wt",encoding="utf-8-sig",newline="") as f:
            w=csv.DictWriter(f,fieldnames=["signal_day","symbol","rank","score","risk_on","eligible_count"]);w.writeheader()
            for day in signals:
                shift=(day.year+day.month)%len(symbols); ordered=symbols[shift:]+symbols[:shift]
                for rank,symbol in enumerate(ordered[:10],1):
                    w.writerow({"signal_day":day.isoformat(),"symbol":symbol,"rank":rank,"score":1-rank/20,"risk_on":"false" if day.year==2022 else "true","eligible_count":len(symbols)})
    return store,v68,symbols


class TestDeepPortfolioBacktestV70(unittest.TestCase):
    def test_cap_never_exceeds_15_percent(self):
        w=v70._cap_weights({"A":20,"B":1,"C":1,"D":1,"E":1,"F":1,"G":1},1.0)
        self.assertLessEqual(max(w.values()),.15+1e-12);self.assertAlmostEqual(sum(w.values()),1.0,places=12)

    def test_inverse_vol_uses_no_future_price(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);store,v68,symbols=build_fixture(root)
            snaps=v70.load_snapshots(v68/"variants"/"BROAD_PROVISIONAL"/"v67_c3_monthly_rankings.csv.gz");market=v70.load_market(store,set(symbols));snap=snaps[8]
            before=v70.target_weights(market,snap,v70.STRATEGIES[1]);future=next(d for d in market.cal if d>snap.day);key=(snap.symbols[0],future);market.sc[key]*=100
            self.assertEqual(before,v70.target_weights(market,snap,v70.STRATEGIES[1]))

    def test_base_cost_below_gross_and_lots_are_100(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);store,v68,symbols=build_fixture(root);snaps=v70.load_snapshots(v68/"variants"/"BROAD_PROVISIONAL"/"v67_c3_monthly_rankings.csv.gz");market=v70.load_market(store,set(symbols))
            gross=v70.simulate(market,snaps,v70.STRATEGIES[0],v70.COST_SCENARIOS[0],1e9,"TEST");base=v70.simulate(market,snaps,v70.STRATEGIES[0],v70.COST_SCENARIOS[1],1e9,"TEST")
            self.assertLess(base["summary"]["total_return"],gross["summary"]["total_return"]);self.assertTrue(base["ledger"]);self.assertTrue(all(int(r["shares"])%100==0 for r in base["ledger"]))

    def test_t2_no_negative_cash_and_catchup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);store,v68,symbols=build_fixture(root);snaps=v70.load_snapshots(v68/"variants"/"BROAD_PROVISIONAL"/"v67_c3_monthly_rankings.csv.gz");market=v70.load_market(store,set(symbols))
            r=v70.simulate(market,snaps,v70.T2_STRATEGY,v70.COST_SCENARIOS[1],1e9,"TEST")
            self.assertTrue(all(float(x["cash_vnd"])>=-1e-6 for x in r["daily"]));events={v70._next(market.cal,s.day).isoformat() for s in snaps if v70._next(market.cal,s.day)};trade_days={x["trade_day"] for x in r["ledger"]};self.assertTrue(any(d not in events for d in trade_days))

    def test_missing_target_open_leaves_cash_and_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);store,v68,symbols=build_fixture(root);snaps=v70.load_snapshots(v68/"variants"/"BROAD_PROVISIONAL"/"v67_c3_monthly_rankings.csv.gz");market=v70.load_market(store,set(symbols));entry=v70._next(market.cal,snaps[0].day);market.so.pop((snaps[0].symbols[0],entry),None)
            r=v70.simulate(market,snaps,v70.STRATEGIES[0],v70.COST_SCENARIOS[1],1e9,"TEST");self.assertTrue(any(x["event"]=="MISSING_TARGET_ENTRY_OPEN_LEAVE_CASH" for x in r["missing"]));self.assertTrue(all(float(x["cash_vnd"])>=-1e-6 for x in r["daily"]))

    def test_end_to_end_outputs_and_2026_alpha_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);store,v68,_=build_fixture(root);out=root/"v70";report=v70.analyze(v68,store,out)
            self.assertEqual(report["status"],"SUCCESS");self.assertEqual(report["champion_model"],"C3_STABLE_3_PAST_IC_SHRUNK");self.assertFalse(report["champion_replaced"]);self.assertFalse(report["promotion_authorized"])
            for name in ("v70_backtest_summary.csv","v70_monthly_returns.csv","v70_annual_returns.csv","v70_rolling_alpha.csv","v70_cost_drag.csv","v70_bear_market_scorecard.csv","v70_capital_lot_sensitivity.csv","v70_trade_ledger.csv.gz","v70_daily_equity.csv.gz","v70_missing_price_events.csv","v70_report.json"):self.assertTrue((out/name).is_file(),name)
            with (out/"v70_bear_market_scorecard.csv").open("r",encoding="utf-8-sig",newline="") as f:rows=list(csv.DictReader(f))
            self.assertTrue(rows)
            for row in rows:self.assertAlmostEqual(float(row["alpha_arithmetic"]),float(row["strategy_return"])-float(row["benchmark_return"]),places=12)

if __name__=="__main__":unittest.main()
