# Bản điều phối hiện hành

Cập nhật: 2026-07-29

Tài liệu này là snapshot current-state. Nếu tài liệu trạng thái tích lũy cũ mâu thuẫn với snapshot này, dùng snapshot này cùng merged `main` và `DECISIONS.md`.

## 1. Anchor

```text
repository: Tienkhoaa2908/vn-quant-system
main: 60779f0607f00d32bc499fb4ca2f7797dfbb0870
last_merged_pr: 27
last_verified_pr_ci: 30460565044
ubuntu_job: 90605237730
windows_job: 90605237640
ci_conclusion: success
post_merge_push_ci: NOT_OBSERVABLE_BY_CURRENT_CONNECTOR
```

PR #27 đã merge bằng merge commit. Head trước merge đã vượt 402 test trên Ubuntu và Windows.

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

## 4. Work package đã merge

```text
DATA-GATE-CLOSURE-BATCH-01
DATA_GATE_FOUNDATION_READY
```

Đã merge qua PR #27:

- contract nguồn, identity, review cycle và membership interval v2;
- tri-state as-of và coverage candidate;
- EOD/price-basis comparison foundation;
- corporate-action inventory foundation;
- research preflight fail closed;
- deterministic publication và independent auditor;
- acquisition CLI single-file;
- 402 test đạt trên Ubuntu/Windows.

Foundation dùng fixture và không research eligible.

## 5. Capability blocker đã khóa

```text
local checkout: UNAVAILABLE_DNS
outbound network: UNAVAILABLE
raw-byte transfer: UNAVAILABLE
web source observation: AVAILABLE
GitHub read/write: AVAILABLE
```

Không tiếp tục phát prompt thử tải raw trong cùng môi trường. Raw acquisition được chuyển sang workstation có browser/network.

## 6. Work package active

```text
DATA-EVIDENCE-BATCH-01
branch: data-evidence-batch-01
pull_request: 28
state: OPEN_DRAFT_UNMERGED
base: 60779f0607f00d32bc499fb4ca2f7797dfbb0870
```

Outcome:

```text
một manifest
→ một thư mục browser downloads
→ một lệnh
→ nhiều raw archive bất biến
→ một evidence ZIP tổng hợp không chứa raw
```

Đã triển khai trên PR #28:

- batch contract `data_evidence_batch_v1`;
- mode `--manifest` + `--download-dir`;
- giữ compatibility mode `--file`;
- path-traversal guard;
- unique ID/filename;
- optional expected SHA-256;
- hash mismatch và DO_NOT_STORE không copy raw;
- partial progress khi tài liệu độc lập thiếu;
- batch status COMPLETE/PARTIAL/FAILED;
- source registry candidate tổng hợp;
- metadata ZIP không chứa raw;
- manifest VN100 batch 01;
- runbook một lệnh;
- negative/boundary tests.

## 7. Corpus acquisition batch 01

```text
RB HOSE-Index 4.0 — required
HOSE-Index review 01/2024 — required
HOSE-Index review 07/2024 — required
HOSE-Index review 01/2026 — optional
```

Các URL trong manifest phải là URL đã quan sát. Không suy direct attachment URL chưa xác minh.

Batch này không khóa research range và không nâng Tier 2 thành canonical.

## 8. Cửa PR #28

PR chỉ được nghiệm thu khi:

- full regression Ubuntu/Windows đạt;
- single-file mode cũ không bị vỡ;
- hash mismatch không tạo raw;
- ZIP tổng hợp không có raw;
- path traversal bị chặn;
- không dependency/workflow/lockfile change;
- PR #20 không thay đổi;
- Mốc 5 không mở.

## 9. Next gate duy nhất

Sau khi PR #28 merge, chạy đúng một batch command trên workstation và gửi metadata evidence ZIP hoặc batch summary cùng SHA-256.

Đoạn `00` sau đó quyết định:

```text
NONCANONICAL_ACQUISITION_READY_FOR_CONTENT_REVIEW
hoặc
DATA_EVIDENCE_BATCH_NEEDS_REPAIR
```

Chưa mở content extraction hoặc research run trước khi có evidence batch thực tế.
