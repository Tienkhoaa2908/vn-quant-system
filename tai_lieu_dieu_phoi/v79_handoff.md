# V79 handoff — tactical capital-action policy

## Current phase

V79 is the approved research phase after V78 tactical observability.

- parent branch: `agent/v78-c3-tactical-terminal`;
- parent HEAD at creation: `36b9234e90d4d92a9146390a33704ef51dd4cd4d`;
- V79 branch: `agent/v79-c3-tactical-capital-policy`.

V79 stays stacked on V78 until V78 integration lineage is resolved. Do not reopen a model-search lane.

## User intent

Solve two mid-month operational gaps without recalculating/refitting C3 daily:

1. trim/cut C3 incumbents that strongly and persistently drag portfolio P&L;
2. admit strong non-Top10 leaders only when they cross a frozen causal gate.

The user explicitly wants all directions consolidated into one workstation run, not fragmented into many reruns.

## Approved scope

Read `tai_lieu_dieu_phoi/v79_tactical_capital_policy_contract.md`.

The one-shot matrix includes incumbent trim25/trim50/severe-exit research, exact-L15 swap/cash-add, rotate25/rotate50, combined policy, V72 anchors, EQUAL/INVOL60, four cost scenarios, T2 sensitivity, 100M/1B/10B sensitivity, pre-2026 inference/BH-FDR and 2026 shadow.

## Frozen invariants

- champion stays `C3_STABLE_3_PAST_IC_SHRUNK`;
- historical model/hyperparameter search remains stopped;
- V72 exact L15 is reused, not retuned;
- weekly close -> next-session-open execution;
- monthly rebalance precedence;
- no live orders;
- no promotion;
- data-lineage gates remain fail-closed.

## Most recent local-data evidence before V79

The workstation pipeline artifact uploaded 2026-08-14 reported:

- source freshness `CURRENT_FINAL_EOD`;
- expected final session `2026-08-14`;
- latest stock day `2026-08-14`;
- latest VNINDEX day `2026-08-14`;
- expected stock count 119;
- symbol error count 0.

Do not request another standalone pipeline run merely to prove 2026-08-14 EOD freshness before V79. V79 still checks that the local market-store SHA is unchanged by the research run.

## Awaiting evidence

V79 is incomplete until the real Windows one-shot workstation ZIP is uploaded and audited.

Expected artifact:

`UPLOAD_THIS_v79_TACTICAL_CAPITAL_POLICY-*.zip`

Until then V79 outcomes are implementation/CI evidence only, not observed workstation research results.
