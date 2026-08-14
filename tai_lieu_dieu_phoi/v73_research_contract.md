# V73 research contract — C3 factor-health regime

## Purpose

V73 tests one narrow endogenous hypothesis after V71 adaptive-memory and V72 weekly-overlay audits failed to produce a pre-2026 return-gate winner: when the **recent completed predictive IC of C3's own momentum/trend components turns non-positive**, reducing portfolio stock exposure may improve causal out-of-sample portfolio results.

This is a post-selected mechanism audit because the hypothesis was motivated after observing historical V70/V71/V72 behavior, including 2026. It is not pristine OOS evidence.

## Frozen champion

Champion remains `C3_STABLE_3_PAST_IC_SHRUNK`.

Frozen invariants:

- components: `low_volatility`, `relative_strength_120`, `high_52_week`;
- weight-training label: close(T) -> close(T+20), benchmark-relative;
- tradable execution: signal information known after close, earliest trade next market open;
- monthly C3 Top10 ranking is unchanged in V73;
- no adaptive-weight candidate is combined;
- no V72 weekly overlay is combined;
- no macro input is included.

## Predeclared candidate gates

All gates use only historical monthly component IC observations satisfying BOTH:

- historical `signal_day < current signal_day`;
- historical `label_end < current signal_day`.

No current/future label is allowed.

The only candidates are:

1. `FH_RS3_SOFT50`
   - recent window: latest 3 completed monthly IC observations;
   - trigger: mean `relative_strength_120` IC <= 0;
   - triggered exposure: 50% stock / residual cash.

2. `FH_MOM3_AVG_SOFT50`
   - latest 3 completed IC observations;
   - trigger: mean of recent RS120 IC and recent High52 IC <= 0;
   - triggered exposure: 50%.

3. `FH_MOM6_AVG_SOFT50`
   - same sign rule using latest 6 completed IC observations;
   - triggered exposure: 50%.

There are no magnitude thresholds to tune. Zero is the frozen sign boundary; 50% is the project's existing soft-risk-off exposure convention.

## Inference boundary

Primary candidate inference ends `2025-12-31`.

2026 is `OBSERVED_STRESS_NOT_SELECTION_SET` and MUST NOT affect candidate choice, threshold, window, FDR or any other research decision inside V73.

Primary paired comparison:

- candidate monthly BASE_DNSE return minus `NO_FACTOR_HEALTH_GATE` return;
- same universe and allocator;
- contiguous two-calendar-month sign-flip null test;
- block-bootstrap CI only;
- BH-FDR within universe × allocator;
- annual sign stability.

Diagnostic watchlist gate requires:

- mean paired monthly delta > 0;
- BH-FDR q < 0.10;
- bootstrap 95% CI lower > 0;
- >=60% positive annual return deltas before 2026;
- pre-2026 MDD deterioration no worse than 2 percentage points.

Passing this remains research-only because V73 is post-selected.

## Deep backtest

Every policy is evaluated through V70 mechanics:

- frozen monthly Top10;
- equal and inverse-vol60 allocation;
- actual shares;
- next-session-open execution;
- lot size 100;
- max 15% per symbol;
- residual cash;
- GROSS / BASE_DNSE / STRESS / SEVERE costs;
- T+2 no-advance sensitivity;
- capital sensitivity 100m / 1bn / 10bn VND;
- daily NAV and drawdown;
- annual and rolling alpha;
- trade ledger, missing-price diagnostics and ADV capacity fields.

`NO_FACTOR_HEALTH_GATE` must reconstruct the V70 always-invested equal/inverse-vol baselines with total-return/CAGR/MDD error <= `1e-10`.

## Profit-first reporting

A valid V73 artifact must report P&L before signal diagnostics, including total return, benchmark, alpha, CAGR, MDD, yearly returns, cost stress, settlement sensitivity and 2026 shadow.

## Decision after V73

- If no gate survives pre-2026 inference: do not tune IC windows or exposure levels from 2026; move to a publication-date point-in-time macro ablation using official NSO/SBV sources or to fresh paper holdout/data-lineage work.
- If one gate survives across sensitivity universes: preserve it as a research/paper candidate, then test a minimal predeclared integration matrix only after independent evidence.
- Any benefit seen only in 2026 is a stress clue, not selection evidence.

No historical result authorizes live capital.
