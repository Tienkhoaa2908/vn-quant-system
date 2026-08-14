# V72 handoff — frozen C3 weekly overlay deep backtest

## Required reading

A successor chat must read, at minimum, before designing further research:

1. `tai_lieu_dieu_phoi/nguyen_tac_du_an.md`;
2. `tai_lieu_dieu_phoi/chuan_nghien_cuu_va_backtest.md`;
3. `tai_lieu_dieu_phoi/anti_regression_c3_hose.md`;
4. `tai_lieu_dieu_phoi/v70_workstation_result_20260814.md`;
5. `tai_lieu_dieu_phoi/v71_workstation_result_20260814.md`;
6. `tai_lieu_dieu_phoi/v72_research_contract.md`;
7. latest V72 source/tests/runner/workflow and newest workstation artifact.

Repository/artifact newer than this handoff wins if they conflict.

## Frozen strategy state

Champion remains `C3_STABLE_3_PAST_IC_SHRUNK`.

Three components remain:

- `low_volatility`;
- `relative_strength_120`;
- `high_52_week`.

Weight-training label remains close(T) -> close(T+20), benchmark-relative. Tradable execution remains after-close signal -> earliest next-session open.

No adaptive candidate, weekly overlay, macro factor, ML challenger or historical diagnostic has been promoted.

## V70 workstation fact

V70 deep backtest on real local store was structurally successful.

Representative GAP18_CLEAN BASE_DNSE equal-weight frozen C3:

- total return `+372.5536%`;
- CAGR `18.6432%`;
- daily max drawdown `-38.1011%`;
- same-calendar VNINDEX total return `+124.5317%`.

Historical edge survived GROSS / BASE / STRESS / SEVERE modeled costs.

2026 was a real relative failure, especially April. GAP18 equal BASE through the observed 2026 slice returned about `-12.38%` versus VNINDEX `+2.71%`; the April interval was about `-11.00%` versus benchmark `+9.15%`.

## V71 workstation fact

V71 tested only C3 IC-memory adaptation:

- `C3_IC_EWMA_HL24`;
- `C3_IC_ROLLING60`.

Primary inference stopped at `2025-12-31`. 2026 was excluded.

Result: **0/12 candidate × variant × allocator tests passed the pre-2026 watchlist gate.** Therefore expanding frozen C3 remains champion.

EWMA-HL24 materially improved the already-observed 2026 shadow in several universes, for example GAP18 equal from roughly `-12.38%` frozen to `-5.51%`, but this is stress-mechanism evidence only and cannot select/promote EWMA.

V71 workstation artifact also exposed a reporting-only defect: adaptive annual rows omitted `cost_scenario`, causing adaptive rows to disappear from `v71_2026_shadow.csv`. The underlying monthly/deep-backtest results were intact. A reporting-safe wrapper and regression test were added on the V71 branch; do not require another real-data V71 run solely for this defect.

## Why V72 is next

V69 had already identified endogenous weekly signal mechanisms:

- `R07_DD20_08` and `R08_DD60_12`: strong adverse-excursion separation but no proven mechanical exit policy;
- `L15_PERSIST_REL`: strongest historical opportunity mechanism in matched-control research.

The missing evidence was portfolio action P&L. V72 therefore translates them into predeclared, standalone actions and passes each through the V70 deep-backtest mechanics.

Because these cohorts were historically surfaced before V72, this is a **post-selected mechanism audit**, not pristine OOS evidence.

## V72 standalone policies

- `NO_OVERLAY`: exact frozen V70 comparator.
- `R07_TRIM50_CASH`: trim 50% of held R07-triggered name, once per symbol per monthly cycle, keep proceeds in cash.
- `R08_TRIM50_CASH`: same for R08.
- `L15_SWAP50_WORST`: sell 50% of weekly-worst held name and buy strongest unheld L15 leader, capped at 15% per name.

Do not combine them in V72. Do not combine adaptive C3 weights. Do not add macro in V72.

Signal forms at completed weekly close, executes next market open. Monthly C3 rebalance has precedence on collisions.

## V72 evidence contract

Deep backtest includes:

- equal + inverse-vol60 allocation;
- actual shares, lot 100, max 15%/name;
- GROSS / BASE_DNSE / STRESS / SEVERE;
- T+2 no-advance sensitivity;
- 100m / 1bn / 10bn capital sensitivity;
- daily NAV/MDD, annual/rolling returns, trade ledger, action log, missing-price log, ADV/turnover.

`NO_OVERLAY` must reconstruct V70 total return/CAGR/MDD within `1e-10`.

Primary inference stops at `2025-12-31`; 2026 is shadow only. Paired monthly policy-minus-base deltas use two-calendar-month sign-flip null tests, block bootstrap CI and BH-FDR.

Return gate requires positive mean delta, q<0.10, CI lower>0 and >=60% positive annual deltas. Risk policies additionally expose a diagnostic risk-efficiency gate (MDD improvement >=2pp, CAGR loss <=1pp, p10 month improvement), but this cannot promote a post-selected mechanism.

## After V72 workstation artifact

Read P&L first.

Then decide among:

1. no overlay survives -> retain frozen C3; move to a tightly controlled macro point-in-time ablation or future-paper data gate work;
2. one standalone overlay is consistently useful pre-2026 -> preserve it as a paper-holdout candidate; only then consider a predeclared minimal integration matrix;
3. overlay only helps 2026 but not pre-2026 -> treat as stress clue, not selection evidence;
4. adaptive + overlay combination must not be attempted until standalone evidence justifies both components independently.

No historical result authorizes live capital.
