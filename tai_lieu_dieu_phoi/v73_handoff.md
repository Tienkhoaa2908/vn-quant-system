# V73 handoff — C3 factor-health regime audit

## Required reading for successor chats

Before designing any research after V73, read in this order:

1. `tai_lieu_dieu_phoi/nguyen_tac_du_an.md`;
2. `tai_lieu_dieu_phoi/chuan_nghien_cuu_va_backtest.md`;
3. `tai_lieu_dieu_phoi/anti_regression_c3_hose.md`;
4. `tai_lieu_dieu_phoi/v70_workstation_result_20260814.md`;
5. `tai_lieu_dieu_phoi/v71_workstation_result_20260814.md`;
6. `tai_lieu_dieu_phoi/v72_workstation_result_20260814.md`;
7. `tai_lieu_dieu_phoi/v73_research_contract.md`;
8. latest V73 source/tests/runner/workflow and newest workstation artifact.

Repository/artifact newer than this handoff wins if there is a conflict.

## Frozen state

Champion remains `C3_STABLE_3_PAST_IC_SHRUNK`.

No adaptive C3, weekly overlay, macro factor, ML challenger or historical diagnostic has been promoted.

C3 components remain `low_volatility`, `relative_strength_120`, `high_52_week`.
Training label remains close(T)->close(T+20), benchmark-relative.
Tradable execution remains next-session open after signal information is known.

## Durable empirical state before V73

### V70

Frozen C3 survived modeled costs in deep actual-share backtest. Representative GAP18_CLEAN BASE_DNSE equal-weight:

- total return about `+372.55%`;
- CAGR about `18.64%`;
- daily MDD about `-38.10%`;
- same-calendar VNINDEX about `+124.53%` total return.

2026 was a genuine relative failure, concentrated strongly in April.

### V71

Adaptive IC-memory candidates EWMA-HL24 and rolling60 did not pass pre-2026 paired inference (`0/12` tests passed). EWMA materially reduced the already-observed 2026 stress but is only a clue, not a selected replacement.

### V72

Standalone weekly portfolio actions were deep-backtested:

- `R07_TRIM50_CASH`;
- `R08_TRIM50_CASH`;
- `L15_SWAP50_WORST`.

No policy passed the pre-2026 return gate in any scope.

Directional findings:

- L15 increased total return/CAGR and improved MDD across all six universe × allocator BASE scopes, but evidence was not strong enough after paired inference/FDR. GAP18 Equal BASE improved from about `+372.55%` to `+406.75%`, with CAGR about `19.56%` and MDD about `-36.39%`.
- R08 was also directionally positive long-run and improved MDD, but not statistically sufficient. GAP18 Equal BASE reached about `+402.85%`, CAGR about `19.46%`, MDD about `-36.60%`.
- R07 generally damaged return and worsened further as costs increased.
- In 2026, L15 improved the frozen result modestly. R07/R08 reduced April damage but hurt the full 2026 slice, demonstrating rebound/false-exit cost.

Do not tune weekly thresholds or fractions further from these historical results. Preserve L15/R08 as paper/fresh-holdout clues only.

## Why V73 exists

V70/V71 attribution showed the 2026 failure coincided with stale positive weight on momentum/trend components even after recent completed ICs weakened. Continuous recent-IC reweighting did not survive pre-2026 inference, so V73 tests a simpler binary regime question without changing ranking:

> when recent completed C3 momentum-factor IC becomes non-positive, does reducing stock exposure to 50% improve portfolio results?

This is still post-selected because the hypothesis was formed after observing historical behavior.

## V73 candidates

Only:

- `FH_RS3_SOFT50`;
- `FH_MOM3_AVG_SOFT50`;
- `FH_MOM6_AVG_SOFT50`.

All use zero as sign boundary and 50% as exposure when active. No additional thresholds, no adaptive weights, no weekly overlays, no macro.

Only IC observations with BOTH `signal_day < current signal_day` and `label_end < current signal_day` are allowed.

Primary selection cutoff is `2025-12-31`. 2026 is shadow only.

## Backtest and reporting

V73 reuses V70 deep mechanics and must reconstruct the no-gate V70 baseline exactly.

It evaluates equal/inverse-vol60, GROSS/BASE/STRESS/SEVERE, T+2 no-advance, 100m/1bn/10bn, actual shares, lot100, 15% single-name cap, daily NAV/MDD, annual/rolling alpha, trade ledger and capacity diagnostics.

Profit-first reporting is mandatory.

## Decision after workstation V73

1. If no gate survives pre-2026 inference: **do not tune IC windows/exposure from 2026**. Next research lane should be publication-date PIT macro ablation using official NSO/SBV data, or fresh paper/data-lineage work.
2. If one gate survives robustly across sensitivity universes: preserve it as a research/paper candidate; no automatic promotion.
3. Any improvement seen only in 2026 remains shadow evidence.
4. Do not stack V71/V72/V73 mechanisms until each proposed component has independent evidence and a predeclared integration test.

No historical result authorizes live capital.
