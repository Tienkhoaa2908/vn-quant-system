# DATA-EVIDENCE-BATCH-01

Trạng thái: `READY_FOR_REVIEW`

Anchor:

```text
main: 60779f0607f00d32bc499fb4ca2f7797dfbb0870
last_merged_pr: 27
active_pr: 28
verified_ci_run: 30462309283
verified_ci_conclusion: success
```

## 1. Outcome

Giảm acquisition VN100 PIT từ nhiều lệnh và nhiều prompt xuống:

```text
một manifest
→ một thư mục browser downloads
→ một lệnh
→ nhiều raw archive bất biến
→ một evidence ZIP tổng hợp không chứa raw
```

Package không tự tải mạng, không khóa canonical data và không mở research gate.

## 2. Capability quyết định

```text
GitHub read/write: AVAILABLE
Python isolated test: AVAILABLE
local checkout: UNAVAILABLE_DNS
outbound/raw download: UNAVAILABLE
web source observation: AVAILABLE
```

Do raw download unavailable, package không lặp lại 01F-C/C2. Nó tạo đường chạy workstation duy nhất để người dùng hoàn tất acquisition trong một lượt.

## 3. Phạm vi implementation

- batch manifest contract `data_evidence_batch_v1`;
- schema validation trước khi copy file;
- unique source ID và filename;
- chặn path traversal;
- optional expected SHA-256;
- file mismatch không được copy vào raw archive;
- `DO_NOT_STORE` không được copy;
- partial progress không bị rollback vì một tài liệu thiếu;
- trạng thái batch `COMPLETE/PARTIAL/FAILED`;
- source registry candidate tổng hợp;
- metadata evidence ZIP không chứa raw;
- CLI giữ backward compatibility với mode `--file`;
- mode mới `--manifest` + `--download-dir`;
- manifest VN100 batch 01 chỉ chứa URL đã quan sát, không suy direct URL;
- runbook một lệnh;
- full CI Ubuntu/Windows.

## 4. Corpus batch 01

```text
RB HOSE-Index 4.0 — required
HOSE-Index review 01/2024 — required
HOSE-Index review 07/2024 — required
HOSE-Index review 01/2026 — optional
```

Batch này là acquisition pilot. Nó không phải research range.

## 5. Trạng thái tài liệu

```text
ACQUIRED
MISSING_FILE
HASH_MISMATCH
BLOCKED_DO_NOT_STORE
```

Một tài liệu chỉ được `ACQUIRED` sau khi:

- file cục bộ tồn tại;
- expected hash, nếu có, khớp;
- raw byte được copy nguyên trạng;
- SHA-256 hai invocation khớp;
- metadata và source candidate hợp lệ.

## 6. Acceptance criteria

### Code

- single-file mode cũ tiếp tục chạy;
- batch mode xử lý nhiều file xác định;
- file tùy chọn thiếu không làm batch thất bại;
- file bắt buộc thiếu làm batch partial/failed;
- hash mismatch không tạo raw archive;
- ZIP tổng hợp không chứa raw;
- path traversal bị từ chối.

### CI

```text
workflow: kiem_tra_tu_dong
run_number: 418
run_id: 30462309283
ubuntu_job: 90611234969
ubuntu_tests: 406
ubuntu_result: success
windows_job: 90611235250
windows_tests: 406
windows_result: success
```

- full regression Ubuntu đạt;
- full regression Windows đạt;
- không dependency/workflow/lockfile change.

### Safety

```text
RESEARCH_GATE=FAIL
VN100_POINT_IN_TIME_HISTORY_INCOMPLETE
HOSE_EOD_CROSSCHECK_INCOMPLETE
CORPORATE_ACTION_INVENTORY_INCOMPLETE
PRICE_BASIS_UNCONFIRMED
```

- không raw data trong Git;
- không canonical promotion;
- không research/model run;
- PR #20 không thay đổi;
- Mốc 5 không mở.

## 7. Next gate

Sau khi PR xanh và merge, người dùng chỉ cần chạy batch command trong runbook một lần và gửi `batch_metadata_evidence.zip` hoặc `batch_summary.json` cùng hash.

Đoạn `00` sau đó quyết định:

```text
NONCANONICAL_ACQUISITION_READY_FOR_CONTENT_REVIEW
hoặc
DATA_EVIDENCE_BATCH_NEEDS_REPAIR
```

Không tự mở content extraction trước khi có evidence batch thực tế.
