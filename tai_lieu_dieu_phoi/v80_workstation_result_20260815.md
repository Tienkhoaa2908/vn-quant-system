# V80 workstation result — 2026-08-15

## Status

`SUCCESS` — first real workstation V80 persistent observation was created and audited from the uploaded bundle.

This result verifies registry initialization and the real no-action path. It does **not** verify a real exact-L15 paper fill yet because no exact-L15 event was active at capture.

## Provenance

- branch: `agent/v80-forward-paper-tactical-actions`
- Git HEAD: `ef9e14968309542cd32e259624fd87115728c97f`
- workstation Python: `3.12.13`
- canonical interpreter: `vn_quant_local_system/.venv/Scripts/python.exe`
- scikit-learn: `1.9.0`
- uploaded ZIP SHA256: `f88d3a6b2534380c56775598e980dc84c5e9c8cc9d266418815e750953d55300`

The uploaded HEAD exactly matched PR #56 final tested HEAD at the time of audit.

## Market-store integrity

Physical SQLite SHA256 before and after:

`9edd743d91ef3a27a03503a20980bf37fe853c490de272eaae3e588520d65680`

Logical `bars` fingerprint before and after:

`481a31b20d855e65f873d37ae08bd1f4fb1b6e74dfee32bc2e4c44f43ff409b6`

Logical store census:

- first day: `2015-06-29`
- last day: `2026-08-14`
- row count: `300661`

No market-bar mutation was observed.

## V77 integrity

V77 persistent-state digest before and after was byte-identical:

`cd947687102f861f69c35482743cd01885ff4e567f835ca1a978780b41d4a838`

The preserved V77 freeze still names:

- champion: `C3_STABLE_3_PAST_IC_SHRUNK`
- shadow: `V76_RIDGE_RANK`
- capital authorized: `false`
- future model mutation allowed: `false`

## Current V78 observation

- source monthly signal: `2026-07-31`
- capture market day: `2026-08-14`
- monthly Top10: `VPI, MSB, HCM, VIC, GMD, LPB, STB, BAF, DHC, ACB`
- current preview Top10: `MSB, BAF, BWE, HCM, STB, KDC, LPB, GMD, TLG, DHC`
- risk-on: `false`
- prior-week preview available: `false`
- exact L15 swap active: `false`
- live orders allowed: `false`

Incumbent diagnostics:

- `VPI`: monthly rank 1, preview rank 12, current-period return about `-4.55%`, relative to VNINDEX about `-3.64pp`, `WATCH_MONTH_DRAG`.
- `VIC`: monthly rank 4, preview rank 16, current-period return about `-7.22%`, relative to VNINDEX about `-6.31pp`, drawdown20 about `-8.91%`, drawdown60 about `-13.06%`, `R07=true`, `R08=true`, action `RISK_ALERT_R08`.

This is an important live contract check: even though VIC now satisfies the severe R07/R08 health thresholds, V80 did not create a sell action because incumbent health is advisory only.

Emerging candidates did not satisfy exact L15:

- `BWE`: preview rank 3 and relative5 about `+3.12%`, but prior-week persistence is unavailable and volume ratio5/20 is only about `0.387`; therefore `WATCH_EMERGING`, not L15.
- `TLG`: relative5 about `+8.68%` and volume ratio about `1.96`, but preview rank is 9 and prior-week persistence is unavailable; therefore not L15.

## First V80 frozen observation

Observation ID:

`2026-07-31__2026-08-14`

Capture wall time Vietnam:

`2026-08-15T11:41:16.090493+07:00`

Execution floor recorded by the original implementation:

`2026-08-16`

Original contract:

`FIRST_MARKET_SESSION_ON_OR_AFTER_CAPTURE_VN_DATE_PLUS_1`

This first observation is immutable. Later V80 code refined **new-observation** timing to `FIRST_MARKET_OPEN_STRICTLY_AFTER_CAPTURE_WALL_TIME_VN` with a `09:00:00` Vietnam paper-open cutoff; that refinement does not rewrite this historical record.

Frozen target hash:

`1797912d83be3a2dbc477139369e5320aeea5ecc0d33808c2f01c6403aa56c5a`

Frozen tactical rows hash:

`4d79e16b8eeca3c905d915014b979a94494adda7f9e02dc8822cc4356e286237`

The audited bundle recomputed both hashes exactly from the frozen target and 25 frozen tactical rows.

## Policy statuses

All three frozen policies correctly recorded:

- `L15_SWAP25_WORST` → `NO_ACTION_NO_EXACT_L15`
- `L15_SWAP50_WORST` → `NO_ACTION_NO_EXACT_L15`
- `L15_CASH_ADD25_SLOT` → `NO_ACTION_NO_EXACT_L15`

Counts:

- observations: `1`
- actions: `3`
- outcomes: `0`
- exact L15 active: `false`
- incumbent-health auto-sell: `false`
- promotion authorized: `false`
- live orders allowed: `false`

No paper fill was legally expected because there was no exact-L15 action. Therefore the empty outcome set is correct.

## Test evidence in workstation bundle

The workstation runner executed 29 V78/V79/V80/WAL regression tests and all passed, including:

- no retroactive fill / causal execution floor;
- exact L15 reuse;
- swap fraction as incumbent-position fraction, not NAV;
- cash-add bounded by real simulated idle cash;
- risk-off blocks cash-add;
- monthly rebalance precedence;
- same-observation drift failure;
- WAL logical-store fingerprint;
- full V80 persistent run twice on the same state;
- exclusion of `*.rows.json` from observation enumeration.

## Audit conclusion

The first real V80 workstation observation is valid and the persistent registry is now initialized.

Operational interpretation:

1. keep `du_lieu/v80-tactical-paper-state/` permanently; never delete/reset it;
2. continue future V80 runs on the same state to collect genuinely fresh observations;
3. no policy efficacy claim can be made from this first observation because no exact-L15 event occurred;
4. a real fill path remains `not_yet_observed` until a future exact-L15 event produces a legal paper-open fill;
5. no live-order or promotion authority is created by this result;
6. PIT HOSE membership, price basis, corporate-action inventory, and PIT sector gates remain fail-closed for canonical promotion/live claims.

The uploaded ZIP does not independently contain the outer wrapper's local-web restore transcript. That is not a V80 forward-registry blocker because the inner runner does not mutate the web; the preserve/restore transaction remains CI-verified separately.
