# V73 workstation result — 2026-08-14

Observed workstation artifact from `agent/v73-c3-factor-health-regime` at HEAD `25a29ebf500338d3b0ec8115f35157b688757c57`.

Store SHA256: `2959f8cce0c11e8e4186fcb49ae75bf7babf86b84afe64ca3b843a7470d58b1a`.
Canonical workstation Python: `vn_quant_local_system/.venv/Scripts/python.exe`, Python 3.12.13.

## Structural status

- run status: `SUCCESS`;
- frozen champion remains `C3_STABLE_3_PAST_IC_SHRUNK`;
- baseline reconstruction: 24 summaries, max total-return/CAGR/MDD error = `0.0`;
- candidate inference stops `2025-12-31`; 2026 is observed shadow only;
- factor-health source is V67 monthly component IC with `label_end < current signal_day`;
- no adaptive weight, weekly overlay, macro or ML integration;
- diagnostic watchlist count = `0`;
- no promotion/live authorization.

## BASE_DNSE deep-backtest P&L — 1bn VND, immediate settlement sensitivity

Same-calendar VNINDEX total return: `+124.5317%`.

### GAP18_CLEAN equal-weight

| policy | total return | CAGR | daily MDD |
|---|---:|---:|---:|
| NO_FACTOR_HEALTH_GATE | +372.5536% | 18.6432% | -38.1011% |
| FH_RS3_SOFT50 | +304.5946% | 16.6327% | -33.0295% |
| FH_MOM3_AVG_SOFT50 | +241.6519% | 14.4818% | -33.1194% |
| FH_MOM6_AVG_SOFT50 | +329.0298% | 17.3880% | -34.2738% |

### GAP18_CLEAN inverse-vol60

| policy | total return | CAGR | daily MDD |
|---|---:|---:|---:|
| NO_FACTOR_HEALTH_GATE | +332.9436% | 17.5054% | -35.8503% |
| FH_RS3_SOFT50 | +281.3553% | 15.8757% | -33.4372% |
| FH_MOM3_AVG_SOFT50 | +224.1014% | 13.8191% | -33.5264% |
| FH_MOM6_AVG_SOFT50 | +296.8037% | 16.3833% | -34.5493% |

The exposure gates improve drawdown, but the long-run opportunity cost is large enough that full-history wealth falls materially for all GAP18 candidates.

## Pre-2026 paired inference

Each scope uses 101 paired months / 51 contiguous two-calendar-month blocks. No candidate passes the watchlist gate.

Representative GAP18 results:

- Equal FH_RS3_SOFT50: mean monthly delta `-0.3046pp`, sign-flip `p≈0.1049`, q≈0.1573, bootstrap CI lower negative, only 2/9 years positive versus baseline; pre-2026 MDD improves about `5.07pp`.
- Equal FH_MOM3_AVG_SOFT50: mean monthly delta `-0.3410pp`, p≈0.0641, q≈0.1573; MDD improves about `4.98pp`, but annual return delta is materially negative.
- Equal FH_MOM6_AVG_SOFT50: mean monthly delta `-0.1374pp`, p≈0.4700, q≈0.4700; MDD improves about `3.83pp` but return evidence is still negative.
- INVOL60 variants show the same qualitative tradeoff: lower drawdown, lower long-run return, no passing inference.

The gates activate frequently before 2026 (roughly 29% of monthly signals for RS3/MOM6 and 38% for MOM3 in GAP18), explaining the large opportunity cost.

## 2026 observed shadow

VNINDEX over the observed slice: `+2.7122%`.

### GAP18 equal-weight

- frozen/no gate: `-12.3799%`;
- FH_RS3_SOFT50: `-2.0649%` (`+10.3150pp` versus frozen);
- FH_MOM3_AVG_SOFT50: `-14.1454%` (`-1.7654pp`);
- FH_MOM6_AVG_SOFT50: `-12.5313%` (`-0.1513pp`).

### GAP18 inverse-vol60

- frozen/no gate: `-10.7358%`;
- FH_RS3_SOFT50: `-1.3336%` (`+9.4022pp`);
- FH_MOM3_AVG_SOFT50: `-11.9411%` (`-1.2053pp`);
- FH_MOM6_AVG_SOFT50: `-10.7399%` (approximately flat versus frozen).

At the April-2026 failure interval, RS3 improves GAP18 Equal by about `+5.57pp` and GAP18 INVOL60 by about `+4.96pp`.

Mechanism: by the 2026-03-31 signal the latest three completed `relative_strength_120` IC observations have a mean around `-0.1106`, so RS3 is already active for the next-open April portfolio. The two-factor momentum average remains slightly positive (~`+0.0007`) because `high_52_week` IC stays positive, so MOM3 does not activate and misses the April protection.

## Annual tradeoff — GAP18 Equal

Frozen versus RS3 illustrates why the 2026 improvement cannot select the gate retrospectively:

- 2018: frozen `-2.13%`, RS3 `+1.06%`;
- 2020: frozen `+26.80%`, RS3 `+14.01%`;
- 2021: frozen `+114.76%`, RS3 `+93.21%`;
- 2022: frozen `-30.17%`, RS3 `-23.59%`;
- 2023: frozen `+12.65%`, RS3 `+1.71%`;
- 2025: frozen `+49.16%`, RS3 `+44.48%`;
- 2026 shadow: frozen `-12.38%`, RS3 `-2.06%`.

RS3 is therefore a useful **diagnostic of factor-regime failure**, not a historically justified permanent exposure policy.

## Research decision

1. keep frozen expanding C3 as champion;
2. do not promote any V73 factor-health gate;
3. do not tune IC windows (2/4/5/9 months), sign thresholds or 30/70% exposure using 2026;
4. preserve the fact that short-horizon RS120 IC deterioration was observable before the April-2026 loss and is a useful explanatory feature;
5. next research lane should be an independent publication-date point-in-time macro ablation rather than more endogenous threshold search;
6. start macro with a small auditable official-data set and explicit release dates; do not backfill monthly values before publication;
7. retain V70 deep backtest and profit-first reporting in every future package.

Historical results remain research-only. PIT HOSE, price-basis/corporate-action and PIT-sector data gates still block canonical/live claims.