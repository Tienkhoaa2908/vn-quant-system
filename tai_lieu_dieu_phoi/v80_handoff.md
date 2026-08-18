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

Observed registry state after the 2026-08-18 workstation run:

- observation IDs: `2026-07-31__2026-08-14`, `2026-07-31__2026-08-17`;
- latest capture wall time VN: `2026-08-18T08:35:53.960924+07:00`;
- latest execution floor date: `2026-08-18`;
- latest floor contract: `FIRST_MARKET_OPEN_STRICTLY_AFTER_CAPTURE_WALL_TIME_VN`;
- prior-week preview available: `true`;
- exact L15 active: `false`;
- total actions: `6`, all `NO_ACTION_NO_EXACT_L15`;
- outcome count: `0`;
- promotion/live authorization: `false`.

The first observation remains immutable under its original floor. For **new** observations, the canonical driver uses wall-clock session-aware timing: paper-open cutoff is `09:00:00` Vietnam time; a target frozen before that cutoff may use the still-future same-day open, while a target frozen at/after the cutoff must wait for the next actual market session. See `v80_forward_paper_tactical_contract.md`.

The 2026-08-17 observation is the first real observation with prior-week persistence available. No exact L15 qualified. `BWE` passed current-rank, prior-week-rank, relative-strength and eligibility gates but failed volume confirmation (`volume_ratio_5_20` about `0.366`). `TLG` had strong relative/volume and prior-week rank 9 but current preview rank 8, so it failed the current-rank <=5 gate. `SBT` had strong relative/volume but current rank 6 and prior-week rank 11. Thresholds remain frozen.

Incumbent health remained advisory: `VIC` reached preview rank 17 with period return about -8.33%, DD20 about -10.0%, DD60 about -14.10%, and R07/R08 both true; V80 correctly created no sell without exact L15.

## Workstation flow

Canonical entrypoint:

`scripts/run_v80_tactical_forward_paper_workstation_gitbash.sh`

One invocation owns freshness as well as paper capture:

1. syncs the latest available EOD through the existing local pipeline before the V80 read-only store fingerprint is taken;
2. preserves the approved V78 tracked web patch if present;
3. compiles/tests V78/V79/V80 and WAL fingerprint contracts;
4. refreshes V78 tactical state directly through the V78 driver, without running the web installer;
5. freezes/advances the V80 paper registry under `FIRST_MARKET_OPEN_STRICTLY_AFTER_CAPTURE_WALL_TIME_VN`;
6. applies only legal paper-open fills;
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

The next meaningful V80 run is after a new EOD session becomes available. Continue using the same one-shot workstation entrypoint. The next milestone is the first observation with `exact_l15_active=true`; after that, a later store containing the legal execution-day open can turn the frozen action into `FILLED_PAPER`, followed by H5/H10/H20/monthly outcomes.
