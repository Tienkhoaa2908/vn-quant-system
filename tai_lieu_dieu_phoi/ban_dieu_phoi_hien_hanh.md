# Bản điều phối hiện hành

Cập nhật: 2026-07-30

Tài liệu này là snapshot current-state. Nếu tài liệu trạng thái tích lũy cũ mâu thuẫn với snapshot này, dùng snapshot này cùng merged `main` và `DECISIONS.md`.

## 1. Anchor

```text
repository: Tienkhoaa2908/vn-quant-system
main: e66ffdd7ff30f78b5607d6b39796adcf1194390b
last_merged_pr: 29
last_verified_pr_ci: 30515929824
ubuntu_job: 90785615051
windows_job: 90785615142
ci_conclusion: success
post_merge_push_ci: NOT_OBSERVABLE_BY_CURRENT_CONNECTOR
```

PR #29 đã merge bằng merge commit. Head trước merge đạt 411 test trên Ubuntu và Windows.

PR #20 vẫn Open/Draft/Unmerged và không thuộc phạm vi active.

## 2. Trạng thái kỹ thuật

- Mốc 0–4 có implementation nền và technical validation.
- Lần chạy kỹ thuật rộng Mốc 4: 121 mã nguồn, 120 mã có prediction, 36 fold, 34 fold thành công.
- Logistic Regression là baseline kỹ thuật và yếu hơn momentum trong lần chạy rộng.
- Không có research claim, alpha claim hoặc tín hiệu vận hành.
- Mốc 5 tiếp tục tạm dừng.

## 3. Data gates

```text
VN100_POINT_IN_TIME_HISTORY_INCOMPLETE
HOSE_EOD_CROSSCHECK_INCOMPLETE
CORPORATE_ACTION_INVENTORY_INCOMPLETE
PRICE_BASIS_UNCONFIRMED
RESEARCH_GATE=FAIL
```

Không blocker nào được coi là resolved.

## 4. Work packages đã merge

```text
DATA-GATE-CLOSURE-BATCH-01
PR: 27

DATA-EVIDENCE-BATCH-01
PR: 28

CONTENT-REVIEW-BATCH-01
PR: 29
```

Các package đã cung cấp contract, acquisition, deterministic content parser và evidence pipeline. Chúng không tự canonical hoặc research eligible.

## 5. Acquisition thực tế

```text
workstation_root: C:\Users\welcome\Documents\vn-quant-data
run: run-02
batch_status: COMPLETE
document_count: 4
acquired_count: 4
required_failure_count: 0
batch_metadata_evidence.zip sha256:
cf26cada5388d1145d9194e12e5e13a45bd12d47ea010162beb062e4058e5e5d
```

Raw hashes:

```text
rb-hose-index-4-0-2024-12-30
52d3b347c394e074cd613f8255c80f3f07dc1bb1fc36deedaeb7f2ea96efb228
9154693 bytes

rc-hose-index-2024-01
5f5c31dad02f73437a054a49e6eaaa04650ff71336c2d069c26b6883eae62ba5
710475 bytes

rc-hose-index-2024-07
527385e4ef8781c07aae755fb3563eaee4aad77eb0d2e5799a29f839eb968e84
725589 bytes

rc-hose-index-2026-01
a89a30791f450cc66a2bb81496eda3f250a75697b4102ea75401d29da0ff2814
698067 bytes
```

## 6. Content review thực tế

```text
run: content-review-01
batch_status: READY_FOR_MANUAL_REVIEW
document_count: 4
review_ready_count: 4
required_failure_count: 0
content_review_metadata_evidence.zip sha256:
cfe60261dd899433abc8bdd5c58b7000ab848b781dbed6d7a9355dbae42cb6f5
```

Candidate extraction:

```text
01/2024: 100 rows
07/2024: 100 rows
01/2026: 100 rows
```

Content review đã đạt objective machine checks nhưng vẫn giữ:

```text
content_reviewed=false
chain_verified=false
canonical_eligible=false
research_eligible=false
```

Ngày hiệu lực kỳ 2026 chưa được audit và không được suy diễn.

## 7. Work package active

```text
INDEPENDENT-AUDIT-BATCH-01
branch: independent-audit-batch-01
pull_request: 30
state: OPEN_DRAFT_UNMERGED
base: e66ffdd7ff30f78b5607d6b39796adcf1194390b
implementation_head: 56b000f362a7445eb7772a6ec8e788202e8b48c6
ci: PENDING
```

Outcome:

```text
raw PDF
→ pdfplumber word coordinates
→ independent row parser
→ independent rows 1–100
→ field-by-field candidate comparison
→ discrepancies + fingerprints
→ metadata evidence ZIP không chứa raw/full text
```

## 8. Independence boundary

Audit active không import hoặc gọi parser từ `review_noi_dung.py`.

Nó dùng:

```text
pdfplumber==0.11.10
word-coordinate visual lines
row-start state machine
right-to-left numeric column detection
canonical field comparison
```

Nó so sánh:

```text
raw_symbol
company_name
shares_for_index
free_float_pct
capitalization_cap_pct
source_locator
```

## 9. Safety invariants

Mọi output audit giữ:

```text
content_reviewed=false
chain_verified=false
canonical_eligible=false
research_eligible=false
interval_dates_audited=false
```

Independent match không tự chứng nhận ngày hiệu lực, stable instrument ID, chain-of-custody, corporate action, price basis, canonical range hoặc research eligibility.

Không:

- commit raw PDF/full extracted text;
- OCR;
- forward-fill kỳ thiếu;
- mở research/model run;
- sửa PR #20;
- mở Mốc 5.

## 10. Cửa PR #30

PR chỉ được nghiệm thu khi:

- full regression Ubuntu/Windows đạt trên current head cuối;
- review ZIP hash và internal hashes được kiểm;
- raw hash mismatch chặn trước PDF open;
- row mismatch tạo discrepancies;
- ZIP audit không chứa raw/PDF/full text;
- không dependency/workflow/lockfile change;
- branch không behind `main`;
- PR #20 không thay đổi;
- Mốc 5 không mở.

## 11. Next gate

Sau khi PR #30 merge, chạy đúng một lệnh từ:

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
