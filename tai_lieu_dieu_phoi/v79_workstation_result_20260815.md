# V79 workstation result — 2026-08-15 audit

## Provenance

Uploaded artifact SHA-256:

`5d28ebe4a27586b5a286530d33b5b28ff1f51b3027ad5a27dbdb521cd98daede`

Observed artifact provenance:

- branch: `agent/v79-c3-tactical-capital-policy`;
- artifact HEAD: `479f9b6a53fba33ecbfac1ab6a89a26facec2d3d`;
- Python 3.12.13 from canonical `vn_quant_local_system/.venv`;
- scikit-learn 1.9.0;
- V79 report status `SUCCESS` before the runner's final store-integrity guard;
- 14 V72/V79 regression tests passed;
- policy count: 12;
- frozen champion remains `C3_STABLE_3_PAST_IC_SHRUNK`;
- champion replacement, promotion and live orders remain false.

Baseline reconstruction is exact: 24 V70 summary comparisons with maximum total-return, CAGR and MDD error all `0.0`.

## Store-integrity false positive discovered

The original runner recorded:

- physical `.sqlite3` SHA before: `2959f8cce0c11e8e4186fcb49ae75bf7babf86b84afe64ca3b843a7470d58b1a`;
- physical `.sqlite3` SHA after: `9edd743d91ef3a27a03503a20980bf37fe853c490de272eaae3e588520d65680`.

It therefore exited with `FAILED: market store changed during research run` after all research outputs had already been written.

This physical-file check is invalid for a SQLite database with WAL state. In the same artifact, V68 read 300,661 logical `bars` rows through `2026-08-14` while the physical main-file SHA at run start was still the previously observed pre-checkpoint SHA. V68 itself reported `store_mutated=false` / `source_store_mutated=false`.

A WAL regression fixture reproduced the exact class of failure: logical rows visible through WAL remain identical while checkpointing changes the physical main-file SHA. V79 was patched after artifact audit to use a deterministic read-only logical `bars` fingerprint as the pass/fail invariant while keeping physical SHA for audit only.

The artifact is therefore usable for diagnostic research conclusions, but it is not relabeled as an original runner PASS. No promotion/live authorization follows from this interpretation.

## Primary pre-2026 conclusion

Selection/inference ends at `2025-12-31`; 2026 is shadow only.

### Incumbent-cut family — rejected

On GAP18_CLEAN / Equal, versus `NO_OVERLAY`:

- `DRAG_PERSIST_TRIM25_CASH`: mean monthly delta `-0.0358pp`, pre-2026 CAGR delta `-0.446pp`, MDD worsens about `0.308pp`;
- `DRAG_PERSIST_TRIM50_CASH`: mean monthly delta `-0.0706pp`, CAGR delta `-0.889pp`, MDD worsens about `0.724pp`;
- `SEVERE_DRAG_EXIT100_CASH`: mean monthly delta `-0.0279pp`, CAGR delta `-0.321pp`, MDD worsens about `0.649pp`.

The same direction remains negative under INVOL60. Full-history BASE_DNSE total-return deltas are negative in all six variant/allocator combinations for all three new incumbent-cut rules.

Conclusion: do not promote automatic cut/exit based on `DRAG_PERSIST` or `SEVERE_DRAG` as currently defined.

### Opportunity / exact-L15 family — promising, not promoted

GAP18_CLEAN / Equal / BASE_DNSE full-history:

- frozen C3 `NO_OVERLAY`: total return `+381.39%`, CAGR `18.89%`, MDD `-37.46%`;
- `L15_SWAP25_WORST`: `+396.77%`, CAGR `19.30%`, MDD `-36.61%`;
- `L15_SWAP50_WORST`: `+415.07%`, CAGR `19.77%`, MDD `-36.27%`;
- `L15_CASH_ADD25_SLOT`: `+383.25%`, CAGR `18.94%`, MDD `-37.42%`.

For pre-2026 GAP18 Equal:

