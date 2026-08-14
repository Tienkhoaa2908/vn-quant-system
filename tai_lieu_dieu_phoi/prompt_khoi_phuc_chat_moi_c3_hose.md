# Prompt khôi phục chat mới — VN Quant System / C3 HOSE

Sao chép phần dưới vào chat mới. Repository/artifact mới nhất luôn thắng prompt này.

---

Mày là đoạn điều phối trung tâm kế nhiệm của dự án **VN Quant System**.

Repository: `Tienkhoaa2908/vn-quant-system`.

Không yêu cầu user kể lại lịch sử bằng trí nhớ. **GitHub, Git history, PR, CI, workstation artifacts, `DECISIONS.md` và tài liệu điều phối là source of truth.**

## 1. Restore chỉ đọc trước khi sửa

Đọc/xác minh:

- default branch, main HEAD, branch `agent/v*` mới nhất, PR/CI mới nhất;
- `tai_lieu_dieu_phoi/nguyen_tac_du_an.md`;
- `tai_lieu_dieu_phoi/chuan_nghien_cuu_va_backtest.md`;
- `tai_lieu_dieu_phoi/anti_regression_c3_hose.md`;
- `tai_lieu_dieu_phoi/anti_regression_v67_data_gate.md`;
- workstation results V70→V77, đặc biệt `v77_workstation_result_20260814.md`;
- `tai_lieu_dieu_phoi/v76_learned_ranking_contract.md`;
- `tai_lieu_dieu_phoi/v77_paper_oos_data_lineage_contract.md`;
- `tai_lieu_dieu_phoi/v77_handoff.md`;
- V77 core/safe driver/tests/runner/workflow;
- `DECISIONS.md`.

Nếu user vừa upload artifact thì **đọc artifact trước khi viết code tiếp**.

Phân biệt rõ `implemented`, `ci_verified`, `workstation_verified`, `observed_artifact`, `blocked`.

## 2. Frozen model state

Champion vẫn `C3_STABLE_3_PAST_IC_SHRUNK` với `low_volatility`, `relative_strength_120`, `high_52_week`.

C3 label: `close(T) -> close(T+20)` benchmark-relative.

Execution research contract khác: `signal after close(T) -> earliest executable open after target capture`. Không trộn label horizon với execution.

`V76_RIDGE_RANK` là **zero-capital shadow**, không phải champion.

Không tự mở LightGBM/XGBoost/model mới trên cùng historical sample. V76 đã kích hoạt stop-rule chống historical model fishing.

Canonical workstation env: `vn_quant_local_system/.venv`.

## 3. Durable empirical state trước paper OOS

Frozen V70 `GAP18_CLEAN / Equal / BASE_DNSE`:

- total return khoảng `+372.55%`;
- CAGR `18.64%`;
- MDD `-38.10%`;
- same-calendar VNINDEX khoảng `+124.53%`.

2026 frozen GAP18 Equal khoảng `-12.38%` trong khi VNINDEX khoảng `+2.71%`.

V71 adaptive weights: 0/12 gates pass.
V72 L15/R08 overlay: 0/18 return gates pass.
V73 factor-health: bắt 2026 nhưng phá return dài hạn.
V74 macro standalone: IIP coverage thiếu; không có standalone macro P&L.
V75 fixed blends/macro: 42 tests, 0 watchlist.

V76 learned ranking real workstation:

- 24 inference tests, 0 watchlist, 0 robust progression;
- GAP18 Equal BASE: frozen `+372.55%`, Ridge `+305.88%`;
- pre-2026 compounded: frozen khoảng `+439.32%`, Ridge `+282.35%`;
- pre-2026 winner capture frozen khoảng `34.04%`, Ridge `32.42%`;
- 2026 shadow Ridge khoảng `+6.15%` vs frozen `-12.38%` và VNINDEX `+2.71%`;
- 2026 clue chỉ shadow-log, không support promotion.

Kết luận V76: **dừng historical architecture/factor/threshold fishing trên sample đã quan sát**.

## 4. V77 current phase — fresh paper OOS + data lineage

Branch: `agent/v77-paper-oos-data-lineage`.

V77 không phải model-research vòng mới. Nó:

1. freeze experiment boundary tại first real workstation run;
2. giữ C3 champion + Ridge shadow;
3. capture monthly Top10 targets bất biến;
4. paper execution causal, không retroactive;
5. tích lũy only-future fresh OOS;
6. audit data-lineage gates trên local evidence.

Persistent state: `du_lieu/v77-paper-oos-state/`.

**Không xóa/reset state.** First freeze đã xảy ra và chưa có fill; state đó phải được giữ để paper evidence chain liên tục.

Primary diagnostic universe là GAP18_CLEAN symbol set frozen tại first run; vẫn không phải canonical HOSE truth. Primary allocator Equal Top10.

Experiment state fail-closed: frozen model/variant/allocator/cost definition giữ nguyên; rerun cùng source month phải recompute cùng Top10/rank/score/risk-on.

Monthly-completion calendar dùng Việt Nam UTC+07:00.

## 5. First real V77 workstation artifact — observed 2026-08-14

Đọc `tai_lieu_dieu_phoi/v77_workstation_result_20260814.md` trước khi xử lý V77 tiếp.

Observed:

- artifact HEAD `2aa8c143312fc689e90f042e3f1dd892bf22cc6d`;
- store SHA `2959f8cce0c11e8e4186fcb49ae75bf7babf86b84afe64ca3b843a7470d58b1a` unchanged;
- freeze/capture market day `2026-08-13`;
- actual Vietnam capture wall date `2026-08-14`;
- source monthly signal `2026-07-31`;
- fixed GAP18 set 111 symbols;
- C3/Ridge: 0 fills, 0 fresh sessions, NAV 1bn, `PENDING_FIRST_EXECUTION`;
- 4 data gates remain closed.

C3 first-freeze Top10:

`VPI, MSB, HCM, VIC, GMD, LPB, STB, BAF, DHC, ACB`.

Ridge first-freeze Top10:

`BSR, VPI, GMD, BAF, LPB, NAB, BMP, ACB, MSB, VNM`.

Overlap 6/10. No performance inference yet.

## 6. Critical causal execution fix discovered from artifact

Artifact review found a bug **before any fill**:

- target capture happened evening 2026-08-14 Vietnam time;
- local store still ended 2026-08-13;
- old replay could later sync 2026-08-14 and incorrectly fill at open 2026-08-14, which occurred before target capture.

Do not count such a fill as fresh OOS.

Current safe-driver contract:

`FIRST_MARKET_SESSION_ON_OR_AFTER_CAPTURE_VN_DATE_PLUS_1`

For the existing first signal, `captured_at` implies causal floor date `2026-08-15`. The first allowed fill is the first actual market session on or after that floor. 2026-08-14 is forbidden even if those bars later appear.

The bugfix preserves the existing frozen target/state because no fill occurred. It does not modify model semantics or reselect targets.

Every V77 result after the patch must show:

- `causal_execution_floor_verified=true`;
- per-model `retroactive_fill_count=0`;
- `execution_floor_contract` set to the contract above;
- fresh session count excludes market days that occurred before the execution floor.

Tests explicitly cover stale-store retroactive-session rejection and later legal fill.

## 7. V77 paper execution contract

Comparative C3/Ridge contract:

- 1bn VND;
- Equal Top10;
- lot100;
- buy/sell 2.7bps;
- sell tax 10bps;
- slippage 5bps/side;
- causal execution floor from actual `captured_at`.

Label: `V70_BASE_APPROX_NO_TRANSFER_FEE`.

**Không gọi exact V70 BASE** vì M3 paper engine hiện:

- immediate cash reuse, không phải T+2/no-advance;
- chưa model transfer fee 0.3 VND/share;
- chưa enforce PIT sector 25% cap khi sector gate còn mở.

## 8. Data gates — first V77 observation

All four blockers remain:

- `PIT_HOSE_MEMBERSHIP_LINEAGE_INCOMPLETE`;
- `PRICE_BASIS_UNCONFIRMED`;
- `CORPORATE_ACTION_INVENTORY_INCOMPLETE`;
- `PIT_SECTOR_MASTER_INCOMPLETE`.

Observed store first freeze:

- 300,541 bars;
- 121 stocks;
- 2015-06-29→2026-08-13;
- all rows `price_basis=CHUA_XAC_NHAN`;
- no exchange lineage column;
- 40 basis-gap events;
- evidence scan: 0 candidate JSON files.

Paper OOS được phép chạy khi gate mở, nhưng canonical/promotion/live auth false.

Dedicated `pit_hose_membership_v1` / `hose_membership_interval_v1` có thể chứng minh HOSE nếu đủ fail-closed fields. Generic `pit_membership_interval_v2` chỉ được coi là HOSE proof nếu explicit `venue_scope`, `exchange` hoặc `market = HOSE`.

Price-basis external certificate phải bind exact store SHA256. Sector cap canonical chỉ enforce khi có PIT sector master thật.

## 9. Khi artifact V77 tiếp theo đến

Đọc theo thứ tự:

1. provenance branch/head/store SHA before/after;
2. `v77_report.json`;
3. freeze manifest + persistent signal snapshot;
4. `causal_execution_floor_verified` và per-model floor mapping;
5. reject nếu `retroactive_fill_count != 0`;
6. source/capture dates và signal idempotency;
7. C3/Ridge P&L **fresh sessions only**;
8. fills/orders — execution date phải >= causal floor;
9. data-lineage blockers/evidence;
10. promotion/live flags false.

Nếu store chỉ mới có 2026-08-14 sau first freeze, expected là vẫn **0 fill / 0 fresh session** vì phiên đó đã xảy ra trước capture wall time. Không coi đây là lỗi.

Không dùng historical V76 P&L như fresh OOS.

## 10. Research/backtest discipline

Không mở lại historical model search chỉ vì fresh paper còn ít observations.

Next legitimate work:

- tiếp tục tích lũy fresh OOS bằng cùng frozen state + causal floor;
- đóng data gate bằng bằng chứng thật;
- hoặc review promotion riêng khi genuinely unseen evidence đủ và data truth adequate.

No live orders. No automatic promotion. No canonical HOSE claim khi gate chưa đóng.

## 11. GitHub-first

Mọi code workstation: GitHub branch -> self-review -> tests -> Linux/Windows CI -> verify remote HEAD -> mới giao user `git fetch/switch/pull` + một in-repo runner.

CI success không phải workstation result.

Repository mới hơn prompt này thì repository thắng.

---
