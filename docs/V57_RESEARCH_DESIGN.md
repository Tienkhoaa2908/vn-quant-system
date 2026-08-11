# V57 staged deployment + tail-risk continuation study

Research only. No workstation/live policy changes.

## Questions

1. Can unused cash from an on-demand contribution be redeployed without forcing exact target-weight balance inside the same cycle?
2. Can loss-aware NO-ADD reduce single-name tail damage without the return destruction observed in V56 hard exits?
3. Does a tighter position cap improve robustness once staged full deployment is allowed?

## Current live allocator issue

The current workstation candidate ceiling is effectively `min(cap_gap, max(target_gap, one_share_cost))`. After target gaps are filled, residual buying power can remain idle even when preview-eligible C3 Top-10 names remain buyable.

## Staged deployment principle

First pass: fill the largest underweights toward target.

Second pass: redeploy residual cash to the strongest still-eligible C3 candidates, while respecting the effective concentration cap and maximum order count. Future contributions recompute underweights, so names that were temporarily over target lose priority and lagging eligible names catch up later.

"Strongest" means C3 signal quality (canonical rank / score and preview eligibility), not recent realized P&L.

## Tail overlays to test

- baseline P1
- loss-aware NO-ADD at 0.75%, 1.00%, 1.25% NAV damage
- symbol cap 12.5% and 10%
- NO-ADD + 12.5% cap
- monthly rank-deterioration + loss confirmation

NO-ADD never forces a sale. It only blocks additional purchases in the affected symbol until the next canonical monthly signal.

## Deployment variants to test

- one-order V43.1 parity baseline
- current-style target-gap allocator, max 3 orders
- staged full deployment, max 3 orders
- staged full deployment, max 5 orders
- staged full deployment + tighter cap
- staged full deployment + NO-ADD

## Evaluation protocol

Use the frozen C3 walk-forward research inputs and local DNSE OHLCV. Calibration ends 2021-12-31. Holdout begins 2022-01-01. The August 2026 VPI episode is excluded from parameter selection.

Primary metrics:

- annualized unitized return / XIRR
- max drawdown
- worst single-position loss as fraction of NAV
- median and 10th percentile deployment ratio
- weeks with >20% deployable cash left idle despite an affordable eligible candidate
- turnover and estimated transaction cost
- largest position weight

Promotion requires holdout robustness across 200k/250k/300k contribution sizes and BASE/STRESS/SEVERE slippage scenarios. No live change is authorized by this study alone.
