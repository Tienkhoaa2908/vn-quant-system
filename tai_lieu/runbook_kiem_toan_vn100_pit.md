# Runbook kiểm toán dữ liệu VN100 point-in-time v2

## 1. Mục tiêu và giới hạn

Runbook này mô tả quy trình thủ công có kiểm soát cho source inventory, provenance, extraction, reconciliation, publication và audit của `pit_membership_interval_v2`.

Đây chưa phải bằng chứng đã thu thập dữ liệu. Không có URL hoặc endpoint cụ thể nào được xác nhận trong tài liệu này. Người thực hiện không được bịa URL, tham số, archive hoặc khả năng truy cập.

Raw source document nằm ngoài Git khi quyền lưu trữ chưa rõ. Git chỉ lưu schema, fixture tổng hợp, manifest/hash, provenance metadata và runbook.

## 2. Vai trò

Tối thiểu:

- `collector`: đăng ký và lưu tài liệu;
- `extractor`: trích xuất dữ liệu;
- `reviewer_1`, `reviewer_2`: double review dữ liệu nhập tay;
- `identity_reviewer`: xác minh instrument/alias;
- `reconciler`: dựng cycle/event/interval;
- `publisher`: tạo publication;
- `auditor`: kiểm toán chỉ đọc;
- `doan_00_reviewer`: nhận bằng chứng và phán quyết.

Một người có thể giữ nhiều vai trò khi nguồn lực hạn chế, nhưng `auditor` không được là người duy nhất tự phê duyệt thay đổi do chính mình tạo. Manual double entry phải có hai reviewer identity khác nhau.

## 3. Chuẩn bị phiên làm việc

1. Ghi repository, base commit và branch chuyên môn.
2. Xác nhận phạm vi được đoạn `00` cho phép.
3. Xác nhận `TARGET_RESEARCH_RANGE_PROVISIONAL`; không tự ghi start/end canonical.
4. Tạo run ID duy nhất.
5. Tạo thư mục raw ngoài Git với quyền truy cập phù hợp.
6. Xác nhận không có credential trong log hoặc metadata công bố.
7. Không sửa PR #20, không mở Mốc 5 và không chạy pipeline nghiên cứu ngoài phạm vi.

## 4. Đăng ký tài liệu nguồn

Với mỗi tài liệu:

1. Xác minh đây là candidate source phù hợp với source hierarchy.
2. Ghi tên nguồn, loại tài liệu, chỉ số, số văn bản và tiêu đề nếu có.
3. Ghi URL gốc đúng như quan sát; không chuẩn hóa làm mất query/path có ý nghĩa.
4. Ghi URL lưu trữ nếu có và đã xác minh.
5. Ghi collection time timezone-aware, ưu tiên UTC.
6. Ghi content type và kích thước byte quan sát.
7. Ghi publication date/time đúng bằng chứng; không suy đoán giờ.
8. Ghi quyền lưu trữ và việc byte có được phép commit hay không.
9. Cấp `source_document_id` mới.
10. Không dùng cùng document ID cho byte khác.

Nếu nguồn chỉ là nguồn thứ cấp, đánh dấu đúng cấp; không nâng canonical status.

## 5. Lưu byte ngoài Git

1. Lưu nguyên byte, không mở rồi save lại bằng phần mềm làm đổi encoding/metadata.
2. Dùng tên nội bộ theo `source_document_id`, không phụ thuộc duy nhất filename từ website.
3. Đặt file trong vùng immutable hoặc write-once theo khả năng môi trường.
4. Không commit byte nếu quyền lưu trữ chưa rõ.
5. Ghi `duong_dan_luu_bat_bien` trong registry nội bộ.
6. Hạn chế quyền sửa/xóa.
7. Nếu cùng URL trả byte mới, lưu thành document mới; giữ byte cũ.

## 6. Tính và xác minh SHA-256

Lệnh tham khảo theo môi trường, không khóa một công cụ duy nhất:

```bash
sha256sum <duong_dan_tai_lieu>
```

