# Kiến trúc dữ liệu VN100 point-in-time v2

## 1. Phạm vi kiến trúc

Tài liệu này mô tả kiến trúc dự kiến cho contract `pit_membership_interval_v2`. Đây là kiến trúc, chưa phải package hoặc production code. Không có lời gọi mạng, acquisition thật, parser thật hoặc publication dữ liệu thật trong lát cắt `01F-A`.

Luồng tổng thể:

```text
source documents
→ immutable registry
→ extraction
→ identity resolution
→ normalized events
→ interval construction
→ review-cycle reconciliation
→ gap/conflict validation
→ coverage certificate
→ atomic publication
→ read-only audit
→ as-of API
→ Mốc 4 research preflight
```

## 2. Ranh giới canonical

Dữ liệu đi qua ba vùng:

```text
RAW_EVIDENCE
NONCANONICAL_NORMALIZED
CANONICAL_PUBLICATION
```

- `RAW_EVIDENCE`: byte và metadata nguồn bất biến; có thể chưa đầy đủ hoặc mâu thuẫn.
- `NONCANONICAL_NORMALIZED`: extraction, identity candidate, event candidate, conflict và gap; không được dùng cho research.
- `CANONICAL_PUBLICATION`: chỉ gồm record VERIFIED, interval đã chứng minh, coverage certificate đạt và manifest/hash hợp lệ.

Không có đường tắt từ raw hoặc technical candidate union sang canonical publication.

## 3. Tầng 1 — Source documents

### Input

- tài liệu nguồn được thu thập có kiểm soát;
- metadata HTTP hoặc metadata tương đương nếu có;
- chính sách quyền lưu trữ.

### Output

- raw byte ngoài Git khi quyền chưa rõ;
- metadata candidate cho registry.

### Invariant

- không sửa byte;
- không tải hàng loạt trong CI;
- không bịa URL hoặc endpoint;
- mỗi acquisition có collection timestamp timezone-aware;
- cùng URL trả byte khác tạo document mới.

### Fail closed

Thiếu byte, URL/provenance cần thiết hoặc quyền xử lý không rõ thì không chuyển tài liệu sang VERIFIED canonical source.

## 4. Tầng 2 — Immutable registry

### Input

Raw byte và metadata acquisition.

### Output

`source_document_registry` append-only với `source_document_id`, SHA-256, size, content type, URL, collection time, publication metadata, storage policy và verification status.

### Invariant

- SHA-256 tính từ byte gốc;
- document ID duy nhất;
- không ghi đè;
- ETag không thay SHA-256;
- sort publication theo `source_document_id` hoặc khóa canonical đã quy định;
- registry record không tự chứng minh membership.

### Fail closed

- hash mismatch;
- thiếu source locator khả dụng ở các tầng sau;
- document status không VERIFIED.

## 5. Tầng 3 — Extraction

### Input

Verified hoặc candidate source document từ registry.

### Output

Raw extraction rows có locator, raw text, raw symbol/date/action và parser/reviewer metadata.

### Invariant

- extraction giữ nguyên raw representation;
- parser version explicit;
- mọi row trỏ đến source document;
- manual entry dùng `MANUAL_DOUBLE_ENTRY` và hai reviewer;
- output order xác định theo `source_document_id,page,table,row,extraction_id`.

### Fail closed

- missing locator;
- hai reviewer mâu thuẫn;
- parser không xác định version;
- extraction không truy lại được raw evidence.

## 6. Tầng 4 — Identity resolution

### Input

Extraction rows, tài liệu identity và alias history cần thiết trong khoảng thu thập.

### Output

- `instrument_id` canonical;
- alias interval `ma,san,valid_from,valid_to_exclusive`;
- identity conflict rows.

### Invariant

- membership dùng `instrument_id`;
- alias dùng interval half-open;
- không map cùng alias/time sang hai instrument;
- không dùng tên công ty tương tự làm bằng chứng duy nhất;
- MVP chỉ giải quyết identity cần cho source range, không xây master-data toàn thị trường.

### Fail closed

Identity không duy nhất tạo `MEMBERSHIP_SYMBOL_IDENTITY_AMBIGUOUS`; event/interval liên quan ở lại noncanonical.

## 7. Tầng 5 — Normalized events

### Input

Extraction đã resolve identity và publication metadata.

### Output

Membership events normalized: `ADD`, `REMOVE`, `REPLACE`, `SYMBOL_CHANGE`, `DELIST`, `TRANSFER`, `MERGER`, `OTHER_OFFICIAL_ADJUSTMENT`.

### Invariant

- event có effective date;
- publication timestamp timezone-aware khi cutoff yêu cầu;
- event trỏ đến document/hash/locator;
- không sửa snapshot/event raw;
- duplicate business event bị từ chối hoặc đưa vào conflict set;
- output sort theo `ten_chi_so,ngay_hieu_luc,thoi_diem_cong_bo,instrument_id,membership_event_id`.

