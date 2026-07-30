# Runbook cập nhật EOD và chạy dự đoán hằng ngày

Cập nhật: 2026-07-30

## Mục tiêu

Sau 18:00 giờ Việt Nam, chạy một lệnh để:

```text
KBS EOD + VCI EOD
→ đối chiếu open/close/volume
→ cập nhật publication bất biến
→ tính feature ngày mới nhất
→ chạy champion–challenger
→ xuất Top 10 và paper portfolio
```

Không dùng dữ liệu trong phiên. Không cần tài khoản SSI.

## Điều kiện trước khi chạy

Máy phải còn các dữ liệu đã tạo trước đó trong:

```text
C:\Users\welcome\Documents\vn-quant-data
```

Tối thiểu phải có:

```text
prediction_input.zip
một publication reduced hợp lệ chứa 5 file canonical
```

Pipeline tự tìm publication mới nhất; người dùng không cần biết tên thư mục publication.

## Thời điểm chạy

Chạy sau:

```text
18:00 mỗi ngày giao dịch
```

Nếu chạy sớm hơn, chương trình dừng với:

```text
MARKET_NOT_FINAL_BEFORE_18H_VN
```

Nếu KBS/VCI chưa công bố đủ dữ liệu, chương trình dừng và không tạo prediction mới.

## Bước 1 — Mở Git Bash

Mở File Explorer, vào:

```text
C:\Users\welcome\Documents\vn-quant-system
```

Nhấp chuột phải vùng trống và chọn `Open Git Bash here`.

## Bước 2 — Dán nguyên khối lệnh

```bash
git switch main
git pull --ff-only origin main

DATA_ROOT="/c/Users/welcome/Documents/vn-quant-data"
RUN_ID="$(date +%Y%m%d_%H%M%S)"
OUTPUT="$DATA_ROOT/eod-daily-$RUN_ID"

 test -f "$DATA_ROOT/prediction_input.zip" || {
  echo "LOI: khong tim thay prediction_input.zip"
  exit 1
}

PYTHONPATH=src uv run --python 3.12 \
  --with vnstock==4.0.4 \
  --with lightgbm==4.6.0 \
  python -m he_thong_dinh_luong.eod_hang_ngay \
  --data-root "$DATA_ROOT" \
  --output-dir "$OUTPUT" \
  --min-coverage 0.95 \
  --price-tolerance-bps 10 \
  --volume-tolerance-ratio 0.05

STATUS=$?

echo
echo "===== THU MUC KET QUA ====="
echo "$OUTPUT"

if [ -f "$OUTPUT/daily_prediction_summary.txt" ]; then
  echo
  echo "===== TOM TAT DU DOAN ====="
  cat "$OUTPUT/daily_prediction_summary.txt"
fi

if [ -f "$OUTPUT/data_quality_report.json" ]; then
  echo
  echo "===== CHAT LUONG DU LIEU ====="
  cat "$OUTPUT/data_quality_report.json"
fi

if [ -f "$OUTPUT/daily_quant_output.zip" ]; then
  echo
  echo "===== SHA-256 ====="
  sha256sum "$OUTPUT/daily_quant_output.zip"
fi

exit $STATUS
```

Dòng `test -f` không có khoảng trắng ở đầu cũng chạy được; khoảng trắng đầu dòng trong Git Bash không làm thay đổi lệnh.

## Kết quả thành công

Terminal phải có JSON chứa:

```text
"status": "SUCCESS"
```

Thư mục kết quả có:

```text
data_quality_report.json
daily_prediction_summary.txt
daily_prediction_input.zip
updated_publication/
prediction/
paper_portfolio.csv
manifest.json
daily_quant_output.zip
raw/
```

`raw/` lưu bằng chứng KBS và VCI trên máy. `daily_quant_output.zip` không chứa raw.

## File cần gửi vào chat

Gửi đúng file:

```text
C:\Users\welcome\Documents\vn-quant-data\eod-daily-<RUN_ID>\daily_quant_output.zip
```

Kèm phần terminal từ:

```text
===== TOM TAT DU DOAN =====
```

Không gửi `raw/kbs.json` hoặc `raw/vci.json`.

## Các trạng thái lỗi chính

### `EOD_NOT_PUBLISHED`

Nguồn mở chưa có dữ liệu của phiên hôm nay. Chờ 30–60 phút rồi chạy lại; lệnh tạo một thư mục output mới theo thời gian nên không ghi đè lần cũ.

### `EOD_DATA_NOT_FINAL`

Dưới 95% universe có dữ liệu khớp giữa KBS và VCI. Không tạo dự đoán.

### `FEATURE_COVERAGE_NOT_FINAL`

Dữ liệu EOD đã đủ nhưng dưới 95% mã tạo được feature đầy đủ. Không tạo dự đoán.

### `HISTORICAL_REVISION_CONFLICT`

Nguồn mới trả dữ liệu khác với publication đã khóa cho cùng mã/ngày. Pipeline không tự sửa lịch sử.

## Nguyên tắc vận hành

- Signal của ngày `t` chỉ dùng sau khi EOD ngày `t` đã chốt.
- Giao dịch paper sớm nhất là phiên kế tiếp.
- KBS là nguồn primary; VCI là nguồn đối chiếu.
- Chỉ đối chiếu open/close/volume vì publication hiện dùng hợp đồng reduced.
- Output tiếp tục giữ `research_eligible=false` cho đến khi đóng price basis, corporate actions và PIT universe.
