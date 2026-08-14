# V75 handoff — consolidated stock-selection optimization

## Required reading

Successor chats must read, in order:

1. `nguyen_tac_du_an.md`;
2. `chuan_nghien_cuu_va_backtest.md`;
3. `anti_regression_c3_hose.md`;
4. V70/V71/V72/V73/V74 workstation result documents;
5. `v75_research_plan.md`;
6. latest V75 source/tests/runner/workflow and workstation artifact.

Repo/artifact newer than this handoff wins.

## Frozen state

Champion remains `C3_STABLE_3_PAST_IC_SHRUNK`. No V71 adaptive weights, V72 weekly overlay, V73 factor-health gate or V74 macro rule has been promoted.

## Why V75 exists

The sequential V71–V74 pattern consumed too many workstation cycles. V75 changes workflow: one consolidated package runs several predeclared stock-selection challengers, explanatory diagnostics, optional macro PIT and deep backtest in parallel.

The primary unresolved model issue is not PNJ or a single bad stock. Observed 2026 showed a cross-sectional selection failure: medium-horizon C3 momentum reacted slowly, missed some emerging winners and at times entered stale momentum after the move. 2026 is already observed and is therefore stress/shadow only.

## V74 status entering V75

Standalone V74 did not produce macro P&L. Workstation collection obtained CPI=111 first-release months and IIP=59, below V74's 80-month strict gate. This is a coverage/collector limitation, not a macro model conclusion. V75 must not spend another standalone workstation cycle on collector-only debugging. Macro is optional and must not block stock-selection lanes.

## V75 invariant

- frozen V67 ranking/score is comparator truth;
- training label remains close(T)->close(T+20), benchmark-relative;
- execution remains next-open;
- selection cutoff remains 2025-12-31;
- deep backtest and profit-first reporting are mandatory;
- no live/promotion authorization from historical results;
- PIT HOSE/price-basis/corporate-action/sector blockers remain active.