### Fail closed

Missing effective date, source, locator, identity hoặc publication cutoff tạo error code và ngăn canonical event.

## 8. Tầng 6 — Interval construction

### Input

- complete snapshot candidates;
- normalized events;
- identity map;
- rulebook/index contract theo giai đoạn.

### Output

Membership interval candidates:

```text
[ngay_hieu_luc, ngay_ket_thuc_hieu_luc)
```

### Invariant

- end exclusive;
- không open-ended canonical interval;
- không suy ra end chỉ vì có snapshot gần nhất nếu cycle/event coverage chưa chứng minh;
- cùng instrument/index không có interval MEMBER chồng lấn;
- mỗi query date thuộc không quá một segment index candidate;
- output sort theo `ten_chi_so,ngay_hieu_luc,ngay_ket_thuc_hieu_luc,instrument_id`.

### Fail closed

- `MEMBERSHIP_INTERVAL_OVERLAP`;
- `MEMBERSHIP_INTERVAL_AMBIGUOUS`;
- `MEMBERSHIP_INTERVAL_END_UNPROVEN`;
- `MEMBERSHIP_LOOKAHEAD_RISK`.

## 9. Tầng 7 — Review-cycle reconciliation

### Input

Interval candidates, rulebook version, complete list/event evidence và expected cycle inventory.

### Output

Review-cycle rows với expected/observed member count, source documents, reconciliation status và coverage status.

### Invariant

- `expected_member_count` lấy từ contract/rulebook giai đoạn;
- framework chung không hard-code 100;
- đối với VN100, chỉ canonical khi tài liệu chính thức chứng minh expected count 100 và observed count khớp;
- add/remove giữa hai cycle phải reconcile;
- extraordinary event được chèn đúng effective date;
- derived VN100 chỉ dùng khi rulebook đúng giai đoạn cho phép và mọi parent publication canonical.

### Fail closed

- missing cycle;
- rulebook version missing;
- unauthorized derivation;
- count mismatch;
- review incomplete.

## 10. Tầng 8 — Gap/conflict validation

### Input

Reconciled cycles, intervals, source hierarchy và requested range candidate.

### Output

- gap report;
- conflict report;
- overlap report;
- look-ahead risk report;
- blocking error list.

### Invariant

- không forward-fill qua gap;
- missing cycle tạo explicit gap interval;
- nguồn cấp thấp không tự lấp gap;
- conflict cùng cấp không resolve bằng timestamp đơn thuần;
- `UNKNOWN` được bảo toàn;
- deterministic sort theo period, error code, field và source ID.

### Fail closed

Bất kỳ blocking error nào giữ publication noncanonical và `research_eligible=false`.

## 11. Tầng 9 — Coverage certificate

### Input

Validated intervals/cycles, gap/conflict reports, manifest hashes và target range status.

### Output

Coverage certificate có:

```text
membership_contract_version=pit_membership_interval_v2
target_research_range_status=TARGET_RESEARCH_RANGE_PROVISIONAL
research_eligible
blocking_error_codes
coverage_by_day
coverage_by_cycle
coverage_by_document
coverage_by_instrument
```

### Invariant

- chưa khóa start/end canonical trong lát cắt này;
- range change phải quay lại đoạn `00`;
- mọi ngày trong requested range phải thuộc đúng một segment canonical;
- certificate trỏ đến source và normalized manifest hash;
- certificate không tự tuyên bố `research_eligible=true` khi range còn provisional và chưa được phê duyệt.

### Fail closed

Thiếu certificate, hash sai, range không bao phủ hoặc blocking error không rỗng làm research preflight dừng.

## 12. Tầng 10 — Atomic publication

### Input

Canonical candidate products, coverage certificate, conflict/gap reports, provenance metadata và explicit build configuration.

### Output

Publication directory mới, dự kiến gồm các nhóm:

```text
source_document_manifest
raw_extraction_manifest
identity_map
membership_events
membership_intervals
review_cycles
coverage_certificate
conflict_report
gap_report
manifest
sha256
```

Tên file và schema version sẽ được khóa ở lát cắt implementation, không được tự suy diễn từ tài liệu này.

### Invariant

- staging cùng filesystem;
- exclusive create;
- file fsync theo capability;
- deterministic encoding/order;
- SHA-256 input/output;
- atomic rename;
- không ghi đè;
- rollback khi lỗi;
- canonical/noncanonical publication không trộn.

### Fail closed

Schema, finite value, hash, file set, metadata hoặc certificate sai thì không tạo publication thành công.

## 13. Tầng 11 — Read-only audit

### Input

Publication đã đóng và raw registry/archive có quyền đọc.

