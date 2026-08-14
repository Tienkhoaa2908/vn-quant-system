"""V70 deep execution-aligned backtest for frozen C3. Research only."""
from __future__ import annotations
import argparse,bisect,csv,gzip,json,math,sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from statistics import fmean,pstdev
from typing import Mapping,Sequence

SCHEMA_VERSION="deep_portfolio_backtest_v70"
CHAMPION_MODEL="C3_STABLE_3_PAST_IC_SHRUNK"
PRICE_MULTIPLIER=1000.0
LOT_SIZE=100
SINGLE_NAME_CAP=0.15
INITIAL_CAPITAL_VND=1_000_000_000.0

@dataclass(frozen=True)
class Cost:
    name:str; buy_fee_bps:float=0.; sell_fee_bps:float=0.; sell_tax_bps:float=0.; transfer_vnd:float=0.; slip_bps:float=0.
COSTS=(Cost("GROSS"),Cost("BASE_DNSE",2.7,2.7,10.,.3,5.),Cost("STRESS",2.7,2.7,10.,.3,10.),Cost("SEVERE",2.7,2.7,10.,.3,20.))

@dataclass(frozen=True)
class Strategy:
    id:str; allocator:str; risk_off:float; settlement:str="IMMEDIATE"
STRATEGIES=(Strategy("C3_EQ_ALWAYS","EQUAL",1.),Strategy("C3_INVOL_ALWAYS","INVOL60",1.),
 Strategy("C3_EQ_SOFT50","EQUAL",.5),Strategy("C3_INVOL_SOFT50","INVOL60",.5),
 Strategy("C3_EQ_BINARY_CASH","EQUAL",0.),Strategy("C3_INVOL_BINARY_CASH","INVOL60",0.))
T2=Strategy("C3_EQ_ALWAYS_T2_NO_ADVANCE","EQUAL",1.,"T2_NO_ADVANCE")

@dataclass(frozen=True)
class Snap: day:date; symbols:tuple[str,...]; risk_on:bool
@dataclass
class Market:
    cal:list[date]; io:dict[date,float]; ic:dict[date,float]
    so:dict[tuple[str,date],float]; sc:dict[tuple[str,date],float]; vol:dict[tuple[str,date],int]
@dataclass
class State:
    cash:float; shares:dict[str,int]; pending:list[tuple[date,float]]; mark:dict[str,float]; desired:dict[str,int]

def _bool(x): return str(x or "").strip().lower() in {"1","true","yes","y"}
def _next(cal,d):
    i=bisect.bisect_right(cal,d); return cal[i] if i<len(cal) else None
def _pos(cal,d):
    i=bisect.bisect_left(cal,d); return i if i<len(cal) and cal[i]==d else None
def _std(v):
    if len(v)<2:return 0.
    m=fmean(v); return math.sqrt(sum((x-m)**2 for x in v)/(len(v)-1))

def _csv(path,rows):
    rows=list(rows); fields=[]; seen=set()
    for r in rows:
        for k in r:
            if k not in seen: seen.add(k); fields.append(k)
    fields=fields or ["empty"]; path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n"); w.writeheader()
        for r in rows:w.writerow({k:r.get(k,"") for k in fields})
