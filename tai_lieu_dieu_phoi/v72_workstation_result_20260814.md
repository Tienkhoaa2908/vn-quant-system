# V72 workstation result — 2026-08-14

Observed workstation artifact from `agent/v72-weekly-overlay-deep-backtest` at HEAD `3478002dad438a79df04827ac223a34d76b617eb`.

Store SHA256: `2959f8cce0c11e8e4186fcb49ae75bf7babf86b84afe64ca3b843a7470d58b1a`.
Canonical workstation Python: `vn_quant_local_system/.venv/Scripts/python.exe`, Python 3.12.13.

## Structural status

- run status: `SUCCESS`;
- workstation regression tests: 16/16 PASS;
- frozen champion: `C3_STABLE_3_PAST_IC_SHRUNK`, unchanged;
- `NO_OVERLAY` reconstructs V70 exactly: max total-return/CAGR/MDD error = `0.0` across 24 comparator summaries;
- weekly signal forms after close and executes at next market open;
- monthly C3 rebalance has precedence on collision;
- candidate inference ends `2025-12-31`; 2026 is shadow only;
- policies are standalone; adaptive weights and macro are not combined;
- PIT HOSE, price-basis/corporate-action and PIT-sector gates remain unresolved for canonical claims;
- no promotion or live authorization.

## BASE_DNSE P&L — 1bn VND, immediate settlement sensitivity

Same-calendar VNINDEX total return: `+124.5317%`.

### GAP18_CLEAN

| allocator / policy | total return | CAGR | daily max DD | delta total return vs NO_OVERLAY | delta CAGR | MDD improvement |
|---|---:|---:|---:|---:|---:|---:|
| Equal NO_OVERLAY | +372.5536% | 18.6432% | -38.1011% | — | — | — |
| Equal L15 swap50 | +406.7526% | 19.5593% | -36.3894% | +34.1990pp | +0.9161pp | +1.7117pp |
| Equal R07 trim50 | +342.3437% | 17.7836% | -37.0156% | -30.2099pp | -0.8597pp | +1.0855pp |
| Equal R08 trim50 | +402.8526% | 19.4577% | -36.6017% | +30.2990pp | +0.8144pp | +1.4994pp |
| INVOL60 NO_OVERLAY | +332.9436% | 17.5054% | -35.8503% | — | — | — |
| INVOL60 L15 swap50 | +356.0247% | 18.1791% | -35.1761% | +23.0811pp | +0.6738pp | +0.6742pp |
| INVOL60 R07 trim50 | +298.5716% | 16.4403% | -35.7439% | -34.3720pp | -1.0651pp | +0.1065pp |
| INVOL60 R08 trim50 | +349.7790% | 17.9999% | -34.9726% | +16.8354pp | +0.4945pp | +0.8778pp |

Directional full-history improvement is **not** enough for selection. Pre-2026 paired inference remains the gate.

## Cost stress

Across the six universe × allocator scopes, L15 and R08 keep positive average total-return deltas under every modeled-cost level. Mean deltas versus NO_OVERLAY:

| policy | GROSS | BASE_DNSE | STRESS | SEVERE |
|---|---:|---:|---:|---:|
| L15 swap50 | +42.26pp | +35.40pp | +32.44pp | +28.17pp |
| R08 trim50 | +36.17pp | +29.46pp | +27.44pp | +23.12pp |
| R07 trim50 | -12.94pp | -15.84pp | -17.17pp | -19.01pp |

The extra weekly turnover therefore does not explain away L15/R08 directional gains; R07 degrades as costs rise.

## Pre-2026 paired inference

Each policy scope has 101 paired months / 51 contiguous two-month blocks.

**No policy passes the return watchlist gate in any of 18 policy × universe × allocator tests.**

Representative results:

- GAP18 Equal L15: mean monthly delta `+0.0602pp`, sign-flip `p≈0.213`, q≈0.639, bootstrap lower bound negative, 6/9 positive annual deltas;
- GAP18 Equal R08: mean monthly delta `+0.0599pp`, p≈0.478, q≈0.689, bootstrap lower negative;
- SEAM Equal L15 is statistically closest: mean monthly delta `+0.1143pp`, p≈0.0607, q≈0.1821, bootstrap lower just positive, 6/9 positive annual deltas; still fails BH-FDR q<0.10;
- R07 mean monthly delta is negative in BROAD/GAP18 and does not pass return gate.

Two SEAM Equal risk policies pass only the **diagnostic risk-efficiency** gate because they improve MDD/tail metrics with bounded pre-2026 CAGR loss; this is not a return/promotion gate and is not robust across sensitivity universes.

Conclusion: no standalone weekly overlay is historically strong enough to promote from V72.

## 2026 observed shadow

VNINDEX: `+2.7122%` over the V70/V72 observed 2026 slice.

GAP18 Equal:

- NO_OVERLAY: `-12.3799%`;
- L15 swap50: `-11.3491%` (`+1.0309pp` vs frozen);
- R07 trim50: `-16.3691%` (`-3.9891pp` vs frozen);
- R08 trim50: `-13.9205%` (`-1.5406pp` vs frozen).

GAP18 INVOL60:

- NO_OVERLAY: `-10.7358%`;
- L15 swap50: `-9.5144%` (`+1.2214pp`);
- R07 trim50: `-15.2403%` (`-4.5045pp`);
- R08 trim50: `-12.5126%` (`-1.7768pp`).

During the April-2026 failure interval, risk trims did reduce damage:

- GAP18 Equal R07 improved April by about `+2.13pp`;
- GAP18 Equal R08 improved April by about `+1.68pp`.

But both hurt the full 2026 slice, demonstrating rebound/false-exit cost. L15 improves the full 2026 slice modestly but does not fix the April cross-sectional factor failure.

## Turnover and capacity

Representative GAP18 Equal BASE action counts:

- L15: 86 weekly swaps, 1,731 total trades;
- R07: 359 trims, 1,887 total trades;
- R08: 217 trims, 1,747 total trades;
- NO_OVERLAY: 1,523 total trades.

At 1bn VND, max observed ADV20 participation remains around 8–13% depending on policy/scope. At 10bn VND the existing capacity caveat remains: fixed-slippage P&L is diagnostic, not executable.

T+2 no-advance sensitivity preserves the same broad ranking of policies: L15/R08 remain directionally helpful and R07 harmful, but settlement friction materially lowers absolute ending wealth as already established in V70.

## Research decision

1. keep frozen expanding C3 as champion;
2. do not promote or combine R07/R08/L15 from V72;
3. preserve L15 as the strongest directional opportunity clue and R08 as a directional protection clue, but only for future paper/fresh-holdout observation unless new independent evidence appears;
4. do not tune trim/swap fractions or cohort thresholds from V72/2026;
5. next low-structural-risk research lane should test a **C3 factor-health regime gate** using only completed historical IC observations before each monthly signal, with 2026 excluded from selection;
6. if factor-health gating also fails pre-2026, then open a publication-date point-in-time macro ablation (NSO/SBV) rather than continuing threshold search;
7. every subsequent work package must retain deep backtest and profit-first reporting.

Historical results remain research-only and cannot authorize live capital.
