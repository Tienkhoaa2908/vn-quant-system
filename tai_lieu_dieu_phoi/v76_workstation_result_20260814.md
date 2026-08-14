# V76 workstation result — 2026-08-14

Observed workstation artifact from `agent/v76-learned-ranking-challenger-lab` at HEAD `9ba5998992181c4c39a156d3208d9d25d66c422c`.

Store SHA256: `2959f8cce0c11e8e4186fcb49ae75bf7babf86b84afe64ca3b843a7470d58b1a`.
Canonical workstation Python: `vn_quant_local_system/.venv/Scripts/python.exe`, Python 3.12.13, scikit-learn 1.9.0.
Verified V75 V68/V70 reference was reused from `/d/VNQuant/vn-quant-system/artifacts/v75-consolidated-selection-20260814-164438` with matching store SHA.

## Structural status

- V76 status `SUCCESS`;
- frozen champion remains `C3_STABLE_3_PAST_IC_SHRUNK`;
- V70 baseline reconstruction total return/CAGR/MDD errors = exactly `0.0`;
- deep backtest completed;
- trainable panel is separate from portfolio eligibility;
- primary selection cutoff = `2025-12-31`;
- 2026 portfolio outcomes are shadow/stress only;
- candidate inference count = 24;
- diagnostic watchlist count = 0;
- robust progression model count = 0;
- no promotion/live/canonical-HOSE authorization.

## Profit-first — BASE_DNSE, 1bn VND, immediate settlement

Same-calendar VNINDEX total return remains about `+124.53%` over the full V70/V76 calendar.

### GAP18_CLEAN Equal

| policy | full-history total return | CAGR | daily MDD |
|---|---:|---:|---:|
| frozen C3 | +372.55% | 18.64% | -38.10% |
| V76_RIDGE_RANK | +305.88% | 16.67% | -45.41% |
| V76_LOGIT_BOTTOM20_SAFE | +169.06% | 11.51% | -35.68% |
| V76_HGB_CONTEXT | +149.32% | 10.58% | -40.06% |
| V76_RIDGE_CONTEXT | +97.81% | 7.80% | -56.00% |

### GAP18_CLEAN INVOL60

| policy | full-history total return | CAGR | daily MDD |
|---|---:|---:|---:|
| frozen C3 | +332.94% | 17.51% | -35.85% |
| V76_RIDGE_RANK | +328.60% | 17.38% | -37.49% |
| V76_LOGIT_BOTTOM20_SAFE | +156.69% | 10.93% | -32.19% |
| V76_HGB_CONTEXT | +154.80% | 10.84% | -36.56% |
| V76_RIDGE_CONTEXT | +125.42% | 9.36% | -52.06% |

BROAD is the only universe where Ridge rank has higher full-history wealth than frozen C3: about `+392.06%` Equal / `+406.76%` INVOL versus frozen `+336.09%` / `+313.43%`. This does not survive GAP18/SEAM or pre-2026 inference and cannot support progression.

## Pre-2026 compounded P&L

Using all BASE monthly periods ending on or before 2025-12-31:

- GAP18 Equal frozen C3: approximately `+439.32%`;
- GAP18 Equal Ridge rank: approximately `+282.35%`;
- GAP18 INVOL frozen C3: approximately `+385.01%`;
- GAP18 INVOL Ridge rank: approximately `+308.78%`.

Thus Ridge rank's excellent 2026 stress behavior does not reverse the fact that it lagged the frozen champion materially on the admissible pre-2026 selection history.

## Pre-2026 inference

Every challenger has 98 paired months / 49 two-calendar-month blocks. Zero of 24 tests passes the diagnostic watchlist gate.

Representative GAP18 results:

- Ridge rank Equal: mean monthly delta `-0.2909pp`, sign-flip `p≈0.507`, q≈0.507, bootstrap CI about `[-1.1817pp, +0.5307pp]`, positive annual delta rate `3/9`, pre-2026 MDD worsens by about `7.31pp`;
- Ridge rank INVOL: mean monthly delta `-0.1191pp`, `p≈0.787`, CI crosses zero, annual improvement only `3/9`;
- Logistic bottom20 Equal: mean delta `-0.7115pp`, p≈0.0457 but in the wrong direction, q≈0.183; it reduces drawdown but sacrifices return;
- HGB and Ridge-context have negative mean deltas and no robust evidence.

No learned challenger may replace C3.

## Rank IC

Pre-2026 GAP18 mean monthly rank IC:

- frozen C3: `0.0573`;
- Ridge rank: `0.0358`;
- HGB context: `0.0266`;
- Logistic bottom20 safe: `0.0054`;
- Ridge context: `-0.0058`.

