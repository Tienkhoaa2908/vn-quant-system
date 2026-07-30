# Bản điều phối hiện hành

Cập nhật: 2026-07-30

Nếu tài liệu trạng thái cũ mâu thuẫn, dùng snapshot này cùng merged `main` và `DECISIONS.md`.

## 1. Anchor

```text
repository: Tienkhoaa2908/vn-quant-system
main: e66ffdd7ff30f78b5607d6b39796adcf1194390b
last_merged_pr: 29
last_verified_pr_ci: 30515929824
post_merge_push_ci: NOT_OBSERVABLE_BY_CURRENT_CONNECTOR
```

PR #29 đã merge. Head trước merge đạt 411 test trên Ubuntu và Windows.

PR #20 vẫn Open/Draft/Unmerged và không thuộc phạm vi active.

## 2. Trạng thái kỹ thuật

- Mốc 0–4 có implementation nền và technical validation.
- Lần chạy kỹ thuật rộng Mốc 4: 121 mã nguồn, 120 mã có prediction, 36 fold, 34 fold thành công.
- Logistic Regression yếu hơn momentum trong lần chạy rộng.
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
PR #27 DATA-GATE-CLOSURE-BATCH-01
PR #28 DATA-EVIDENCE-BATCH-01
PR #29 CONTENT-REVIEW-BATCH-01
```

Các package đã cung cấp contract, acquisition và content-review pipeline. Chúng không tự canonical hoặc research eligible.

## 5. Acquisition thực tế

```text
root: C:\Users\welcome\Documents\vn-quant-data
run: run-02
batch_status: COMPLETE
document_count: 4
acquired_count: 4
required_failure_count: 0
batch_metadata_evidence.zip sha256:
cf26cada5388d1145d9194e12e5e13a45bd12d47ea010162beb062e4058e5e5d
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

01/2024: 100 rows
07/2024: 100 rows
01/2026: 100 rows
```

Các cờ vẫn là:

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
state: OPEN_READY_PENDING_FINAL_CI
base: e66ffdd7ff30f78b5607d6b39796adcf1194390b
implementation_head_verified: cf494820aa525b11a660e0018692d6a122b04da3
verified_ci_run: 30517342117
verified_ci_conclusion: success
```

CI #428 trên implementation head:

```text
ubuntu_job: 90790034590
ubuntu_tests: 416
ubuntu_skipped: 2
ubuntu_result: success

windows_job: 90790034636
windows_tests: 416
windows_skipped: 3
windows_result: success
```

Commit tài liệu trạng thái sau CI phải được full regression lại trước khi PR chuyển Ready.

## 8. Audit independence

```text
raw PDF
→ pdfplumber==0.11.10
→ word-coordinate visual lines
→ row-start state machine
→ independent rows 1–100
→ field-by-field candidate comparison
→ discrepancies + fingerprints
```

Audit không import parser `review_noi_dung.py` và không dùng candidate page fingerprints.

Fields so sánh:

```text
raw_symbol
company_name
shares_for_index
free_float_pct
capitalization_cap_pct
source_locator
```

## 9. Safety invariants

```text
content_reviewed=false
chain_verified=false
canonical_eligible=false
research_eligible=false
interval_dates_audited=false
```

Independent match không tự chứng nhận ngày hiệu lực, stable instrument ID, chain-of-custody, corporate action, price basis, canonical range hoặc research eligibility.

Không commit raw/full text, không OCR, không forward-fill, không chạy research/model, không sửa PR #20 và không mở Mốc 5.

## 10. Cửa PR #30

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

Sau khi PR #30 merge, chạy:

```text
tai_lieu/runbook_kiem_toan_doc_lap_vn100_theo_lo.md
```

Sau evidence thực tế:

```text
VN100_MEMBERSHIP_EXTRACTION_INDEPENDENTLY_MATCHED
hoặc
INDEPENDENT_AUDIT_NEEDS_REPAIR
```

Research gate vẫn FAIL cho đến khi chain, identity, interval coverage, EOD, corporate action và price basis được đóng.
