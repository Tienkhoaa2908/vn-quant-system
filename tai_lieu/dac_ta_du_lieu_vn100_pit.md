# Đặc tả dữ liệu VN100 point-in-time v2

## 1. Trạng thái và phạm vi quyết định

Tài liệu này khóa hợp đồng dữ liệu cho lát cắt `01F-A — khóa hợp đồng VN100 point-in-time v2`. Lát cắt này chỉ đặc tả; chưa thu thập dữ liệu thật, chưa tạo package, chưa sửa pipeline Mốc 4 và chưa giải quyết blocker `VN100_POINT_IN_TIME_HISTORY_INCOMPLETE`.

Contract canonical cho nghiên cứu là:

```text
pit_membership_interval_v2
```

Hai contract hiện hữu được giữ riêng:

```text
pit_membership_v1             # compatibility và fixture
technical_candidate_union_v1 # technical validation, không phải PIT
```

Không auto-detect contract từ header hoặc nội dung. Không auto-convert `pit_membership_v1` thành `pit_membership_interval_v2`. Không dùng `technical_candidate_union_v1` trong research.

## 2. Mục tiêu

Hợp đồng v2 phải cho phép xây dựng lịch sử thành phần VN100 sao cho:

- không có survivorship bias;
- không áp thành phần hiện tại cho ngày quá khứ;
- không dùng thông tin công bố sau thời điểm tạo tín hiệu;
- phân biệt ngày công bố, thời điểm công bố, ngày hiệu lực và khoảng hiệu lực;
- có provenance đến byte tài liệu nguồn và locator;
- có thể kiểm toán độc lập và tái lập;
- fail closed khi thiếu, mâu thuẫn hoặc không chứng minh được;
- không forward-fill membership qua khoảng chưa có bằng chứng;
- tương thích với eligibility, thanh khoản, feature và MA250 theo từng cặp `ma-ngay`;
- tạo được universe as-of một ngày và thời điểm tín hiệu cụ thể.

## 3. Ngoài phạm vi

Lát cắt này không:

- thu thập hoặc tải hàng loạt tài liệu nguồn;
- xác nhận một URL, API hoặc endpoint cụ thể;
- commit byte tài liệu nguồn khi quyền lưu trữ chưa rõ;
- xác định master-data toàn thị trường;
- sửa `src/`, `tests/`, workflow hoặc dependency;
- chạy lại Mốc 4, huấn luyện mô hình hoặc backtest;
- mở Mốc 5;
- giải quyết các blocker khác;
- xác nhận `TARGET_RESEARCH_RANGE_PROVISIONAL` thành phạm vi canonical;
- kết luận alpha, hiệu quả đầu tư hoặc đưa khuyến nghị giao dịch.

## 4. Ngữ nghĩa thời gian

### 4.1 Interval canonical

Membership canonical dùng interval half-open:

```text
[ngay_hieu_luc, ngay_ket_thuc_hieu_luc)
```

Predicate tại ngày đánh giá `T`:

```text
ngay_hieu_luc <= T
AND T < ngay_ket_thuc_hieu_luc
```

`ngay_hieu_luc` inclusive. `ngay_ket_thuc_hieu_luc` exclusive.

Không có interval canonical mở vô hạn. Không có interval canonical với end chưa được chứng minh. Bản ghi staging có end chưa chứng minh phải mang trạng thái noncanonical và tạo lỗi `MEMBERSHIP_INTERVAL_END_UNPROVEN`.

### 4.2 Publication cutoff

Một membership chỉ được sử dụng khi đồng thời:

```text
ngay_hieu_luc <= T < ngay_ket_thuc_hieu_luc
thoi_diem_cong_bo <= thoi_diem_tao_tin_hieu
```

`thoi_diem_cong_bo` và `thoi_diem_tao_tin_hieu` phải là timestamp ISO-8601 có múi giờ đã resolve. Không ngầm hiểu timezone máy chạy.

Nếu ngày công bố bằng ngày hiệu lực nhưng thiếu giờ đáng tin cậy, dữ liệu tạo lỗi:

```text
MEMBERSHIP_LOOKAHEAD_RISK
```

Không tự gán `00:00`, `15:00`, `23:59` hoặc bất kỳ giờ thay thế nào.

Nếu chỉ có ngày công bố và ngày đó trước ngày hiệu lực, dữ liệu vẫn phải ghi rõ độ chính xác của publication time; việc chấp nhận canonical còn phụ thuộc validation và source provenance.

