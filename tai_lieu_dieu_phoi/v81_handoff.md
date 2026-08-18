# V81 handoff — frozen tactical historical audit

## Current phase

V81 historical descriptive audit has completed and the real workstation artifact is recorded at:

`tai_lieu_dieu_phoi/v81_workstation_result_20260818.md`

V81 is closed as a research-characterization step. Do not reopen threshold/model/policy search on the same historical sample.

Champion remains `C3_STABLE_3_PAST_IC_SHRUNK`.

Frozen tactical surface after V81:

1. `L15_SWAP50_WORST` — primary tactical paper challenger;
2. `L15_SWAP25_WORST` — conservative shadow challenger;
3. `L15_CASH_ADD25_SLOT` — secondary diagnostic shadow only.

Autonomous incumbent-loss cuts remain rejected.

## Profit result that must remain visible in future reporting

Primary historical reference: `GAP18_CLEAN / EQUAL / BASE_DNSE / 1bn / immediate`.

- frozen C3 ending NAV: about `4.814bn`, net profit `3.814bn`, total return `+381.39%`, CAGR `18.89%`, MDD `-37.46%`;
- SWAP25 ending NAV: about `4.968bn`, incremental NAV vs C3 `+153.77m`, return uplift `+15.38pp`, CAGR uplift `+0.41pp`, MDD improvement `+0.85pp`;
- SWAP50 ending NAV: about `5.151bn`, incremental NAV vs C3 `+336.78m`, return uplift `+33.68pp`, CAGR uplift `+0.89pp`, MDD improvement `+1.19pp`;
- CASH_ADD25 ending NAV: about `4.832bn`, incremental NAV only `+18.53m`, return uplift `+1.85pp`.

SWAP50 is positive across all 3 historical universe sensitivities x both allocators, all frozen cost scenarios, and T2/no-advance. It remains paper-only.

## Mechanism findings

GAP18 pre-2026 has 81 actionable exact-L15 events across 60 active months and 56 unique leaders. At the next monthly rebalance, mean leader-minus-replaced-incumbent spread is about `+1.51%`, win rate `55.56%`, regret rate `44.44%`. The positive edge is real but not high-hit-rate; sizing matters.

H20 has no strategy-valid uncensored observations because monthly rebalance precedence closes the tactical holding before a full 20-session horizon. Monthly-boundary outcome is the correct long tactical horizon under the frozen contract.

10bn simulated economics remain positive but capacity is not realistic for many names; 100m is cleanest and 1bn is generally usable with a small number of high-ADV-participation trades.

## Forward-paper continuation

Do not stop or reset V80. Persistent state remains:

`du_lieu/v80-tactical-paper-state/`

V80 keeps collecting genuinely fresh observations and legal fills/outcomes. V81 did not mutate V77 or V80 state.

## Research stop / acceleration rule

No new large historical matrix is justified now. Research proceeds only through:

- V80 fresh forward-paper evidence;
- data-truth improvements (PIT HOSE, price basis/corporate actions, PIT sector lineage);
- compact diagnostics that do not alter frozen thresholds/policies.

This is intentionally faster than continuing threshold fishing.

## Parallel web track

Start an additive web-integration track immediately, based on the already-approved local workstation UI. It may run in parallel with V80 forward collection.

The web should expose, read-only:

- C3 monthly Top10 and tactical preview;
- incumbent health/drag warnings without autonomous sell;
- exact-L15 status and current replacement pair if active;
- V80 observation/action/outcome counts and latest paper status;
- explicit profit panel with frozen C3 vs SWAP25/SWAP50/CASH_ADD historical diagnostics;
- clear labels separating historical post-selection evidence, fresh forward-paper evidence, and live authorization (`false`).

Do not redesign the approved web, change port 8787, or add broker/live-order endpoints.
