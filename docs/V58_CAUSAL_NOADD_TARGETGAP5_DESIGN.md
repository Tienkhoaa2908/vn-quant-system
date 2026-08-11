# V58 causal NO-ADD + target-gap 4/5 study

Research only. No workstation/live policy changes.

## Corrections from V57

1. V57 capital-deployment results remain usable for allocator comparisons that only use canonical information and same-session open execution assumptions inherited from V43.1.
2. V57 tail NO-ADD / rank-loss results are not admissible because the harness evaluated the current weekly close and then allowed execution at that same session open. V58 requires previous-session close information for any loss-aware decision executed at the next session open.
3. V57 did not test the most conservative fix for residual cash: increase the number of target-gap names before permitting any above-target spillover.

## Capital variants

- BASELINE_ONE_ORDER
- TARGET_GAP_3
- TARGET_GAP_4
- TARGET_GAP_5
- STAGED_FULL_3 (reference only)
- STAGED_FULL_5 (reference only)

TARGET_GAP_4/5 never redeploy above each candidate's target gap except the existing one-share bootstrap allowance. They address residual cash by adding additional underweight C3 names rather than concentrating more money in already-selected names.

## Tail variants

Retest the V57 tail variants causally:

- BASELINE
- NOADD_075 / 100 / 125
- RANKLOSS_EXIT_100

Loss state is observed at previous-session close. Any resulting purchase block or rank-loss sale first affects execution at the next weekly/session open. No current-session close may influence current-session open execution.

## Decision rule

A planner change is eligible for live implementation only if TARGET_GAP_4/5 materially reduces avoidable idle-cash weeks versus TARGET_GAP_3 without a robust deterioration in holdout annualized return, max drawdown, or largest-position weight across 200k/250k/300k and BASE/STRESS/SEVERE slippage cells.

Tail changes remain research-only unless causal holdout results are robust. August 2026 remains excluded from parameter selection.