## 5. Ba trạng thái membership

Mọi as-of evaluation phải trả đúng một trong ba trạng thái:

```text
MEMBER
NOT_MEMBER_PROVEN
UNKNOWN
```

- `MEMBER`: segment canonical hoàn chỉnh chứng minh instrument thuộc chỉ số tại cutoff.
- `NOT_MEMBER_PROVEN`: segment canonical hoàn chỉnh chứng minh tập thành phần đầy đủ tại cutoff và instrument không thuộc tập đó.
- `UNKNOWN`: thiếu coverage, thiếu nguồn, conflict, interval không rõ, identity không rõ, publication cutoff không đạt hoặc canonical status không hợp lệ.

`UNKNOWN` phải fail closed. Không chuyển `UNKNOWN` thành `false`, `NOT_MEMBER_PROVEN`, danh sách rỗng hoặc membership của segment gần nhất.

## 6. Phân cấp nguồn

### 6.1 Cấp 1 — nguồn chính thức

Ưu tiên cao nhất là tài liệu chính thức của đơn vị quản lý chỉ số hoặc sở giao dịch, gồm các loại dự kiến:

- rulebook hoặc quyết định chỉ số;
- thông báo kết quả review định kỳ;
- phụ lục danh mục thành phần;
- thông báo thêm, loại hoặc thay thế giữa kỳ;
- thông báo thay đổi mã, hủy niêm yết, chuyển sàn hoặc sự kiện identity liên quan;
- metadata publication chính thức.

Nguồn cấp 1 chỉ canonical khi index, kỳ, ngày hiệu lực, provenance và nội dung cần thiết được xác minh; hash khớp; không có conflict cùng cấp chưa giải quyết.

### 6.2 Cấp 2 — bản chính thức được lưu hoặc dẫn lại

Tài liệu chính thức được lưu trữ hoặc dẫn lại bởi tổ chức phát hành có thể là canonical surrogate chỉ khi chứng minh được chain of custody, nhận diện văn bản gốc, không bị trích lược hoặc chỉnh sửa, và được double review. Nếu không đạt, nguồn chỉ dùng đối chiếu.

### 6.3 Cấp 3 — nguồn thứ cấp

Báo chí, broker research, vendor, web archive hoặc nguồn cộng đồng chỉ dùng để:

- phát hiện kỳ thiếu;
- tìm số văn bản hoặc candidate source;
- đối chiếu count, mã hoặc ngày;
- tạo conflict report.

Nguồn cấp 3 không tự động trở thành canonical và không được dùng để lấp gap.

### 6.4 Không bịa khả năng truy cập

Source inventory ở lát cắt sau phải xác minh từng nguồn. Tài liệu này không ghi URL giả, API giả, endpoint giả hoặc tuyên bố archive lịch sử đã tồn tại.

## 7. Source-document registry bất biến

Schema tối thiểu:

```text
source_document_id
ten_chi_so
loai_tai_lieu
cap_nguon
ten_nguon
url_goc
url_luu_tru
so_van_ban
tieu_de_tai_lieu
ngay_cong_bo
thoi_diem_cong_bo
do_chinh_xac_thoi_diem_cong_bo
thoi_diem_thu_thap
http_etag
http_last_modified
content_type
kich_thuoc_byte
sha256_tai_lieu_nguon
phien_ban_nguon
duong_dan_luu_bat_bien
quyen_luu_tru
trang_thai_tai_lieu
trang_thai_xac_minh
ghi_chu
```

Invariant:

- registry append-only;
- không ghi đè tài liệu cũ khi cùng URL trả byte mới;
- byte mới tạo `source_document_id` mới;
- SHA-256 tính trên byte gốc;
- `thoi_diem_thu_thap` có UTC offset;
- `ETag` và `Last-Modified` không thay thế SHA-256;
- raw byte nằm ngoài Git khi quyền lưu trữ chưa rõ;
- Git chỉ lưu schema, fixture tổng hợp, manifest/hash, provenance metadata và runbook;
- tài liệu chưa xác minh hoặc hash mismatch không đi qua canonical boundary.

## 8. Raw extraction schema

Schema tối thiểu:

