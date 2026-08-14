# V76 learned-ranking challenger contract

## Why V76 exists

V75 showed that fixed manual blends can reduce 2026 damage but do not robustly improve pre-2026 winner capture or portfolio P&L. Zero V75 candidates passed the pre-2026 watchlist gate. Therefore V76 stops adding hand-picked blend fractions/thresholds and moves to a learned cross-sectional ranking challenger lab.

Frozen champion remains `C3_STABLE_3_PAST_IC_SHRUNK`.

## Comparator truth

- exact V67 recorded ranking/score is the frozen comparator;
- C3 training label remains `close(T) -> close(T+20)` benchmark-relative;
- tradable execution remains earliest next-session open;
- baseline deep backtest must reconstruct V70 within `1e-10` for total return/CAGR/MDD;
- no V76 result may silently replace C3.

## Training population separation

This is a critical V76 change.

Model-trainable history is built from **all feature-complete symbols in each V68 sensitivity universe**, not only symbols that pass C3 portfolio eligibility at that month.

Portfolio eligibility remains frozen V67/C3 eligibility and is applied only at prediction/execution time.

This prevents the learner from being trained only on names that C3 already selected as eligible and makes it possible to learn from future leaders/losers before they enter the portfolio set.

Universe remains diagnostic because PIT HOSE and price-basis gates are unresolved:

- BROAD_PROVISIONAL: all local stock symbols;
- SEAM_CLEAN: broad minus provenance seam candidates;
- GAP18_CLEAN: broad minus symbols with >=18% consecutive-session gaps;
- any unknown/strict variant falls back explicitly to observed variant symbols and records that fallback.

## Feature panel

Monthly cross-sectional percentile features:

1. low volatility 60;
2. relative strength 120;
3. high-52-week position;
4. relative return 20;
5. relative return 10;
6. relative return 5;
7. momentum acceleration;
8. fresh breakout-20 gap;
9. distance MA20;
10. distance MA50;
11. drawdown20;
12. drawdown60;
13. log volume 5/20 confirmation;
14. short-vs-long volatility stability.

Target is monthly cross-sectional percentile of the original C3 close(T)->close(T+20) benchmark-relative label.

## Causal factor-health context

V73 showed recent RS120 IC deterioration is informative but hard soft-50 gating destroys long-run return. V76 therefore uses recent factor health only as a **model interaction/context**, never as a hard exposure rule.

For each signal day, only component-IC observations whose label_end is strictly before that signal may enter the recent 3-month context.

## Challengers

All run in the same package:

- `V76_RIDGE_RANK`: regularized linear cross-sectional rank prediction;
- `V76_RIDGE_CONTEXT`: Ridge plus market-regime and recent RS/high52 IC interactions;
- `V76_HGB_CONTEXT`: nonlinear HistGradientBoosting rank regressor with causal context;
- `V76_LOGIT_BOTTOM20_SAFE`: logistic probability of avoiding the future bottom 20% cross-sectional tail.

Ridge alpha grid is `(1, 10, 100)`. Logistic C grid is `(0.1, 1, 10)`. HGB l2 grid is `(1, 10)` with fixed structural parameters. Hyperparameters are selected only on the latest prior 3 completed validation months, then the selected model is refit on all safe prior rows. No test label is used.

## Walk-forward

For test month T:

- training/validation rows must have `signal_day < T` and `label_end < T`;
- latest 3 safe signal months are validation;
- validation training itself only sees labels completed before the first validation month;
- minimum 12 earlier training months;
- early months without enough history fall back exactly to frozen C3 and are excluded from candidate inference until the model is genuinely fitted.

Model fitting during 2026 may causally consume labels that have already completed during 2026 because that is how a predeclared online learner would operate. **2026 portfolio outcomes remain excluded from research candidate selection.**

## Candidate selection cutoff

Primary research inference ends `2025-12-31`.

2026 is stress/shadow only. It can answer whether the already-defined online learning protocol handles the observed regime better, but it cannot select a model, feature, threshold, hyperparameter grid, or research direction retrospectively.

## Diagnostics

Every challenger receives:

- monthly rank IC;
- future-winner Top10 capture;
- future-loser Top10 contamination;
- focus rank audit for VIC/NVL/PNJ/VPI/TLG around March-April 2026;
- paired pre-2026 return inference using the V75 two-calendar-month sign-flip + block bootstrap + BH-FDR protocol;
- 2026 shadow separated from inference.

A stronger progression flag requires P&L evidence across at least two sensitivity universes plus positive GAP18 winner-capture delta without worse loser contamination. This is still only research progression, not promotion.

## Deep backtest

Every model runs the unchanged V70 mechanics:

- Equal and INVOL60;
- next-session open;
- actual shares;
- lot 100;
- max 15% per symbol;
- cash ledger;
- GROSS / BASE_DNSE / STRESS / SEVERE;
- T+2 no-advance sensitivity;
- 100m / 1bn / 10bn capital sensitivity;
- daily NAV and drawdown;
- annual and rolling alpha;
- turnover, ADV/capacity, missing-price diagnostics;
- profit-first output.

## Workstation acceleration

V76 runner may reuse an existing successful V75 V68/V70 reference only when:

- the old V75 bundle is present locally;
- its recorded market-store SHA256 equals the current store SHA256;
- V68 and V70 reports are SUCCESS;
- both report the frozen C3 champion;
- V70 says deep backtest completed.

If any check fails, V76 rebuilds V68 and V70. This turns expensive unchanged baseline work into a verified cache rather than rerunning it blindly.

The V76 upload bundle contains V76 outputs plus compact V68/V70 reference reports instead of duplicating all large historical intermediate files.

## Stop rule

If no learned challenger produces robust pre-2026 portfolio improvement and better winner/loser selection, do not continue historical model fishing with more architectures/thresholds. Shift primary effort to:

1. fresh paper OOS collection;
2. PIT HOSE membership lineage;
3. price-basis/corporate-action reconstruction;
4. PIT sector master;
5. only then consider a narrowly justified next challenger such as LightGBM ranking.

No live orders, no automatic promotion, no canonical HOSE claim are authorized by V76.