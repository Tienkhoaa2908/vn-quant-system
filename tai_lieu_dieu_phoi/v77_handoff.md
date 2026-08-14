# V77 handoff — fresh paper OOS + data-lineage closure

## Current branch

`agent/v77-paper-oos-data-lineage`

V77 bắt đầu từ V76 result commit `e8050fde905c069f8e23e8616cdab24449f58e05`.

Frozen champion vẫn `C3_STABLE_3_PAST_IC_SHRUNK`. `V76_RIDGE_RANK` chỉ là zero-capital shadow.

## Vì sao V77 tồn tại

V76 learned-ranking real workstation result có 0/24 watchlist pass và 0 robust progression model. Ridge xử lý observed 2026 tốt nhưng pre-2026 P&L/rank-IC/winner-capture không đủ. Stop-rule đã kích hoạt: không thử tiếp architecture/hyperparameter trên cùng historical sample.

V77 do đó làm hai việc song song:

1. tạo fresh paper-OOS registry bất biến cho C3 vs Ridge;
2. audit PIT HOSE / price basis / corporate actions / PIT sector evidence trên local workstation.

Đọc theo thứ tự:

1. `tai_lieu_dieu_phoi/v76_workstation_result_20260814.md`;
2. `tai_lieu_dieu_phoi/v77_paper_oos_data_lineage_contract.md`;
3. file này;
4. `src/he_thong_dinh_luong/paper_oos_data_lineage_v77.py`;
5. `src/he_thong_dinh_luong/paper_oos_data_lineage_v77_driver.py`;
6. tests V77;
7. `scripts/run_v77_paper_oos_lineage_gitbash.sh`;
8. `.github/workflows/v77_paper_oos_lineage.yml`.

## Experiment freeze

First real workstation V77 run creates persistent ignored state:

`du_lieu/v77-paper-oos-state/`.

Do not delete/reset this directory after fresh OOS starts unless explicitly abandoning the experiment. `freeze_manifest.json` and captured signal CSVs are the paper-evidence chain.

Freeze locks model IDs, diagnostic GAP18 symbol set, allocator, original store SHA/HEAD and first market day. Historical 2026 performance is not fresh OOS.

## Signal cadence

V77 does not rebalance daily. It recomputes the already-frozen algorithms but appends a new target only when the completed monthly `source_signal_day` changes.

Current mid-August expected behavior with store ending around 2026-08-13:

- source monthly signal likely 2026-07-31;
- capture market day = latest local market day;
- C3 and Ridge Top10 captured at freeze;
- if no later market session exists yet, both paper books should be `PENDING_FIRST_EXECUTION`;
- next run after a new session should fill at that exact next open without adding a duplicate source-month signal.

This is the desired first-run state, not a failure.

## Current costs

Paper engine uses V70-like BASE research assumptions except transfer fee is not implemented in the M3 paper engine:

`V70_BASE_APPROX_NO_TRANSFER_FEE`.

Never compare tiny C3/Ridge differences as exact V70 BASE differences without accounting for this.

## Data gates

Expected current blockers from known store state:

- `PIT_HOSE_MEMBERSHIP_LINEAGE_INCOMPLETE`;
- `PRICE_BASIS_UNCONFIRMED`;
- `CORPORATE_ACTION_INVENTORY_INCOMPLETE`;
- `PIT_SECTOR_MASTER_INCOMPLETE`.

V77 scans local evidence JSON but does not download or invent proof. Fixtures never close gates. Price-basis external certificate must bind exact current store SHA.

Paper OOS is allowed with blockers; promotion/canonical/live remain false.

## First workstation artifact review

When the user uploads `UPLOAD_THIS_v77_PAPER_OOS_LINEAGE-*.zip`, inspect in this order:

1. provenance: branch/head/store SHA before/after;
2. `v77_report.json` status and freeze manifest;
3. verify `store_mutated=false`;
4. capture/source dates and Vietnam wall-date contract;
5. current C3 vs Ridge Top10 rankings;
6. signals appended exactly once per model/source month;
7. paper status. First run can legitimately have 0 fills / fresh sessions;
8. data-lineage blocker list and any evidence candidates;
9. no promotion/live authorization.

Do **not** demand historical P&L from V77. V70/V76 already provide historical P&L; V77's purpose is future unseen evidence.

## Subsequent workstation runs

Reuse the same branch/code until intentionally changed for bugfix only and keep the same state directory. A code change that changes model semantics invalidates continuity and requires an explicit new experiment version; do not silently mutate V77 algorithms.

After each new EOD/session, user can run the same one-shot script. It should:

- leave old signals immutable;
- fill previously pending orders at exact next open when price exists;
- update NAV;
- append a new model target only when the completed monthly source signal changes;
- rerun data-lineage audit.

## Stop / next decision

No V78 historical model research is implied.

Next substantive decision is one of:

- continue accumulating fresh OOS;
- close a specific data gate with real evidence;
- review promotion only after genuinely unseen evidence exists and data truth is adequate.

No live orders or automatic capital authorization are allowed.