- `L15_SWAP25_WORST`: mean monthly delta `+0.0261pp`, CAGR delta `+0.365pp`, MDD improvement `+0.851pp`;
- `L15_SWAP50_WORST`: mean monthly delta `+0.0582pp`, CAGR delta `+0.817pp`, MDD improvement `+1.194pp`;
- `L15_CASH_ADD25_SLOT`: mean monthly delta `+0.0052pp`, CAGR delta `+0.072pp`.

The swap25/swap50 direction is positive in all six BASE_DNSE variant/allocator combinations and improves MDD in all six. GAP18 Equal remains positive under GROSS/BASE/STRESS/SEVERE costs and under T2_NO_ADVANCE.

However, the GAP18 inference CIs still cross zero after the predeclared multiple-testing discipline. These are forward-paper candidates, not promotion evidence.

The only formal V79 diagnostic watchlist row is `BROAD_PROVISIONAL / INVOL60 / L15_CASH_ADD25_SLOT`, with block sign-flip `p≈0.0202`, BH-FDR `q≈0.0741`, positive bootstrap lower bound and positive annual delta in 7/9 pre-2026 years. Because this is BROAD_PROVISIONAL while PIT/data gates remain open, it cannot authorize canonical use.

### Rotation / combined family — do not freeze as operational rule

`DRAG_L15_ROTATE25`, `DRAG_L15_ROTATE50` and `COMBINED50_CASHFALLBACK25` can look better in the observed 2026 shadow, but primary pre-2026 GAP18 inference is negative/weak. This indicates the bad-incumbent trigger degrades the otherwise useful L15 opportunity mechanism.

Conclusion: do not force emerging-leader admission to depend on the current `DRAG_PERSIST` cut trigger.

## Mechanism conclusion

V79 separates two superficially similar actions:

1. sell/trim because an incumbent is currently bad;
2. replace a weak incumbent only when an exact-L15 leader has independently passed a strong opportunity gate.

Historical evidence rejects mechanism 1 as currently specified and supports continued forward testing of mechanism 2.

The practical research architecture after V79 is therefore:

- C3 monthly Top10 remains the frozen core;
- incumbent deterioration remains a warning/priority signal, not an autonomous sell trigger;
- exact L15 remains the opportunity gate;
- `L15_SWAP50_WORST` is the strongest economically robust replacement challenger;
- `L15_SWAP25_WORST` is the lower-intensity replacement challenger;
- `L15_CASH_ADD25_SLOT` remains a separate idle-cash admission challenger;
- no new threshold tuning on the repeatedly inspected historical sample.

## 2026 shadow caveat

The 2026 shadow is not used for selection. For GAP18 Equal it ends at the completed backtest period ending `2026-08-03`, so it does not evaluate the later V78 VPI/VIC/TLG tactical state around 13–14 August.

Observed 2026 shadow deltas versus frozen C3 include:

- L15 swap25 `+0.57pp`;
- L15 swap50 `+1.04pp`;
- rotate50 `+1.64pp`;
- combined50 `+1.61pp`;
- R08 `-2.08pp`.

These are stress diagnostics only.

## Capacity / data-gate caveats

At 1bn VND, some GAP18 L15 policies reach roughly 12–13% maximum ADV20 participation in the modeled ledger. At 10bn VND the sensitivity exceeds 100% ADV20 and is not operationally credible without a nonlinear impact/partial-fill model.

Data gates remain fail-closed:

- PIT HOSE membership;
- price basis;
- corporate actions;
- PIT sector master.

No canonical HOSE, promotion or live-order claim is authorized.

## Decision

Do not continue threshold fishing for a stronger autonomous sell rule on the same historical sample.

Freeze the V79 result as:

- autonomous incumbent cut/exit: rejected;
- exact-L15 opportunity admission/replacement: forward-paper candidate;
- strongest economic challenger: `L15_SWAP50_WORST`;
- lower-intensity challenger: `L15_SWAP25_WORST`;
- idle-cash challenger: `L15_CASH_ADD25_SLOT`;
- combined drag-trigger rotation: rejected for now;
- C3 remains operational champion.
