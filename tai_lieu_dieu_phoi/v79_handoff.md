# V79 handoff — unified tactical capital-action policy research

## Current phase

V79 is the consolidated research package for intra-month capital actions on top of frozen C3.

Champion remains `C3_STABLE_3_PAST_IC_SHRUNK`. No model search, champion replacement, promotion, live order or broker mutation is authorized.

## Workstation result

Read `tai_lieu_dieu_phoi/v79_workstation_result_20260815.md` first.

Observed workstation artifact at HEAD `479f9b6a53fba33ecbfac1ab6a89a26facec2d3d` completed all V68/V70/V79 calculations and regression tests. The original runner exited only at its final physical SQLite SHA check.

That check was found invalid under SQLite WAL semantics. The artifact already saw logical bars through `2026-08-14` while the main `.sqlite3` file still had the older physical SHA, which is consistent with uncheckpointed WAL state. A dedicated regression reproduces physical-SHA drift across checkpoint with identical logical bars.

Current V79 code therefore uses a deterministic read-only logical `bars` fingerprint for the mutation invariant and keeps physical SHA as audit metadata only.

No workstation rerun is required merely to reproduce the already-completed policy P&L. Future workstation runs should use the WAL-safe guard.

## Research decision

Do not continue threshold fishing for an autonomous incumbent sell rule on the same historical sample.

Rejected as autonomous action rules:

- `DRAG_PERSIST_TRIM25_CASH`;
- `DRAG_PERSIST_TRIM50_CASH`;
- `SEVERE_DRAG_EXIT100_CASH`;
- drag-trigger-dependent rotation/combined as an operational rule.

Reason: pre-2026 paired evidence is negative/weak, and the new incumbent-cut family reduces return across the main sensitivity combinations.

Keep as forward-paper opportunity challengers:

1. `L15_SWAP50_WORST` — strongest economic replacement challenger;
2. `L15_SWAP25_WORST` — lower-intensity replacement challenger;
3. `L15_CASH_ADD25_SLOT` — idle-cash admission challenger and the only formal V79 diagnostic watchlist row in one BROAD_PROVISIONAL/INVOL60 configuration.

Interpretation: cutting because an incumbent is bad is not supported; replacing a weak incumbent when an independently qualified exact-L15 leader exists is the promising mechanism.

## Operational architecture after V79

- monthly C3 Top10 stays core;
- incumbent drag/health remains warning and replacement-priority information;
- no autonomous sell from R07/R08/DRAG_PERSIST/SEVERE_DRAG;
- exact L15 stays frozen from V72;
- tactical replacement should be opportunity-conditioned, not loss-conditioned;
- current exact-L15 challengers remain advisory/paper only until genuinely fresh forward evidence exists.

## Important caveats

- 2026 is shadow only and not used for selection;
- V79's 2026 deep-backtest period ends at `2026-08-03`; it does not validate the later VPI/VIC/TLG state around 13–14 August;
- GAP18_CLEAN is still a provisional non-PIT sensitivity and can drift when newly observed future price gaps alter the excluded-symbol set;
- PIT HOSE, price basis, corporate actions and PIT sector master remain fail-closed;
- 10bn capital sensitivity is not operationally credible where modeled ADV20 participation exceeds 100%;
- no live/promotion claim.

## Next research mode

Do not open another historical threshold matrix. Move the frozen tactical opportunity challengers into forward paper logging against current V78 tactical observations and next-session-open hypothetical execution, while continuing the existing V77 fresh-OOS discipline and preserving persistent states.