### Output

Audit report và audit hashes trong thư mục riêng.

### Invariant

- auditor không sửa publication;
- auditor không gọi builder/normalizer để tự xác nhận bằng cùng execution path;
- kiểm lại hash, interval, cutoff, count, identity, provenance, ordering và as-of samples;
- audit output deterministic theo audit contract;
- mtime/hash publication không đổi.

### Fail closed

Hash mismatch, missing file, inconsistent manifest hoặc semantic violation làm audit fail. Không sửa tại chỗ; quay lại source/normalization và tạo publication mới.

## 14. Tầng 12 — As-of API

### Input

- `ten_chi_so`;
- `T`;
- `thoi_diem_tao_tin_hieu` timezone-aware;
- canonical publication;
- coverage certificate.

### Output

`UniverseAsOf` với tri-state membership, resolved alias, interval/cycle/document provenance và deterministic order.

### Invariant

```text
ngay_hieu_luc <= T < ngay_ket_thuc_hieu_luc
thoi_diem_cong_bo <= thoi_diem_tao_tin_hieu
```

- `UNKNOWN` không chuyển thành false;
- không chọn interval gần nhất ngoài range;
- không forward-fill qua gap;
- expected count lấy từ contract giai đoạn;
- output sort theo `ma,instrument_id`.

### Fail closed

Certificate không đạt, segment không duy nhất, publication cutoff không đạt, alias không resolve hoặc count mismatch làm query dừng.

## 15. Tầng 13 — Mốc 4 research preflight

### Input

Mốc 4 config, membership publication, coverage certificate, requested research range và các input nghiên cứu khác.

### Output

- cho phép tiếp tục vào feature pipeline; hoặc
- structured preflight failure.

### Invariant

Research chỉ được đi tiếp khi:

```text
universe_contract=pit_membership_interval_v2
coverage certificate tồn tại và hash hợp lệ
research_eligible=true
blocking_error_codes rỗng
range được bao phủ
ten_chi_so/contract identity khớp config
```

Eligibility sau preflight vẫn được đánh giá riêng theo từng `ma-ngay`, gồm membership, liquidity, warm-up, feature, dữ liệu, benchmark metadata và open T+1 theo contract Mốc 4.

### Fail closed

- `pit_membership_v1` không được coi là real canonical research input;
- `technical_candidate_union_v1` không được dùng trong research;
- không tự hạ `nghien_cuu` xuống `kiem_tra_ky_thuat`;
- blocker membership hoặc blocker khác còn tồn tại thì research gate vẫn FAIL.

## 16. Tương thích với v1

### Giữ nguyên

- fixture và regression dùng `pit_membership_v1`;
- technical validation dùng `technical_candidate_union_v1`;
- explicit config chọn contract;
- timestamp cutoff hiện hành không bị làm yếu.

### Không được làm

- auto-detect schema;
- auto-convert snapshot v1 sang interval v2;
- suy end từ snapshot kế tiếp mà không có cycle/event coverage;
- coi `thieu_snapshot` v1 là bằng chứng `NOT_MEMBER_PROVEN`;
- dùng technical bar availability làm membership PIT.

### Adapter tương lai

Adapter v1/v2 phải nằm ở boundary explicit và giữ provenance contract version trong output. Adapter không được biến dữ liệu v1 thành canonical v2.

## 17. Deterministic ordering

Mọi sản phẩm phải khóa sort key. Tối thiểu:

- registry: `source_document_id`;
- extraction: `source_document_id,page_number,table_number,row_number,extraction_id`;
- identity: `instrument_id,valid_from,ma,san`;
- events: `ten_chi_so,ngay_hieu_luc,thoi_diem_cong_bo,instrument_id,membership_event_id`;
- intervals: `ten_chi_so,ngay_hieu_luc,ngay_ket_thuc_hieu_luc,instrument_id`;
- cycles: `ten_chi_so,ngay_hieu_luc,review_cycle_id`;
- conflicts/gaps: period rồi error code và stable ID;
- as-of: `ma,instrument_id`;
- manifest keys: lexical order.

Input order không được làm đổi output byte.

## 18. Trạng thái thời gian

Kiến trúc chỉ ghi:

```text
TARGET_RESEARCH_RANGE_PROVISIONAL
```

Source inventory ở lát cắt sau mới xác định khoảng có thể chứng minh. Kiến trúc không tự chọn start/end và không cho phép pipeline tự thu hẹp range để đạt gate.

## 19. Trạng thái triển khai

```text
CHUA_TAO_PACKAGE
CHUA_SUA_PRODUCTION_CODE
CHUA_THU_THAP_DU_LIEU
CHUA_TAO_CANONICAL_PUBLICATION
RESEARCH_GATE_VAN_FAIL
```
