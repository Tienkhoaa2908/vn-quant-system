# Runbook kiểm toán độc lập VN100 theo lô

Cập nhật: 2026-07-30

## 1. Mục tiêu

Đọc lại bốn `original.bin` trong `run-02` bằng `pdfplumber==0.11.10`, dùng parser theo tọa độ từ độc lập với parser `pypdf` của content review, rồi so sánh từng dòng với candidate trong `content_review_metadata_evidence.zip`.

Audit chỉ kiểm:

- exact raw SHA-256 và byte size;
- exact review ZIP SHA-256 và hash nội bộ;
- số trang và marker;
- chuỗi dòng 1–100;
- mã, tên chuẩn hóa, số cổ phiếu, free-float, capitalization cap và source locator;
- chênh lệch từng field.

Audit không chứng nhận ngày hiệu lực, stable instrument ID, chain-of-custody, canonical status hoặc research eligibility.

## 2. Đường dẫn workstation

```text
repository:
C:\Users\welcome\Documents\vn-quant-system

raw acquisition:
C:\Users\welcome\Documents\vn-quant-data\run-02

content-review evidence:
C:\Users\welcome\Documents\vn-quant-data\content-review-01\content_review_metadata_evidence.zip

audit output:
C:\Users\welcome\Documents\vn-quant-data\independent-audit-01
```

## 3. Chạy một khối lệnh

Mở Git Bash trong repository và chạy nguyên khối:

```bash
git switch main
git pull --ff-only origin main

RUN_ROOT="/c/Users/welcome/Documents/vn-quant-data/run-02"
REVIEW_ZIP="/c/Users/welcome/Documents/vn-quant-data/content-review-01/content_review_metadata_evidence.zip"
OUTPUT="/c/Users/welcome/Documents/vn-quant-data/independent-audit-01"

test -d "$RUN_ROOT" || {
  echo "LOI: khong tim thay run-02"
  exit 1
}

test -f "$REVIEW_ZIP" || {
  echo "LOI: khong tim thay content_review_metadata_evidence.zip"
  exit 1
}

test ! -e "$OUTPUT" || {
  echo "LOI: independent-audit-01 da ton tai; dung independent-audit-02"
  exit 1
}

PYTHONPATH=src uv run --python 3.12 --with pdfplumber==0.11.10 \
  python -m he_thong_dinh_luong.cua_du_lieu.kiem_toan_doc_lap \
  --run-root "$RUN_ROOT" \
  --review-evidence-zip "$REVIEW_ZIP" \
  --manifest tai_lieu/manifest_kiem_toan_doc_lap_vn100_batch_01.json \
  --output-dir "$OUTPUT"

echo
echo "===== KET QUA AUDIT ====="
cat "$OUTPUT/evidence/batch_summary.json"

echo
echo "===== CHENH LECH ====="
cat "$OUTPUT/evidence/discrepancies.json"

echo
echo "===== SHA-256 ====="
sha256sum "$OUTPUT/independent_audit_metadata_evidence.zip"
```

`--with pdfplumber==0.11.10` chỉ cài parser cho lần chạy, không sửa `pyproject.toml` hoặc `uv.lock`.

## 4. Kết quả đạt

```text
batch_status: INDEPENDENT_AUDIT_PASSED
document_count: 4
matched_count: 4
required_failure_count: 0
discrepancy_count: 0
```

Nếu tài liệu 2026 tùy chọn không đạt nhưng ba tài liệu bắt buộc đạt, trạng thái có thể là `INDEPENDENT_AUDIT_PARTIAL`. Trạng thái này không đủ để tự nâng canonical.

## 5. File gửi lại

```text
C:\Users\welcome\Documents\vn-quant-data\independent-audit-01\independent_audit_metadata_evidence.zip
```

Kèm output terminal từ `===== KET QUA AUDIT =====` trở xuống.

Không gửi `original.bin` hoặc raw PDF.

## 6. Cấu trúc evidence

```text
independent-audit-01/
  evidence/
    manifest_copy.json
    audit_results.json
    independent_membership_rows.json
    discrepancies.json
    word_stream_fingerprints.json
    batch_summary.json
    evidence_hashes.json
  independent_audit_metadata_evidence.zip
```

ZIP không chứa raw PDF, `original.bin` hoặc full extracted text.

## 7. Cửa sau audit

Ngay cả khi audit đạt, mọi cờ vẫn là:

```text
content_reviewed=false
chain_verified=false
canonical_eligible=false
research_eligible=false
interval_dates_audited=false
```

Kết quả đạt chỉ cho phép mở manual review/identity/interval audit tiếp theo. Không được chạy research, forward-fill kỳ thiếu hoặc tuyên bố PIT history hoàn chỉnh.