hoặc công cụ tương đương đã xác minh.

Quy trình:

1. Tính SHA-256 ngay sau khi lưu.
2. Ghi hash chữ thường 64 ký tự hex.
3. Ghi kích thước byte.
4. Một reviewer khác tính lại độc lập hoặc dùng auditor tính lại.
5. Hash registry và hash tính lại phải khớp.
6. Không dùng ETag, filename hoặc timestamp thay hash.

Hash mismatch xử lý theo mục 16; không tiếp tục canonicalization.

## 7. Ghi provenance truy cập

Registry tối thiểu phải có:

```text
url_goc
url_luu_tru
thoi_diem_thu_thap
content_type
kich_thuoc_byte
sha256_tai_lieu_nguon
http_etag
http_last_modified
quyen_luu_tru
```

Trường không có bằng chứng để trống/null theo schema, không bịa. Ghi chú phải phân biệt “nguồn không cung cấp” và “chưa thu thập”.

## 8. Trích xuất có locator

Mỗi extraction row phải trỏ đến:

- `source_document_id`;
- trang;
- bảng/mục;
- dòng hoặc vị trí tương đương;
- raw text hoặc raw field;
- extractor và version;
- extraction time.

Không tạo normalized membership trực tiếp từ ghi nhớ hoặc danh sách hiện tại.

Nếu tài liệu cấu trúc:

1. giữ raw field;
2. ghi parser/version;
3. ghi row locator ổn định nếu có.

Nếu PDF/text:

1. ghi page và vùng/mục;
2. giữ raw text;
3. không sửa typo trong raw field;
4. correction nằm ở normalized notes và có review.

## 9. Double review cho nhập tay

Áp dụng khi `extraction_method=MANUAL_DOUBLE_ENTRY`.

1. Reviewer 1 nhập độc lập từ tài liệu gốc.
2. Reviewer 2 nhập độc lập, không xem kết quả reviewer 1 trước khi hoàn thành.
3. So sánh từng trường business và locator.
4. Sai khác tạo review discrepancy record.
5. Hai reviewer đối chiếu lại raw document.
6. Resolution ghi người, thời điểm và căn cứ.
7. Chỉ row khớp hoặc resolved có bằng chứng mới được VERIFIED.
8. Không dùng majority vote hoặc “mã trông hợp lý” để giải quyết.

## 10. Xác minh publication cutoff

1. Ghi `ngay_cong_bo` và `thoi_diem_cong_bo` có offset nếu nguồn chứng minh.
2. Không tự gán giờ.
3. Kiểm effective interval half-open.
4. Với mỗi as-of sample, kiểm:

```text
ngay_hieu_luc <= T < ngay_ket_thuc_hieu_luc
thoi_diem_cong_bo <= thoi_diem_tao_tin_hieu
```

5. Nếu ngày công bố bằng ngày hiệu lực nhưng thiếu giờ đáng tin cậy, tạo:

```text
MEMBERSHIP_LOOKAHEAD_RISK
```

6. Dữ liệu đó không canonical cho cutoff trong ngày.

## 11. Xác minh identity

1. Chuẩn hóa raw symbol nhưng giữ raw value.
2. Tìm bằng chứng chính thức nối alias với instrument.
3. Tạo/tra `instrument_id` ổn định trong phạm vi nguồn.
4. Ghi alias interval `valid_from,valid_to_exclusive`.
5. Kiểm không overlap mâu thuẫn.
6. Kiểm đổi mã, chuyển sàn, hủy niêm yết, merger hoặc relisting khi có liên quan.
7. Không dựa duy nhất vào tên công ty giống nhau.
8. Không xây master-data ngoài phạm vi cần thiết.
9. Không resolve được thì tạo `MEMBERSHIP_SYMBOL_IDENTITY_AMBIGUOUS` và giữ noncanonical.

## 12. Xử lý source conflict

Khi hai nguồn cho giá trị khác nhau:

1. Tạo `conflict_set_id`.
2. Ghi mọi candidate value và source document.
3. Ghi source hierarchy level.
4. Kiểm byte/hash/locator trước khi so nội dung.
5. Ưu tiên nguồn cấp cao hơn chỉ khi đúng phạm vi và tài liệu hợp lệ.
6. Hai nguồn cùng cấp không được chọn chỉ vì timestamp mới hơn.
7. Tìm correction notice, later official notice hoặc rulebook applicable.
8. Ghi resolution basis và reviewer.
9. Chưa resolve thì `MEMBERSHIP_SOURCE_CONFLICT`; cycle/interval không canonical.
10. Nguồn thứ cấp có thể phát hiện conflict nhưng không tự trở thành canonical.

## 13. Xử lý missing review cycle

1. Đối chiếu expected cycle inventory theo rulebook giai đoạn.
2. Nếu thiếu tài liệu, tạo `MEMBERSHIP_SOURCE_MISSING` hoặc `MEMBERSHIP_REVIEW_INCOMPLETE`.
3. Ghi gap start/end candidate và expected cycle.
4. Không forward-fill cycle trước.
5. Không dùng danh sách hiện tại hoặc dữ liệu giá/thanh khoản/vốn hóa để suy membership.
6. Nguồn thứ cấp chỉ tạo candidate source list.
7. As-of trong gap phải là `UNKNOWN` và fail closed.
8. Không thu hẹp target range để che gap; báo đoạn `00`.

## 14. Reconcile review cycle và interval

1. Xác định rulebook version áp dụng.
2. Lấy `expected_member_count` từ rulebook/index contract, không hard-code trong framework.
3. Đối với VN100, kiểm tài liệu chính thức chứng minh expected count 100.
4. Dựng complete snapshot hoặc chuỗi event được phép.
5. Kiểm observed count khớp expected count.
6. Reconcile add/remove với cycle trước.
7. Chèn extraordinary event đúng effective date.
8. Dựng interval:

```text
[ngay_hieu_luc, ngay_ket_thuc_hieu_luc)
```

9. Không để canonical interval open-ended.
10. Kiểm overlap/gap.
11. Derived VN100 chỉ thực hiện khi rulebook đúng giai đoạn cho phép và mọi parent publication canonical.
12. Thiếu điều kiện tạo error code tương ứng.

## 15. Tạo coverage certificate

1. Xác định requested range chỉ sau khi đoạn `00` phê duyệt; trước đó giữ:

```text
TARGET_RESEARCH_RANGE_PROVISIONAL
```

2. Liệt kê expected/verified/missing/ambiguous/conflict cycles.
3. Kiểm coverage theo từng ngày.
4. Kiểm interval gap/overlap.
5. Kiểm publication look-ahead risks.
6. Kiểm member count failures.
7. Kiểm identity ambiguities.
8. Kiểm source hash failures.
9. Ghi source manifest và normalized manifest hash.
10. Chỉ đặt `research_eligible=true` khi không có blocking error và toàn range được bao phủ.
11. Không dùng phần trăm gần đủ thay coverage đầy đủ.
12. Reviewer độc lập ký xác nhận certificate metadata.

## 16. Xử lý hash mismatch

Khi hash tính lại không khớp registry:

1. Dừng normalization/publication liên quan.
2. Tạo `MEMBERSHIP_SOURCE_HASH_MISMATCH`.
3. Giữ cả byte cũ và byte mới nếu có.
4. Không cập nhật hash cũ để “làm cho khớp”.
5. Kiểm nhầm file, transfer corruption, website thay byte hoặc thao tác save lại.
6. Nếu byte mới là phiên bản nguồn mới, đăng ký document mới.
7. Xác định publication nào phụ thuộc document bị ảnh hưởng.
8. Đánh dấu publication đó không còn audit-passed, nhưng không sửa tại chỗ.
9. Tạo publication mới sau khi resolution được duyệt.
10. Báo bằng chứng và phạm vi ảnh hưởng cho đoạn `00`.

## 17. Atomic publication và rollback

