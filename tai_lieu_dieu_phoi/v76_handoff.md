# V76 handoff — learned cross-sectional ranking challenger

## Current branch

`agent/v76-learned-ranking-challenger-lab`

Frozen champion remains `C3_STABLE_3_PAST_IC_SHRUNK`.

V76 exists because V75 showed that fixed manual blends, factor-health gates and simple macro exposure gates can improve selected 2026 stress slices but do not robustly improve pre-2026 portfolio P&L or future-winner capture. V75 had zero watchlist candidates.

Read in this order after a new-chat restore:

1. `tai_lieu_dieu_phoi/chuan_nghien_cuu_va_backtest.md`;
2. `tai_lieu_dieu_phoi/v75_workstation_result_20260814.md`;
3. `tai_lieu_dieu_phoi/v76_learned_ranking_contract.md`;
4. this handoff;
5. `src/he_thong_dinh_luong/learned_ranking_challenger_v76.py`;
6. `tests/test_learned_ranking_challenger_v76.py`;
7. `scripts/run_v76_learned_ranking_gitbash.sh`;
8. `.github/workflows/v76_learned_ranking.yml`.

## V75 decision carried forward

Do not continue tuning manual blend percentages, IC windows, hard factor-health thresholds, or 2026-specific rules.

Durable V75 facts:

- GAP18 frozen Equal BASE: `+372.55%`, CAGR `18.64%`, MDD `-38.10%`;
- FAST_ACCEL / REL20 / AUX reduced 2026 loss but none had robust pre-2026 evidence;
- future-winner capture did not materially improve;
- at 2026-03-31 VIC/NVL remained far below Top10 under all V75 fixed blends;
- macro IIP soft50 reduced 2026 damage but lacked pre-2026 return evidence and had only 59 first-release IIP months;
- zero V75 candidate tests passed the watchlist gate.

## V76 architecture

V76 is not a C3 replacement. It is a challenger laboratory with four learned ranking policies:

- `V76_RIDGE_RANK`;
- `V76_RIDGE_CONTEXT`;
- `V76_HGB_CONTEXT`;
- `V76_LOGIT_BOTTOM20_SAFE`.

The repository pins `scikit-learn==1.9.0`. A workstation can still have a stale canonical `.venv` that predates that dependency. The V76 runner therefore verifies the exact version inside `vn_quant_local_system/.venv` and, only when missing or mismatched, installs the pinned wheel into that same canonical environment before compilation/tests. This is dependency bootstrap only; it does not change model architecture or select a different environment.

Critical anti-regression change: model-trainable history is built from all **feature-complete symbols in the sensitivity universe**, not from the monthly C3-eligible set. Portfolio eligibility is applied only to the monthly prediction/execution candidate set. This prevents the learner from being trained only on stocks the frozen model already liked.

Features are the frozen C3 three plus relative 5/10/20, momentum acceleration, fresh breakout, MA20/MA50 distance, drawdown20/60, volume confirmation and volatility stability. Recent completed RS120/high52 IC and market regime are context/interactions, not hard gates.

## First workstation attempt — dependency bootstrap failure

Observed failure bundle on 2026-08-14:

- branch: `agent/v76-learned-ranking-challenger-lab`;
- HEAD: `47a67cc77835675864bafde68f569a3e65d97f2f`;
- store SHA256: `2959f8cce0c11e8e4186fcb49ae75bf7babf86b84afe64ca3b843a7470d58b1a`;
- failure occurred before compile/regression and before V68/V70 cache resolution;
- canonical Python raised `ModuleNotFoundError: No module named 'sklearn'`;
- `output/v76` contained no research artifacts;
- therefore this attempt produced **no V76 P&L, inference, rank-IC, winner-capture or 2026 research result**.

The runner was corrected to bootstrap exactly `scikit-learn==1.9.0` into the canonical workstation `.venv` when needed, then verify its version before proceeding. The failed attempt must never be interpreted as evidence about any challenger.

## Causality

Target remains the monthly cross-sectional rank of `close(T)->close(T+20)` benchmark-relative return.

For each test month:

- train/validation rows require `signal_day < test_day` and `label_end < test_day`;
- latest three safe prior months are validation;
- training labels for hyperparameter selection must complete before the first validation month;
- minimum 12 earlier training months;
- early insufficient-history periods fall back exactly to frozen C3 and candidate inference starts only after every sensitivity universe can genuinely fit the challenger.

2026 can causally update the already-predeclared online learner using labels that have completed by then, but 2026 portfolio outcomes remain excluded from research model selection.

## Deep backtest and outputs

Every challenger runs through unchanged V70 mechanics: Equal/INVOL60, actual shares, next-open, lot100, 15% symbol cap, GROSS/BASE/STRESS/SEVERE, T+2, 100m/1bn/10bn, daily NAV/MDD, annual/rolling alpha, ADV/capacity and missing-price diagnostics.

Key V76 outputs:

- `v76_training_coverage.csv`;
- `v76_model_fit_history.csv`;
- `v76_candidate_rankings.csv.gz`;
- `v76_rank_ic_monthly.csv` / `v76_rank_ic_summary.csv`;
- `v76_winner_capture_monthly.csv` / `v76_winner_capture_summary.csv`;
- `v76_backtest_summary.csv`;
- `v76_monthly_returns.csv`;
- `v76_annual_returns.csv`;
- `v76_rolling_alpha.csv`;
- `v76_candidate_inference.csv`;
- `v76_2026_shadow.csv`;
- `v76_focus_rank_audit_2026.csv`;
- `v76_capital_sensitivity.csv`;
- `v76_daily_equity_base.csv.gz`;
- `v76_trade_ledger_base.csv.gz`;
- `v76_report.json`.

Every result response must start with P&L and benchmark/alpha before model diagnostics.

## Speed-up contract

The runner first tries to reuse the most recent local V75 V68/V70 outputs. Reuse is allowed only when the old V75 bundle exists locally, the old recorded market-store SHA matches the current store SHA, and both V68/V70 reports are successful frozen-C3 references. Otherwise it rebuilds V68/V70.

This is verified-cache reuse, not blind reuse. It is intended to save most of the repeated baseline runtime.

## Stop rule

If no V76 learned challenger produces robust pre-2026 improvement across at least two sensitivity universes while improving GAP18 winner capture without worse loser contamination, stop historical architecture fishing. The next primary effort becomes:

- fresh paper OOS collection;
- PIT HOSE membership lineage;
- price-basis/corporate-action reconstruction;
- PIT sector master.

Only after those should a narrowly justified LightGBM/ranking challenger be considered.

No historical artifact from V76 authorizes canonical HOSE claims, model promotion, paper/live promotion, or automatic orders.