```text
extraction_id
source_document_id
extractor_name
extractor_version
extraction_time_utc
page_number
table_number
row_number
source_locator
raw_text
raw_symbol
raw_company_name
raw_index_name
raw_publication_date
raw_publication_time
raw_effective_date
raw_action
raw_notes
extraction_method
extraction_status
reviewer_1
reviewer_2
```

`source_locator` phải đủ để người kiểm toán tìm lại bằng chứng trong tài liệu, ví dụ trang, bảng, mục, dòng hoặc vùng định danh tương đương.

`extraction_method` phải là giá trị explicit, tối thiểu:

```text
STRUCTURED
PDF_TEXT
MANUAL_DOUBLE_ENTRY
OTHER_REVIEWED
```

Không sửa raw text để hợp thức hóa normalized value. Mọi correction hoặc interpretation nằm ở tầng normalized và trỏ lại `extraction_id`.

Dữ liệu nhập tay bắt buộc double review độc lập. Hai reviewer không được là cùng identity. Sai khác chưa giải quyết giữ trạng thái noncanonical.

## 9. Identity schema

Canonical membership liên kết `instrument_id`. `ma` là alias theo thời gian, không phải khóa vĩnh viễn.

Schema tối thiểu:

```text
instrument_id
ma
ten_phap_ly
san
valid_from
valid_to_exclusive
source_document_id
source_locator
verification_status
reviewed_by
reviewed_at
notes
```

Invariant:

- alias dùng interval half-open;
- một alias không được ánh xạ mâu thuẫn sang nhiều instrument trong cùng thời gian;
- membership event và interval dùng `instrument_id` làm identity canonical;
- output as-of render alias hợp lệ tại `T`;
- đổi mã, hủy niêm yết hoặc chuyển sàn không xóa lịch sử;
- thiếu bằng chứng nối identity tạo `MEMBERSHIP_SYMBOL_IDENTITY_AMBIGUOUS`;
- MVP chỉ xử lý identity cần thiết trong khoảng nguồn thu thập, chưa xây master-data toàn thị trường.

## 10. Membership event schema

Schema tối thiểu:

```text
membership_event_id
ten_chi_so
review_cycle_id
instrument_id
ma_tai_thoi_diem_su_kien
loai_su_kien
ngay_cong_bo
thoi_diem_cong_bo
do_chinh_xac_thoi_diem_cong_bo
ngay_hieu_luc
source_document_id
sha256_tai_lieu_nguon
source_locator
nguon
phien_ban_nguon
thoi_diem_thu_thap
trang_thai_xac_minh
ghi_chu
```

`loai_su_kien` tối thiểu:

```text
ADD
REMOVE
REPLACE
SYMBOL_CHANGE
DELIST
TRANSFER
MERGER
OTHER_OFFICIAL_ADJUSTMENT
```

Event bất thường giữa kỳ không sửa byte hoặc extraction của snapshot gốc. Interval được dựng lại từ chuỗi event bất biến đã xác minh.

## 11. Canonical interval schema

Schema tối thiểu:

```text
ten_chi_so
review_cycle_id
instrument_id
ma
ngay_cong_bo
thoi_diem_cong_bo
do_chinh_xac_thoi_diem_cong_bo
ngay_hieu_luc
ngay_ket_thuc_hieu_luc
nguon
phien_ban_nguon
source_document_id
sha256_tai_lieu_nguon
source_locator
thoi_diem_thu_thap
trang_thai_xac_minh
canonical
derivation_method
conflict_set_id
ghi_chu
```

Chỉ bản ghi có:

```text
canonical=true
trang_thai_xac_minh=VERIFIED
```

mới được dùng bởi as-of API và research preflight.

Không có hai interval `MEMBER` của cùng `ten_chi_so,instrument_id` chồng lấn. Không có segment index chồng lấn hoặc gap trong phạm vi được chứng nhận.

## 12. Review-cycle schema

Schema tối thiểu:

```text
review_cycle_id
ten_chi_so
rulebook_version
cycle_type
period_label
expected
ngay_cong_bo
thoi_diem_cong_bo
ngay_hieu_luc
ngay_ket_thuc_hieu_luc
expected_member_count
observed_member_count
source_document_ids
reconciliation_status
coverage_status
verification_status
notes
```

`cycle_type` tối thiểu:

```text
PERIODIC
EXTRAORDINARY
INITIAL
RULEBOOK_TRANSITION
```

`expected_member_count` không hard-code trong framework chung. Giá trị lấy từ rulebook/index contract áp dụng cho từng giai đoạn.

