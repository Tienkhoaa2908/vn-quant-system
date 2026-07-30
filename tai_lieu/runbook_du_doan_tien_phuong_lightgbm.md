# Runbook forward prediction bằng LightGBM

Cập nhật: 2026-07-30

## Mục tiêu

Đọc `prediction_input.zip`, kiểm tra SHA-256 theo manifest, huấn luyện LightGBM ranker theo thời gian, so sánh với momentum baseline và xuất bảng dự đoán mới nhất.

LightGBM chỉ được chọn làm champion khi vượt momentum qua toàn bộ cửa:

- Rank IC dương;
- Rank IC cao hơn momentum;
- Top-K relative return cao hơn momentum;
- Precision@K không thấp hơn momentum;
- turnover không vượt giới hạn.

Nếu không đạt, momentum tiếp tục là champion. Không ép ML thắng.

## Bước 1 — Mở Git Bash

Mở thư mục:

```text
C:\Users\welcome\Documents\vn-quant-system
```

Nhấp chuột phải vùng trống và chọn `Open Git Bash here`.

## Bước 2 — Chạy nguyên khối

```bash
git switch main
git pull --ff-only origin main

INPUT="/c/Users/welcome/Documents/vn-quant-data/prediction_input.zip"
OUTPUT="/c/Users/welcome/Documents/vn-quant-data/forward-prediction-01"

test -f "$INPUT" || {
  echo "LOI: khong tim thay prediction_input.zip"
  exit 1
}

test ! -e "$OUTPUT" || {
  echo "LOI: forward-prediction-01 da ton tai; dung forward-prediction-02"
  exit 1
}

PYTHONPATH=src uv run --python 3.12 --with lightgbm==4.6.0 \
  python -m he_thong_dinh_luong.nghien_cuu_moc_4.du_doan_tien_phuong \
  --input-zip "$INPUT" \
  --output-dir "$OUTPUT" \
  --top-k 10 \
  --validation-months 12

echo
echo "===== TOM TAT ====="
cat "$OUTPUT/prediction_summary.txt"

echo
echo "===== SO SANH MODEL ====="
cat "$OUTPUT/model_comparison.json"

echo
echo "===== SHA-256 ====="
sha256sum "$OUTPUT/forward_prediction_output.zip"
```

`--with lightgbm==4.6.0` chỉ cài LightGBM cho lần chạy. Không sửa `pyproject.toml` hoặc `uv.lock`.

## Bước 3 — File cần gửi lại

Gửi file:

```text
C:\Users\welcome\Documents\vn-quant-data\forward-prediction-01\forward_prediction_output.zip
```

Kèm phần terminal từ `===== TOM TAT =====` trở xuống.

Không gửi lại raw OHLCV.

## Đầu ra

```text
forward-prediction-01/
  latest_prediction.csv
  model_comparison.json
  prediction_summary.txt
  manifest.json
  forward_prediction_output.zip
```

## Cách đọc kết quả

- `champion_model=lightgbm_ranker`: LightGBM vượt momentum qua toàn bộ cửa.
- `champion_model=momentum_baseline`: LightGBM chưa đủ tốt; hệ thống giữ baseline.
- `selected_top_k=true`: mã nằm trong Top 10 của champion.
- `technical_weight_pct`: tỷ trọng kỹ thuật theo risk budget heuristic.
- `research_eligible=false`: kết quả chưa phải tín hiệu production hoặc khuyến nghị đầu tư.

Risk budget hiện là heuristic kỹ thuật, chưa được validation:

- `RISK_ON`: 100%;
- `NEUTRAL`: 50%;
- `RISK_OFF`: 25%.

Nó tách biệt với alpha ranking và không quyết định champion model.
