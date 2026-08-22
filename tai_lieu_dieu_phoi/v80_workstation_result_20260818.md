# V80 workstation result — 2026-08-18

## Status

`SUCCESS` — second real forward-paper observation was appended on the existing V80 persistent registry from the uploaded workstation bundle.

This run verifies the new pre-open causal floor and the real persisted prior-week gate. It still does **not** verify a real exact-L15 fill because no exact-L15 candidate passed all frozen conditions on 2026-08-17.

## Provenance

- branch: `agent/v80-forward-paper-tactical-actions`
- Git HEAD in uploaded artifact: `a3e43a9c07604549d4fe0e5a04043452cfe6b8b6`
- workstation Python: `3.12.13`
- canonical interpreter: `vn_quant_local_system/.venv/Scripts/python.exe`
- scikit-learn: `1.9.0`
- uploaded ZIP SHA256: `14e0fa09df4a7c61c72f059225edb2c254a0d0520d1b716300d41f5dfe5b1811`

## Market freshness and integrity

The market store seen by V80 was current through Monday 2026-08-17:

- bars first day: `2015-06-29`
- bars last day: `2026-08-17`
- row count: `300781`
- logical bars SHA256 before/after V80: `fc5e9c44099afed3ae6d78558939716c56a600a12e92005ec0308faf89374cd1`
- physical SQLite SHA256 before/after: `b309fdd424dbba39794b9114cbce18b66b8cc3db21a7b732fc2039463491193c`

No market-bar mutation occurred during the V80 phase.

The outer pre-sync transcript is stored separately by the workstation wrapper and was not bundled in this ZIP, so the uploaded ZIP does not independently contain the sync command transcript. The resulting store census nevertheless proves that the V80 phase consumed EOD through 2026-08-17.

## V77 integrity

V77 persistent-state digest before/after remained byte-identical:

`cd947687102f861f69c35482743cd01885ff4e567f835ca1a978780b41d4a838`

The preserved freeze still keeps C3 champion, Ridge shadow only, capital unauthorized, and future model mutation disabled.

## Persistent-registry continuity

Registry observation IDs are now:

1. `2026-07-31__2026-08-14`
2. `2026-07-31__2026-08-17`

The first observation was preserved under its original timing contract and was not rewritten:

- capture wall time: `2026-08-15T11:41:16.090493+07:00`
- execution floor: `2026-08-16`
- original contract: `FIRST_MARKET_SESSION_ON_OR_AFTER_CAPTURE_VN_DATE_PLUS_1`

The new observation uses the refined wall-clock contract:

- capture market day: `2026-08-17`
- capture wall time VN: `2026-08-18T08:35:53.960924+07:00`
- paper-open cutoff: `09:00:00`
- execution floor date: `2026-08-18`
- contract: `FIRST_MARKET_OPEN_STRICTLY_AFTER_CAPTURE_WALL_TIME_VN`

Because capture occurred before 09:00, same-day 2026-08-18 open remained a legal future execution point if an exact-L15 action had existed. No action existed, so no paper fill was expected.

Frozen hashes for the new observation independently recompute exactly:

- target hash: `1507687c85e585921349f8fd786aedb7530a6274eb59fbede07c93183e73083f`
- tactical rows hash: `2f90bcfe226bea8124ddfb337012af9f2fe3866661edc1e2b14de6338abd4631`

## V78 observation — 2026-08-17

- source monthly signal: `2026-07-31`
- monthly Top10: `VPI, MSB, HCM, VIC, GMD, LPB, STB, BAF, DHC, ACB`
- current preview Top10: `MSB, BAF, STB, BWE, HCM, SBT, KDC, TLG, GMD, VPI`
- prior-week preview available: `true`
- risk-on: `false`
- exact L15 active: `false`
- incumbent health alerts: `3`
- dragging incumbents: `VPI, VIC, LPB`

This is the first real observation where prior-week persistence was available from the persisted 2026-08-14 preview.

## Why exact L15 still did not trigger

The exact frozen L15 gate requires all of:

- outside monthly Top10;
- current preview rank <= 5;
- prior-week preview rank <= 10;
- relative5 >= +2%;
- volume ratio 5/20 >= 1;
- current eligibility.

`BWE` was the closest candidate:

- outside monthly Top10: yes;
- current preview rank: `4` — pass;
- prior-week preview rank: `3` — pass;
- relative5: about `+3.00%` — pass;
- current eligibility: pass;
- volume ratio5/20: about `0.366` — **fail**.

Therefore BWE remains `WATCH_EMERGING`, not L15.

Other notable emerging names:

- `SBT`: relative5 about `+12.66%`, volume ratio about `1.42`, but current rank `6` and prior-week rank `11`; therefore fails both rank gates.
- `TLG`: prior-week rank `9`, relative5 about `+5.97%`, volume ratio about `1.75`, but current rank `8`; therefore fails current rank <=5.

No threshold was changed in response.

## Incumbent diagnostics

Three monthly C3 incumbents were dragging the period:

- `VPI`: period return about `-4.71%`, relative to VNINDEX about `-3.70pp`, preview rank `10`; no R07/R08 trigger.
- `VIC`: period return about `-8.33%`, relative about `-7.32pp`, DD20 about `-10.0%`, DD60 about `-14.10%`, preview rank `17`, `R07=true`, `R08=true`.
- `LPB`: period return about `-2.30%`, relative about `-1.29pp`, preview rank `12`; no R07/R08 trigger.

Despite severe VIC health, V80 correctly generated no sell because incumbent health remains advisory and exact L15 was inactive.

## V80 policy state

Counts after this run:

- observations: `2`
- actions: `6`
- outcomes: `0`
- live orders: `false`
- promotion authorized: `false`

All six policy records — three from 2026-08-14 plus three from 2026-08-17 — are:

`NO_ACTION_NO_EXACT_L15`

No policy-efficacy conclusion should be drawn yet because no exact-L15 event has produced a legal paper fill.

## Regression evidence

The workstation run executed 32 relevant V78/V79/V80/WAL tests and all passed, including:

- persisted prior-week preview semantics;
- pre-open same-day future-open floor;
- at/after-open deferral;
- immutable existing observation floor;
- no retroactive fill;
- exact L15 reuse;
- no autonomous incumbent sell;
- WAL logical fingerprint;
- repeated persistent-state run semantics.

## Audit conclusion

The second V80 forward observation is valid. The persistent registry is behaving correctly and the first real prior-week persistence check has been exercised.

Operational rule remains unchanged:

1. do not reset V80 state;
2. do not tune L15 thresholds after observing this result;
3. continue appending fresh EOD observations on the same state;
4. wait for a future exact-L15 event before evaluating SWAP25/SWAP50/CASH_ADD25 realized paper outcomes;
5. no live or promotion authority is created by this result.
