# V61 Adaptive C3 Portfolio Policy Study

## Objective

Keep the frozen C3 stock-selection model and research whether portfolio policy can:

1. reduce damage from a canonical leader whose current preview collapses (VPI-like risk);
2. avoid adding new money to stale/weakening leaders;
3. re-route or partially rotate capital toward still-confirmed canonical leaders;
4. capture genuinely strong mid-month newcomers without blindly buying every new Preview Top-5/Top-10;
5. improve net portfolio return after fees, tax and BASE/STRESS/SEVERE slippage.

V61 is research-only. It never authorizes live capital or automatic orders.

## Why there is no pristine holdout claim

V60 already inspected the former 2022+ holdout. V61 therefore treats the historical archive as consumed research data and uses cross-era/year robustness plus three execution-cost scenarios. August 2026 and the current VPI episode remain outside the default analysis end (2026-07-31) and are not used for selection.

## Causality

Preview is observed only at a completed weekly close. It can affect a trade only at a later weekly open. A preview tied to a different canonical month is ignored for routing/trim decisions so month-transition state cannot silently mix two canonical models.

## Policy families

### Baseline

`BASELINE_P1`: original monthly canonical Top-10, underweight buy, outside Top-20 for two monthly signals before full exit.

### New-capital routing

- `ROUTE_CONFIRMED10`: new money only to canonical Top-10 names that remain Preview Top-10.
- `NOADD_BREAKDOWN20`: canonical names may still receive money while Preview rank <=20; >20/ineligible blocks new adds.

### Partial breakdown trims

- 25% or 50% trim after one/two weekly breakdown observations.
- one partial trim per breakdown episode;
- a one-share position is never silently converted from a 25% trim into a 100% exit;
- hysteresis variants require Preview <=10 to reset the breakdown episode.

### Rotation

Trim proceeds may be recycled only into preview-confirmed canonical leaders. This tests whether earlier de-risking is useful only when capital has a sufficiently strong alternative destination.

### Age + breakdown

Age-conditioned variants require a canonical signal to be at least 10 or 15 sessions old before a confirmed breakdown can trigger a partial trim. These are predefined tests; the V60 exploratory age pattern is not treated as untouched OOS evidence.

### Filtered tactical newcomers

Naive new Preview Top-5/Top-10 was rejected by V60. V61 only tests a small sleeve for new Preview Top-5 names with extra confirmation:

- persistence in Top-5;
- moderate volume acceleration (`ADV/volume 5d vs 20d` proxy);
- anti-extension filter using 5-session return and distance to MA20;
- rank-velocity variant for gradual entry into Top-5;
- combined persistence + volume + anti-extension.

Tactical positions are capped, use 5%/10% weekly allocation variants, exit after about 10 sessions or Preview breakdown, and automatically become core if the next monthly canonical ranking promotes them into Top-10.

## Metrics

For each policy × 200k/250k/300k contribution × BASE/STRESS/SEVERE slippage, V61 records:

- final value, XIRR and XIRR excess;
- unitized and annualized return;
- max drawdown and Calmar;
- cash ratio and largest single-symbol weight;
- fees, gross turnover and order counts;
- worst single-name unrealized loss as % NAV;
- worst weighted drawdown from a held symbol's post-entry peak;
- count of weeks where one position damages NAV by >=1%;
- preview trim count and two-week whipsaw recoveries;
- tactical candidate/buy/exit/promotion counts;
- per-calendar-year return, drawdown and tail-risk diagnostics.

## Robustness gate

No policy is called a live improvement. A `historical_robustness_candidate` must at minimum:

- have positive median annualized-return difference vs baseline across nine capital/cost cells;
- beat baseline return in at least 6/9 cells;
- avoid materially worsening median max drawdown;
- beat drawdown in at least 4/9 cells;
- have non-negative median return improvement under SEVERE slippage;
- beat baseline calendar-year return in at least 55% of comparable year/cell observations.

The report still sets `live_model_change_authorized=false`. Any candidate requires manual review and a later paper/live-forward stage.

## Baseline parity

Before any V61 comparison is emitted, custom `BASELINE_P1` must reproduce frozen V43 P1 final value, XIRR and max drawdown at V43's original terminal day for all 3 contribution levels × 3 cost scenarios. A parity mismatch aborts the study.
