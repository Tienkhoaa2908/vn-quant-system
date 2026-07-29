# Runbook nền cửa dữ liệu nghiên cứu

Cập nhật: 2026-07-29

## 1. Trạng thái

Package:

```text
DATA-GATE-CLOSURE-BATCH-01
```

Nền kỹ thuật này xử lý bằng fixture tổng hợp và fail closed cho bốn blocker:

```text
VN100_POINT_IN_TIME_HISTORY_INCOMPLETE
HOSE_EOD_CROSSCHECK_INCOMPLETE
CORPORATE_ACTION_INVENTORY_INCOMPLETE
PRICE_BASIS_UNCONFIRMED
```

Nó không giải quyết blocker bằng dữ liệu thật và không đổi:

```text
RESEARCH_GATE=FAIL
```

Không fixture, publication candidate hoặc evidence metadata nào trong package được dùng làm tín hiệu vận hành hay bằng chứng hiệu quả đầu tư.

## 2. Package mã

```text
src/he_thong_dinh_luong/cua_du_lieu/
```

Thành phần:

- `hop_dong.py`: schema, enum và invariant dùng chung;
- `vn100_pit.py`: review cycle, interval half-open, identity check, tri-state query và coverage candidate;
- `doi_chieu_eod.py`: đối chiếu exact open/close/volume và trạng thái price basis;
- `hanh_dong_doanh_nghiep.py`: inventory split, dividend, rights, merger, delist, symbol change và transfer;
- `preflight.py`: tổng hợp bốn data gate, mặc định fail closed;
- `cong_bo.py`: publication candidate nguyên tử và auditor đọc độc lập;
- `thu_thap_bang_chung.py`: acquisition kit chạy trên workstation bằng file đã tải từ browser.

## 3. Bất biến VN100 PIT

Contract nghiên cứu duy nhất:

```text
pit_membership_interval_v2
```

Không auto-detect hoặc auto-convert từ:

```text
pit_membership_v1
technical_candidate_union_v1
```

Interval:

```text
[effective_from, effective_to)
```

Mọi interval phải có end đã chứng minh. Query trả đúng một trong:

```text
MEMBER
NOT_MEMBER_PROVEN
UNKNOWN
```

`UNKNOWN` không được chuyển thành false. Publication cutoff và signal cutoff phải là timestamp có múi giờ. Fixture không được `canonical_eligible` hoặc `research_eligible`.

## 4. Acquisition workstation kit

### 4.1 Điều kiện

Người dùng tự tải file trực tiếp bằng browser trên workstation có mạng. Không Print to PDF, không screenshot-to-PDF, không copy parsed text và không Save As làm thay đổi byte.

Raw archive phải nằm ngoài Git.

### 4.2 Lệnh mẫu

```bash
PYTHONPATH=src uv run --python 3.12 \
  python -m he_thong_dinh_luong.cua_du_lieu.thu_thap_bang_chung \
  --file "/duong/dan/file-da-tai.pdf" \
  --output-dir "/duong/dan/archive/run-id" \
  --source-document-id "rb40-official-001" \
  --publisher "HOSE" \
  --document-type "RULEBOOK" \
  --observed-url "https://..." \
  --locator "trang 1, bang tom tat" \
  --rights-status "RESTRICTED" \
  --source-tier "TIER_1_OFFICIAL"
```

CLI chỉ hỗ trợ raw file người dùng cung cấp. Nó không gọi mạng trong CI hoặc runtime.

### 4.3 Sản phẩm

```text
<run-id>/
  raw/<source-document-id>/
    original.bin
    acquisition_metadata.json
    sha256.txt
  evidence/
    acquisition_manifest.json
    hash_verification.json
    source_document_registry_candidate.json
    evidence_hashes.json
  metadata_evidence.zip
```

`metadata_evidence.zip` không chứa `original.bin` hoặc thư mục `raw/`.

Hash được tính bằng hai lần đọc độc lập. Nếu hai hash khác nhau, CLI dừng với `DOUBLE_HASH_MISMATCH`.

`DO_NOT_STORE` chặn copy raw. `UNKNOWN` và `RESTRICTED` yêu cầu archive hạn chế ngoài Git và không tái phân phối.

