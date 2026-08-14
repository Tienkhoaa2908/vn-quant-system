# V77 fresh paper-OOS + data-lineage contract

## Mục tiêu

V76 đã kích hoạt stop-rule: không tiếp tục model/factor/threshold fishing trên cùng historical sample. V77 chuyển sang hai việc có giá trị thông tin mới:

1. thu **fresh paper OOS** cho frozen C3 và một learned shadow đã khóa;
2. audit fail-closed các data gate còn mở để biết bằng chứng nào cần bổ sung trước canonical/promotion.

V77 **không phải vòng nghiên cứu model V77** và không được dùng để chọn kiến trúc mới.

## Model contract

Champion cố định:

`C3_STABLE_3_PAST_IC_SHRUNK`.

Shadow không vốn:

`V76_RIDGE_RANK`.

Không có LightGBM/XGBoost/model mới, không tune hyperparameter, không dùng P&L 2026 để đổi architecture. Ridge được giữ vì V76 cho thấy nó bắt VIC/TLG và xử lý 2026 tốt trong shadow, nhưng pre-2026 evidence không đủ nên không được promote.

## Fresh-OOS boundary

Lần chạy workstation V77 đầu tiên tạo `freeze_manifest.json` ngoài Git trong:

`du_lieu/v77-paper-oos-state/`.

Manifest khóa:

- freeze market day;
- store SHA tại thời điểm freeze;
- Git HEAD tại freeze;
- champion/shadow IDs;
- primary variant/allocator;
- fixed diagnostic symbol set;
- paper cost contract;
- không cho phép model mutation hoặc capital authorization.

Dữ liệu/return trước freeze **không được tính là fresh OOS**, kể cả 2026 đã quan sát.

Historical bars trước freeze chỉ được dùng để fit hai thuật toán đã khóa theo đúng causality cũ. Paper execution bắt đầu từ target được capture sau freeze.

Nếu state đã tồn tại, V77 phải xác minh model IDs, variant, allocator, cost contract và symbol-set shape vẫn khớp manifest. Drift phải fail closed.

## Paper signal semantics

Primary diagnostic universe: `GAP18_CLEAN`, nhưng symbol set được **freeze tại lần chạy đầu** để tránh universe drift sau khi nhìn kết quả. Đây vẫn không phải canonical HOSE universe vì PIT HOSE gate chưa đóng.

Primary allocator: Equal, Top10, 10% mỗi mã.

Mỗi invocation:

1. đọc latest market day từ local store;
2. dựng latest completed monthly frozen-C3 snapshot theo giờ/ngày Việt Nam;
3. fit lại đúng predeclared `V76_RIDGE_RANK` bằng completed labels trước source signal day;
4. capture Top10 của C3 và Ridge tại **capture market day**;
5. chỉ append signal khi `source_signal_day` thay đổi;
6. replay toàn bộ signal store bằng engine paper hiện có;
7. lệnh phát sinh sau capture day, fill ở exact next available session open.

Rerun nhiều lần trong cùng source month không tạo daily-rebalance giả. Trước khi coi rerun là idempotent, Top10/rank/score/risk-on của source month cũ phải recompute khớp signal đã freeze; drift phải fail closed.

Nếu EOD tháng vừa đóng đã xác nhận nhưng local wall date chưa sang tháng mới, runner cho phép opt-in `V77_MONTH_CLOSE_CONFIRMED=1`; mặc định không tự đoán.

## Timezone

Quyết định monthly completion dùng lịch Việt Nam UTC+07:00 (`Asia/Ho_Chi_Minh` semantics), không dùng UTC host date và không phụ thuộc OS tzdata.

## Paper execution/cost contract

V77 dùng:

- initial capital 1bn VND;
- lot 100;
- buy fee 2.7 bps;
- sell fee 2.7 bps;
- sell tax 10 bps;
- slippage 5 bps/side.

M3 paper engine hiện chưa có transfer fee 0.3 VND/share của V70 BASE và dùng default immediate cash reuse, không phải V70 T+2/no-advance. PIT sector cap cũng chưa enforce khi sector gate còn mở.

Vì vậy V77 ghi rõ:

`V70_BASE_APPROX_NO_TRANSFER_FEE`

và report thêm execution limitations:

- `M3_ENGINE_DEFAULT_IMMEDIATE_CASH_REUSE`;
- `t2_no_advance_modeled=false`;
- `transfer_fee_vnd_per_share_modeled=false`;
- `pit_sector_cap_enforced=false`.

Không được gọi đây là exact V70 BASE P&L. Hai model dùng cùng paper contract nên vẫn dùng được cho fresh comparative evidence. Không gửi live order.

## Persistent state

State nằm dưới ignored path:

`du_lieu/v77-paper-oos-state/`

Tối thiểu gồm:

- `freeze_manifest.json`;
- `signals/<model>/...csv` bất biến.

Runner không xóa state giữa các lần chạy. Artifact upload chỉ snapshot manifest + signals + output hiện tại; state workstation là source of truth cho paper OOS continuity.

Cùng source day không được append signal khác. Conflict hoặc recompute drift phải fail closed.

## Data-lineage audit

V77 read-only audit local store + evidence JSON ở các search roots. Store SHA trước/sau invocation bắt buộc giống nhau.

Bốn blocker canonical:

1. `PIT_HOSE_MEMBERSHIP_LINEAGE_INCOMPLETE`;
2. `PRICE_BASIS_UNCONFIRMED`;
3. `CORPORATE_ACTION_INVENTORY_INCOMPLETE`;
4. `PIT_SECTOR_MASTER_INCOMPLETE`.

Paper OOS được phép chạy khi blocker còn mở, nhưng:

- canonical HOSE claim = false;
- research promotion = false;
- live authorization = false.

### PIT HOSE

Dedicated HOSE contracts được nhận trực tiếp:

- `pit_hose_membership_v1`;
- `hose_membership_interval_v1`.

Foundation contract `pit_membership_interval_v2` cũng có thể được audit, **nhưng nó chỉ đóng PIT-HOSE gate nếu record có explicit `venue_scope`, `exchange` hoặc `market` bằng `HOSE`**. Generic VN100/index membership coverage không chứng minh venue HOSE và không được đóng gate.

Mọi bằng chứng phải non-fixture, `research_eligible=true`, complete, không gaps/conflicts và cover target day.

### Price basis

Pass nếu local store dùng duy nhất một explicit basis recognized `ADJUSTED` hoặc `UNADJUSTED`.

Nếu store vẫn `CHUA_XAC_NHAN`, chỉ external `price_basis_certificate_v1` non-fixture/research-eligible, `confirmed=true`, basis explicit và **bound exact store SHA256** mới có thể đóng gate.

### Corporate actions

Certificate phải đến từ corporate-action evidence file, non-fixture, `inventory_complete=true`, `research_eligible=true`, không conflict và cover target day.

### PIT sector

Contract `pit_sector_master_v1`, non-fixture/research-eligible, complete, no gap/conflict, cover target day.

## Outputs

Mỗi run tạo trong artifact output:

- `v77_report.json`;
- `v77_current_rankings.csv`;
- `v77_paper_summary.csv`;
- per-model NAV/fills/orders/positions;
- `v77_data_lineage_report.json`;
- `v77_evidence_requirements.json`;
- `v77_freeze_manifest_copy.json`.

Khi chưa có session sau freeze, trạng thái đúng là `PENDING_FIRST_EXECUTION`; đây không phải lỗi.

## Promotion rule

Không đặt số tháng tối thiểu tùy tiện trong V77 để tránh tạo một promotion threshold mới sau khi nhìn data. V77 chỉ **thu evidence**.

Bất kỳ quyết định promotion sau này phải là một review riêng, dùng fresh observations đã được thu bất biến và data gates thích hợp. Historical V76 result không được cộng vào fresh-OOS sample.

## Safety

- no market-store mutation;
- no live orders;
- no automatic capital;
- no champion replacement;
- no historical architecture fishing;
- no future-price substitution;
- no retroactive paper entry;
- no overwriting frozen signal history;
- generic membership evidence cannot masquerade as HOSE venue proof;
- CI synthetic success không thay thế first real workstation freeze/artifact.
