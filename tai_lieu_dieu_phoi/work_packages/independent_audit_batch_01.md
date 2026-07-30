# INDEPENDENT-AUDIT-BATCH-01

Trạng thái: `IMPLEMENTED_PENDING_CI`

## 1. Anchor

```text
main: e66ffdd7ff30f78b5607d6b39796adcf1194390b
last_merged_pr: 29
acquisition_run: run-02
content_review_run: content-review-01
content_review_status: READY_FOR_MANUAL_REVIEW
content_review_evidence_sha256:
cfe60261dd899433abc8bdd5c58b7000ab848b781dbed6d7a9355dbae42cb6f5
```

## 2. Outcome

```text
exact raw byte
→ independent PDF engine
→ word-coordinate parser
→ independent rows 1–100
→ field-by-field candidate comparison
→ discrepancies + fingerprints
→ metadata evidence ZIP không chứa raw/full text
```

Package dùng `pdfplumber==0.11.10`, tách biệt với `pypdf==5.9.0` và parser regex/lookahead của CONTENT-REVIEW-BATCH-01.

## 3. Dữ liệu đầu vào khóa

```text
rulebook:
52d3b347c394e074cd613f8255c80f3f07dc1bb1fc36deedaeb7f2ea96efb228
9154693 bytes
28 pages

01/2024:
5f5c31dad02f73437a054a49e6eaaa04650ff71336c2d069c26b6883eae62ba5
710475 bytes
29 pages
VN100 pages: 3,4,5
100 rows

07/2024:
527385e4ef8781c07aae755fb3563eaee4aad77eb0d2e5799a29f839eb968e84
725589 bytes
29 pages
VN100 pages: 7,8
100 rows

01/2026:
a89a30791f450cc66a2bb81496eda3f250a75697b4102ea75401d29da0ff2814
698067 bytes
28 pages
VN100 pages: 3,4,5
100 rows
required: false
```

## 4. Independence boundary

Independent audit không import hoặc gọi:

```text
review_noi_dung._ROW_RE
review_noi_dung._extract_rows_from_page
review_noi_dung._extract_vn100_rows
pypdf
candidate page fingerprints
```

Nó dùng:

```text
pdfplumber word coordinates
visual-line clustering
row-start state machine
right-to-left numeric column identification
field-by-field normalized comparison
```

Candidate chỉ được nạp sau khi review ZIP và hash nội bộ đã xác minh.

## 5. Kiểm tra

- review ZIP exact SHA-256;
- exact file set trong ZIP;
- safe ZIP paths;
- internal evidence hashes;
- unsafe promotion flags phải false;
- raw hash/size trước PDF open;
- expected page count;
- marker groups;
- page indexes;
- row sequence;
- exact member count;
- duplicate/conflict;
- field comparison: `raw_symbol`, canonical company name, `shares_for_index`, `free_float_pct`, `capitalization_cap_pct`, `source_locator`.

## 6. Trạng thái

Tài liệu:

```text
AUDIT_MATCHED
AUDIT_MISMATCH
FAILED
```

Batch:

```text
INDEPENDENT_AUDIT_PASSED
INDEPENDENT_AUDIT_PARTIAL
INDEPENDENT_AUDIT_FAILED
```

## 7. Safety

Mọi output giữ:

```text
content_reviewed=false
chain_verified=false
canonical_eligible=false
research_eligible=false
interval_dates_audited=false
```

Independent match không tự chứng nhận ngày hiệu lực, stable instrument ID, corporate action, price basis, official-byte chain, canonical range hoặc research eligibility.

Không:

- commit raw PDF/full extracted text;
- sửa PR #20;
- mở Mốc 5;
- chạy model/research;
- forward-fill kỳ thiếu.

## 8. Tests

Synthetic tests bắt buộc:

1. parser tọa độ xử lý tên công ty xuống dòng;
2. end-to-end exact match;
3. field mismatch bị phát hiện;
4. raw hash mismatch chặn trước PDF open;
5. review evidence ZIP hash mismatch bị chặn;
6. evidence ZIP không chứa raw/PDF.

## 9. Acceptance

- full regression Ubuntu thành công;
- full regression Windows thành công;
- không đổi `pyproject.toml`, `uv.lock` hoặc workflow;
- branch không behind `main`;
- PR #20 không thay đổi;
- Mốc 5 không mở;
- PR chỉ chuyển Ready khi CI current-head cuối xanh.

## 10. Next gate

Sau merge, chạy một khối lệnh trong:

```text
tai_lieu/runbook_kiem_toan_doc_lap_vn100_theo_lo.md
```

Sau evidence thực tế, đoạn `00` quyết định:

```text
VN100_MEMBERSHIP_EXTRACTION_INDEPENDENTLY_MATCHED
hoặc
INDEPENDENT_AUDIT_NEEDS_REPAIR
```

Ngay cả khi matched, research gate vẫn FAIL cho đến khi chain, identity, interval coverage, EOD, corporate action và price basis được đóng.
