# DATA-GATE-CLOSURE-BATCH-01

Trạng thái: `PROPOSED`

Work package này chỉ được bắt đầu từ exact `main` sau khi PR chứa giao thức gói công việc lớn đã merge và CI hậu gộp thành công.

## 1. Outcome

Triển khai nền kỹ thuật đầy đủ để tiếp nhận, chuẩn hóa, kiểm tra và kiểm toán bằng chứng cho bốn data gate, sử dụng fixture tổng hợp và fail-closed contracts; đồng thời tạo action kit acquisition chạy trên workstation có mạng.

Kết quả cuối là một Draft PR xanh trên Ubuntu/Windows và một evidence package ngoài Git. Không cần chờ raw VN100 byte để bắt đầu các lane triển khai độc lập.

## 2. Đường găng

```text
VN100_POINT_IN_TIME_HISTORY_INCOMPLETE
HOSE_EOD_CROSSCHECK_INCOMPLETE
CORPORATE_ACTION_INVENTORY_INCOMPLETE
PRICE_BASIS_UNCONFIRMED
```

```text
RESEARCH_GATE=FAIL
```

## 3. Preflight

Bắt buộc thực hiện capability matrix theo `giao_thuc_goi_cong_viec_lon.md`.

Nếu outbound/raw download unavailable trong môi trường thực thi:

- không lặp lại 01F-C/01F-C2;
- tiếp tục implementation bằng fixture;
- tạo workstation action kit;
- ghi blocker rõ trong báo cáo cuối.

## 4. LANE A — VN100 PIT v2 foundation

Triển khai package phù hợp cấu trúc repository cho:

1. source-document registry candidate và validator;
2. raw extraction import contract;
3. stable `instrument_id` và alias interval;
4. normalized membership events;
5. review-cycle representation;
6. half-open interval builder;
7. conflict/gap detection;
8. tri-state membership query;
9. coverage certificate candidate;
10. deterministic manifest/publication candidate;
11. read-only independent auditor;
12. Mốc 4 research preflight fail closed.

Yêu cầu:

- giữ `pit_membership_v1` cho compatibility/fixture;
- không auto-detect/auto-convert;
- `technical_candidate_union_v1` không được dùng trong research;
- không có canonical open-ended interval;
- `UNKNOWN` không chuyển thành false;
- publication cutoff timezone-aware;
- expected count lấy từ contract/rulebook;
- không đặt `research_eligible=true` bằng fixture.

## 5. LANE B — acquisition workstation kit

Tạo CLI hoặc script cục bộ không gọi mạng trong CI, cho phép người dùng cung cấp URL hoặc file đã tải bằng browser.

Chức năng:

- lưu nguyên raw byte ngoài Git;
- không Save As hoặc reconstruct;
- tính SHA-256 hai invocation;
- ghi byte size;
- ghi collection timestamp timezone-aware;
- ghi HTTP metadata khi người dùng cung cấp;
- tạo source registry row;
- rights status;
- source locator metadata;
- search/acquisition log;
- evidence ZIP không chứa raw restricted documents;
- kiểm lại hashes của evidence products.

CLI phải hỗ trợ mode `--file` để không phụ thuộc outbound của Python runtime.

## 6. LANE C — HOSE EOD crosscheck và price basis

Triển khai contract và fixture cho:

- official/source candidate registry;
- stock EOD comparison schema;
- open/close/volume exact comparison;
- missing/duplicate/date mismatch;
- price scale mismatch;
- adjusted/unadjusted/unknown basis state;
- corporate-action interaction;
- per-symbol and per-date mismatch report;
- fail-closed research preflight.

Không sửa, nội suy hoặc thay raw value để làm cho khớp.

Không coi `CHUA_XAC_NHAN` là `dieu_chinh` hoặc `khong_dieu_chinh`.

## 7. LANE D — corporate-action inventory

Triển khai schema, validator và fixture cho:

```text
SPLIT
STOCK_DIVIDEND
CASH_DIVIDEND
RIGHTS_ISSUE
MERGER
DELIST
SYMBOL_CHANGE
TRANSFER
OTHER_OFFICIAL_ACTION
```

Bắt buộc có:

- source/provenance;
- publication timestamp;
- effective date;
- record/ex date khi có;
- payment date khi có;
- ratio/value;
- identity linkage;
- duplicate/conflict handling;
- adjusted-price compatibility;
- fail-closed preflight.

Không áp dụng event thật trong package này.

## 8. LANE E — audit và integration

- independent auditor không gọi builder để tự xác nhận;
- deterministic ordering;
- byte/hash reproducibility cho products được khóa;
- negative tests cho look-ahead, gap, overlap, identity ambiguity, count mismatch, hash mismatch và source conflict;
- boundary tests cho publication/effective dates;
- backward compatibility tests;
- full unit test suite;
- CI Ubuntu và Windows;
- docs và runbook.

## 9. File scope

Đoạn chuyên môn được tự xác định file chi tiết sau khi đọc repository, nhưng chỉ trong:

```text
src/vn_quant_system/
tests/
tai_lieu/
tai_lieu_dieu_phoi/
DECISIONS.md
README.md
```

Không đổi dependency hoặc workflow trừ khi có blocker kỹ thuật trực tiếp và phải escalation trước.

Không sửa PR #20 hoặc tài liệu Mốc 5.

## 10. Branch và PR

Tên nhánh đề xuất:

```text
data-gate-closure-batch-01
```

Một Draft PR duy nhất.

Được tự sửa tối đa ba vòng trong cùng PR mà không xin lại phép.

Không force-push, squash hoặc rebase.

## 11. Acceptance criteria

### Implementation

- registry, event, interval, coverage, audit và preflight contracts chạy được;
- acquisition kit chạy được với file fixture;
- EOD/price-basis và corporate-action schemas chạy được;
- no-network CI;
- no restricted raw data in Git.

### Safety

- research defaults fail closed;
- fixture không thể được promoted thành real evidence;
- no look-ahead;
- no survivorship fill;
- no implicit timezone;
- no interval forward-fill;
- no silent schema detection;
- no current constituents as history.

### Verification

- unit tests mới;
- negative and boundary tests;
- full regression;
- current-head CI Ubuntu/Windows;
- diff scope audit;
- independent audit report.

## 12. Escalation points

Chỉ quay lại đoạn `00` khi:

- cần đổi QĐ-0069;
- cần dependency mới;
- cần đổi public schema hiện hữu không tương thích;
- cần canonical promotion;
- cần mở research run;
- cần sửa PR #20/Mốc 5;
- package không thể đạt outcome do blocker toàn cục.

## 13. Báo cáo cuối

1. capability preflight;
2. architecture decisions;
3. implemented components;
4. branch/commits/PR;
5. changed files;
6. test matrix;
7. CI IDs;
8. acquisition kit commands;
9. evidence artifacts;
10. independent audit;
11. remaining data blockers;
12. next gate.

Phán quyết đề xuất đúng một trong:

```text
DATA_GATE_FOUNDATION_READY
DATA_GATE_FOUNDATION_PARTIAL
DATA_GATE_FOUNDATION_FAILED
```

Không tự mở package kế tiếp.
