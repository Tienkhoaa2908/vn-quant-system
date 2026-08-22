# V80 handoff — forward paper tactical actions

## Current phase

V80 follows the V79 research decision. Do not reopen the V79 historical matrix or tune new loss/drawdown/rank thresholds.

Frozen forward-paper challengers:

1. `L15_SWAP50_WORST` — primary economic challenger;
2. `L15_SWAP25_WORST` — lower-intensity challenger;
3. `L15_CASH_ADD25_SLOT` — idle-cash admission challenger.

Champion remains `C3_STABLE_3_PAST_IC_SHRUNK`.

## Persistent state

`du_lieu/v80-tactical-paper-state/`

Never delete/reset this directory to rerun an observation. Same-observation target drift must fail closed. V77 state at `du_lieu/v77-paper-oos-state/` is read-only from the V80 runner and must remain byte-identical.

Audited real workstation results:

- `tai_lieu_dieu_phoi/v80_workstation_result_20260815.md`
- `tai_lieu_dieu_phoi/v80_workstation_result_20260818.md`
- `tai_lieu_dieu_phoi/v80_workstation_result_20260822.md`

Observed registry state after the 2026-08-22 workstation run:

- observation IDs: `2026-07-31__2026-08-14`, `2026-07-31__2026-08-17`, `2026-07-31__2026-08-21`;
- latest capture wall time VN: `2026-08-22T20:04:14.520722+07:00`;
- latest execution floor lower-bound date: `2026-08-23`;
- latest floor contract: `FIRST_MARKET_OPEN_STRICTLY_AFTER_CAPTURE_WALL_TIME_VN`;
- exact L15 active: `false`;
- total actions: `9`, all `NO_ACTION_NO_EXACT_L15`;
- outcome count: `0`;
- promotion/live authorization: `false`.

`execution_floor_date` is a calendar lower bound. Fill processing uses the first actual market session on/after that floor, so a weekend floor date does not imply a weekend fill. Existing observations are never rewritten by the wall-clock timing refinement.

The 2026-08-17 observation was the first real observation with prior-week persistence available. No exact L15 qualified. `BWE` passed current-rank, prior-week-rank, relative-strength and eligibility gates but failed volume confirmation (`volume_ratio_5_20` about `0.366`). `TLG` had strong relative/volume and prior-week rank 9 but current preview rank 8, so it failed the current-rank <=5 gate. `SBT` had strong relative/volume but current rank 6 and prior-week rank 11. Thresholds remain frozen.

The 2026-08-21 observation added important forward behavioral evidence. `VPI`, which had been a clear drag on 2026-08-17 (preview rank 10, period return about -4.71%, relative-to-VNINDEX about -3.70pp), recovered by 2026-08-21 to preview rank 1, period return about +2.04%, relative-to-VNINDEX about +0.72pp, and `CORE_HOLD`. This is consistent with the frozen decision not to auto-sell solely on temporary drag, but it is not a policy-selection event and does not justify tuning thresholds.

Current 2026-08-21 dragging incumbents are `MSB`, `VIC`, and `LPB`. `VIC` improved from its severe 2026-08-17 drawdown state but remains weak at preview rank 17, period return about -5.09%, relative about -6.41pp. `LPB` worsened to preview rank 15, period return about -4.03%, relative about -5.35pp. Health remains advisory only: these names become source-capital candidates only if an independently qualified exact-L15 leader exists.

No exact L15 qualified on 2026-08-21. `SAB` reached current preview rank 5 and passed volume confirmation, but prior-week rank 13 failed persistence and relative-5d about +1.05% failed the >=+2% gate. `BWE` was no longer present in the current eligible/tactical rows. `SBT` and `TLG` were ranks 9 and 10, outside the <=5 gate.

## Workstation flow

Canonical entrypoint:

`scripts/run_v80_tactical_forward_paper_workstation_gitbash.sh`

One invocation owns freshness as well as paper capture:

1. syncs the latest available EOD through the existing local pipeline before the V80 read-only store fingerprint is taken;
2. preserves the approved V78 tracked web patch if present;
3. compiles/tests V78/V79/V80 and WAL fingerprint contracts;
4. refreshes V78 tactical state directly through the V78 driver, without running the web installer;
5. freezes/advances the V80 paper registry under `FIRST_MARKET_OPEN_STRICTLY_AFTER_CAPTURE_WALL_TIME_VN`;
6. applies only legal paper-open fills at the first actual market session on/after the stored floor lower bound;
7. advances H5/H10/H20/monthly-boundary outcomes when those sessions exist;
8. verifies logical market data unchanged during the V80 research phase and V77 state unchanged;
9. emits one V80 ZIP. The pre-sync transcript is retained under `artifacts/v80-pre-sync-*.json` for workstation audit.

Expected artifact:

`UPLOAD_THIS_v80_TACTICAL_FORWARD_PAPER-*.zip`

## Interpretation

No exact L15 => no action, regardless of how bad an incumbent looks.

Exact L15 => V80 records independent SWAP25/SWAP50 counterfactuals. CASH_ADD25 additionally requires risk-on and real simulated idle-cash capacity.

All outputs are paper/counterfactual evidence only. No live or promotion decision is authorized by V80.

## Next operating rule

Do not reset V80 state and do not tune the policy matrix after observing future outcomes. Future workstation runs only append/advance fresh observations and legal H5/H10/H20/monthly outcomes under the frozen contract.

The next meaningful V80 run is after a new EOD session becomes available. Continue using the same one-shot workstation entrypoint. The next milestone remains the first observation with `exact_l15_active=true`; after that, a later store containing the legal execution-day open can turn the frozen action into `FILLED_PAPER`, followed by H5/H10/H20/monthly outcomes.
