# Bản điều phối hiện hành

Cập nhật: 2026-07-29

Tài liệu này là snapshot current-state. Nếu các tài liệu trạng thái tích lũy cũ mâu thuẫn với tài liệu này, dùng tài liệu này cùng merged `main` và `DECISIONS.md`.

## 1. Anchor

```text
repository: Tienkhoaa2908/vn-quant-system
main: c1ca73e39714e34b1693422aa051386b13a6a15c
last_merged_pr: 25
post_merge_ci: 30449420185
ubuntu_job: 90567628616
windows_job: 90567628691
ci_conclusion: success
```

PR #20 vẫn Open/Draft/Unmerged và không thuộc phạm vi active.

## 2. Trạng thái kỹ thuật

- Mốc 0–4 đã có implementation nền và technical validation.
- Lần chạy kỹ thuật rộng Mốc 4 đã hoàn tất với 121 mã nguồn, 120 mã có prediction, 36 fold và 34 fold thành công.
- Logistic Regression là baseline kỹ thuật và yếu hơn momentum trong lần chạy rộng.
- Không có research claim, alpha claim hoặc tín hiệu vận hành.
- Mốc 5 tiếp tục tạm dừng.

## 3. Data gates hiện hành

```text
VN100_POINT_IN_TIME_HISTORY_INCOMPLETE
HOSE_EOD_CROSSCHECK_INCOMPLETE
CORPORATE_ACTION_INVENTORY_INCOMPLETE
PRICE_BASIS_UNCONFIRMED
RESEARCH_GATE=FAIL
```

Bốn data gate là đường găng hiện tại.

## 4. Kết quả 01F-A đến 01F-C2

- 01F-A đã khóa contract `pit_membership_interval_v2` và merge qua PR #25.
- 01F-B xác định source inventory đủ một phần để mở controlled acquisition.
- 01F-C và 01F-C2 đều không nhận được raw source byte trong môi trường ChatGPT.
- 01F-C2 ghi:

```text
document_count_planned=8
document_count_acquired=0
document_count_chain_verified=0
document_count_canonical_eligible=0
OFFICIAL_BYTE_RECOVERY_PARTIAL
```

Không tiếp tục phát prompt official-byte recovery trong cùng môi trường. Đây là capability blocker, không phải prompt-quality blocker.

## 5. Thay đổi điều phối

Từ thời điểm này, dự án dùng `WORK_PACKAGE` theo `giao_thuc_goi_cong_viec_lon.md`.

Mặc định:

- một prompt cho cả package;
- một nhánh và một Draft PR;
- nhiều lane song song;
- tự sửa trong cùng PR;
- chỉ quay lại đoạn `00` cho quyết định ngữ nghĩa, mở scope, quyền truy cập hoặc canonical promotion;
- không tạo prompt mới để thử lại capability đã xác định unavailable.

## 6. Work package đường găng tiếp theo

```text
DATA-GATE-CLOSURE-BATCH-01
```

Outcome dự kiến:

Triển khai nền kỹ thuật đóng data gate bằng dữ liệu fixture tổng hợp và công cụ acquisition cục bộ, đồng thời điều tra ba blocker dữ liệu còn lại. Package không cần chờ raw VN100 byte mới bắt đầu các phần độc lập.

### LANE A — VN100 PIT v2 implementation

- source-document registry schema và validator;
- extraction import contract;
- stable instrument/alias contract;
- normalized membership events;
- half-open interval builder;
- tri-state as-of evaluation;
- coverage certificate builder;
- read-only auditor;
- deterministic publication;
- synthetic fixtures và negative tests;
- Mốc 4 research preflight integration ở trạng thái fail closed.

Không dùng fixture làm dữ liệu thật và không đặt `research_eligible=true`.

### LANE B — acquisition workstation kit

Tạo công cụ chạy cục bộ để người dùng chỉ cần cung cấp URL hoặc file tải bằng browser:

- lưu raw byte ngoài Git;
- HTTP/file metadata;
- SHA-256 hai lần;
- manifest;
- rights status;
- source locator;
- evidence ZIP không chứa raw restricted files.

ChatGPT không tự lặp download khi outbound unavailable.

### LANE C — HOSE EOD và price basis

- inventory nguồn đối chiếu EOD chính thức;
- contract so sánh open/close/volume và corporate-action adjustment;
- mismatch report schema;
- fixture và tests;
- không sửa hoặc suy diễn raw market values.

### LANE D — corporate actions

- inventory schema cho split, stock dividend, cash dividend, rights, merger, delist và symbol transfer;
- publication/effective/payment cutoff;
- duplicate and conflict rules;
- fixture và tests;
- kết nối preflight, chưa áp dụng dữ liệu thật.

### LANE E — audit và tài liệu

- independent contract audit;
- boundary/look-ahead/survivorship tests;
- cross-platform CI;
- runbook người dùng;
- một báo cáo cuối và một Draft PR.

## 7. Cửa package

Package chỉ được nghiệm thu khi:

- full test Ubuntu/Windows đạt;
- backward compatibility của `pit_membership_v1` và technical union giữ nguyên;
- không có raw restricted data trong Git;
- không tự hạ research mode thành technical mode;
- mọi canonical gate mặc định fail closed;
- PR #20 không thay đổi;
- Mốc 5 không mở.

## 8. Công việc song song được phép

Trong khi DATA-GATE-CLOSURE-BATCH-01 chạy, người dùng có thể thực hiện đúng một action kit acquisition trên workstation có mạng. Kết quả được nhập vào package sau, không làm dừng implementation bằng fixture.

Không mở model optimization implementation. Được phép chuẩn bị protocol đánh giá model trong tài liệu, nhưng không tuning trên dữ liệu research chưa đạt gate.

## 9. Next gate duy nhất

Sau khi DATA-GATE-CLOSURE-BATCH-01 có Draft PR xanh và evidence acquisition thực tế được gửi, đoạn `00` sẽ quyết định:

```text
NONCANONICAL_DATA_PIPELINE_READY
hoặc
DATA_GATE_FOUNDATION_NEEDS_REPAIR
```

Chưa có quyền tuyên bố bất kỳ blocker nào resolved.