## 5. Dựng VN100 PIT candidate

Đầu vào cần có:

- `TaiLieuNguon` đã xác thực metadata;
- `KyReview` có publication timestamp có múi giờ;
- `effective_from` và `effective_to` rõ;
- `expected_member_count` từ rulebook;
- complete member list được sắp xếp và không trùng;
- stable `instrument_id` và alias interval khi có thay đổi mã.

Dùng:

```python
publication = tao_cong_bo_pit_candidate(cycles, sources)
coverage = tao_chung_nhan_coverage(publication)
```

Fixture có thể kiểm semantics với `require_canonical=False`, nhưng coverage vẫn không research eligible.

Research query phải giữ mặc định:

```python
truy_van_thanh_vien(..., require_canonical=True)
```

Gap, overlap, thiếu cycle, publication sau signal cutoff hoặc source chưa canonical đều trả `UNKNOWN` hoặc giữ gate fail.

## 6. HOSE EOD và price basis

`doi_chieu_eod(...)` so sánh exact:

```text
symbol
trading_date
open_price
close_price
volume
price_basis
```

Không sửa, scale, nội suy hoặc thay raw value để làm khớp.

Mismatch codes gồm:

```text
MISSING_CANDIDATE
MISSING_REFERENCE
OPEN_MISMATCH
CLOSE_MISMATCH
VOLUME_MISMATCH
PRICE_SCALE_MISMATCH
PRICE_BASIS_MISMATCH
```

`UNKNOWN` không được diễn giải thành adjusted hoặc unadjusted.

## 7. Corporate actions

Hỗ trợ contract:

```text
SPLIT
STOCK_DIVIDEND
CASH_DIVIDEND
RIGHTS_ISSUE
MERGER
DELIST
SYMBOL_CHANGE
TRANSFER
OTHER_OFFICIAL_ACTION
```

Mọi record cần publication timestamp có múi giờ, effective date, provenance và identity linkage. Loại sự kiện quyết định ratio, cash value, record date, payment date hoặc target instrument bắt buộc.

Inventory completeness phải được khai báo và chứng minh; không suy ra completeness từ việc không tìm thấy event.

Adjusted price đi cùng corporate actions tạo conflict `ADJUSTED_PRICE_WITH_CORPORATE_ACTIONS` để tránh áp dụng hai lần.

## 8. Publication và audit

`cong_bo_candidate(...)`:

- từ chối destination đã tồn tại;
- tạo staging cùng parent;
- serialize JSON deterministic;
- hash từng product;
- file fsync;
- một lần `os.replace`;
- luôn ghi `research_eligible=false`.

`kiem_toan_cong_bo_doc_lap(...)` không gọi builder. Auditor đọc manifest, kiểm file set, byte size, SHA-256, JSON và stable ordering. Tamper tạo lỗi rõ như `HASH_MISMATCH`.

## 9. Research preflight

Dùng:

```python
result = danh_gia_research_preflight(inputs)
```

Preflight không tự hạ research thành technical mode. `technical_candidate_union_v1`, fixture coverage, fixture corporate actions, EOD chưa đối chiếu hoặc price basis chưa xác nhận đều giữ `passed=false`.

## 10. Kiểm thử

```bash
PYTHONPATH=src uv run --python 3.12 \
  python -m unittest discover -s tests -v
```

Test mới bao phủ:

- fixture không được canonical;
- alias overlap;
- interval half-open;
- publication cutoff;
- tri-state membership;
- member-count mismatch;
- EOD exact/scale/basis mismatch;
- corporate-action validation;
- bốn blocker research preflight;
- exact raw byte và double hash;
- evidence ZIP không chứa raw;
- publication tamper detection.

## 11. Ngoài phạm vi

Package không:

- thu thập raw qua mạng trong CI;
- commit raw restricted data;
- tạo dữ liệu VN100 thật;
- xác nhận HOSE EOD thật;
- xác nhận price basis thật;
- áp dụng corporate action thật;
- chạy lại Mốc 4 research;
- tối ưu model;
- sửa PR #20;
- mở Mốc 5.
