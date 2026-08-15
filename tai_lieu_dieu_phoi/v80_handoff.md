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

## Workstation flow

Canonical entrypoint:

`scripts/run_v80_tactical_forward_paper_workstation_gitbash.sh`

One invocation:

1. preserves the approved V78 tracked web patch if present;
2. compiles/tests V78/V79/V80 and WAL fingerprint contracts;
3. refreshes V78 tactical state directly through the V78 driver, without running the web installer;
4. freezes/advances the V80 paper registry;
5. applies only legal next-session-open paper fills;
6. advances H5/H10/H20/monthly-boundary outcomes when those sessions exist;
7. verifies logical market data unchanged and V77 state unchanged;
8. emits one ZIP.

Expected artifact:

`UPLOAD_THIS_v80_TACTICAL_FORWARD_PAPER-*.zip`

## Interpretation

No exact L15 => no action, regardless of how bad an incumbent looks.

Exact L15 => V80 records independent SWAP25/SWAP50 counterfactuals. CASH_ADD25 additionally requires risk-on and real simulated idle-cash capacity.

All outputs are paper/counterfactual evidence only. No live or promotion decision is authorized by V80.
