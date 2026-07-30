# Runbook review nội dung VN100 theo lô

Cập nhật: 2026-07-30

## 1. Mục tiêu

Đọc bốn `original.bin` đã acquisition trong `run-02`, xác minh lại SHA-256/byte size,
trích xuất text bằng `pypdf==5.9.0`, kiểm marker, kiểm số trang và trích đúng bảng VN100
theo page contract.

Công cụ chỉ tạo candidate và bằng chứng review. Công cụ không tự đặt:

```text
content_reviewed=true
chain_verified=true
canonical_eligible=true
research_eligible=true
```

## 2. Đường dẫn mặc định của workstation

```text
repository:
C:\Users\welcome\Documents\vn-quant-system

acquisition run:
C:\Users\welcome\Documents\vn-quant-data\run-02

content review output:
C:\Users\welcome\Documents\vn-quant-data\content-review-01
```

## 3. Chạy một khối lệnh

Mở Git Bash trong repository và chạy nguyên khối:

```bash
git switch main
git pull --ff-only origin main

RUN_ROOT="/c/Users/welcome/Documents/vn-quant-data/run-02"
OUTPUT="/c/Users/welcome/Documents/vn-quant-data/content-review-01"

test -d "$RUN_ROOT" || {
  echo "LOI: khong tim thay run-02"
  exit 1
}

test ! -e "$OUTPUT" || {
  echo "LOI: content-review-01 da ton tai; dung content-review-02"
  exit 1
}

PYTHONPATH=src uv run --python 3.12 --with pypdf==5.9.0 \
  python -m he_thong_dinh_luong.cua_du_lieu.review_noi_dung \
  --run-root "$RUN_ROOT" \
  --manifest tai_lieu/manifest_review_noi_dung_vn100_batch_01.json \
  --output-dir "$OUTPUT"

cat "$OUTPUT/evidence/batch_summary.json"
sha256sum "$OUTPUT/content_review_metadata_evidence.zip"
```

`--with pypdf==5.9.0` chỉ bổ sung parser cho lần chạy; không sửa `pyproject.toml`
hoặc `uv.lock`.

## 4. Kết quả mong đợi

```text
batch_status: READY_FOR_MANUAL_REVIEW
document_count: 4
review_ready_count: 4
required_failure_count: 0
```

Nếu tài liệu tùy chọn 2026 không đạt nhưng ba tài liệu bắt buộc đạt, batch vẫn có thể
`READY_FOR_MANUAL_REVIEW`.

## 5. File cần gửi lại

```text
C:\Users\welcome\Documents\vn-quant-data\content-review-01\
content_review_metadata_evidence.zip
```

Kèm output SHA-256 cuối terminal.

Không gửi `original.bin`.

## 6. Cấu trúc evidence

```text
content-review-01/
  evidence/
    manifest_copy.json
    document_review_results.json
    page_text_fingerprints.json
    vn100_membership_candidates.json
    batch_summary.json
    evidence_hashes.json
  content_review_metadata_evidence.zip
```

ZIP không chứa PDF, `original.bin` hoặc full extracted text. Nó chỉ chứa metadata,
page fingerprints và candidate rows.

## 7. Cửa sau khi chạy

Kết quả đạt chỉ cho phép mở manual review và independent audit. Không được dùng candidate
để chạy research, forward-fill kỳ thiếu hoặc tuyên bố PIT history đã hoàn chỉnh.
