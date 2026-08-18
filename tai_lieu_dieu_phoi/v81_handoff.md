# V81 handoff — frozen tactical historical audit

## Current phase

V81 is the historical descriptive companion to V80 forward-paper collection.

Do not stop or reset V80. Do not reopen threshold/model search.

Frozen policies:

1. `NO_OVERLAY`;
2. `L15_SWAP25_WORST`;
3. `L15_SWAP50_WORST`;
4. `L15_CASH_ADD25_SLOT`.

Champion remains `C3_STABLE_3_PAST_IC_SHRUNK`.

## Why V81 exists

V79 selected the tactical mechanism from historical research. V80 now collects genuinely fresh forward evidence. V81 uses the same historical data again only to characterize the already-frozen mechanism in more detail while V80 continues to accumulate fresh observations.

V81 is therefore post-selection descriptive replay, not a new unbiased confirmation set.

## Questions V81 answers

- exact-L15 frequency and quiet periods;
- leader/incumbent concentration;
- actual replacement regret after H5/H10/H20 and monthly rebalance;
- leader versus VNINDEX after execution;
- causal bull/bear/sideways diagnostics;
- whether portfolio uplift is broad or dominated by a few months;
- behavior when no exact-L15 event exists;
- cost robustness;
- T+2 sensitivity;
- 100M/1B/10B capacity sensitivity.

It does not generate alternative thresholds or new policies.

## One-shot workstation entrypoint

`scripts/run_v81_frozen_tactical_historical_audit_workstation_gitbash.sh`

The runner:

1. preserves approved V78 tracked web modifications if present;
2. compiles and runs V72/V79/V81/WAL regression tests;
3. rebuilds V68 causal monthly/weekly states from the local market store;
4. reconstructs the frozen V70 C3 baseline;
5. replays only the four frozen V81 policy IDs;
6. generates event/regret/horizon/regime/concentration/cost/T2/capital diagnostics;
7. verifies logical market bars unchanged;
8. verifies V77 persistent state byte-identical;
9. verifies V80 persistent state byte-identical;
10. emits one ZIP.

Expected upload artifact:

`artifacts/UPLOAD_THIS_v81_FROZEN_TACTICAL_HISTORICAL_AUDIT-*.zip`

Do not upload screenshots or separate logs unless the runner fails.

## Required audit after workstation run

Read the package in this order:

1. provenance/head + store/V77/V80 integrity;
2. V70 baseline reconstruction;
3. `GAP18_CLEAN / EQUAL / BASE_DNSE` as the first historical reference scope;
4. exact-L15 frequency and event concentration;
5. H5/H10/H20/monthly replacement spread and regret rate;
6. portfolio delta concentration versus `NO_OVERLAY`;
7. regime splits;
8. cost/T2/capital robustness;
9. compare with V80 forward observations without retuning rules.

A result where historical uplift comes from only a few events or has high replacement regret is a valid negative finding. Do not repair it by threshold fishing.

## Safety

- V80 state is read-only to V81;
- V77 state is read-only to V81;
- no live orders;
- no promotion authorization;
- no champion replacement;
- no PIT/data-gate closure;
- 2026 is descriptive and not used to retune.
