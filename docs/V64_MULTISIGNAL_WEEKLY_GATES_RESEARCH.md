# V64 — Multi-signal weekly risk/leader cohort research

Research only. No live or paper-trading policy is changed by this branch.

## Why V64 exists

V63 confirmed two different failure modes that cannot be solved by one monthly/rank rule:

1. a canonical leader can remain high in weekly Preview rank while its price/risk state deteriorates materially (the August-2026 VPI shadow example remained Preview #4 then #10);
2. new leaders can emerge between monthly canonical updates (August shadow examples included BAF and TLG), while raw new-Top5 entry historically was not robust.

V64 therefore evaluates a broad but **pre-declared** cohort matrix instead of tuning one threshold to August observations.

## Causality and anti-overfit contract

- historical selection end: 2026-07-31;
- analysis/shadow end: 2026-08-13;
- August 2026 is shadow-only and cannot alter thresholds or candidate selection;
- every feature is formed on a completed weekly close;
- every forward outcome begins at the next market-session open;
- the former V60 holdout is already consumed, so V64 uses year/era stability rather than claiming pristine OOS evidence;
- all 36 cohort definitions are frozen before workstation execution.

## Risk-deterioration matrix — 18 hypotheses

Families cover rank collapse, rank velocity, score deterioration, MA20/MA50 breaks, 5/10-session relative weakness, 20/60-session drawdown, negative-return/volume shock, realized-volatility shock, price breaks, multi-factor composites, and two-week confirmation.

The key design change versus V63 is that rank is **not required** for every risk cohort. A canonical Top-10 name can be classified as deteriorating from price/relative-risk evidence even while Preview rank is still high.

Risk cohorts are evaluated by the sign and magnitude of subsequent forward returns over 1/3/5/10/15/20 sessions plus 10-session adverse excursion. A useful cohort should repeatedly precede negative forward returns across years and eras, rather than only fitting one historical episode.

## Emerging-leader matrix — 18 hypotheses

Families cover raw Top-5, MA20/MA50 trend, relative strength, volume confirmation, anti-extension, persistence, rank velocity, score acceleration, 20-session breakout, risk-on regime, composite confirmation, pullback leadership, and high-conviction Top-3 trend/volume.

Only symbols outside the current monthly canonical Top-10 are eligible for emerging-leader cohorts. V64 measures forward excess return at 1/3/5/10/15/20 sessions and whether the symbol reaches a future canonical Top-10 within the next two monthly snapshots.

## Cost and turnover

V64 is deliberately an event-level signal-identification study. Transaction-cost and turnover vetoes are deferred to the later portfolio stage. This implements the current requirement that small-ticket trading cost should not dominate signal discovery. The eventual portfolio study must reintroduce realistic friction, capital displacement, symbol/sector caps, and simultaneous interactions.

## Decision philosophy

A historical candidate needs nearby-horizon stability and cross-year/cross-era consistency; a one-period optimum is rejected. Passing V64 only creates a **research shortlist**. It does not authorize a live model change, automatic order, or paper/live deployment.

## Outputs

- `v64_features.csv`
- `v64_cohort_events.csv`
- `v64_historical_metrics.csv`
- `v64_shortlist.csv`
- `v64_shadow_events.csv`
- `v64_shadow_focus_vpi_tlg_baf.csv`
- `v64_cohort_contract.csv`
- `v64_report.json`

The VPI/TLG/BAF focus file is only a convenient shadow audit view. Those names do not participate in historical candidate selection.
