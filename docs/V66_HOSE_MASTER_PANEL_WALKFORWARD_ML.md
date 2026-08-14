# V66 — HOSE master panel + purged walk-forward ML

Research-only. V66 changes the research foundation from narrow C3/V22 candidate snapshots to the workstation's accumulated HOSE market store.

## Primary data contract

- primary training source: `vn_quant_local_system/data/market/dnse_ohlcv.sqlite3`;
- target exchange: HOSE only;
- V22 is not a training input;
- weekly observations are rebuilt from the stored daily bars;
- the panel includes liquid and non-long-eligible states so the protection model can learn deterioration after a stock leaves MA250 eligibility;
- opportunity training is restricted to liquid names that satisfy the long eligibility state at the signal date;
- point-in-time exchange membership is mandatory by default.

V66 prefers exchange information stored on each `bars` row. If unavailable, it searches for a symbol/exchange table with dated membership intervals. A static current symbol-to-exchange mapping is detected but rejected by the normal runner because it creates survivorship/migration bias.

## Panel

The master panel is one row per completed weekly close × HOSE symbol after 250 sessions of feature history. It derives roughly forty feature dimensions covering:

- returns and relative strength from 1 to 250 sessions;
- MA10/20/50/100/250 state and MA20 slope;
- drawdown over 20/60/250 sessions;
- realized volatility and volatility acceleration;
- volume and ADV20 liquidity;
- 20-session breakout/breakdown state;
- overnight gap, intraday return and trading range;
- VNINDEX regime;
- cross-sectional HOSE ranks for relative strength, low volatility, drawdown, volume, trend and liquidity.

Forward outcomes begin at the next session open. Targets include 5/10/20-session stock/excess returns and 10-session adverse/favorable excursion.

Two binary research targets are derived per weekly cross-section:

1. `target_opportunity_10`: top 20% next-10-session excess return among currently long-eligible HOSE names;
2. `target_damage_10`: bottom 20% next-10-session excess return among liquid HOSE names, or a forward 10-session adverse excursion of at least 8%.

The continuous outcomes are retained so later ranking/regression work is not locked to these binary labels.

## Model protocol

V66 evaluates two models plus a simple heuristic baseline:

- standardized Logistic Regression;
- `HistGradientBoostingClassifier` as a nonlinear tree benchmark available from the project's pinned scikit-learn dependency;
- a transparent heuristic rank baseline.

The evaluation uses expanding chronological walk-forward folds. For each test year:

- the immediately prior year is internal validation;
- hyperparameters are selected only on that validation year;
- training rows are strictly earlier;
- any row whose forward label overlaps the validation/test boundary is purged using `label_end_20`;
- no random cross-validation is used;
- the test year is never used for fitting or hyperparameter selection.

V66 also runs feature-family ablations for momentum/relative strength, trend, risk, liquidity/volume, market regime and all features. Logistic standardized coefficients are stored by fold to evaluate sign/stability rather than relying on one fit.

## Why LightGBM is not promoted in this step

The project goal still includes LightGBM. V66 deliberately validates the broad HOSE data lineage and walk-forward signal first using the already-pinned scikit-learn stack. Adding/tuning LightGBM before confirming the master panel would confound data-foundation changes with model-complexity changes. If V66's panel and labels pass the workstation audit, the next model study can add LightGBM on exactly this frozen panel contract.

## Outputs

Panel outputs:

- `v66_sqlite_schema.json`
- `v66_panel_report.json`
- `v66_hose_master_panel.csv.gz`
- `v66_weekly_universe_audit.csv`
- `v66_symbol_coverage.csv`

ML outputs:

- `v66_ml_report.json`
- `v66_walkforward_folds.csv`
- `v66_hyperparameter_trials.csv`
- `v66_model_summary.csv`
- `v66_logistic_coefficients.csv`
- `v66_calibration_bins.csv`
- `v66_feature_family_ablations.csv`

No V66 result authorizes live or paper-order policy changes.