Đối với VN100, segment chỉ canonical khi tài liệu chính thức chứng minh `expected_member_count=100` và `observed_member_count` khớp. Nếu rulebook/index contract không chứng minh count hoặc observed count không khớp, fail closed.

## 13. Derived VN100

Chỉ derive VN100 từ component indices khi đồng thời:

- rulebook đúng giai đoạn cho phép phép derive;
- mọi parent publication là canonical;
- parent interval và cutoff tương thích;
- identity đã resolve;
- expected count lấy từ contract áp dụng;
- observed count khớp expected count;
- provenance ghi toàn bộ parent document và rulebook document.

Không giả định quan hệ giữa VN100 và component indices bất biến qua thời gian.

`derivation_method` cho trường hợp được phép phải explicit, ví dụ:

```text
OFFICIAL_COMPONENT_UNION
```

Thiếu điều kiện tạo `MEMBERSHIP_DERIVATION_NOT_AUTHORIZED`.

## 14. Coverage certificate

Schema logic tối thiểu:

```text
coverage_certificate_id
membership_contract_version
ten_chi_so
target_research_range_status
requested_start
requested_end_exclusive
actual_verified_start
actual_verified_end_exclusive
expected_cycles
verified_cycles
missing_cycles
ambiguous_cycles
conflict_cycles
interval_gaps
interval_overlaps
same_day_publication_risks
member_count_failures
identity_ambiguities
source_hash_failures
coverage_by_day
coverage_by_cycle
coverage_by_document
coverage_by_instrument
research_eligible
blocking_error_codes
source_manifest_sha256
normalized_manifest_sha256
created_at_utc
```

`TARGET_RESEARCH_RANGE_PROVISIONAL` là trạng thái bắt buộc hiện tại. Source inventory ở lát cắt sau mới xác định khoảng có thể chứng minh. Không tự thu hẹp, mở rộng hoặc thay đổi khoảng mà không quay lại đoạn `00`.

Một khoảng chỉ `research_eligible=true` khi mọi ngày trong requested range thuộc đúng một segment canonical hoàn chỉnh, không gap, không overlap, không conflict, cutoff hợp lệ và count khớp contract.

Không dùng tỷ lệ gần đủ để thay thế coverage membership đầy đủ.

## 15. Conflict report

Schema tối thiểu:

```text
conflict_set_id
ten_chi_so
period
field
candidate_values
source_document_ids
source_hierarchy_levels
resolution_status
resolution_basis
resolved_by
resolved_at
notes
```

Không chọn nguồn chỉ vì timestamp mới hơn khi hai nguồn cùng cấp mâu thuẫn. Conflict chưa giải quyết giữ dữ liệu noncanonical và tạo `MEMBERSHIP_SOURCE_CONFLICT`.

## 16. Manifest và SHA-256

Manifest publication tối thiểu:

```text
manifest_schema_version
membership_contract_version
git_commit
run_id
created_at_utc
python_version
parser_versions
normalizer_version
identity_resolver_version
coverage_validator_version
configuration
source_documents
input_hashes
output_hashes
output_sizes
coverage_summary
conflict_summary
error_codes
research_eligible
limitations
```

Yêu cầu:

- UTF-8;
- JSON key order xác định;
- CSV column order xác định;
- newline xác định;
- không NaN/Inf;
- SHA-256 cho mọi input và output;
- không ghi đè publication;
- cùng input, config, code và explicit build metadata phải cho cùng byte đối với sản phẩm được quy định tái lập;
- manifest không tuyên bố fact mà builder hoặc auditor không tự xác minh.

## 17. As-of query contract

Giao diện logic:

```text
tao_universe_as_of(
    ten_chi_so,
    ngay=T,
    thoi_diem_tao_tin_hieu,
    membership_publication,
) -> UniverseAsOf
```

Quy trình bắt buộc:

1. kiểm manifest và hash;
2. kiểm coverage certificate bao phủ `T`;
3. xác định đúng một segment canonical chứa `T`;
4. áp publication cutoff;
5. kiểm expected/observed member count theo contract giai đoạn;
6. resolve alias hợp lệ của từng `instrument_id` tại `T`;
7. tạo trạng thái `MEMBER`, `NOT_MEMBER_PROVEN` hoặc `UNKNOWN`;
8. sort output xác định theo `ma`, sau đó `instrument_id`;
9. trả provenance cấp segment, cycle và source document.

