# V71 workstation result — 2026-08-14

Observed workstation artifact from branch `agent/v71-c3-adaptive-weight-ablation` at HEAD `656c5d510d2613cb90e79c52eac25e4e5639db63`.

## Structural status

- artifact status: `SUCCESS`;
- canonical workstation env: `vn_quant_local_system/.venv`;
- frozen champion remains `C3_STABLE_3_PAST_IC_SHRUNK`;
- 2026 was excluded from candidate inference (`year_2026_used_for_candidate_selection=false`);
- frozen V67 ranking/weights/scores reconstructed within tolerance;
- no diagnostic adaptive candidate passed the pre-2026 watchlist gate (`0/12` candidate × universe × allocator tests);
- no promotion/live authorization.

## BASE_DNSE deep-backtest P&L — 1bn VND, immediate settlement sensitivity

Same VNINDEX benchmark total return: `+124.5317%` over the common 109-period calendar.

### BROAD_PROVISIONAL

| allocator / candidate | total return | CAGR | daily max DD |
|---|---:|---:|---:|
| equal frozen C3 | +336.0852% | 17.5989% | -39.7282% |
| equal EWMA-HL24 | +444.7067% | 20.5136% | -41.9107% |
| equal rolling60 | +398.7287% | 19.3494% | -40.8772% |
| inverse-vol frozen C3 | +313.4299% | 16.9104% | -37.8274% |
| inverse-vol EWMA-HL24 | +399.1576% | 19.3607% | -39.9376% |
| inverse-vol rolling60 | +374.2932% | 18.6912% | -38.5014% |

### GAP18_CLEAN

| allocator / candidate | total return | CAGR | daily max DD |
|---|---:|---:|---:|
| equal frozen C3 | +372.5536% | 18.6432% | -38.1011% |
| equal EWMA-HL24 | +411.5656% | 19.6838% | -40.6748% |
| equal rolling60 | +392.3341% | 19.1800% | -39.9583% |
| inverse-vol frozen C3 | +332.9436% | 17.5054% | -35.8503% |
| inverse-vol EWMA-HL24 | +353.5964% | 18.1097% | -39.2795% |
| inverse-vol rolling60 | +364.4547% | 18.4177% | -36.6876% |

The larger full-history ending wealth of adaptive candidates is **not sufficient evidence of improvement** because candidate selection is based only on pre-2026 paired evidence, and no candidate passed that gate.

## Pre-2026 paired inference

Across 101 paired months / 51 contiguous two-month blocks per scope, all 12 tests failed the frozen watchlist gate. Examples:

- BROAD equal EWMA-HL24: mean monthly delta `-0.0032pp`, sign-flip `p≈0.977`, q≈0.977, bootstrap lower bound negative;
- GAP18 equal EWMA-HL24: mean monthly delta `+0.0069pp`, `p≈0.932`, q≈0.932;
- GAP18 inverse-vol rolling60: strongest p among the set, mean delta `+0.0570pp`, `p≈0.179`, q≈0.359, CI lower still negative.

Therefore V71 does **not** justify replacing expanding C3 weight memory.

## 2026 observed shadow — corrected from monthly BASE_DNSE rows

2026 is diagnostic only and was not used to select either candidate.

| universe / allocator | frozen C3 | EWMA-HL24 | rolling60 | VNINDEX |
|---|---:|---:|---:|---:|
| BROAD equal | -23.55% | **-3.50%** | -10.38% | +2.71% |
| BROAD inverse-vol | -18.83% | **-4.95%** | -9.39% | +2.71% |
| SEAM equal | -16.43% | **-0.47%** | -10.63% | +2.71% |
| SEAM inverse-vol | -12.80% | **-3.05%** | -9.82% | +2.71% |
| GAP18 equal | -12.38% | **-5.51%** | -10.09% | +2.71% |
| GAP18 inverse-vol | -10.74% | **-6.75%** | -9.28% | +2.71% |

At the April-2026 interval, GAP18 equal returns were approximately:

- frozen C3: `-11.00%` vs VNINDEX `+9.15%`;
- EWMA-HL24: `-5.66%`;
- rolling60: `-6.66%`.

EWMA-HL24 reduced the observed failure materially, but this is **shadow evidence only** and cannot retroactively make the pre-2026 gate pass.

Mechanically, GAP18 weights at 2026-03-31 shifted from frozen approximately `20.98% low-vol / 39.25% RS120 / 39.77% high52` to EWMA approximately `37.31% / 28.27% / 34.42%`, explaining why the stress behavior changed.

## Reporting defect found in the artifact

`v71_annual_returns.csv` adaptive-candidate annual rows omitted `cost_scenario`, so `_shadow_2026()` filtered them out and `v71_2026_shadow.csv` printed only frozen C3. This is an **output/reporting schema defect**, not a monthly-return or deep-backtest calculation defect. The corrected 2026 values above were recomputed exactly by compounding `BASE_DNSE` rows from `v71_monthly_returns.csv`.

Future V71/V72 code must regression-test that annual rows retain `cost_scenario` and that the 2026 shadow contains frozen + adaptive rows when adaptive candidates are present. Do not require a workstation rerun solely to repair this already-identifiable reporting defect.

## Research decision

- keep expanding `C3_STABLE_3_PAST_IC_SHRUNK` as champion;
- do not promote EWMA/rolling from V71;
- preserve EWMA-HL24 as a stress-mechanism clue only;
- next endogenous research lane should test frozen weekly overlays (`L15_PERSIST_REL`, `R07_DD20_08`, `R08_DD60_12`) as actual portfolio mechanics with deep backtest and pre-2026 inference, while 2026 remains shadow;
- do not stack adaptive weights + weekly overlays in that first portfolio test;
- defer external macro features until endogenous ranking/allocation/overlay attribution is exhausted or clearly insufficient.
