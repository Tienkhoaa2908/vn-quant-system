# CONTENT-REVIEW-BATCH-01

Trạng thái: `READY_FOR_REVIEW`

## 1. Anchor

```text
main: dbb138fdf28f9bc6aa113f43197dc930560e9407
last_merged_pr: 28
acquisition_run: run-02
acquisition_status: COMPLETE
pull_request: 29
```

## 2. Outcome

Chuyển bốn raw PDF đã acquisition thành bằng chứng review nội dung có thể kiểm toán bằng một lệnh:

```text
exact raw byte
→ SHA-256/byte-size recheck
→ deterministic PDF text extraction
→ marker/page contract validation
→ VN100 rows 1–100 theo page contract
→ candidate JSON + page fingerprints
→ metadata evidence ZIP không chứa raw/full text
```

Package không tự nâng dữ liệu thành canonical, không mở research gate và không chạy model.

## 3. Input khóa từ run-02

```text
rb-hose-index-4-0-2024-12-30
sha256: 52d3b347c394e074cd613f8255c80f3f07dc1bb1fc36deedaeb7f2ea96efb228
size: 9154693
pages expected: 28

rc-hose-index-2024-01
sha256: 5f5c31dad02f73437a054a49e6eaaa04650ff71336c2d069c26b6883eae62ba5
size: 710475
pages expected: 29
VN100 page indexes: 3,4,5
expected rows: 100

rc-hose-index-2024-07
sha256: 527385e4ef8781c07aae755fb3563eaee4aad77eb0d2e5799a29f839eb968e84
size: 725589
pages expected: 29
VN100 page indexes: 7,8
expected rows: 100

rc-hose-index-2026-01
sha256: a89a30791f450cc66a2bb81496eda3f250a75697b4102ea75401d29da0ff2814
size: 698067
pages expected: 28
VN100 page indexes: 3,4,5
expected rows: 100
required: false
```

Page indexes là zero-based và được khóa theo quan sát tài liệu. Không quét toàn PDF để tránh trộn VN30, VNMidcap hoặc VNSmallcap.

## 4. Implementation

- contract `content_review_batch_v1`;
- exact SHA-256 và byte-size recheck trước khi mở PDF;
- đối chiếu lại acquisition registry candidate;
- parser PDF chạy cục bộ bằng `pypdf==5.9.0` qua `uv run --with`;
- không sửa dependency hoặc lockfile;
- page-count validation;
- accent-insensitive marker validation;
- VN100 extraction chỉ trên page indexes đã khóa;
- row sequence 1–100;
- exact expected member count;
- duplicate symbol và row conflict detection;
- page text SHA-256 fingerprints, không xuất full extracted text;
- candidate membership JSON;
- deterministic JSON ordering;
- ZIP metadata không chứa raw PDF hoặc `original.bin`;
- một runbook dùng đúng đường dẫn workstation hiện hành.

## 5. Trạng thái kết quả

Tài liệu:

```text
REVIEW_READY
NEEDS_REVIEW
FAILED
```

Batch:

```text
READY_FOR_MANUAL_REVIEW
PARTIAL
FAILED
```

`READY_FOR_MANUAL_REVIEW` chỉ có nghĩa các kiểm tra máy xác định đã đạt. Nó không tương đương phê duyệt nội dung thủ công.

## 6. Fail closed

Package phải chặn hoặc hạ trạng thái khi có:

```text
ACQUISITION_REGISTRY_MISSING
ACQUISITION_REGISTRY_SHA_MISMATCH
ACQUISITION_REGISTRY_SIZE_MISMATCH
RAW_FILE_MISSING
RAW_SHA256_MISMATCH
RAW_SIZE_MISMATCH
PDF_READ_ERROR
PDF_PAGE_COUNT_MISMATCH
REQUIRED_MARKER_MISSING
VN100_PAGE_OUT_OF_RANGE
VN100_ROW_CONFLICT
VN100_SYMBOL_DUPLICATE
VN100_ROW_SEQUENCE_INCOMPLETE
VN100_ROW_COUNT_MISMATCH
```

Hash/size mismatch phải xảy ra trước khi parser PDF được gọi.

## 7. Safety invariants

Mọi output bắt buộc giữ:

```text
content_reviewed=false
chain_verified=false
canonical_eligible=false
research_eligible=false
```

Không:

- commit raw PDF hoặc full extracted text;
- tự sửa nội dung raw;
- OCR tự động;
- forward-fill kỳ thiếu;
- suy stable instrument ID từ symbol mà không review;
- tuyên bố PIT range hoàn chỉnh;
- mở research run;
- sửa PR #20;
- mở Mốc 5.

## 8. Verification

Local isolated tests trước publication:

```text
5 tests
5 passed
```

CI PR #29, head `e69d0bb822ad10e4e1c207cc57b3ebd9bb950156`:

```text
workflow: kiem_tra_tu_dong
run_number: 423
run_id: 30515784696
conclusion: success

Ubuntu job: 90785149965
411 tests
OK, skipped=2

Windows job: 90785149958
411 tests
OK, skipped=3
```

Commit trạng thái sau phần verification phải được CI lại trước khi PR chuyển Ready.

## 9. Acceptance criteria

- synthetic tests cho normalization, complete row sequence, page contract, hash fail-before-read và ZIP no-raw: đạt;
- full regression Ubuntu: đạt trên implementation head;
- full regression Windows: đạt trên implementation head;
- không thay `pyproject.toml`, `uv.lock` hoặc workflow;
- diff chỉ nằm trong content-review code, tests, manifest, runbook và tài liệu điều phối;
- không merge nếu chưa có phê duyệt riêng của đoạn `00`.

## 10. Next gate

Sau khi PR merge, người dùng chạy đúng một lệnh từ:

```text
tai_lieu/runbook_review_noi_dung_vn100_theo_lo.md
```

và gửi:

```text
content_review_metadata_evidence.zip
SHA-256 của ZIP
```

Đoạn `00` sau đó quyết định:

```text
CONTENT_REVIEW_CANDIDATES_READY_FOR_INDEPENDENT_AUDIT
hoặc
CONTENT_REVIEW_BATCH_NEEDS_REPAIR
```
