# V80 workstation result — 2026-08-22

## Artifact provenance

- uploaded ZIP SHA256: `aa015cc3aa54f2893ca4682a54d176f41bd29bf658986fb1207261e68820dbba`
- branch: `agent/v80-forward-paper-tactical-actions`
- HEAD: `8ee4e49fc2e7dcb1fc941b5fd10c938f339bddcb`
- Python: 3.12.13
- canonical interpreter: `D:\VNQuant\vn-quant-system\vn_quant_local_system\.venv\Scripts\python.exe`
- sklearn: 1.9.0
- runner status: `SUCCESS`
- V78/V79/WAL/V80 regression tests: 32 PASS

## Market-store and persistent-state integrity

Latest market data in the audited V80 phase:

- bars first day: `2015-06-29`
- bars last day: `2026-08-21`
- bars row count: `301259`
- logical bars SHA256 before/after: `7f48a06841fd33de3bf1688d371c13edd5a7a15d896f18ebc32d4fdd0eaf8cad`
- physical store SHA256 before/after: `e3743e6534bf80a379f9dee40c378982ce39ad95363771c38c11dc85c4cc3ffa`
- V77 state digest before/after: `cd947687102f861f69c35482743cd01885ff4e567f835ca1a978780b41d4a838`

No market-bar mutation occurred during the V80 phase and V77 remained byte-identical.

## Registry progression

Persistent registry now contains three immutable observations:

1. `2026-07-31__2026-08-14`
2. `2026-07-31__2026-08-17`
3. `2026-07-31__2026-08-21`

The first two observations retained their original capture wall times, target hashes, tactical-row hashes and no-action statuses.

New observation:

- capture market day: `2026-08-21`
- capture wall time VN: `2026-08-22T20:04:14.520722+07:00`
- execution floor lower-bound date: `2026-08-23`
- execution contract: `FIRST_MARKET_OPEN_STRICTLY_AFTER_CAPTURE_WALL_TIME_VN`
- target hash: `bf19e30e8f55cf8902443c0bca5d8a7ae2c2768bae2386bf2d560b48627ec0b0`
- tactical rows hash: `48f6180427afabf64c5b2e310075a8f20558fed1cd4e6d4a7342f9f706859b4a`
- risk-on: `false`
- exact L15 active: `false`
- leader: none
- swap-out: none

`execution_floor_date=2026-08-23` is a calendar lower bound because capture occurred after the 09:00 cutoff on Saturday. Fill processing still uses the first actual market session on or after that lower bound, so a hypothetical qualified action could not execute before the next available market session (normally Monday 2026-08-24). No action existed in this observation, so no fill was attempted.

Totals after this run:

- observations: 3
- actions: 9
- outcomes: 0
- all 9 actions: `NO_ACTION_NO_EXACT_L15`
- live/promotion authorization: false

## Current V78 tactical state at 2026-08-21

Monthly C3 Top10 remains:

`VPI, MSB, HCM, VIC, GMD, LPB, STB, BAF, DHC, ACB`

Current preview Top10:

`VPI, BAF, MSB, HCM, SAB, STB, KDC, DHC, SBT, TLG`

Risk-on remains false. Incumbent health alerts: 4. Current dragging incumbents: `MSB, VIC, LPB`.

### VPI: important forward recovery evidence

At the previous 2026-08-17 observation, VPI had preview rank 10, period return about -4.71%, relative-to-VNINDEX about -3.70pp and was dragging.

By 2026-08-21:

- preview rank: 1
- period return from monthly T+1 open: about `+2.04%`
- benchmark period return: about `+1.32%`
- period relative return: about `+0.72pp`
- relative-5d: about `+4.65%`
- DD20/DD60: `0% / 0%`
- action: `CORE_HOLD`
- dragging: false

This is fresh forward evidence consistent with the frozen decision not to auto-sell an incumbent solely because it temporarily entered a drag state. It is not sufficient by itself to re-select or tune the policy.

### VIC and LPB remain weak

VIC:

- preview rank: 17
- period return: about `-5.09%`
- relative-to-VNINDEX: about `-6.41pp`
- DD20: about `-6.82%`
- DD60: about `-11.06%`
- action: `WATCH`
- dragging: true

VIC improved from the severe 2026-08-17 state (`-8.33%` period return, DD20 about `-10%`, DD60 about `-14.10%`) and no longer hit R07/R08 thresholds, but it remains a materially weak incumbent.

LPB:

- preview rank: 15
- period return: about `-4.03%`
- relative-to-VNINDEX: about `-5.35pp`
- relative-5d: about `-6.84%`
- DD20: about `-7.41%`
- DD60: about `-10.71%`
- action: `WATCH`
- dragging: true

MSB became a new drag incumbent:

- preview rank: 3
- period return: about `-1.24%`
- relative-to-VNINDEX: about `-2.56pp`
- relative-5d: about `-3.81%`
- dragging: true

GMD is health-alerted due rank decay but is not period-dragging because its period return remains positive and roughly benchmark-neutral.

## Exact-L15 status

No exact L15 qualified on 2026-08-21.

The only outside-monthly-Top10 name inside the current preview Top5 was `SAB` at rank 5. It did not qualify because:

- prior-week preview rank = 13, failing the required `<=10` persistence gate;
- relative-5d about `+1.05%`, failing the required `>=+2%` gate;
- volume ratio about `1.03` did pass volume confirmation.

`BWE`, previously the closest candidate on 2026-08-17, was no longer present in the 2026-08-21 eligible/current tactical rows and therefore was not a valid current L15 candidate. `SBT` and `TLG` remained radar names but current preview ranks 9 and 10 respectively, outside the exact-L15 `<=5` gate.

Thresholds remain frozen. No historical selection is reopened.

## Interpretation

This run adds useful forward behavioral evidence even though no tactical trade occurred:

1. VPI's reversal from a clear drag state to rank-1/core-hold demonstrates why health/drag alone is not a sufficient automatic-sell trigger.
2. VIC and LPB remain weak and are still valid source-capital candidates only if an independently qualified exact-L15 leader appears.
3. The exact-L15 gate continued to refuse marginal leaders rather than forcing a replacement.
4. No efficacy claim for SWAP50 can yet be made from V80 because no genuine exact-L15 paper fill has occurred and outcome count remains zero.
