# V74 research contract — publication-date PIT macro ablation

## Research question

After V71/V72/V73 failed to produce a pre-2026 promotable endogenous adaptation, V74 tests whether a **small independent macro state layer** can improve the frozen C3 portfolio without changing stock ranking.

The champion remains `C3_STABLE_3_PAST_IC_SHRUNK`.

V74 is research-only. Historical results cannot authorize paper/live promotion by themselves.

## Frozen C3 invariants

- components remain `low_volatility`, `relative_strength_120`, `high_52_week`;
- training label remains close(T) -> close(T+20), benchmark-relative;
- monthly C3 ranking is unchanged;
- portfolio execution remains next market-session open after signal information is known;
- V74 changes only the portfolio stock-exposure target when a predeclared macro gate is active.

## Macro data scope

V74 deliberately starts with only two official National Statistics Office (NSO) monthly series:

1. CPI year-on-year;
2. Index of Industrial Production (IIP) year-on-year.

Official NSO English article archives are primary; Vietnamese NSO article archives are parser fallback. V74 does not ingest blogs, news summaries or third-party macro databases.

SBV rates, FX, credit and liquidity are **not** added in V74. They may be a later independent ablation only if V74 establishes a reason to increase dimensionality.

## Point-in-time publication contract

Every parsed macro observation must retain:

- series;
- reference month;
- actual NSO issue/publication date;
- parsed first-release YoY value;
- source URL;
- response SHA256;
- language;
- parsed supporting snippet.

A release is visible to a C3 signal only when:

```text
issue_day <= signal_day
```

Monthly values must never be backfilled to the reference month before publication.

If multiple NSO articles exist for the same series/reference month, V74 uses the earliest parseable official release and records its provenance. This is a first-release research contract; revised later values must not silently replace historical information.

Macro coverage is fail-closed if fewer than 80 monthly observations per required series can be established.

## Predeclared candidate gates

All gates use only information available by the monthly signal date and reduce target stock exposure to 50%. Zero is the only sign boundary; no magnitude threshold is tuned.

### `MACRO_IIP3_DECEL_SOFT50`

```text
IIP impulse = latest published IIP YoY - mean(previous 3 published IIP YoY)
gate active when IIP impulse <= 0
```

### `MACRO_CPI3_ACCEL_SOFT50`

```text
CPI impulse = latest published CPI YoY - mean(previous 3 published CPI YoY)
gate active when CPI impulse >= 0
```

### `MACRO_STAGFLATION3_SOFT50`

Gate active only when both:

```text
IIP impulse <= 0
CPI impulse >= 0
```

Do not tune 2/4/6-month lookbacks, positive/negative magnitude thresholds, or 30/70% exposures after viewing V74/2026 results.

## Candidate selection and 2026

Primary historical inference ends:

```text
2025-12-31
```

2026 is `OBSERVED_STRESS_NOT_SELECTION_SET` and may not alter:

- candidate definitions;
- lookback length;
- exposure fraction;
- significance gate;
- ranking model.

## Statistical contract

For each sensitivity universe × allocator:

- compare candidate monthly BASE_DNSE returns against the exact no-macro frozen C3 comparator on matched months;
- contiguous two-calendar-month block sign-flip null test;
- block-bootstrap confidence interval only;
- BH-FDR within universe × allocator;
- annual sign stability;
- pre-2026 MDD comparison.

Diagnostic watchlist requires all of:

- mean monthly return delta > 0;
- BH-FDR q < 0.10;
- bootstrap CI lower bound > 0;
- >=60% of pre-2026 years have positive candidate-minus-baseline return;
- MDD degradation no worse than 2 percentage points.

Passing remains research/watchlist evidence, not promotion.

## Deep backtest contract

Reuse V70 execution mechanics:

- equal-weight + inverse-vol60;
- actual shares;
- next-open execution;
- lot 100;
- max 15% per symbol;
- residual cash;
- GROSS / BASE_DNSE / STRESS / SEVERE;
- T+2 no-advance sensitivity;
- 100m / 1bn / 10bn capital sensitivity;
- daily equity / drawdown;
- annual/rolling alpha;
- trade/cost/capacity/missing-price diagnostics.

`NO_MACRO_GATE` must reconstruct V70 frozen C3 total return, CAGR and MDD within `1e-10`; otherwise V74 fails before any macro conclusion is accepted.

## Required output

Research report remains profit-first and must include at minimum:

- total return, CAGR, MDD;
- VNINDEX return and alpha;
- annual returns;
- 2026 shadow separately;
- matched pre-2026 inference;
- cost stress;
- T+2 and capital sensitivity;
- macro release-history/provenance table;
- macro state table showing which publication was visible at every signal.

## Explicit exclusions

V74 must not:

- replace C3;
- reweight C3 factors;
- combine V71 adaptive weights;
- combine V72 weekly overlays;
- combine V73 factor-health gates;
- add SBV/macroeconomic series beyond the frozen two-series scope;
- use 2026 to tune rules;
- mutate the local market store;
- place broker/live orders.
