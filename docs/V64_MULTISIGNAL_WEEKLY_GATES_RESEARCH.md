# V64 — Multi-signal weekly protection/opportunity gate research

Research only. No live or paper trading policy is changed by this branch.

## Why V64 exists

V63 confirmed two different failure modes that cannot be solved by one monthly/rank rule:

1. a canonical leader can remain high in weekly Preview rank while its price/risk state deteriorates materially (the August-2026 VPI shadow example remained Preview #4 then #10);
2. new leaders can emerge between monthly canonical updates (August shadow examples included BAF and TLG), while raw new-Top5 entry historically was not robust.

V64 therefore evaluates a broad but **pre-declared** hypothesis matrix instead of tuning one threshold to August observations.

## Causality and anti-overfit contract

- historical selection end: 2026-07-31;
- analysis/shadow end: 2026-08-13;
- August 2026 is shadow-only and cannot alter thresholds or candidate selection;
- every feature is formed on a completed weekly close;
- every forward outcome begins at the next market-session open;
- the former V60 holdout is already consumed, so V64 uses year/era stability rather than claiming pristine OOS evidence;
- thresholds below are frozen before workstation execution.

## Protection matrix — 18 hypotheses

Families cover rank collapse, rank velocity, score deterioration, MA20/MA50 breaks, 5/10-session relative weakness, 20/60-session drawdown, negative-return/volume shock, realized-volatility shock, price breaks, multi-factor composites, and two-week confirmation.

The key design change versus V63 is that rank is **not required** for every protection rule. A canonical Top-10 name can trigger on price/relative-risk evidence even while Preview rank is still high.

Protection is evaluated as event-level **benefit of leaving the position versus continuing to hold** over 1/3/5/10/15/20 sessions, with BASE friction on the hypothetical exit. The decision gate emphasizes 5/10-session consistency, year/era stability, and whether the cohort actually precedes meaningful adverse excursion.

## Opportunity matrix — 18 hypotheses

Families cover raw Top-5, MA20/MA50 trend, relative strength, volume confirmation, anti-extension, persistence, rank velocity, score acceleration, 20-session breakout, risk-on regime, composite confirmation, pullback leadership, and high-conviction Top-3 trend/volume.

Only symbols outside the current monthly canonical Top-10 are eligible for opportunity cohorts. V64 measures BASE net excess return at 1/3/5/10/15/20 sessions and whether the symbol is promoted into a future canonical Top-10 within the next two monthly snapshots.

## Decision philosophy

Turnover and cost stress are diagnostics, not vetoes. BASE cost is primary because the intended workstation contribution/trade scale is small. A historical candidate still needs nearby-horizon stability and cross-year/cross-era consistency; a one-period optimum is rejected.

A V64 candidate is only a **research shortlist**. Portfolio sizing, capital displacement, simultaneous protection/opportunity interactions, symbol/sector caps, and paper/live policy remain out of scope until a later portfolio study.

## Outputs

- `v64_features.csv`
- `v64_gate_events.csv`
- `v64_historical_metrics.csv`
- `v64_shortlist.csv`
- `v64_shadow_events.csv`
- `v64_shadow_focus_vpi_tlg_baf.csv`
- `v64_gate_contract.csv`
- `v64_report.json`

The VPI/TLG/BAF focus file is only a convenient shadow audit view. Those names do not participate in historical candidate selection.
