# V71 research contract — causal adaptive C3 weighting ablation

V71 is a post-V70 research ablation. It must not replace or mutate the frozen champion `C3_STABLE_3_PAST_IC_SHRUNK`.

## Motivation

V70 shows strong long-run post-cost C3 alpha but a concentrated 2026 relative failure, especially the period beginning 2026-04-01. By the 2026-03-31 signal, recently completed relative-strength IC observations had weakened while the expanding all-history C3 still carried a large momentum/trend weight. V71 tests whether a faster but still causal IC estimator improves robustness without introducing new factors.

2026 has already been observed. It is **shadow/stress only** and cannot be used to choose candidate family, parameter, threshold or gate.

## Frozen baseline

- champion/baseline: `C3_STABLE_3_PAST_IC_SHRUNK`;
- components unchanged: `low_volatility`, `relative_strength_120`, `high_52_week`;
- training label unchanged: benchmark-relative `close(T) -> close(T+20)`;
- every IC used at signal T must come from a monthly cohort whose `label_end < T`;
- same 50% shrinkage to equal weights;
- same max component weight 0.50;
- same current eligible universe and same monthly completed-snapshot contract.

## Predeclared challenger estimators

Only these two adaptive weight estimators are authorized in V71:

1. `C3_IC_EWMA_HL24`
   - all completed historical monthly ICs remain usable;
   - exponentially downweight older completed IC observations;
   - half-life = 24 completed monthly observations;
   - no future/current incomplete IC.

2. `C3_IC_ROLLING60`
   - same C3 IC estimator;
   - use the most recent 60 completed monthly IC observations;
   - no future/current incomplete IC.

No component, threshold or parameter may be changed after seeing V71 2026 output.

## Portfolio ablation

For baseline and both challengers, run:

- equal-weight Top10;
- inverse-volatility-60 Top10;
- next-session-open execution;
- actual shares;
- lot size 100;
- max 15%/symbol;
- GROSS / BASE_DNSE / STRESS / SEVERE;
- 100m / 1bn / 10bn VND capital sensitivity under BASE;
- T+2 no-advance sensitivity under BASE;
- same benchmark and same V70 deep-backtest mechanics.

The V70 engine is reused; V71 must not fork a second incompatible transaction-cost/cash-ledger implementation.

## Primary inference period

Candidate-vs-baseline statistical inference and watchlist gating use **only periods ending on or before 2025-12-31**.

Required paired evidence:

- monthly return delta on the same rebalance periods;
- contiguous two-calendar-month block sign-flip null test;
- block bootstrap confidence interval;
- BH-FDR across the two adaptive candidates within each variant/allocation scope;
- year-by-year candidate-minus-baseline return delta;
- Top10 overlap/turnover change;
- cost sensitivity.

2026 is reported separately as `OBSERVED_STRESS_NOT_SELECTION_SET`.

## Watchlist gate

A V71 challenger can enter a diagnostic watchlist only if, on the pre-2026 primary period:

- mean paired monthly return delta > 0;
- BH-FDR q < 0.10;
- block-bootstrap 95% CI lower bound > 0;
- positive annual delta in at least 60% of eligible pre-2026 years.

This gate only creates a research watchlist. It does not promote the challenger, alter C3 champion status, reset paper holdout, or authorize live use.

## 2026 stress reporting

For every candidate/allocation:

- 2026 return;
- VNINDEX return;
- arithmetic alpha;
- candidate-minus-baseline return delta;
- April-2026 period delta;
- max drawdown where available;
- explicit `used_for_selection=false`.

## V69 overlays

`L15_PERSIST_REL`, `R07_DD20_08` and `R08_DD60_12` remain frozen research candidates. V71 does not tune or combine them with adaptive C3. Portfolio integration of weekly overlays is deferred until the adaptive ranking ablation is known, to avoid stacking multiple post-selected mechanisms in one decision.

## Macro

No macro feature is added in V71. Macro is only opened after endogenous ranking/allocation/weekly-overlay attribution, using official sources and release-date point-in-time availability. This prevents 2026-aware macro backfitting.

## Required output

V71 must output, at minimum:

- `v71_component_ic_history.csv`;
- `v71_weight_history.csv`;
- `v71_rankings.csv.gz`;
- `v71_top10_overlap.csv`;
- `v71_predictive_proxy.csv`;
- `v71_backtest_summary.csv`;
- `v71_monthly_returns.csv`;
- `v71_annual_returns.csv`;
- `v71_candidate_inference.csv`;
- `v71_2026_shadow.csv`;
- `v71_cost_drag.csv`;
- `v71_capital_sensitivity.csv`;
- `v71_trade_ledger_base.csv.gz`;
- `v71_report.json`.

Research result replies must begin with portfolio P&L/benchmark/alpha/drawdown before predictive metrics.
