# V70 handoff — deep backtest research standard

## Source artifact V69 observed on workstation

Artifact branch: `agent/v69-matched-control-block-robustness`.

Observed V69 bundle is structurally valid and includes V68 C3 research, V69 matched-control inference and gross portfolio profit report. It remains provisional because PIT HOSE membership and price-basis/corporate-action lineage are incomplete.

### V69 gross C3 Top10 reference

`BROAD_PROVISIONAL` always-invested gross:

- ending equity: 5.630066x;
- total return: +463.0066%;
- CAGR: 20.9528%;
- max drawdown: -34.7069%.

`GAP18_CLEAN` always-invested gross:

- ending equity: 6.148245x;
- total return: +514.8245%;
- CAGR: 22.1308%;
- max drawdown: -32.7409%.

VNINDEX same gross rebalance calendar:

- ending equity: 2.041676x;
- total return: +104.1676%;
- CAGR: 8.1740%;
- max drawdown: -44.1818%.

V69 profit report skipped 2 historical periods per universe because selected-symbol open prices were missing; V70 must not skip the entire period. Missing target entry must leave cash; missing held exit must hold/log without future substitution.

### 2026 stress result

2026 is already observed and is **not a tuning set**.

Always-invested gross annual result in V69:

- BROAD: -25.5512%;
- SEAM_CLEAN: -18.8913%;
- GAP18_CLEAN: -14.8316%;
- VNINDEX: -2.2967%.

Therefore 2026 is a real relative C3 failure, not merely an absolute-loss year. It must be diagnosed by benchmark alpha and mechanism. Market weakness does not excuse underperformance.

Historically, however, C3 was generally useful in down benchmark months: BROAD mean alpha around +1.56 percentage points across 42 down-market months with about 71% beat rate. This makes 2026 an abnormal stress regime worth attribution, not a reason to discard the entire C3 history.

Worst observed BROAD relative month in 2026 was the April interval at roughly -20 percentage points alpha versus VNINDEX.

### V69 matched-control mechanisms

Opportunity:

- `L15_PERSIST_REL` is the strongest surviving historical opportunity mechanism, especially on GAP18_CLEAN (matched-week delta about +0.80%, sign-flip p about 0.0007, FDR q about 0.0126).
- It does not solve the fastest-emergence case such as TLG 2026-08-13 because L15 requires prior persistence.

Protection:

- R07/R08-type drawdown signals show robust adverse-excursion separation from same-week canonical controls.
- They do **not** yet justify mechanical exits because mean-return evidence is weaker and rebound/opportunity cost remains material.

Do not tune these cohorts in V70. V70 is portfolio/backtest attribution, not threshold redesign.

## V70 objective

V70 freezes C3 and the signal research stack, then adds the mandatory deep portfolio layer:

1. actual-share monthly Top10 backtest;
2. next-session-open execution;
3. lot 100;
4. max 15% per name;
5. equal weight and inverse-vol diagnostics;
6. risk-off exposure 100% / 50% / 0% predeclared policies;
7. GROSS / BASE_DNSE / STRESS / SEVERE costs;
8. conservative T+2 no-advance settlement sensitivity with catch-up buys;
9. cash residual instead of future price substitution;
10. daily NAV/drawdown;
11. annual and rolling alpha;
12. exposure-matched benchmark decomposition;
13. ADV20 participation and cost/turnover diagnostics;
14. capital/lot sensitivity at 100m / 1b / 10b VND;
15. explicit 2026 stress scorecard.

## Macro decision

V70 does **not** add macro factors into C3. First attribute 2026 to selection, exposure, allocation, transaction/cash mechanics and data sensitivity.

Macro can enter a later work package only under the contract in `chuan_nghien_cuu_va_backtest.md`: official source, release-date point-in-time, first release/vintage when possible, conservative publication lag and purged C3-vs-C3+macro ablation using the same deep backtest.

## Mandatory documents for successor chats

Read, in order:

1. `tai_lieu_dieu_phoi/nguyen_tac_du_an.md`;
2. `tai_lieu_dieu_phoi/chuan_nghien_cuu_va_backtest.md`;
3. `tai_lieu_dieu_phoi/anti_regression_c3_hose.md`;
4. `tai_lieu_dieu_phoi/v70_backtest_handoff.md`;
5. newest branch source/tests/runner/CI;
6. newest workstation artifact before coding further.