Nếu không chứng minh được bất kỳ bước nào, query fail closed. Không trả segment gần nhất và không forward-fill.

## 18. Error codes

Tối thiểu:

```text
MEMBERSHIP_SOURCE_MISSING
MEMBERSHIP_EFFECTIVE_DATE_MISSING
MEMBERSHIP_INTERVAL_OVERLAP
MEMBERSHIP_INTERVAL_AMBIGUOUS
MEMBERSHIP_SOURCE_HASH_MISMATCH
MEMBERSHIP_SYMBOL_IDENTITY_AMBIGUOUS
MEMBERSHIP_HISTORY_GAP
MEMBERSHIP_LOOKAHEAD_RISK
MEMBERSHIP_PUBLICATION_TIMESTAMP_MISSING
MEMBERSHIP_REVIEW_INCOMPLETE
MEMBERSHIP_SOURCE_CONFLICT
MEMBERSHIP_EXPECTED_COUNT_MISMATCH
MEMBERSHIP_INTERVAL_END_UNPROVEN
MEMBERSHIP_CANONICAL_STATUS_INVALID
MEMBERSHIP_RULEBOOK_VERSION_MISSING
MEMBERSHIP_DERIVATION_NOT_AUTHORIZED
MEMBERSHIP_SOURCE_LOCATOR_MISSING
MEMBERSHIP_COVERAGE_CERTIFICATE_MISSING
```

Định nghĩa:

- `MEMBERSHIP_SOURCE_MISSING`: thiếu tài liệu nguồn bắt buộc cho cycle/event.
- `MEMBERSHIP_EFFECTIVE_DATE_MISSING`: không xác định được ngày hiệu lực.
- `MEMBERSHIP_INTERVAL_OVERLAP`: interval instrument hoặc segment index chồng lấn.
- `MEMBERSHIP_INTERVAL_AMBIGUOUS`: có nhiều cách hợp lý để dựng interval nhưng chưa giải quyết.
- `MEMBERSHIP_SOURCE_HASH_MISMATCH`: byte quan sát không khớp hash đã đăng ký.
- `MEMBERSHIP_SYMBOL_IDENTITY_AMBIGUOUS`: không map duy nhất alias sang instrument.
- `MEMBERSHIP_HISTORY_GAP`: có ngày trong requested range không được segment canonical bao phủ.
- `MEMBERSHIP_LOOKAHEAD_RISK`: publication cutoff không chứng minh được hoặc thông tin đến sau signal.
- `MEMBERSHIP_PUBLICATION_TIMESTAMP_MISSING`: timestamp bắt buộc nhưng không có bằng chứng đáng tin cậy.
- `MEMBERSHIP_REVIEW_INCOMPLETE`: review cycle chưa reconcile thành complete membership.
- `MEMBERSHIP_SOURCE_CONFLICT`: các nguồn chấp nhận được mâu thuẫn chưa giải quyết.
- `MEMBERSHIP_EXPECTED_COUNT_MISMATCH`: observed count không khớp count từ contract.
- `MEMBERSHIP_INTERVAL_END_UNPROVEN`: end interval chưa có bằng chứng.
- `MEMBERSHIP_CANONICAL_STATUS_INVALID`: bản ghi chưa VERIFIED/canonical nhưng bị yêu cầu dùng.
- `MEMBERSHIP_RULEBOOK_VERSION_MISSING`: không xác định rulebook áp dụng.
- `MEMBERSHIP_DERIVATION_NOT_AUTHORIZED`: phép derive không được rulebook giai đoạn cho phép.
- `MEMBERSHIP_SOURCE_LOCATOR_MISSING`: không truy lại được vị trí bằng chứng trong nguồn.
- `MEMBERSHIP_COVERAGE_CERTIFICATE_MISSING`: research runner thiếu chứng chỉ coverage hợp lệ.

Implementation có thể bổ sung error code nhưng không được thay đổi ngữ nghĩa các code đã khóa mà không có quyết định mới.

## 19. Fail-closed behavior

### 19.1 Raw và extraction

Có thể lưu bằng chứng và lỗi; không xóa raw; không tự sửa normalized value; không đánh dấu canonical.

### 19.2 Normalization và interval construction

Conflict, identity ambiguity, missing locator, missing date hoặc end chưa chứng minh không tạo interval canonical.

### 19.3 Coverage

