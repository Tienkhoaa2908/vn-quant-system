# V75 workstation result — 2026-08-14

Observed workstation artifact from `agent/v75-consolidated-selection-optimization` at HEAD `e3fa68cb6c16a52cca24a710e4ddb55bf75abf12`.

Store SHA256: `2959f8cce0c11e8e4186fcb49ae75bf7babf86b84afe64ca3b843a7470d58b1a`.
Canonical workstation Python: `vn_quant_local_system/.venv/Scripts/python.exe`, Python 3.12.13.

## Structural status

- run status `SUCCESS`;
- V68 and V70 phases `SUCCESS`;
- frozen champion remains `C3_STABLE_3_PAST_IC_SHRUNK`;
- V70 baseline reconstruction errors for total return/CAGR/MDD are exactly `0.0`;
- deep backtest completed;
- primary candidate selection stops `2025-12-31`;
- 2026 is observed stress/shadow only;
- macro lane is publication-date PIT and late-era diagnostic only;
- candidate watchlist count = `0`;
- no promotion/live authorization.

## Profit-first — BASE_DNSE, 1bn VND, immediate settlement, Equal

Same-calendar VNINDEX total return for the frozen V70 calendar is about `+124.5317%`.

### BROAD_PROVISIONAL

| policy | total return | CAGR | daily MDD |
|---|---:|---:|---:|
| C3_BASELINE | +336.09% | 17.60% | -39.73% |
| C3_FAST_ACCEL_25 | +399.84% | 19.38% | -38.06% |
| C3_AUX_IC36_35 | +343.01% | 17.80% | -40.69% |
| C3_FAST_REL20_25 | +267.47% | 15.40% | -48.76% |
| C3_FRESH_BREAKOUT_25 | +270.89% | 15.52% | -41.31% |
| MACRO_IIP3_DECEL_SOFT50 | +320.49% | 17.13% | -33.05% |

### GAP18_CLEAN

| policy | total return | CAGR | daily MDD |
|---|---:|---:|---:|
| C3_BASELINE | +372.55% | 18.64% | -38.10% |
| C3_FAST_ACCEL_25 | +334.03% | 17.54% | -35.20% |
| C3_AUX_IC36_35 | +326.67% | 17.32% | -41.88% |
| C3_FAST_REL20_25 | +297.65% | 16.41% | -46.21% |
| C3_FRESH_BREAKOUT_25 | +273.74% | 15.62% | -41.90% |
| MACRO_IIP3_DECEL_SOFT50 | +363.12% | 18.38% | -35.11% |

SEAM_CLEAN is the one sensitivity universe where several learned-by-IC/faster blends show higher full-history wealth: baseline about `+304.28%`, AUX about `+360.42%`, FAST_ACCEL about `+348.92%`. This does not survive cross-universe/pre-2026 robustness gates.

## Cost and settlement sensitivity

GAP18 Equal:

- frozen C3: GROSS `+436.92%`, BASE `+372.55%`, STRESS `+348.57%`, SEVERE `+305.30%`;
- FAST_ACCEL: GROSS `+411.83%`, BASE `+334.03%`, STRESS `+306.23%`, SEVERE `+256.87%`;
- IIP macro: GROSS `+419.82%`, BASE `+363.12%`, STRESS `+341.40%`, SEVERE `+301.34%`.

T+2/no-advance GAP18 Equal:

- frozen `+265.96%`, CAGR about `15.35%`;
- FAST_ACCEL `+191.59%`, CAGR about `12.50%`;
- IIP macro `+281.39%`, CAGR about `15.88%`.

At 10bn VND, both baseline and faster ranking variants can exceed 100% ADV20 participation on individual trades; 10bn fixed-slippage P&L is therefore capacity-warning evidence, not executable P&L.

## Pre-2026 inference

V75 evaluates 42 candidate tests across ranking/macro × universe × allocator. **Zero candidates pass the diagnostic watchlist gate.**

Representative ranking results:

