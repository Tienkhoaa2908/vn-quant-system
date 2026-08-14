# V74 handoff — publication-date PIT macro ablation

## Required reading for successor chats

Before designing research after V74, read in this order:

1. `tai_lieu_dieu_phoi/nguyen_tac_du_an.md`;
2. `tai_lieu_dieu_phoi/chuan_nghien_cuu_va_backtest.md`;
3. `tai_lieu_dieu_phoi/anti_regression_c3_hose.md`;
4. `tai_lieu_dieu_phoi/v70_workstation_result_20260814.md`;
5. `tai_lieu_dieu_phoi/v71_workstation_result_20260814.md`;
6. `tai_lieu_dieu_phoi/v72_workstation_result_20260814.md`;
7. `tai_lieu_dieu_phoi/v73_workstation_result_20260814.md`;
8. `tai_lieu_dieu_phoi/v74_research_contract.md`;
9. latest V74 source/tests/runner/workflow and newest workstation V74 artifact.

Repository/artifact newer than this handoff wins if there is a conflict.

## Frozen champion

Champion remains `C3_STABLE_3_PAST_IC_SHRUNK`.

No adaptive weight, weekly overlay, factor-health gate, macro gate or ML challenger has been promoted.

C3 components remain `low_volatility`, `relative_strength_120`, `high_52_week`.
Training label remains close(T)->close(T+20), benchmark-relative.
Execution remains earliest next-session open after the information set is known.

## Durable state before V74

### V70 — deep backtest

Representative GAP18_CLEAN Equal BASE_DNSE frozen C3:

- total return `+372.5536%`;
- CAGR `18.6432%`;
- daily MDD `-38.1011%`;
- same-calendar VNINDEX total return `+124.5317%`.

The C3 long-run edge survives modeled cost stress. 2026 is nevertheless a genuine relative failure, concentrated strongly in April.

### V71 — adaptive IC memory

EWMA-HL24 and rolling60 did not pass pre-2026 matched inference (`0/12`). EWMA greatly reduced observed 2026 losses but that stress result cannot retroactively select the candidate.

### V72 — weekly overlays

`L15_SWAP50_WORST`, `R08_TRIM50_CASH` and `R07_TRIM50_CASH` were converted to actual portfolio actions and deep-backtested. No standalone policy passed the pre-2026 return gate.

L15 and R08 are directional/fresh-holdout clues only. R07 generally damages return. Do not tune weekly thresholds/fractions from these historical results.

### V73 — factor-health regime

Three frozen exposure gates were tested using only completed historical C3 IC observations:

- `FH_RS3_SOFT50`;
- `FH_MOM3_AVG_SOFT50`;
- `FH_MOM6_AVG_SOFT50`.

No candidate passed pre-2026 inference.

Representative GAP18 Equal BASE:

- frozen: `+372.5536%`, CAGR `18.6432%`, MDD `-38.1011%`;
- RS3: `+304.5946%`, CAGR `16.6327%`, MDD `-33.0295%`;
- MOM3: `+241.6519%`, CAGR `14.4818%`, MDD `-33.1194%`;
- MOM6: `+329.0298%`, CAGR `17.3880%`, MDD `-34.2738%`.

RS3 is diagnostically important but not a valid permanent policy. It was already active at the 2026-03-31 signal because latest-three completed RS120 IC mean was about `-0.1106`; it improved GAP18 Equal 2026 from roughly `-12.38%` to `-2.06%` and April by about `+5.57pp`. However pre-2026 it cut exposure too often and materially reduced long-run return. Do not tune IC window/exposure from this result.

## Why V74 exists

Endogenous adaptations have repeatedly shown the same pattern: they can explain or mitigate the already-observed 2026 failure but have not established robust incremental return before 2026.

V74 therefore opens one small independent macro lane rather than continuing threshold search.

It uses only official NSO monthly first-release data:

- CPI YoY;
- IIP YoY.

The essential contract is publication-date point-in-time. A macro value is visible only if the NSO issue date is on or before the C3 signal day. Reference-month values must never be backfilled before their actual release.

## V74 candidate gates

Only:

- `MACRO_IIP3_DECEL_SOFT50`;
- `MACRO_CPI3_ACCEL_SOFT50`;
- `MACRO_STAGFLATION3_SOFT50`.

All use 50% exposure when active. Zero is the only sign boundary. Do not add or tune additional thresholds within V74.

V74 does not change ranking and does not combine V71/V72/V73 mechanisms.

## Statistical and backtest contract

Candidate selection ends `2025-12-31`. 2026 is shadow only.

Matched pre-2026 monthly returns use two-calendar-month sign-flip inference, block-bootstrap CI, BH-FDR and annual sign stability.

Deep backtest reuses V70 actual-share mechanics, all cost scenarios, Equal/INVOL60, T+2, 100m/1bn/10bn, daily equity/MDD and capacity diagnostics.

The no-macro comparator must reproduce V70 within `1e-10`.

## Data/provenance requirements

V74 official collector must preserve per release:

- series;
- reference month;
- actual publication/issue day;
- first-release YoY value;
- NSO source URL;
- response SHA256;
- parser language/snippet.

Coverage fails closed below 80 observations per required series.

The workstation runner may use network only for official public NSO macro metadata/content. It must not mutate the market DB.

## Decision after V74 workstation artifact

1. No macro gate survives pre-2026 inference -> do not tune these gates using 2026. Retain frozen C3 and move toward fresh paper/holdout evidence, data-lineage completion, or a separately predeclared SBV macro family if justified.
2. One macro gate survives robustly across sensitivity universes -> preserve as research/paper candidate; no automatic promotion or combination.
3. Macro only helps 2026 -> treat as stress explanation, not selection evidence.
4. Do not stack V71/V72/V73/V74 mechanisms until each component has independent evidence and a separately frozen integration matrix.

No historical result authorizes live capital.
