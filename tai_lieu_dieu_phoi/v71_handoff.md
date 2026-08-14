# V71 handoff — causal adaptive C3 weight-memory ablation

## Why V71 exists

V70 workstation evidence shows the frozen C3 remains strongly profitable over the long history after modeled costs, but 2026 contains a real relative failure. The largest residual failure is the rebalance period beginning 2026-04-01, where the C3 Top10 broadly underperformed rather than suffering from one isolated symbol.

The 2026-03-31 frozen expanding C3 still assigned about 76.7% combined weight to `relative_strength_120` and `high_52_week` even though recently completed relative-strength IC observations had weakened. This motivates testing whether the **memory of the IC estimator** should adapt faster while preserving the same C3 factors, label semantics and causal contract.

2026 has already been observed. It is a stress/shadow set only and is excluded from candidate selection and statistical gating.

## Frozen baseline

Champion remains:

`C3_STABLE_3_PAST_IC_SHRUNK`

Nothing in V71 changes:

- the three components: `low_volatility`, `relative_strength_120`, `high_52_week`;
- the benchmark-relative `close(T) -> close(T+20)` C3 training label;
- completed-label causality (`label_end < signal_day`);
- 50% shrinkage toward equal component weights;
- frozen raw component cap semantics before the final renormalization;
- the current C3 champion/promotion status.

## Predeclared candidates

Only two adaptive estimators are allowed:

1. `C3_IC_EWMA_HL24`: exponential weighting of completed monthly component IC observations with a fixed 24-observation half-life.
2. `C3_IC_ROLLING60`: use only the latest 60 completed monthly IC observations.

No alternative half-life/window may be introduced after viewing V71 workstation results.

## Comparator provenance guard

V71 must compare candidates with the **actual frozen C3 that V67 recorded**, not a numerically re-sorted clone.

Historical scoring rules:

- exact V67 training-row component values are used when available;
- raw-store factor reconstruction is an audit/cross-check when those frozen components exist;
- frozen weights and per-symbol scores must reconstruct within strict tolerance;
- frozen rank order comes from `v67_c3_monthly_rankings.csv.gz` as the recorded comparator truth, so sub-tolerance floating ties cannot silently create a different baseline;
- adaptive candidates are ranked from their newly computed causal adaptive scores;
- latest unlabeled rows may use direct raw-store causal factor reconstruction.

The provenance-safe entrypoint is:

`he_thong_dinh_luong.c3_adaptive_weight_v71_safe`

## Inference contract

Candidate selection/inference only uses rebalance periods ending on or before `2025-12-31`.

Required evidence:

- paired candidate-minus-frozen monthly return on the same rebalance periods;
- contiguous two-calendar-month block sign-flip null test;
- block-bootstrap 95% confidence interval;
- BH-FDR across the two adaptive candidates within each variant/allocation scope;
- pre-2026 annual sign stability.

Diagnostic watchlist gate:

- mean paired monthly return delta > 0;
- BH-FDR q < 0.10;
- bootstrap 95% CI lower bound > 0;
- positive candidate-minus-frozen annual delta in at least 60% of eligible pre-2026 years.

Passing only creates a diagnostic watchlist. It never promotes the candidate.

## Deep backtest contract

V71 reuses `deep_portfolio_backtest_v70` instead of creating another transaction engine.

For frozen C3 and adaptive candidates, compare:

- equal-weight Top10;
- inverse-volatility-60 Top10;
- next-session-open execution;
- actual shares;
- lot 100;
- max 15% per symbol;
- GROSS / BASE_DNSE / STRESS / SEVERE;
- 100m / 1bn / 10bn VND capital sensitivity;
- T+2 no-advance sensitivity;
- same VNINDEX benchmark calendar.

Every V71 result reply must start with P&L / benchmark / alpha / CAGR / max drawdown before predictive or statistical metrics.

## 2026 reporting

2026 is output separately with:

- strategy return;
- benchmark return;
- alpha;
- candidate-minus-frozen return delta;
- April-2026 candidate-minus-frozen delta;
- `used_for_selection=false`.

The result may tell us whether a candidate would have helped the observed stress, but that fact cannot make the candidate pass its pre-2026 gate.

## Deferred lanes

V69 mechanisms remain frozen but are deliberately not combined in V71:

- opportunity: `L15_PERSIST_REL`;
- protection diagnostics: R07/R08 family.

Weekly overlay integration is deferred until the standalone adaptive ranking result is known. This avoids stacking multiple post-selected mechanisms at once.

Macro is also deferred. A later macro lane is allowed only with official-source, release-date point-in-time data and the same deep backtest, after endogenous ranking/allocation/weekly-overlay attribution is understood.

## Workstation runner

One-shot runner:

`scripts/run_v71_c3_adaptive_weight_gitbash.sh`

It reruns the full chain in one bundle:

`V68 data/C3/cohorts -> V69 matched controls/profit -> V70 frozen deep backtest -> V71 adaptive-weight ablation`.

Expected upload:

`UPLOAD_THIS_v71_C3_ADAPTIVE_WEIGHT-*.zip`

## Research governance

- research only;
- data gates for PIT HOSE, price basis/corporate actions and PIT sector master remain unresolved;
- no champion replacement;
- no paper/live promotion;
- no automatic orders;
- workstation artifact is required before any V71 research conclusion.