Trước publish:

- tất cả canonical records VERIFIED;
- coverage certificate hợp lệ;
- blocking error rỗng;
- schema/order/finite/hash đạt;
- destination chưa tồn tại.

Publish:

1. tạo staging cùng filesystem;
2. ghi file bằng exclusive create;
3. flush/fsync file theo capability;
4. tính output hash;
5. ghi manifest và hash file;
6. kiểm lại file set;
7. fsync staging directory theo capability;
8. atomic rename;
9. fsync parent theo capability.

Rollback:

- bất kỳ lỗi nào trước rename: xóa staging;
- không để partial destination;
- không ghi đè publication cũ;
- lỗi sau publication được xử lý bằng publication mới, không patch tại chỗ.

## 18. Chạy auditor chỉ đọc

Auditor nhận:

- publication directory;
- raw registry/archive quyền đọc;
- audit contract version;
- expected config/range.

Auditor phải:

1. xác minh file set;
2. tính lại mọi SHA-256;
3. kiểm manifest linkage;
4. kiểm source locator;
5. kiểm timezone-aware cutoff;
6. kiểm half-open interval;
7. kiểm gap/overlap;
8. kiểm rulebook và authorized derivation;
9. kiểm expected/observed count;
10. kiểm identity;
11. kiểm tri-state;
12. tạo as-of samples trước, đúng và sau effective date;
13. kiểm `UNKNOWN` không chuyển thành false;
14. kiểm deterministic order;
15. kiểm coverage certificate;
16. xác nhận publication mtime/hash không đổi.

Auditor không import/gọi builder, acquisition, normalizer hoặc pipeline Mốc 4. Audit output ghi vào thư mục riêng.

## 19. Kiểm tái lập

Chạy hai lần với cùng:

- raw byte;
- registry/provenance;
- config;
- code commit;
- parser/normalizer versions;
- explicit build metadata theo contract.

So sánh byte và SHA-256 của mọi sản phẩm được khóa deterministic. Sai khác phải được giải thích và xử lý trước canonical approval.

## 20. Bằng chứng gửi đoạn `00`

Gói bằng chứng tối thiểu:

```text
repository
base_sha
branch
head_sha
run_id
contract_version
source_inventory_summary
rulebook_inventory_summary
source_document_registry_hash
raw_archive_policy
extraction_summary
double_review_summary
identity_resolution_summary
review_cycle_reconciliation_summary
conflict_report_hash
gap_report_hash
coverage_certificate_hash
requested_range_status
blocking_error_codes
publication_manifest_hash
publication_file_hashes
auditor_version
audit_report_hash
audit_result
reproducibility_result
commands_run
CI run/job IDs
limitations
```

Kèm xác nhận:

- không commit raw tài liệu hạn chế;
- không forward-fill qua gap;
- không dùng technical candidate union trong research;
- không auto-convert v1 sang v2;
- `expected_member_count` lấy từ contract giai đoạn;
- range vẫn provisional nếu chưa được đoạn `00` khóa;
- research gate vẫn FAIL nếu còn blocker.

## 21. Quy trình phán quyết

Auditor hoặc builder không tự tuyên bố blocker resolved.

1. Gửi gói bằng chứng cho đoạn `00`.
2. Đoạn `00` kiểm source inventory, range, conflicts, certificate, audit và CI.
3. Nếu thiếu bằng chứng, giữ blocker.
4. Nếu chỉ một số cycle đạt, không tuyên bố toàn lịch sử đạt.
5. Chỉ sau phê duyệt explicit mới cập nhật tài liệu điều phối hoặc research gate.

## 22. Trạng thái hiện tại

```text
CHUA_THU_THAP_DU_LIEU
CHUA_TAO_SOURCE_INVENTORY
CHUA_TAO_CANONICAL_PUBLICATION
CHUA_CHAY_AUDITOR_VN100_PIT
TARGET_RESEARCH_RANGE_PROVISIONAL
RESEARCH_GATE_VAN_FAIL
```
