# V60 — C3 short-horizon / preview-entry study

Research only. No workstation trade policy is changed by this branch.

## Why this study exists

The current V47/P1 contract is asymmetric:

- monthly canonical Top-10 creates the buy candidate universe;
- latest-session preview can block a canonical candidate when it loses eligibility or falls outside preview Top-20;
- latest preview cannot introduce a new Top-10 symbol that was absent from monthly canonical Top-10;
- sell review remains monthly and requires two completed months outside Top-20.

This can preserve a stale monthly leader while missing a new short-horizon leader. V60 tests whether that is a real, repeatable source of alpha decay rather than reacting to one August 2026 example.

## Causal protocol

- August 2026 is excluded from parameter selection and evaluation.
- Analysis end: 2026-07-31 or the latest earlier market session available.
- Calibration: through 2021-12-31.
- Holdout: 2022-01-01 through analysis end.
- Every preview observation uses only prices/volume through that session close.
- Any hypothetical trade enters at the next market-session open.
- Fixed-horizon exits are known at entry and execute at a later market-session open.
- Component weights are those of the most recent completed canonical month and use only completed past labels.
- The monthly point-in-time eligible universe is carried inside its following month; latest daily eligibility is recomputed from OHLCV.

## Questions

1. How quickly does canonical C3 alpha decay after a month-end signal?
2. Do new preview Top-10 entrants have positive net excess return over the next 5 or 10 sessions?
3. When a canonical Top-10 name deteriorates outside preview Top-20, is its subsequent 5/10-session return sufficiently poor to justify tactical de-risking?
4. Is a separate tactical sleeve more defensible than changing the core P1 sell gate?

## Cohorts

- `PREVIEW_TOP10`: all latest preview Top-10 names.
- `NEW_PREVIEW_TOP10`: latest preview Top-10 names not in canonical Top-10.
- `NEW_PREVIEW_TOP5`: latest preview Top-5 names not in canonical Top-10.
- `CANONICAL_TOP10_RETAINED`: canonical Top-10 and latest preview Top-10.
- `CANONICAL_TOP10_DROPPED20`: canonical Top-10 but latest preview rank is >20 or ineligible.

## Horizons

Signal decay is reported at 1, 3, 5, 10, 15 and 20 market sessions where available.
Tradeable event research focuses on 5 and 10-session fixed horizons.

## Costs

Same friction family as V43/V56:

- broker fee 15 bps;
- exchange fee 2.7 bps;
- sell tax 10 bps;
- transfer fee 0.3 VND/share;
- slippage scenarios BASE 20 bps, STRESS 50 bps, SEVERE 100 bps per side.

## Decision boundary

V60 can only recommend `PROMOTE_TO_PAPER_RESEARCH`; it cannot authorize live policy changes.

A tactical-preview candidate must show in holdout:

- positive mean net excess return in BASE/STRESS/SEVERE;
- no collapse of hit rate under STRESS/SEVERE;
- adequate event count;
- consistent direction across 5/10-session nearby horizons rather than a single sharp optimum.

If short-horizon alpha is confirmed, the preferred architecture is dual horizon:

- **Core**: existing monthly P1 allocation and sell gate.
- **Tactical sleeve**: capped share of NAV, populated by new latest-preview leaders, fixed 5–10 session horizon and/or preview-rank deterioration rule.

The core sell gate is not shortened unless a separate portfolio backtest proves that change robustly improves holdout risk-adjusted performance after costs.