The frozen C3 remains the strongest ranking signal on the admissible historical sample.

## Winner capture / loser contamination

Pre-2026 GAP18:

- frozen winner Top10 capture ≈ `34.04%`, loser contamination ≈ `11.11%`;
- Ridge rank capture ≈ `32.42%`, contamination ≈ `11.21%`;
- HGB capture ≈ `31.11%`, contamination ≈ `13.03%`;
- Ridge-context capture ≈ `30.81%`, contamination ≈ `13.33%`;
- Logistic capture ≈ `28.18%`, contamination ≈ `8.89%`.

Logistic does avoid losers better but misses too many winners and materially lowers portfolio return. None solves the winner-capture problem robustly.

## 2026 stress/shadow

GAP18 Equal:

- frozen C3: `-12.38%`;
- Ridge rank: `+6.15%`;
- Logistic bottom20 safe: `-3.44%`;
- Ridge context: `-12.67%`;
- HGB context: `-22.86%`;
- VNINDEX: about `+2.71%`.

GAP18 Ridge rank therefore beats frozen by about `+18.53pp` and beats VNINDEX by about `+3.44pp` in the observed 2026 slice. April-2026 Ridge rank returns about `+5.40%` versus frozen `-11.00%`, an improvement of about `+16.40pp`.

This is a valuable mechanism clue only. 2026 was excluded from candidate selection, and pre-2026 evidence does not support promotion.

## Direct focus ranking on 2026-03-31 — GAP18

- VIC: frozen `#33`, Ridge rank `#3`, Ridge-context `#12`, HGB `#42`, Logistic `#29`;
- NVL: frozen `#52`, Ridge rank `#36`, Ridge-context `#44`, HGB `#5`, Logistic `#53`;
- TLG: frozen `#23`, Ridge rank `#4`, HGB `#4`, Logistic `#1`;
- PNJ: frozen `#17`, learned challengers mostly rank it lower;
- VPI: frozen `#8`, Ridge rank `#19`.

So learned models can detect some emerging leaders in the exact 2026 failure month, but the mechanisms are unstable across names and historical regimes. HGB captures NVL/TLG but has very poor 2026 GAP18 portfolio P&L; Ridge captures VIC/TLG and works in 2026, but historically sacrifices winner capture and compounded wealth.

## Cost / settlement sensitivity

GAP18 Equal Ridge rank:

- GROSS `+392.40%`;
- BASE `+305.88%`;
- STRESS `+275.48%`;
- SEVERE `+222.35%`;
- BASE T+2/no-advance only `+131.61%`.

Frozen GAP18 Equal:

- GROSS `+436.92%`;
- BASE `+372.55%`;
- STRESS `+348.57%`;
- SEVERE `+305.30%`;
- BASE T+2/no-advance `+265.96%`.

Ridge rank trades more and pays materially larger execution drag. At 1bn GAP18 Equal, modeled cost/slippage is about 525m VND versus 367m for frozen. T+2 hurts Ridge especially strongly. This is another reason not to progress it from historical evidence.

## Training coverage

The anti-regression objective succeeded:

- BROAD: 121 symbols, 12,131 label-complete trainable rows, of which 6,838 are outside recorded portfolio-eligible overlap;
- GAP18: 111 symbols, 11,399 label-complete trainable rows, 6,370 outside portfolio-eligible overlap;
- SEAM: 120 symbols, 12,045 label-complete trainable rows, 6,795 outside portfolio-eligible overlap.

Portfolio eligibility was not used as the training filter.

## Research decision / stop rule

1. Keep `C3_STABLE_3_PAST_IC_SHRUNK` as champion.
2. Do not promote Ridge, HGB, Logistic, or any V76 learned challenger.
3. Preserve Ridge rank's 2026 behavior as a shadow mechanism clue: it successfully catches VIC/TLG and turns 2026 GAP18 positive, but it does not have admissible pre-2026 evidence.
4. Stop historical architecture/factor/threshold fishing on the same repeatedly inspected sample. Do not open V77 merely to try XGBoost/LightGBM or another hyperparameter grid.
5. Shift primary effort to fresh paper OOS collection plus data-gate closure: PIT HOSE membership, price-basis/corporate-action reconstruction, and PIT sector master.
6. Keep frozen C3 as paper champion. Learned challengers may be logged in shadow without capital authorization so future genuinely unseen observations can test whether the 2026 behavior persists.
7. Any future model architecture expansion requires either fresh OOS evidence or a materially improved truth dataset, not another retrospective fit to the same V67/V68 history.

Historical V76 results remain research-only; PIT HOSE membership and price-basis/corporate-action gates are still unresolved.