- BROAD Equal FAST_ACCEL mean monthly delta approximately `-0.0055bp`, sign-flip `p≈0.986`, CI crosses zero;
- BROAD INVOL FAST_ACCEL approximately `+0.0873pp/month`, `p≈0.771`;
- GAP18 Equal FAST_ACCEL approximately `-0.1172pp/month`, `p≈0.656`;
- GAP18 INVOL FAST_ACCEL approximately `-0.0284pp/month`, `p≈0.912`;
- SEAM variants show small positive FAST_ACCEL/AUX mean deltas but weak p/q values and no robust gate.

Macro IIP/CPI/stagflation soft-50 candidates have negative pre-2026 mean return deltas overall and do not pass.

Therefore no V75 candidate may replace frozen C3 despite attractive full-history or 2026 slices.

## Winner capture / loser avoidance

Pre-2026 GAP18:

- frozen C3 future-winner Top10 capture ≈ `34.04%`, loser contamination ≈ `11.11%`;
- FAST_ACCEL winner capture remains ≈ `34.04%` while loser contamination worsens to ≈ `11.63%`;
- FAST_REL20 winner capture falls to ≈ `33.64%`, contamination ≈ `11.93%`;
- AUX winner capture ≈ `32.93%`, contamination ≈ `10.92%`.

BROAD has the same qualitative result: the handcrafted blends do not materially improve future-winner capture and often increase future-loser contamination.

This is the decisive failure of the fixed-blend approach.

## 2026 observed stress

GAP18 Equal:

- frozen C3 `-12.38%`;
- FAST_ACCEL `-8.71%` (`+3.67pp` versus frozen);
- FAST_REL20 `-8.33%` (`+4.05pp`);
- AUX `-7.65%` (`+4.73pp`);
- IIP soft50 `-4.81%` (`+7.57pp`);
- VNINDEX about `+2.71%`.

GAP18 INVOL:

- frozen `-10.74%`;
- FAST_ACCEL `-7.31%`;
- FAST_REL20 `-6.23%`;
- AUX `-5.99%`;
- IIP soft50 `-4.14%`.

April-2026 GAP18 improvements versus frozen are roughly FAST_ACCEL `+2.60pp`, REL20 `+3.48pp`, BREAKOUT `+4.54pp`, IIP macro `+5.54pp`. These are stress clues only because the corresponding candidates do not have pre-2026 selection evidence.

## Direct stock-selection audit at 2026-03-31

Frozen GAP18 ranks:

- VIC `#33`;
- NVL `#52`.

V75 challengers still fail to bring them close to Top10 before the subsequent strong moves:

- FAST_REL20: NVL ~`#41`, VIC ~`#42`;
- FAST_ACCEL: NVL ~`#41`, VIC ~`#42`;
- FRESH_BREAKOUT: VIC ~`#41`, NVL ~`#44`;
- AUX: VIC ~`#37`, NVL ~`#40`.

Thus V75 does not solve the observed 2026 emerging-leader capture problem.

## Macro coverage

V75 collector obtained about:

- CPI: `111` first-release monthly observations;
- IIP: `59` first-release monthly observations.

V75 lowers the macro lane minimum to 48 only so it can run as a **late-era diagnostic**. It is not 11-year macro evidence. Publication-date PIT remains enforced; macro is not allowed to backfill values before issue day.

## Research decision

1. keep `C3_STABLE_3_PAST_IC_SHRUNK` as champion;
2. do not promote any V75 fixed ranking blend or macro exposure gate;
3. stop tuning manual blend fractions, factor thresholds, IC windows, or 2026-specific rules on the same historical sample;
4. preserve V75 evidence that faster/auxiliary information can reduce 2026 damage but does not improve winner capture robustly pre-2026;
5. next consolidated lane should learn cross-sectional ranking directly from a broader causal feature panel rather than guessing fixed 25/35% blends;
6. learned challengers must use expanding/purged completed labels, separate model-trainable rows from portfolio-eligible rows, compare against exact frozen V67 rankings, and pass the same V70 deep execution backtest;
7. 2026 remains stress/shadow and cannot choose the challenger;
8. if no learned challenger beats C3 robustly pre-2026, stop historical model search and shift effort to fresh paper OOS plus PIT HOSE/price-basis/corporate-action data-gate closure.

PIT HOSE membership, price-basis/corporate-action and PIT-sector gates remain unresolved; historical results remain research-only.