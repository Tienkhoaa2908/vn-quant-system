# V77 workstation result — first freeze artifact — 2026-08-14

## Status

Observed workstation artifact: **SUCCESS for freeze/target capture and data-lineage audit; no fresh paper P&L yet.**

This artifact MUST NOT be interpreted as one fresh OOS session. It contains zero fills and zero fresh sessions.

During review, a causal execution bug was found before any fill occurred: the capture happened on Vietnam wall date 2026-08-14 after the local trading day, while the local market store still ended at 2026-08-13. The pre-patch replay could later have treated 2026-08-14 open as the next executable open even though that open occurred before the target was actually captured. Because no fill occurred in this artifact, the frozen target/state can be preserved, but all future replay must enforce the wall-clock causal execution floor introduced after this artifact.

## Provenance

- branch: `agent/v77-paper-oos-data-lineage`
- artifact HEAD: `2aa8c143312fc689e90f042e3f1dd892bf22cc6d`
- Python: 3.12.13
- canonical env: `vn_quant_local_system/.venv`
- scikit-learn: 1.9.0
- market-store SHA before: `2959f8cce0c11e8e4186fcb49ae75bf7babf86b84afe64ca3b843a7470d58b1a`
- market-store SHA after: same
- `store_mutated=false`
- workstation regression tests: 10/10 PASS

## Freeze boundary

- freeze market day: `2026-08-13`
- capture market day: `2026-08-13`
- capture wall time UTC: `2026-08-14T12:49:26.379053+00:00`
- capture wall date Vietnam: `2026-08-14`
- source monthly signal day: `2026-07-31`
- month-close override: false
- fixed GAP18 diagnostic symbol count: 111
- source-to-capture calendar lag: 13 days
- champion remains `C3_STABLE_3_PAST_IC_SHRUNK`
- shadow remains `V76_RIDGE_RANK`
- allocator: Equal Top10
- capital/live/promotion authorization: false

The frozen signal CSVs were appended exactly once for both models and are stored in the persistent workstation state under `du_lieu/v77-paper-oos-state/`.

## Paper P&L at first freeze

Both books are correctly still cash-only:

| Model | Status | Signals | Fresh sessions | Fills | Pending orders | NAV | Return | MDD |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| C3 | `PENDING_FIRST_EXECUTION` | 1 | 0 | 0 | 10 | 1,000,000,000 VND | 0.00% | 0.00% |
| Ridge | `PENDING_FIRST_EXECUTION` | 1 | 0 | 0 | 10 | 1,000,000,000 VND | 0.00% | 0.00% |

`shadow_minus_champion_total_return=0` is therefore mechanically uninformative.

## Frozen ranking snapshot

Signal regime: `risk_on=false`.

Eligible names: 18.

C3 weights:

- low volatility: `0.24031440995977327`
- relative strength 120: `0.3678235312634722`
- high 52-week: `0.3918620587767545`

Ridge fit:

- selected alpha: `10.0`
- context interactions: false
- validation mean rank IC: `0.17601752663919726`
- only completed labels: true

### C3 Top10

1. VPI
2. MSB
3. HCM
4. VIC
5. GMD
6. LPB
7. STB
8. BAF
9. DHC
10. ACB

### Ridge Top10

1. BSR
2. VPI
3. GMD
4. BAF
5. LPB
6. NAB
7. BMP
8. ACB
9. MSB
10. VNM

Top10 overlap is 6/10: `VPI, GMD, BAF, LPB, ACB, MSB`.

The four C3-only names are `HCM, VIC, STB, DHC`; the four Ridge-only names are `BSR, NAB, BMP, VNM`. This divergence makes future unseen comparison informative, but no conclusion is allowed before real fresh sessions accrue.

## Data-lineage audit

Store inventory observed:

- bars: 300,541
- stock symbols: 121
- first day: 2015-06-29
- last day: 2026-08-13
- all 300,541 bars have `price_basis=CHUA_XAC_NHAN`
- no exchange column / exchange lineage in `bars`
- basis gap events: 40

Evidence scan found zero candidate JSON files in the searched workstation roots.

All four canonical gates remain closed:

1. `PIT_HOSE_MEMBERSHIP_LINEAGE_INCOMPLETE`
2. `PRICE_BASIS_UNCONFIRMED`
3. `CORPORATE_ACTION_INVENTORY_INCOMPLETE`
4. `PIT_SECTOR_MASTER_INCOMPLETE`

Paper OOS may continue diagnostically, but canonical HOSE claims, research promotion and live authorization remain false.

## Causal execution issue found during artifact review

Observed condition:

- actual target capture wall date in Vietnam: 2026-08-14;
- store latest market day at capture: 2026-08-13;
- old pending orders were anchored to paper signal day 2026-08-13.

Without an explicit wall-clock floor, a later store sync containing 2026-08-14 could cause the simulator to choose 2026-08-14 open as the next session after 2026-08-13. That would be a retroactive fill relative to the actual capture timestamp.

This was detected **before any paper fill or fresh return existed**, so no observed P&L needs deletion and the captured Top10 targets do not need to be reselected.

Required patch contract:

`FIRST_MARKET_SESSION_ON_OR_AFTER_CAPTURE_VN_DATE_PLUS_1`

For the first frozen targets captured on Vietnam date 2026-08-14, the causal execution floor date is therefore 2026-08-15. The engine must choose the first actual market session on or after that floor; 2026-08-14 is forbidden even if those bars are added later.

The persistent state must NOT be deleted. The patch must reuse the existing `captured_at` values, preserve model/ranking semantics, and fail if any execution date is earlier than its causal floor.

## Decision

- Freeze/target capture: accepted.
- Fresh OOS P&L: not started.
- C3 champion: unchanged.
- Ridge: shadow only.
- Data gates: all four still closed.
- No V78 historical model research.
- Apply causal execution-floor bugfix, verify Linux/Windows CI, then rerun the same V77 workstation state.
- The first valid fresh session is the first market session that satisfies the causal floor; no session that opened before target capture may be counted.
