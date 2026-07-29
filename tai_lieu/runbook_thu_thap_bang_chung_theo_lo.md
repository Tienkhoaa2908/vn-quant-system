# Runbook thu thập bằng chứng theo lô

Cập nhật: 2026-07-29

## 1. Mục tiêu

Runbook này thay việc chạy một lệnh cho từng PDF bằng một batch manifest và một lần chạy duy nhất.

Công cụ chỉ đọc file cục bộ người dùng đã tải bằng browser. Công cụ không gọi mạng, không vượt access control và không đưa raw byte vào Git.

## 2. Manifest chuẩn

Manifest đầu tiên:

```text
tai_lieu/manifest_thu_thap_vn100_batch_01.json
```

Contract:

```text
data_evidence_batch_v1
```

Mỗi dòng tài liệu khóa:

```text
source_document_id
filename
publisher
document_type
observed_url
rights_status
source_tier
locator
required
expected_sha256
```

`expected_sha256` để `null` cho lần acquisition đầu. Sau khi có một raw byte đã kiểm toán, một vòng sau mới được khóa expected hash.

## 3. Chuẩn bị thư mục ngoài Git

Ví dụ trên Windows/Git Bash:

```bash
mkdir -p "/c/vn-quant-evidence/vn100-batch-01/downloads"
```

Tải các attachment bằng browser và đổi tên đúng theo `filename` trong manifest:

```text
rb-hose-index-4-0-2024-12-30.pdf
rc-hose-index-2024-01.pdf
rc-hose-index-2024-07.pdf
rc-hose-index-2026-01.pdf
```

Không dùng Print to PDF, screenshot-to-PDF hoặc Save As làm thay đổi nội dung. Phải giữ file attachment browser tải về.

## 4. Chạy một lệnh

Từ repository đã đồng bộ `main`:

```bash
PYTHONPATH=src uv run --python 3.12 \
  python -m he_thong_dinh_luong.cua_du_lieu.thu_thap_bang_chung \
  --manifest tai_lieu/manifest_thu_thap_vn100_batch_01.json \
  --download-dir "/c/vn-quant-evidence/vn100-batch-01/downloads" \
  --output-dir "/c/vn-quant-evidence/vn100-batch-01/run-01"
```

`output-dir` phải chưa tồn tại để tránh ghi đè bằng chứng cũ.

## 5. Trạng thái batch

```text
COMPLETE
PARTIAL
FAILED
```

Quy tắc:

- `COMPLETE`: mọi tài liệu `required=true` đã acquisition;
- `PARTIAL`: có ít nhất một tài liệu acquisition nhưng còn tài liệu bắt buộc chưa đạt;
- `FAILED`: không tài liệu nào acquisition.

Trạng thái từng tài liệu:

```text
ACQUIRED
MISSING_FILE
HASH_MISMATCH
BLOCKED_DO_NOT_STORE
```

Một tài liệu lỗi không làm mất kết quả của các tài liệu độc lập khác.

## 6. Cấu trúc đầu ra

```text
run-01/
  documents/
    <source_document_id>/
      raw/
        <source_document_id>/
          original.bin
          acquisition_metadata.json
          sha256.txt
      evidence/
        acquisition_manifest.json
        hash_verification.json
        source_document_registry_candidate.json
        evidence_hashes.json
      metadata_evidence.zip
  evidence/
    acquisition_results.json
    batch_manifest_copy.json
    batch_summary.json
    source_document_registry_candidate.json
    evidence_hashes.json
  batch_metadata_evidence.zip
```

`batch_metadata_evidence.zip` chỉ chứa metadata/evidence JSON. Nó không chứa `original.bin` hoặc thư mục `raw/`.

## 7. Kiểm tra nhanh

```bash
python - <<'PY'
from pathlib import Path
from zipfile import ZipFile

root = Path('/c/vn-quant-evidence/vn100-batch-01/run-01')
with ZipFile(root / 'batch_metadata_evidence.zip') as archive:
    bad = [name for name in archive.namelist() if 'original.bin' in name or '/raw/' in name]
    print({'raw_entries_in_zip': bad, 'entry_count': len(archive.namelist())})
    raise SystemExit(1 if bad else 0)
PY
```

## 8. Ý nghĩa kiểm soát

Batch acquisition chỉ tạo source registry candidate và hash evidence.

Nó không tự đặt:

```text
content_reviewed=true
chain_verified=true
canonical_eligible=true
research_eligible=true
```

Sau batch này vẫn cần content review, chain-of-custody comparison, identity resolution, normalized extraction và independent audit.

## 9. Cấm

Không:

- commit raw PDF;
- commit thư mục evidence ngoài Git;
- gửi raw restricted file vào PR;
- suy direct URL chưa quan sát;
- đổi `UNKNOWN` thành `PERMITTED`;
- forward-fill kỳ thiếu;
- mở research run;
- sửa PR #20;
- mở Mốc 5.