Gap, overlap, count mismatch hoặc cutoff risk làm `research_eligible=false` và đưa error code vào certificate.

### 19.4 As-of API

`UNKNOWN` hoặc certificate không đạt làm query dừng với lỗi có cấu trúc. Không trả `false` thay thế.

### 19.5 Mốc 4 research

Research preflight phải dừng trước feature/model nếu bất kỳ điều kiện nào không đạt:

```text
membership_contract_version == pit_membership_interval_v2
coverage_certificate tồn tại và hash hợp lệ
coverage_certificate.research_eligible == true
blocking_error_codes rỗng
requested research range được certificate bao phủ
ten_chi_so và contract identity khớp cấu hình
```

Technical validation không được nâng cấp thành research và phải tiếp tục công bố giới hạn.

## 20. Compatibility v1/v2

- `pit_membership_v1` tiếp tục phục vụ fixture và compatibility hiện hành.
- `pit_membership_interval_v2` là canonical research contract.
- `technical_candidate_union_v1` chỉ phục vụ technical validation.
- Không auto-detect dựa trên header.
- Không auto-convert v1 sang v2.
- Không suy ra `ngay_ket_thuc_hieu_luc` từ snapshot kế tiếp nếu coverage cycle/event chưa được chứng minh.
- Adapter tương lai phải được kích hoạt bằng config explicit.
- Regression của v1 được giữ nhưng không phải bằng chứng lịch sử VN100 thật.

## 21. Publication requirements

Publication phải:

- dùng staging cùng filesystem với destination;
- ghi file mới bằng exclusive create;
- fsync file theo capability nền tảng;
- tạo hash và manifest;
- kiểm finite/encoding/order;
- atomic rename hoặc cơ chế tương đương đã duyệt;
- không ghi đè;
- rollback toàn bộ khi lỗi;
- tách publication thành công và failed audit evidence;
- không commit raw source document khi quyền chưa rõ.

## 22. Audit requirements

Auditor độc lập phải read-only và không import/gọi acquisition, normalizer hoặc builder để tự tạo lại kết quả bằng cùng code path.

Auditor tối thiểu kiểm:

- file set và schema version;
- input/output SHA-256;
- source-document linkage và locator;
- timezone-aware publication cutoff;
- interval half-open, overlap và gap;
- review-cycle reconciliation;
- rulebook version và authorized derivation;
- expected count từ contract và observed count;
- identity mapping;
- tri-state behavior;
- deterministic ordering;
- as-of samples trước/sau effective date;
- coverage certificate;
- publication không bị sửa.

Hai lượt audit cùng input và audit contract phải tạo sản phẩm audit cùng byte/SHA-256 khi contract quy định.

## 23. Phạm vi thời gian

Trạng thái duy nhất được phép trong lát cắt này:

```text
TARGET_RESEARCH_RANGE_PROVISIONAL
```

Chưa có start/end canonical được duyệt. Source inventory ở lát cắt sau phải báo khoảng có thể chứng minh và mọi gap. Không tự thu hẹp hoặc thay đổi mục tiêu để tuyên bố blocker đã đạt.

## 24. Điều kiện đề nghị giải quyết blocker

Chỉ đề nghị đoạn `00` giải quyết `VN100_POINT_IN_TIME_HISTORY_INCOMPLETE` khi đồng thời:

1. source inventory và rulebook inventory được phê duyệt;
2. requested research range được đoạn `00` khóa;
3. mọi source document canonical có provenance, locator và SHA-256;
4. mọi review cycle/event trong range được reconcile;
5. không có unresolved gap, overlap, conflict, hash mismatch hoặc identity ambiguity;
6. publication cutoff được chứng minh cho mọi segment/event;
7. expected count lấy từ contract giai đoạn và observed count khớp;
8. coverage certificate có `research_eligible=true` và không có blocking error;
9. as-of query vượt test trước/sau effective và look-ahead;
10. technical candidate union không thể đi vào research path;
11. publication nguyên tử và auditor read-only đạt;
12. hai lần build/audit theo contract tái lập đạt;
13. regression hiện hành đạt trên nền tảng CI bắt buộc;
14. đoạn `00` rà soát bằng chứng và phê duyệt.

Giải quyết blocker này không tự giải quyết các blocker còn lại. Research gate toàn hệ thống tiếp tục `FAIL` cho đến khi mọi blocker bắt buộc đều đạt.
