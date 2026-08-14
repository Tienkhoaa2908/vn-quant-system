# V65 — Multi-signal robustness audit

V65 is the second-stage audit of the frozen 36-cohort V64 screen. It does not add or tune thresholds.

## Why

V64 is a fast vectorized event screen. V65 tests dependence, overlap, multiplicity, concentration and shadow-data completeness before any mechanism can be retained for later portfolio research.

## Frozen inputs

- V64 matrix: 18 risk + 18 leader cohorts, unchanged.
- Historical selection end: 2026-07-31.
- Shadow end: 2026-08-13.
- August is not used to change thresholds.
- No live or paper policy change.

## Robustness checks

1. 10,000-resample weekly-cluster bootstrap.
2. 10,000-resample symbol-cluster bootstrap.
3. Week-cluster sign-flip test at horizon 10.
4. Benjamini-Hochberg FDR correction separately inside risk and leader families.
5. Year-by-year horizon-10 diagnostics.
6. Cohort Jaccard overlap matrix.
7. Symbol concentration and consecutive-week repeat rates.
8. Risk rebound and future severe-loss rates.
9. Leader incremental comparison against raw new Preview Top-5.
10. Shadow signal-state reconstruction that does not require future outcomes.
11. Canonical freshness audit; month gap greater than one is flagged stale.

A `robust_historical_mechanism=true` row is not fresh out-of-sample evidence and does not authorize any operational change. Portfolio interactions remain a later research stage.
