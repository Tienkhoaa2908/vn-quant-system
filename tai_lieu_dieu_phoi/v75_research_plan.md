# V75 consolidated stock-selection optimization plan

V75 replaces the slow one-hypothesis-per-workstation-cycle pattern.

## Goal

Attack the observed C3 failure mode directly: frozen C3 remains strong long-run, but in some regimes (especially observed 2026) its medium-horizon momentum factors react too slowly, miss newly emerging leaders and can enter stale/late momentum after the move.

## One-shot lanes

A single workstation package must run:

1. V68 frozen C3/data sensitivity;
2. V70 execution-aligned deep baseline;
3. extended monthly stock-selection feature extraction from the same local market store;
4. multiple **predeclared** C3-anchored ranking challengers in parallel;
5. winner-capture / loser-avoidance diagnostics;
6. paired pre-2026 inference with dependence correction;
7. full V70 deep backtest for every ranking candidate;
8. optional official NSO CPI/IIP publication-date-PIT macro lane when coverage is usable;
9. 2026 shadow/stress only;
10. profit-first consolidated report.

Macro coverage failure may not stop stock-selection lanes.

## Frozen comparator

Champion remains `C3_STABLE_3_PAST_IC_SHRUNK`.
Recorded V67 rankings/scores are comparator truth. V75 may not alter the frozen baseline.

## Candidate feature library

All auxiliary features are calculated only from information available at monthly signal close:

- `relative_20`;
- `relative_10`;
- `relative_5`;
- `momentum_acceleration = relative_20 - relative_strength_120 / 6`;
- `breakout_20_gap`;
- `distance_ma20`;
- `volume_ratio_5_20` transformed with log;
- `stability = -realized_vol_ratio_20_60`.

No 2026-derived magnitude threshold is allowed.

## Predeclared C3-anchored ranking candidates

- `C3_FAST_REL20_25`: 75% frozen C3 score + 25% cross-sectional percentile of `relative_20`.
- `C3_FAST_ACCEL_25`: 75% frozen C3 score + 25% percentile of momentum acceleration.
- `C3_FRESH_BREAKOUT_25`: 75% frozen C3 score + 25% percentile of 20-session breakout freshness.
- `C3_AUX_IC36_35`: 65% frozen C3 score + 35% causal auxiliary score. Auxiliary weights come only from the latest 36 **completed** monthly labels before the current signal, use positive mean monthly Spearman IC only, and shrink 50% toward equal weight among positive auxiliaries. If no auxiliary has positive completed-past IC, the candidate falls back to frozen C3.

Candidate definitions are fixed before real workstation execution.

## Causality

Training target remains C3's canonical `close(T) -> close(T+20)` benchmark-relative label. Candidate weighting at T may use only historical rows with both `signal_day < T` and `label_end < T`.

Tradable portfolio execution remains next-session open and is evaluated separately by the V70 engine.

Primary selection ends `2025-12-31`. All 2026 observations are shadow/stress only.

## Winner capture / loser avoidance

For each labeled monthly cross-section report:

- future top-decile / top-10 winner capture by candidate Top10;
- bottom-decile loser contamination inside candidate Top10;
- mean forward excess return of candidate Top10;
- mean realized rank of future winners;
- C3-vs-candidate change in capture/contamination.

These diagnostics explain stock selection; they do not replace portfolio P&L.

## Deep backtest

Every candidate, including frozen comparator, must run through V70 mechanics:

- actual shares;
- next-session open;
- equal and inverse-vol60 allocation;
- lot 100;
- max 15% per symbol;
- GROSS / BASE_DNSE / STRESS / SEVERE;
- T+2 no-advance sensitivity;
- 100m / 1bn / 10bn capital sensitivity;
- daily NAV/MDD;
- annual/rolling alpha;
- cost, turnover and ADV/capacity diagnostics.

Frozen comparator must reconstruct V70 within `1e-10`.

## Statistical gate

Pre-2026 candidate-vs-frozen paired monthly BASE returns use contiguous two-calendar-month sign-flip null tests, block-bootstrap CI and BH-FDR. A research watchlist candidate requires positive mean delta, q<0.10, bootstrap lower bound >0, >=60% positive annual deltas and no >2pp pre-2026 MDD deterioration. This is still historical research, not promotion.

## Macro lane

Use official NSO only. Publication day is the information timestamp. CPI/IIP history is best-effort and late-era diagnostic if the dedicated archive has at least 48 first-release observations per series. If coverage is below that or the site is unavailable, record `MACRO_LANE_BLOCKED` and continue all stock-selection work.

## Decision

V75 should answer in one workstation run whether the next useful improvement is:

- faster stock-selection ranking;
- only a risk/allocation improvement;
- macro context;
- or no historical enhancement strong enough, in which case stop historical rule search and prioritize fresh paper holdout + data-lineage completion.
