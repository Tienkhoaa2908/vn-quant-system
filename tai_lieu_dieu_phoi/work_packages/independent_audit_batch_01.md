# INDEPENDENT-AUDIT-BATCH-01

Trạng thái: `READY_FOR_REVIEW`

## 1. Anchor

```text
main: e66ffdd7ff30f78b5607d6b39796adcf1194390b
last_merged_pr: 29
pull_request: 30
branch: independent-audit-batch-01
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

## 3. Dữ liệu khóa

```text
rulebook:
52d3b347c394e074cd613f8255c80f3f07dc1bb1fc36deedaeb7f2ea96efb228
9154693 bytes; 28 pages

01/2024:
5f5c31dad02f73437a054a49e6eaaa04650ff71336c2d069c26b6883eae62ba5
710475 bytes; 29 pages; VN100 pages 3,4,5; 100 rows

07/2024:
527385e4ef8781c07aae755fb3563eaee4aad77eb0d2e5799a29f839eb968e84
725589 bytes; 29 pages; VN100 pages 7,8; 100 rows

01/2026:
a89a30791f450cc66a2bb81496eda3f250a75697b4102ea75401d29da0ff2814
698067 bytes; 28 pages; VN100 pages 3,4,5; 100 rows; optional
```

## 4. Independence boundary

Không import hoặc gọi:

```text
review_noi_dung._ROW_RE
review_noi_dung._extract_rows_from_page
review_noi_dung._extract_vn100_rows
pypdf
candidate page fingerprints
```

Dùng:

```text
pdfplumber word coordinates
visual-line clustering
row-start state machine
right-to-left numeric column identification
field-by-field normalized comparison
```

Candidate chỉ được nạp sau khi review ZIP và hash nội bộ đã xác minh.

## 5. Kiểm tra

- exact review ZIP SHA-256, exact file set, safe paths và internal hashes;
- unsafe promotion flags phải false;
- raw hash/size trước PDF open;
- page count, markers và page indexes;
- row sequence, member count, duplicate/conflict;
- field comparison: symbol, company, shares, free-float, cap và locator;
- audit ZIP không chứa raw/PDF/full text.

## 6. Trạng thái output

```text
AUDIT_MATCHED
AUDIT_MISMATCH
FAILED

INDEPENDENT_AUDIT_PASSED
INDEPENDENT_AUDIT_PARTIAL
INDEPENDENT_AUDIT_FAILED
```

## 7. CI implementation head

```text
head: cf494820aa525b11a660e0018692d6a122b04da3
workflow: kiem_tra_tu_dong
run_number: 428
run_id: 30517342117
conclusion: success

ubuntu_job: 90790034590
ubuntu_tests: 416
ubuntu_skipped: 2
ubuntu_result: success

windows_job: 90790034636
windows_tests: 416
windows_skipped: 3
windows_result: success
```

Commit trạng thái sau CI phải được chạy full regression lại trước khi PR chuyển Ready.

## 8. Safety

```text
content_reviewed=false
chain_verified=false
canonical_eligible=false
research_eligible=false
interval_dates_audited=false
RESEARCH_GATE=FAIL
```

Independent match không tự chứng nhận ngày hiệu lực, stable instrument ID, corporate action, price basis, official-byte chain, canonical range hoặc research eligibility.

Không commit raw/full text, không sửa PR #20, không mở Mốc 5, không chạy model/research và không forward-fill kỳ thiếu.

## 9. Acceptance

- full regression Ubuntu/Windows đạt trên current head cuối;
- không đổi `pyproject.toml`, `uv.lock` hoặc workflow;
- branch không behind `main`;
- PR #20 không thay đổi;
- Mốc 5 không mở.

## 10. Next gate

Sau merge, chạy:

```text
tai_lieu/runbook_kiem_toan_doc_lap_vn100_theo_lo.md
```

Sau evidence thực tế, đoạn `00` quyết định:

```text
VN100_MEMBERSHIP_EXTRACTION_INDEPENDENTLY_MATCHED
hoặc
INDEPENDENT_AUDIT_NEEDS_REPAIR
```

Research gate vẫn FAIL cho đến khi chain, identity, interval coverage, EOD, corporate action và price basis được đóng.
