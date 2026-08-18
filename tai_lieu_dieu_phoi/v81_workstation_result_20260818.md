# V81 workstation result — 2026-08-18

## Status

`SUCCESS` — uploaded V81 historical frozen-policy audit completed on the expected branch/head and preserved all forward-paper state.

This is post-selection descriptive evidence only. It does not reopen threshold/model/policy search and does not authorize promotion/live orders.

## Provenance and integrity

- branch: `agent/v81-frozen-tactical-historical-audit`
- artifact HEAD: `f72e3f5aa1711822986e3695d4cb687a64bbae3b`
- ZIP SHA256: `763bc7d0bbbb5e5749ad6395c5ef38a0b9c806712f6779ba961ee2e90ff8a155`
- store last day: `2026-08-17`
- store rows: `300781`
- logical bars SHA before/after: `fc5e9c44099afed3ae6d78558939716c56a600a12e92005ec0308faf89374cd1`
- physical SQLite SHA before/after: `b309fdd424dbba39794b9114cbce18b66b8cc3db21a7b732fc2039463491193c`
- V77 digest before/after: `f7f961a202d386815efad18e11d01713ad5eddc2d68297c06bca468b8d85fdc8`
- V80 digest before/after: `26caab5d72d68a13c98260d91a056c05310c9090f845694e7046f04daf516099`
- V70 baseline reconstruction max return/CAGR/MDD error: `0.0`

## Primary profit reference — GAP18_CLEAN / EQUAL / BASE_DNSE / 1bn / immediate

Initial capital is 1,000,000,000 VND.

### NO_OVERLAY frozen C3

- ending NAV: `4,813,925,734 VND`
- net profit: `3,813,925,734 VND`
- total return: `+381.39%`
- CAGR: `18.89%`
- max drawdown: `-37.46%`
- modeled cost/slippage: `371,552,197 VND`

### L15_SWAP25_WORST

- ending NAV: `4,967,695,142 VND`
- net profit: `3,967,695,142 VND`
- total return: `+396.77%`
- CAGR: `19.30%`
- max drawdown: `-36.61%`
- executed overlay actions: `87`
- modeled cost/slippage: `384,162,620 VND`
- incremental ending NAV vs frozen C3: `+153,769,408 VND`
- total-return uplift vs frozen C3: `+15.38pp`
- CAGR uplift: `+0.41pp/year`
- MDD improvement: `+0.85pp`
- extra modeled cost vs frozen C3: about `12.61m VND`

### L15_SWAP50_WORST

- ending NAV: `5,150,706,025 VND`
- net profit: `4,150,706,025 VND`
- total return: `+415.07%`
- CAGR: `19.77%`
- max drawdown: `-36.27%`
- executed overlay actions: `87`
- modeled cost/slippage: `399,231,380 VND`
- incremental ending NAV vs frozen C3: `+336,780,290 VND`
- total-return uplift vs frozen C3: `+33.68pp`
- CAGR uplift: `+0.89pp/year`
- MDD improvement: `+1.19pp`
- extra modeled cost vs frozen C3: about `27.68m VND`

### L15_CASH_ADD25_SLOT

- ending NAV: `4,832,458,763 VND`
- net profit: `3,832,458,763 VND`
- total return: `+383.25%`
- CAGR: `18.94%`
- max drawdown: `-37.42%`
- actions: `49`
- incremental ending NAV vs frozen C3: `+18,533,028 VND`
- total-return uplift: `+1.85pp`
- CAGR uplift: `+0.05pp/year`

## Cross-sensitivity result

At BASE_DNSE / 1bn / immediate, SWAP50 has positive total-return and CAGR uplift in all 3 universe sensitivities and both allocators (6/6). SWAP25 is also positive 6/6 but weaker. CASH_ADD is positive in return 6/6 but economically small and less stable in drawdown.

Examples of SWAP50 total-return uplift vs frozen C3:

- BROAD_PROVISIONAL / EQUAL: `+35.71pp`
- BROAD_PROVISIONAL / INVOL60: `+28.97pp`
- GAP18_CLEAN / EQUAL: `+33.68pp`
- GAP18_CLEAN / INVOL60: `+23.55pp`
- SEAM_CLEAN / EQUAL: `+48.49pp`
- SEAM_CLEAN / INVOL60: `+41.93pp`

## Exact-L15 event frequency

For GAP18_CLEAN:

- pre-2026 raw exact-L15 weeks: `116`
- pre-2026 actionable events after monthly-cycle action semantics: `81`
- active months: `60`
- paired monthly periods: `101`
- no-trigger months: `41`
- unique leaders: `56`
- top leader event share: about `4.94%`

This is not a single-symbol story. Event concentration is low: GAP18/EQUAL SWAP50 has 59 unique leaders over 87 all-history actions; top-1 leader share about 4.6%, top-3 about 12.6%.

## Replacement quality / regret — GAP18_CLEAN / EQUAL / PRE2026

SWAP25 and SWAP50 share the same leader/incumbent event pairs; the difference is capital fraction.

At H5, among 50 uncensored events:

- mean leader-minus-incumbent spread: `+1.84%`
- median spread: `+0.41%`
- replacement win rate: `54%`
- regret rate: `46%`
- leader minus VNINDEX mean: `+2.86%`
- leader beats VNINDEX: `64%`

At H10, among 20 uncensored events:

- mean replacement spread: `+2.34%`
- median: `+4.13%`
- win rate: `55%`
- regret rate: `45%`
- leader minus VNINDEX mean: `+4.21%`
- leader beats VNINDEX: `60%`

At next monthly rebalance, all 81 pre-2026 events are observed:

- mean replacement spread: `+1.51%`
- median: `+0.43%`
- replacement win rate: `55.56%`
- regret rate: `44.44%`
- leader minus VNINDEX mean: `+1.83%`
- leader beats VNINDEX: `53.09%`

H20 has zero strategy-valid uncensored rows because the next monthly C3 rebalance occurs before a full 20-session tactical holding horizon for these weekly events. The monthly-boundary outcome is therefore the economically relevant longer-horizon result under the frozen monthly-precedence contract; V81 must not pretend the tactical position survives beyond that boundary.

## Portfolio-delta concentration — GAP18_CLEAN / EQUAL / PRE2026

SWAP50:

- paired months: `101`
- action periods: `60`
- compounded return delta vs NO_OVERLAY: `+31.00pp`
- mean monthly delta: about `+0.058pp`
- positive monthly-delta rate: `57.43%`
- best month delta: `+2.59pp`
- worst month delta: `-1.37pp`
- largest positive month contributes about `17.49%` of total positive monthly deltas
- top 3 positive months: about `37.53%`
- top 5 positive months: about `48.53%`

The uplift is not produced by one event/month alone, although positive contribution is still moderately concentrated and replacement regret is non-trivial.

SWAP25 pre-2026 compounded return delta is `+13.65pp`, weaker than SWAP50.

## Regime diagnostics — GAP18_CLEAN / EQUAL / SWAP50

Monthly-boundary replacement spread:

- BULL_60D: 32 events, mean spread `+4.03%`, win rate `65.63%`
- BEAR_60D: 15 events, mean spread `+2.65%`, win rate `40%`
- SIDEWAYS_60D: 40 events, mean spread `-0.52%`, win rate `57.5%`

At H10 the small available sample shows BULL strongest (`+6.98%` mean replacement spread), while BEAR is poor (`-11.14%`, only 2 uncensored observations). Regime is diagnostic only and is not used to add a new gate.

## Cost robustness — GAP18_CLEAN / EQUAL

SWAP50 total-return uplift vs matching NO_OVERLAY remains positive under every frozen cost scenario:

- GROSS: `+42.83pp`
- BASE_DNSE: `+33.68pp`
- STRESS: `+30.71pp`
- SEVERE: `+25.09pp`

SWAP25 remains positive from `+19.91pp` gross to `+10.74pp` severe.

CASH_ADD remains only marginally positive: `+5.17pp` gross and `+0.78pp` severe.

## T+2/no-advance robustness — GAP18_CLEAN / EQUAL / BASE_DNSE

- SWAP25 total-return uplift: `+4.71pp`
- SWAP50 total-return uplift: `+17.70pp`
- CASH_ADD total-return uplift: `+1.84pp`

SWAP50 remains the strongest frozen challenger under T+2/no-advance.

## Capital / capacity diagnostics — GAP18_CLEAN / EQUAL / BASE_DNSE

SWAP50 total-return uplift:

- 100m capital: `+35.08pp`, max ADV20 participation about `1.26%`
- 1bn: `+33.68pp`, max participation about `13.40%`
- 10bn: `+34.02pp`, but max participation about `134.38%`; about `30.8%` of trades exceed 5% ADV20 and `18.2%` exceed 10% ADV20.

Thus economics remain positive in the simulator, but 10bn capacity is not execution-realistic for some names. 100m is cleanest; 1bn is mostly feasible but contains a small number of high-participation trades that should be visible operationally.

CASH_ADD behaves poorly as capital scales: at 10bn its uplift is approximately zero and capacity constraints are severe.

## 2026 shadow

2026 is descriptive only. GAP18/EQUAL paired monthly compounded delta through available 2026 history:

- SWAP25: about `+0.57pp`
- SWAP50: about `+1.04pp`
- CASH_ADD: about `-0.10pp`

This is not used to retune or select the frozen policy.

## Decision after V81

1. Keep C3 as champion.
2. Keep V80 forward-paper state unchanged.
3. Treat `L15_SWAP50_WORST` as the primary tactical paper challenger; `SWAP25` remains conservative shadow.
4. Demote `L15_CASH_ADD25_SLOT` to secondary diagnostic shadow because its incremental economics are small and capacity behavior is weak.
5. Do not add bull/bear/sideways gates or alter exact-L15 thresholds from V81 post-selection diagnostics.
6. No additional large historical threshold/model matrix is justified before materially new truth data or fresh forward evidence.
7. Begin additive web integration in parallel so research/profit/paper status can be monitored from the approved local workstation while V80 continues collecting future observations.
