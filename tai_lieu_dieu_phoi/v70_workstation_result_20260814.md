# V70 workstation result — 2026-08-14

Observed workstation artifact from `agent/v70-deep-backtest-research-standard` at HEAD `da2517b8430d3a0821dbb00dc68a06f30e5088ec`.

Store SHA256: `2959f8cce0c11e8e4186fcb49ae75bf7babf86b84afe64ca3b843a7470d58b1a`.
Canonical workstation Python: `vn_quant_local_system/.venv/Scripts/python.exe`, Python 3.12.13.

## Structural status

- run status: SUCCESS;
- workstation regression tests: 24/24 PASS;
- champion: `C3_STABLE_3_PAST_IC_SHRUNK`, unchanged;
- completed monthly backtest periods: 109;
- execution: next-session open, actual shares, lot 100, max 15%/symbol;
- costs: GROSS / BASE_DNSE / STRESS / SEVERE;
- deep backtest completed;
- PIT HOSE, price basis/corporate actions and PIT sector master remain open data gates;
- no promotion or live order authorization.

## BASE_DNSE — equal-weight always-invested

Same benchmark calendar for all variants: VNINDEX total return +124.5317%, daily max drawdown -45.2633%.

| Variant | C3 total return | CAGR | Max drawdown | Arithmetic total alpha |
|---|---:|---:|---:|---:|
| BROAD_PROVISIONAL | +336.0852% | 17.5989% | -39.7282% | +211.5535 pp |
| SEAM_CLEAN | +304.2757% | 16.6226% | -41.5526% | +179.7441 pp |
| GAP18_CLEAN | +372.5536% | 18.6432% | -38.1011% | +248.0219 pp |

GAP18_CLEAN is the strongest sensitivity universe but remains diagnostic, not canonical HOSE, because gap filtering is not a corporate-action adjustment and PIT membership is unresolved.

## Cost sensitivity — GAP18_CLEAN equal-weight

- GROSS: +436.9232%, CAGR 20.3228%;
- BASE_DNSE: +372.5536%, CAGR 18.6432%;
- STRESS: +348.5677%, CAGR 17.9649%;
- SEVERE: +305.2959%, CAGR 16.6549%.

Historical C3 edge survives the modeled-cost stress ladder.

## Allocation

GAP18_CLEAN BASE:

- equal-weight always: +372.5536%, CAGR 18.6432%, MDD -38.1011%;
- inverse-vol60 always: +332.9436%, CAGR 17.5054%, MDD -35.8503%;
- equal soft-50 risk-off: +319.3339%, CAGR 17.0930%, MDD -34.1206%;
- inverse-vol soft-50: +295.7822%, CAGR 16.3503%, MDD -34.4831%.

Inverse-vol trades some long-run return for lower drawdown and stronger down-market hit rate. MA250 risk-off exposure changes do not address the 2026 failure because every completed 2026 monthly signal through 2026-06-30 remained `risk_on=true`.

## 2026 observed stress — BASE_DNSE through 2026-08-03

VNINDEX benchmark: +2.7122%.

Equal-weight C3:

- BROAD: -23.5471%, alpha -26.2593 pp;
- SEAM_CLEAN: -16.4285%, alpha -19.1407 pp;
- GAP18_CLEAN: -12.3799%, alpha -15.0921 pp.

Inverse-vol improves the stress outcome:

- BROAD: -18.8279%, alpha -21.5401 pp;
- SEAM_CLEAN: -12.7987%, alpha -15.5109 pp;
- GAP18_CLEAN: -10.7358%, alpha -13.4480 pp.

The majority of residual GAP18 underperformance is concentrated in the period starting 2026-04-01: strategy -10.9977% versus VNINDEX +9.1451%, alpha -20.1428 pp. The 2026-03-31 C3 Top10 had 0/10 positive close-to-close 20-session excess outcomes, mean about -20.0% and median about -21.5%.

This is a cross-sectional factor/regime failure, not a single-name event. Data anomaly filtering materially improves January/July but does not remove the April failure.

## Factor-health finding

At 2026-03-31 the frozen expanding C3 weights were approximately:

- low volatility 23.34%;
- relative strength 120 39.10%;
- high-52-week 37.56%.

Therefore about 76.7% remained in momentum/trend-like components. By that signal, completed January and February relative-strength IC observations were already negative, but expanding all-history IC estimation adapted slowly. This motivates a causal adaptive-weight challenger while keeping the frozen C3 as champion.

2026 is observed and may only be used as a stress/shadow slice, never for threshold/hyperparameter selection.

## Settlement sensitivity

`C3_EQ_ALWAYS_T2_NO_ADVANCE` reduces ending wealth about 22–23% relative to immediate cash reuse across variants and reduces CAGR by roughly 3.2–3.4 percentage points. Treat this as a cash-availability/settlement sensitivity, not signal alpha. Broker-specific exact availability is still required before calling P&L exact.

## Capital/liquidity sensitivity

At 1bn VND, max observed ADV20 participation is roughly 11–12%, while about 1–1.5% of trades exceed 5% ADV20 and roughly 0.2% exceed 10%. At 10bn VND some trades exceed 100% ADV20; fixed-slippage results at that scale are capacity diagnostics only, not executable P&L.

## Next research decision

Open V71 as a post-V70 ablation, not as a C3 replacement:

1. freeze expanding C3 as baseline;
2. test causal recent-IC adaptive C3 weighting using only labels completed before each signal;
3. primary candidate families: exponential IC half-life 24 completed months and rolling 60 completed months;
4. compare equal-weight and inverse-vol allocation;
5. run full GROSS/BASE/STRESS/SEVERE deep backtest, lot/cash/capacity and T+2 diagnostics;
6. candidate inference/gating uses only periods ending before 2026;
7. 2026 remains shadow stress and cannot affect selection;
8. retain V69 L15/R07/R08 as frozen overlay candidates for a later portfolio integration only after standalone adaptive-weight evidence is known;
9. do not add macro yet. If endogenous ranking/allocation/weekly overlays leave a residual stress failure, open a release-date point-in-time macro ablation afterward.
