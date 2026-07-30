# Bản điều phối hiện hành

Cập nhật: 2026-07-30

Tài liệu này là snapshot current-state. Nếu tài liệu trạng thái tích lũy cũ mâu thuẫn với snapshot này, dùng snapshot này cùng merged `main` và `DECISIONS.md`.

## 1. Anchor

```text
repository: Tienkhoaa2908/vn-quant-system
main: dbb138fdf28f9bc6aa113f43197dc930560e9407
last_merged_pr: 28
last_verified_pr_ci: 30462721822
ubuntu_job: 90612684497
windows_job: 90612684453
ci_conclusion: success
post_merge_push_ci: NOT_OBSERVABLE_BY_CURRENT_CONNECTOR
```

PR #28 đã merge bằng merge commit. Head trước merge đã vượt 406 test trên Ubuntu và Windows.

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

Không blocker nào được coi là resolved.

## 4. Work packages đã merge

```text
DATA-GATE-CLOSURE-BATCH-01
DATA_GATE_FOUNDATION_READY
PR: 27

DATA-EVIDENCE-BATCH-01
DATA_EVIDENCE_BATCH_READY
PR: 28
```

Đã có nền contract, audit, preflight và acquisition theo lô. Foundation không tự research eligible.

## 5. Acquisition thực tế đã hoàn tất

```text
workstation_root: C:\Users\welcome\Documents\vn-quant-data
run: run-02
batch_status: COMPLETE
document_count: 4
acquired_count: 4
missing_count: 0
required_failure_count: 0
batch_metadata_evidence.zip sha256:
cf26cada5388d1145d9194e12e5e13a45bd12d47ea010162beb062e4058e5e5d
```

Raw documents:

```text
rb-hose-index-4-0-2024-12-30
sha256: 52d3b347c394e074cd613f8255c80f3f07dc1bb1fc36deedaeb7f2ea96efb228
size: 9154693

rc-hose-index-2024-01
sha256: 5f5c31dad02f73437a054a49e6eaaa04650ff71336c2d069c26b6883eae62ba5
size: 710475

rc-hose-index-2024-07
sha256: 527385e4ef8781c07aae755fb3563eaee4aad77eb0d2e5799a29f839eb968e84
size: 725589

rc-hose-index-2026-01
sha256: a89a30791f450cc66a2bb81496eda3f250a75697b4102ea75401d29da0ff2814
size: 698067
```

Acquisition đủ để mở content-review candidate pipeline. Nó chưa khóa chain-of-custody hoặc canonical status.

## 6. Work package active

```text
CONTENT-REVIEW-BATCH-01
branch: content-review-batch-01
pull_request: 29
state: OPEN_DRAFT_UNMERGED
base: dbb138fdf28f9bc6aa113f43197dc930560e9407
implementation_head_verified: e69d0bb822ad10e4e1c207cc57b3ebd9bb950156
current_head_after_status_docs: PENDING_FINAL_CI
```

Outcome:

```text
exact raw byte
→ SHA-256/byte-size recheck
→ PDF text extraction
→ marker/page contract validation
→ VN100 rows 1–100
→ candidate JSON + page fingerprints
→ metadata evidence ZIP không chứa raw/full text
```

Đã triển khai:

- contract `content_review_batch_v1`;
- acquisition-registry crosscheck;
- lazy parser với workstation command `uv run --with pypdf==5.9.0`;
- page-count và marker validation;
- accent-insensitive normalization;
- page-specific VN100 extraction;
- exact row sequence/member count;
- duplicate/conflict detection;
- page text fingerprints;
- candidate membership JSON;
- one-command runbook;
- synthetic negative/boundary tests.

## 7. Page contracts khóa

```text
HOSE-Index rulebook 4.0
expected pages: 28

VN100 01/2024
page indexes: 3,4,5
expected rows: 100
candidate interval: [2024-02-05, 2024-08-02)

VN100 07/2024
page indexes: 7,8
expected rows: 100
candidate interval: [2024-08-05, 2025-01-24)

VN100 01/2026
page indexes: 3,4,5
expected rows: 100
required: false
```

Page indexes là zero-based. Không quét toàn tài liệu để tránh trộn các bảng chỉ số khác.

## 8. CI PR #29

Implementation head `e69d0bb822ad10e4e1c207cc57b3ebd9bb950156`:

```text
workflow: kiem_tra_tu_dong
run_number: 423
run_id: 30515784696
conclusion: success

ubuntu_job: 90785149965
ubuntu_tests: 411
ubuntu_result: success
ubuntu_skipped: 2

windows_job: 90785149958
windows_tests: 411
windows_result: success
windows_skipped: 3
```

Status-document commit sau CI phải được chạy full regression lại trước khi PR chuyển Ready.

## 9. Safety invariants

Mọi output content review hiện giữ:

```text
content_reviewed=false
chain_verified=false
canonical_eligible=false
research_eligible=false
```

Không:

- commit raw PDF hoặc full extracted text;
- OCR tự động;
- forward-fill kỳ thiếu;
- suy stable instrument ID từ symbol mà không review;
- mở research/model run;
- sửa PR #20;
- mở Mốc 5.

## 10. Cửa PR #29

PR chỉ được nghiệm thu khi:

- full regression Ubuntu/Windows đạt trên current head cuối;
- hash/size mismatch chặn trước PDF read;
- row sequence 1–100 và member count được kiểm;
- ZIP không chứa raw/full text;
- không dependency/workflow/lockfile change;
- PR #20 không thay đổi;
- Mốc 5 không mở.

## 11. Next gate duy nhất

Sau khi PR #29 xanh và merge, chạy đúng một lệnh từ:

```text
tai_lieu/runbook_review_noi_dung_vn100_theo_lo.md
```

Sau khi nhận evidence thực tế, đoạn `00` quyết định:

```text
CONTENT_REVIEW_CANDIDATES_READY_FOR_INDEPENDENT_AUDIT
hoặc
CONTENT_REVIEW_BATCH_NEEDS_REPAIR
```

Chưa mở canonical promotion hoặc research run.
