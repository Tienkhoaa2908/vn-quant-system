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
3. `tai_lieu_dieu_phoi/v77_workstation_result_20260814.md`;
4. file này;
5. `src/he_thong_dinh_luong/paper_oos_data_lineage_v77.py`;
6. `src/he_thong_dinh_luong/paper_oos_data_lineage_v77_driver.py`;
7. tests V77, đặc biệt `test_paper_oos_data_lineage_v77_causal_floor.py`;
8. `scripts/run_v77_paper_oos_lineage_gitbash.sh`;
9. `.github/workflows/v77_paper_oos_lineage.yml`.

## First real workstation freeze — observed

Artifact first-freeze ngày 2026-08-14 đã được đọc và lưu bền ở `v77_workstation_result_20260814.md`.

Observed provenance:

- artifact HEAD `2aa8c143312fc689e90f042e3f1dd892bf22cc6d`;
- store SHA `2959f8cce0c11e8e4186fcb49ae75bf7babf86b84afe64ca3b843a7470d58b1a` before/after giống nhau;
- Python 3.12.13 canonical `.venv`;
- scikit-learn 1.9.0;
- 10/10 workstation regressions PASS;
- freeze market day/capture market day `2026-08-13`;
- actual Vietnam capture wall date `2026-08-14`;
- source monthly signal `2026-07-31`;
- fixed GAP18 symbol set 111 names;
- C3/Ridge đều 0 fills, 0 fresh sessions, NAV 1bn, `PENDING_FIRST_EXECUTION`.

C3 Top10 first freeze:

`VPI, MSB, HCM, VIC, GMD, LPB, STB, BAF, DHC, ACB`.

Ridge Top10 first freeze:

`BSR, VPI, GMD, BAF, LPB, NAB, BMP, ACB, MSB, VNM`.

Top10 overlap 6/10: `VPI, GMD, BAF, LPB, ACB, MSB`.

No performance inference is allowed yet because fresh session count is zero.

## Experiment freeze

Persistent ignored state:

`du_lieu/v77-paper-oos-state/`.

**Do not delete/reset it.** The first freeze target itself remains valid because no execution/fill occurred before the causal bug was discovered.

Freeze locks model IDs, diagnostic GAP18 symbol set, allocator, paper-cost contract, original store SHA/HEAD and first market day. Historical 2026 performance is not fresh OOS.

Existing state is fail-closed: model/variant/allocator/cost-definition drift aborts. A rerun of an already-captured monthly source signal must recompute the same Top10/rank/score/risk-on before idempotent reuse.

## Critical causal execution patch after first artifact

Artifact review found a causal bug before any fill:

- target was actually captured at Vietnam evening 2026-08-14;
- store still ended at 2026-08-13;
- old replay anchored the pending order to market day 2026-08-13;
- after a later sync of 2026-08-14 bars, old logic could have filled at open 2026-08-14, which happened before target capture.

That is forbidden retroactive execution.

Bugfix contract now is:

`FIRST_MARKET_SESSION_ON_OR_AFTER_CAPTURE_VN_DATE_PLUS_1`

For the already-frozen first target, `captured_at` implies causal floor date `2026-08-15`. The first allowed fill is the first actual market session on or after that date. A 2026-08-14 fill must fail closed even if those bars are added later.

Implementation lives in the V77 safe driver and reuses the immutable `captured_at` already written in each frozen signal CSV. It does **not** alter C3/Ridge model semantics or reselect the frozen targets.

The driver reports:

- `causal_execution_floor_verified`;
- per-model `execution_floor_contract`;
- `execution_floor_by_signal_day`;
- `earliest_execution_floor_date`;
- `retroactive_fill_count` which must be 0.

Synthetic regression covers both cases:

1. store adds a session that occurred before capture -> still pending, no fill, no fresh session;
2. store later contains a session on/after the floor -> fill occurs there, not earlier.

## Signal cadence

V77 does not rebalance daily. It recomputes the already-frozen algorithms but appends a new target only when completed monthly `source_signal_day` changes.

Rerun in the same source month must not append a duplicate target. Monthly-completion uses Vietnam UTC+07:00 semantics and does not depend on Windows/Linux tzdata.

## Current paper execution contract

Comparative assumptions for C3 and Ridge:

- initial capital 1bn VND;
- Equal Top10;
- lot 100;
- buy/sell fee 2.7 bps;
- sell tax 10 bps;
- slippage 5 bps/side;
- causal wall-clock execution floor as above.

Contract label:

`V70_BASE_APPROX_NO_TRANSFER_FEE`.

Important limitations:

- M3 engine uses immediate cash reuse, not V70 `T+2/no-advance`;
- transfer fee 0.3 VND/share is not modeled;
- PIT sector 25% cap is not enforced while sector gate is open.

Do **not** call V77 exact V70 BASE P&L. It is a frozen comparative paper lane; both models use the same contract.

## Data gates — observed first freeze

All four remain closed:

- `PIT_HOSE_MEMBERSHIP_LINEAGE_INCOMPLETE`;
- `PRICE_BASIS_UNCONFIRMED`;
- `CORPORATE_ACTION_INVENTORY_INCOMPLETE`;
- `PIT_SECTOR_MASTER_INCOMPLETE`.

Observed store:

- 300,541 bars;
- 121 stock symbols;
- 2015-06-29 -> 2026-08-13;
- all 300,541 bars `price_basis=CHUA_XAC_NHAN`;
- no exchange lineage in bars;
- 40 basis-gap events;
- evidence scan found 0 candidate JSON files in searched roots.

V77 does not download or invent proof. Fixtures never close gates. Price-basis external certificate must bind exact current store SHA.

For PIT HOSE, dedicated contracts `pit_hose_membership_v1` / `hose_membership_interval_v1` can prove venue when all fail-closed fields pass. Generic `pit_membership_interval_v2` **does not prove HOSE by itself**; it may close the gate only if `venue_scope`, `exchange`, or `market = HOSE` is explicit.

Paper OOS is allowed with blockers; promotion/canonical/live remain false.

## Next workstation run

Reuse the **same** `du_lieu/v77-paper-oos-state/`.

Do not manually edit/remove the first signal files. Pull the causal-floor bugfix first. Then run the same one-shot V77 runner.

Expected behavior if store only gains 2026-08-14 data:

- same July source target;
- no duplicate signal;
- no 2026-08-14 fill;
- `fresh_oos_session_count=0`;
- orders remain pending because causal floor has not reached an executable session.

When a later actual market session on/after the floor is present, the pending target may fill at that session open and fresh OOS starts there.

## Stop / next decision

No V78 historical model research is implied.

Next substantive decision is one of:

- continue accumulating fresh OOS under this exact frozen state + causal floor;
- close a specific data gate with real evidence;
- review promotion only after genuinely unseen evidence exists and data truth is adequate.

No live orders or automatic capital authorization are allowed.