def _gzcsv(path,rows):
    rows=list(rows); fields=[]; seen=set()
    for r in rows:
        for k in r:
            if k not in seen:seen.add(k);fields.append(k)
    fields=fields or ["empty"]; path.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(path,"wt",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n");w.writeheader()
        for r in rows:w.writerow({k:r.get(k,"") for k in fields})

def load_snaps(path):
    by={}
    with gzip.open(path,"rt",encoding="utf-8-sig",newline="") as f:
        for r in csv.DictReader(f):
            try:d=date.fromisoformat(r["signal_day"]);rank=int(r["rank"])
            except:continue
            b=by.setdefault(d,{"x":[],"risk":False})
            if rank<=10:b["x"].append((rank,str(r["symbol"]).strip().upper()))
            b["risk"]=_bool(r.get("risk_on"))
    out=[Snap(d,tuple(s for _,s in sorted(v["x"])),v["risk"]) for d,v in sorted(by.items()) if v["x"]]
    if len(out)<3:raise ValueError("V70_TOO_FEW_MONTHLY_SNAPSHOTS")
    return out

def load_market(store,symbols):
    uri=store.resolve().as_uri()+"?mode=ro"
    with closing(sqlite3.connect(uri,uri=True)) as db:
        cols={str(r[1]).lower():str(r[1]) for r in db.execute('PRAGMA table_info("bars")')}
        if not {"symbol","day","open","close","volume","asset_type"}<=set(cols):raise ValueError("V70_BARS_REQUIRED_COLUMNS_MISSING")
        q=lambda x:'"'+x.replace('"','""')+'"'
        sql=f"SELECT {q(cols['symbol'])},{q(cols['day'])},{q(cols['open'])},{q(cols['close'])},{q(cols['volume'])},{q(cols['asset_type'])} FROM bars ORDER BY 2,1"
        io_,ic,so,sc,vo={},{},{},{},{}
        for sr,dr,op,cl,vr,ar in db.execute(sql):
            s=str(sr or "").strip().upper();a=str(ar or "").strip().upper()
            try:d=date.fromisoformat(str(dr)[:10]);o=float(op);c=float(cl);v=max(0,int(vr))
            except:continue
            if s in {"VNINDEX","VN-INDEX","VN_INDEX"} and a=="INDEX":
                if o>0:io_[d]=o
                if c>0:ic[d]=c
            elif s in symbols and a in {"STOCK","EQUITY",""}:
                if o>0:so[s,d]=o*PRICE_MULTIPLIER
                if c>0:sc[s,d]=c*PRICE_MULTIPLIER
                vo[s,d]=v
    cal=sorted(set(io_)&set(ic))
    if len(cal)<300:raise ValueError("V70_VNINDEX_HISTORY_TOO_SHORT")
    return Market(cal,io_,ic,so,sc,vo)

def vol60(m,s,d):
    p=bisect.bisect_right(m.cal,d)-1
    if p<60:return None
    c=[m.sc.get((s,x)) for x in m.cal[p-60:p+1]]
    if any(x is None or x<=0 for x in c):return None
    z=_std([c[i]/c[i-1]-1 for i in range(1,len(c))]);return z if z>0 else None
def adv20(m,s,d):
    p=bisect.bisect_right(m.cal,d)-1
    if p<19:return None
    x=[]
    for day in m.cal[p-19:p+1]:
        c=m.sc.get((s,day));v=m.vol.get((s,day))
        if c is not None and v is not None:x.append(c*v)
    return fmean(x) if len(x)==20 else None

def _cap(raw,exposure):
    if not raw or exposure<=0:return {s:0. for s in raw}
    pos={s:max(0.,float(v)) for s,v in raw.items()}
    if sum(pos.values())<=0:pos={s:1. for s in pos}
    free=set(pos);out={};rem=exposure
    while free and rem>1e-15:
        den=sum(pos[s] for s in free)
        trial={s:rem*pos[s]/den for s in free}
        hit=[s for s,w in trial.items() if w>SINGLE_NAME_CAP+1e-15]
        if not hit:out.update(trial);break
        for s in hit:
            out[s]=SINGLE_NAME_CAP;free.remove(s);rem-=SINGLE_NAME_CAP
    for s in raw:out.setdefault(s,0.)
    return out
def weights(m,snap,spec):
    ex=1. if snap.risk_on else spec.risk_off
    if spec.allocator=="EQUAL":raw={s:1. for s in snap.symbols}
    else:
        vv={s:vol60(m,s,snap.day) for s in snap.symbols}
        raw={s:(1./vv[s] if vv[s] else 1.) for s in snap.symbols} if all(vv.values()) else {s:1. for s in snap.symbols}
    return _cap(raw,ex)

def _settle_day(cal,d):
    p=_pos(cal,d)
    if p is None:raise ValueError("V70_SETTLEMENT_DAY")
    return cal[min(len(cal)-1,p+2)]
def _settle(st,d):
    amt=sum(v for day,v in st.pending if day<=d);st.pending=[x for x in st.pending if x[0]>d];st.cash+=amt;return amt
def _value(st,m,d,open_,missing):
    src=m.so if open_ else m.sc;total=st.cash+sum(v for _,v in st.pending)
    for s,q in st.shares.items():
        px=src.get((s,d))
        if px is None:
            px=st.mark.get(s);missing.append({"day":d.isoformat(),"symbol":s,"event":"MISSING_OPEN_MARK_CARRY" if open_ else "MISSING_CLOSE_MARK_CARRY"})
        else:st.mark[s]=px
        if px:total+=q*px
    return total
def _stock_value(st,m,d,open_):
    src=m.so if open_ else m.sc;return sum(q*(src.get((s,d)) or st.mark.get(s,0.)) for s,q in st.shares.items())

def _sell(st,m,s,q,d,signal,cost,mode,ledger,missing):
    q=min(q,st.shares.get(s,0));q=q//LOT_SIZE*LOT_SIZE
    if q<=0:return
    raw=m.so.get((s,d))
    if raw is None:missing.append({"day":d.isoformat(),"symbol":s,"event":"MISSING_SELL_OPEN_HOLD"});return
    px=raw*(1-cost.slip_bps/10000);notional=px*q;fee=notional*cost.sell_fee_bps/10000;tax=notional*cost.sell_tax_bps/10000;transfer=q*cost.transfer_vnd;net=notional-fee-tax-transfer
    if mode=="T2_NO_ADVANCE":st.pending.append((_settle_day(m.cal,d),net))
    else:st.cash+=net
    st.shares[s]-=q
    if st.shares[s]<=0:st.shares.pop(s,None)
    st.mark[s]=raw;ad=adv20(m,s,signal)
    ledger.append({"signal_day":signal.isoformat(),"trade_day":d.isoformat(),"symbol":s,"side":"SELL","shares":q,"raw_open_vnd":raw,"execution_price_vnd":px,"notional_vnd":notional,"fee_vnd":fee,"sell_tax_vnd":tax,"transfer_fee_vnd":transfer,"slippage_drag_vnd":raw*q-notional,"adv20_vnd":ad,"participation_adv20":notional/ad if ad else None,"settlement_mode":mode,"lot_size":LOT_SIZE})
def _buy(st,m,s,q,d,signal,cost,mode,ledger,missing):
    q=q//LOT_SIZE*LOT_SIZE
    if q<=0:return
    raw=m.so.get((s,d))
    if raw is None:missing.append({"day":d.isoformat(),"symbol":s,"event":"MISSING_BUY_OPEN_LEAVE_CASH"});return
    px=raw*(1+cost.slip_bps/10000);rate=cost.buy_fee_bps/10000;aff=int(st.cash//(px*(1+rate)*LOT_SIZE))*LOT_SIZE;q=min(q,aff)
    if q<=0:return
    notional=px*q;fee=notional*rate;st.cash-=notional+fee
    if st.cash<-1e-6:raise ValueError("V70_NEGATIVE_CASH")
    st.shares[s]=st.shares.get(s,0)+q;st.mark[s]=raw;ad=adv20(m,s,signal)
    ledger.append({"signal_day":signal.isoformat(),"trade_day":d.isoformat(),"symbol":s,"side":"BUY","shares":q,"raw_open_vnd":raw,"execution_price_vnd":px,"notional_vnd":notional,"fee_vnd":fee,"sell_tax_vnd":0.,"transfer_fee_vnd":0.,"slippage_drag_vnd":notional-raw*q,"adv20_vnd":ad,"participation_adv20":notional/ad if ad else None,"settlement_mode":mode,"lot_size":LOT_SIZE})

def _target(st,m,snap,spec,d,nav,missing):
    out={}
    for s,w in weights(m,snap,spec).items():
        raw=m.so.get((s,d))
        if raw is None:missing.append({"day":d.isoformat(),"symbol":s,"event":"MISSING_TARGET_ENTRY_OPEN_LEAVE_CASH"});out[s]=st.shares.get(s,0);continue
        out[s]=int(nav*w//(raw*LOT_SIZE))*LOT_SIZE
    return out
def _rebalance(st,m,snap,spec,cost,d,ledger,missing,liquidate=False):
    _settle(st,d);nav=_value(st,m,d,True,missing);des={} if liquidate else _target(st,m,snap,spec,d,nav,missing);st.desired=dict(des)
    for s in sorted(set(st.shares)|set(des)):
        if st.shares.get(s,0)>des.get(s,0):_sell(st,m,s,st.shares.get(s,0)-des.get(s,0),d,snap.day,cost,spec.settlement,ledger,missing)
    for s in sorted(des,key=lambda x:(-des[x],x)):
        if des[s]>st.shares.get(s,0):_buy(st,m,s,des[s]-st.shares.get(s,0),d,snap.day,cost,spec.settlement,ledger,missing)
def _catchup(st,m,snap,spec,cost,d,ledger,missing):
    if spec.settlement!="T2_NO_ADVANCE" or _settle(st,d)<=0:return
    for s in sorted(st.desired,key=lambda x:(-st.desired[x],x)):
        if st.desired[s]>st.shares.get(s,0):_buy(st,m,s,st.desired[s]-st.shares.get(s,0),d,snap.day,cost,spec.settlement,ledger,missing)

def _mdd(v):
    peak=0.;worst=0.
    for x in v:
        peak=max(peak,x)
        if peak:worst=min(worst,x/peak-1)
    return worst
def _cagr(a,b,d0,d1):
    y=(d1-d0).days/365.2425;return (b/a)**(1/y)-1 if a>0 and b>0 and y>0 else None
def _ratio(v,kind):
    if len(v)<3:return None
    if kind=="sharpe":den=pstdev(v)
    else:den=math.sqrt(fmean(min(0.,x)**2 for x in v))
    return math.sqrt(12)*fmean(v)/den if den else None
def _ir(v):
    return math.sqrt(12)*fmean(v)/pstdev(v) if len(v)>=3 and pstdev(v)>0 else None
def _annual(rows):
    acc={}
    for r in rows:
        y=date.fromisoformat(r["period_end_day"]).year;s,b=acc.get(y,(1.,1.));acc[y]=(s*(1+r["strategy_return"]),b*(1+r["benchmark_return"]))
    return [{"year":y,"strategy_return":s-1,"benchmark_return":b-1,"alpha_arithmetic":s-b} for y,(s,b) in sorted(acc.items())]
def _rolling(rows):
    out=[]
    for i,r in enumerate(rows):
        for w in (3,6,12):
            if i+1<w:continue
            s=b=1.
            for x in rows[i-w+1:i+1]:s*=1+x["strategy_return"];b*=1+x["benchmark_return"]
            out.append({"period_end_day":r["period_end_day"],"window_months":w,"strategy_return":s-1,"benchmark_return":b-1,"alpha_arithmetic":s-b})
    return out

def simulate(m,snaps,spec,cost,capital,variant):
    events=[_next(m.cal,s.day) for s in snaps];pairs=[(e,s) for e,s in zip(events,snaps) if e]
    if len(pairs)<3:raise ValueError("V70_TOO_FEW_REBALANCE_EVENTS")
    events=[x[0] for x in pairs];snaps=[x[1] for x in pairs];first,final=events[0],events[-1];a,b=_pos(m.cal,first),_pos(m.cal,final)
    st=State(float(capital),{},[],{},{});ledger=[];missing=[];daily=[];periods=[];lookup={d:i for i,d in enumerate(events)};checkpoint=capital;exp={};last=snaps[0]
    bmstart=m.io[first]
    for d in m.cal[a:b+1]:
        if d in lookup:
            i=lookup[d];snap=snaps[i];last=snap;_rebalance(st,m,snap,spec,cost,d,ledger,missing,liquidate=i==len(events)-1);nav=_value(st,m,d,True,missing);exp[i]=_stock_value(st,m,d,True)/nav if nav else 0.
            if i>=1:
                br=m.io[d]/m.io[events[i-1]]-1;sr=nav/checkpoint-1;ie=1. if snaps[i-1].risk_on else spec.risk_off
                periods.append({"variant_id":variant,"strategy_id":spec.id,"cost_scenario":cost.name,"period_start_day":events[i-1].isoformat(),"period_end_day":d.isoformat(),"strategy_return":sr,"benchmark_return":br,"alpha":sr-br,"risk_on_at_period_start":snaps[i-1].risk_on,"intended_stock_exposure":ie,"actual_stock_exposure_at_period_start":exp.get(i-1),"exposure_matched_benchmark_return":ie*br,"alpha_vs_exposure_matched_benchmark":sr-ie*br});checkpoint=nav
        else:_catchup(st,m,last,spec,cost,d,ledger,missing)
        navc=_value(st,m,d,False,missing);stock=_stock_value(st,m,d,False);daily.append({"variant_id":variant,"strategy_id":spec.id,"cost_scenario":cost.name,"day":d.isoformat(),"nav_close_vnd":navc,"equity":navc/capital,"benchmark_equity":m.ic[d]/bmstart,"cash_vnd":st.cash,"pending_cash_vnd":sum(x[1] for x in st.pending),"stock_exposure":stock/navc if navc else 0.,"position_count":len(st.shares)})
    finalnav=_value(st,m,final,True,missing);bmfinal=capital*m.io[final]/bmstart
    monthly=[r["strategy_return"] for r in periods];bench=[r["benchmark_return"] for r in periods];alpha=[x-y for x,y in zip(monthly,bench)];ea=[r["alpha_vs_exposure_matched_benchmark"] for r in periods];down=[(x,y) for x,y in zip(monthly,bench) if y<0];up=[(x,y) for x,y in zip(monthly,bench) if y>=0]
    parts=[r["participation_adv20"] for r in ledger if r["participation_adv20"] is not None];modeled=sum(r["fee_vnd"]+r["sell_tax_vnd"]+r["transfer_fee_vnd"]+r["slippage_drag_vnd"] for r in ledger);sell=sum(r["notional_vnd"] for r in ledger if r["side"]=="SELL")
    cagr=_cagr(capital,finalnav,first,final);mdd=_mdd([r["nav_close_vnd"] for r in daily]+[finalnav])
    summary={"variant_id":variant,"strategy_id":spec.id,"allocator":spec.allocator,"risk_off_exposure":spec.risk_off,"settlement_mode":spec.settlement,"cost_scenario":cost.name,"initial_capital_vnd":capital,"first_entry_day":first.isoformat(),"final_liquidation_day":final.isoformat(),"period_count":len(periods),"total_return":finalnav/capital-1,"benchmark_total_return":bmfinal/capital-1,"total_alpha_arithmetic":(finalnav-bmfinal)/capital,"ending_nav_vnd":finalnav,"cagr":cagr,"max_drawdown_daily":mdd,"benchmark_max_drawdown_daily":_mdd([r["benchmark_equity"] for r in daily]+[bmfinal/capital]),"monthly_sharpe_rf0":_ratio(monthly,"sharpe"),"monthly_sortino_rf0":_ratio(monthly,"sortino"),"calmar":cagr/abs(mdd) if cagr is not None and mdd<0 else None,"information_ratio_monthly":_ir(alpha),"positive_month_rate":sum(x>0 for x in monthly)/len(monthly),"beat_benchmark_month_rate":sum(x>y for x,y in zip(monthly,bench))/len(monthly),"mean_intended_stock_exposure":fmean(r["intended_stock_exposure"] for r in periods),"mean_alpha_vs_exposure_matched_benchmark":fmean(ea),"positive_exposure_matched_alpha_rate":sum(x>0 for x in ea)/len(ea),"down_market_month_count":len(down),"down_market_mean_alpha":fmean(x-y for x,y in down) if down else None,"down_market_beat_rate":sum(x>y for x,y in down)/len(down) if down else None,"up_market_month_count":len(up),"up_market_mean_alpha":fmean(x-y for x,y in up) if up else None,"up_market_beat_rate":sum(x>y for x,y in up)/len(up) if up else None,"trade_count":len(ledger),"modeled_cost_and_slippage_vnd":modeled,"modeled_cost_drag_vs_initial":modeled/capital,"mean_monthly_one_way_sell_turnover_vs_initial":sell/capital/max(len(periods),1),"max_adv20_participation":max(parts) if parts else None,"trade_rate_adv20_gt_5pct":sum(x>.05 for x in parts)/len(parts) if parts else None,"trade_rate_adv20_gt_10pct":sum(x>.10 for x in parts)/len(parts) if parts else None,"missing_price_event_count":len(missing),"final_position_count":len(st.shares),"final_pending_cash_vnd":sum(x[1] for x in st.pending),"lot_size":LOT_SIZE,"single_name_cap":SINGLE_NAME_CAP,"sector_cap_enforced":False,"corporate_actions_complete":False,"price_basis_confirmed":False,"pit_hose_confirmed":False}
    return {"summary":summary,"periods":periods,"annual":_annual(periods),"rolling":_rolling(periods),"ledger":ledger,"daily":daily,"missing":missing}

def analyze(v68_output,store,output_dir,initial_capital=INITIAL_CAPITAL_VND):
    root=v68_output/"variants";by={};symbols=set()
    if not root.is_dir():raise ValueError("V70_V68_VARIANTS_MISSING")
    for d in sorted(x for x in root.iterdir() if x.is_dir()):
        p=d/"v67_c3_monthly_rankings.csv.gz"
        if p.is_file():
            by[d.name]=load_snaps(p)
            for snap in by[d.name]:symbols.update(snap.symbols)
    if not by:raise ValueError("V70_NO_VARIANTS")
    m=load_market(store,symbols);output_dir.mkdir(parents=True,exist_ok=True);summ=[];period=[];annual=[];rolling=[];ledger=[];daily=[];missing=[]
    for variant,snaps in sorted(by.items()):
        for spec in STRATEGIES:
            for cost in COSTS:
                r=simulate(m,snaps,spec,cost,initial_capital,variant);summ.append(r["summary"]);period+=r["periods"];annual += [{**x,"variant_id":variant,"strategy_id":spec.id,"cost_scenario":cost.name,"initial_capital_vnd":initial_capital} for x in r["annual"]];rolling += [{**x,"variant_id":variant,"strategy_id":spec.id,"cost_scenario":cost.name,"initial_capital_vnd":initial_capital} for x in r["rolling"]];ledger += [{**x,"variant_id":variant,"strategy_id":spec.id,"cost_scenario":cost.name,"initial_capital_vnd":initial_capital} for x in r["ledger"]];missing += [{**x,"variant_id":variant,"strategy_id":spec.id,"cost_scenario":cost.name} for x in r["missing"]]
                if cost.name=="BASE_DNSE" or (cost.name=="GROSS" and spec.id=="C3_EQ_ALWAYS"):daily+=r["daily"]
        r=simulate(m,snaps,T2,COSTS[1],initial_capital,variant);summ.append(r["summary"]);period+=r["periods"];annual += [{**x,"variant_id":variant,"strategy_id":T2.id,"cost_scenario":"BASE_DNSE","initial_capital_vnd":initial_capital} for x in r["annual"]];rolling += [{**x,"variant_id":variant,"strategy_id":T2.id,"cost_scenario":"BASE_DNSE","initial_capital_vnd":initial_capital} for x in r["rolling"]];ledger += [{**x,"variant_id":variant,"strategy_id":T2.id,"cost_scenario":"BASE_DNSE","initial_capital_vnd":initial_capital} for x in r["ledger"]];daily+=r["daily"];missing += [{**x,"variant_id":variant,"strategy_id":T2.id,"cost_scenario":"BASE_DNSE"} for x in r["missing"]]
    cap=[]
    for variant,snaps in sorted(by.items()):
        for capital in (100_000_000.,1_000_000_000.,10_000_000_000.):cap.append(simulate(m,snaps,STRATEGIES[0],COSTS[1],capital,variant)["summary"])
    groups={}
    for r in summ:groups.setdefault((r["variant_id"],r["strategy_id"],r["initial_capital_vnd"]),{})[r["cost_scenario"]]=r
    drag=[]
    for (v,s,c),g in groups.items():
        if "GROSS" not in g:continue
        for name in ("BASE_DNSE","STRESS","SEVERE"):
            if name in g:drag.append({"variant_id":v,"strategy_id":s,"initial_capital_vnd":c,"cost_scenario":name,"total_return_drag_vs_gross":g[name]["total_return"]-g["GROSS"]["total_return"],"cagr_drag_vs_gross":g[name]["cagr"]-g["GROSS"]["cagr"]})
    bear=[{"variant_id":r["variant_id"],"strategy_id":r["strategy_id"],"year":2026,"strategy_return":r["strategy_return"],"benchmark_return":r["benchmark_return"],"alpha_arithmetic":r["alpha_arithmetic"],"interpretation":"OBSERVED_STRESS_SLICE_NOT_TUNING_SET"} for r in annual if int(r["year"])==2026 and r["cost_scenario"]=="BASE_DNSE"]
    _csv(output_dir/"v70_backtest_summary.csv",summ);_csv(output_dir/"v70_monthly_returns.csv",period);_csv(output_dir/"v70_annual_returns.csv",annual);_csv(output_dir/"v70_rolling_alpha.csv",rolling);_csv(output_dir/"v70_cost_drag.csv",drag);_csv(output_dir/"v70_bear_market_scorecard.csv",bear);_csv(output_dir/"v70_capital_lot_sensitivity.csv",cap);_gzcsv(output_dir/"v70_trade_ledger.csv.gz",ledger);_gzcsv(output_dir/"v70_daily_equity.csv.gz",daily);_csv(output_dir/"v70_missing_price_events.csv",missing)
    report={"schema_version":SCHEMA_VERSION,"status":"SUCCESS","champion_model":CHAMPION_MODEL,"champion_replaced":False,"research_only":True,"promotion_authorized":False,"deep_backtest_completed":True,"profit_report_required":True,"portfolio_contract":"MONTHLY_C3_TOP10_ACTUAL_SHARES_NEXT_OPEN_REBALANCE","initial_capital_vnd":initial_capital,"lot_size":LOT_SIZE,"single_name_cap":SINGLE_NAME_CAP,"cost_scenarios":[c.__dict__ for c in COSTS],"strategy_ids":[s.id for s in STRATEGIES]+[T2.id],"base_equal_weight_summary":[r for r in summ if r["strategy_id"]=="C3_EQ_ALWAYS" and r["cost_scenario"]=="BASE_DNSE"],"data_gates":{"pit_hose_closed":False,"price_basis_closed":False,"corporate_actions_complete":False,"pit_sector_master_closed":False},"macro_lane":{"included_in_v70_model":False,"reason":"ATTRIBUTE_2026_TO_SELECTION_AND_PORTFOLIO_MECHANICS_FIRST","future_contract":"OFFICIAL_SOURCE_RELEASE_DATE_POINT_IN_TIME_FIRST_RELEASE_OR_VINTAGE_PURGED_ABLATION"},"limitations":["Sensitivity universes are provisional until point-in-time HOSE lineage is closed.","Price basis/corporate actions remain incomplete; GAP18/SEAM_CLEAN are sensitivity tests, not adjustments.","Sector cap 25% is blocked until a point-in-time sector master exists.","T2_NO_ADVANCE is a conservative settlement sensitivity with catch-up buys after settlement, not broker-specific exact credit.","Fixed slippage does not model limit queues/partial fills/nonlinear impact; ADV20 participation is reported.","2026 is observed stress/audit data and must not be used to tune thresholds."],"automatic_live_orders_allowed":False}
    (output_dir/"v70_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8");return report

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument("--v68-output",type=Path,required=True);p.add_argument("--store",type=Path,required=True);p.add_argument("--output-dir",type=Path,required=True);p.add_argument("--initial-capital",type=float,default=INITIAL_CAPITAL_VND);a=p.parse_args(argv);r=analyze(a.v68_output,a.store,a.output_dir,a.initial_capital);print(json.dumps({"schema_version":r["schema_version"],"status":r["status"],"deep_backtest_completed":True,"promotion_authorized":False}));return 0
COST_SCENARIOS=COSTS
T2_STRATEGY=T2
_cap_weights=_cap
load_snapshots=load_snaps
target_weights=weights
if __name__=="__main__":raise SystemExit(main())
