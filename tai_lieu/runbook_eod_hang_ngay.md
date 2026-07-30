# Runbook cập nhật EOD và chạy dự đoán hằng ngày

Cập nhật: 2026-07-30

## Kiến trúc nguồn

DNSE OpenAPI có ba nhóm sản phẩm:

```text
Trading API
Broker API
Market Data API
```

Vòng EOD này chỉ dùng `Market Data API`. `Trading API` chưa được dùng để đặt lệnh; `Broker API` không thuộc phạm vi hệ thống cá nhân.

Nguồn vận hành:

```text
DNSE Market Data API: primary
KBS qua vnstock: secondary cross-check
VCI qua vnstock: fallback có thể chọn bằng CLI
```

Sau 18:00 giờ Việt Nam, pipeline:

```text
DNSE EOD + KBS EOD
→ tìm toàn bộ phiên còn thiếu kể từ publication local
→ đối chiếu open/close/volume từng phiên
→ cập nhật publication bất biến
→ tính feature ngày mới nhất
→ chạy champion–challenger
→ xuất Top 10 và paper portfolio
```

Không dùng dữ liệu trong phiên. Nếu nhiều ngày chưa chạy, pipeline tự bắt kịp toàn bộ phiên giao dịch bị thiếu trước khi dự đoán.

## Bảo mật credential

DNSE dùng hai giá trị:

```text
API Key
API Secret
```

Không gửi hai giá trị này vào chat, issue, pull request hoặc commit. File local `.env.dnse` đã thuộc mẫu `.env.*` được `.gitignore` loại trừ.

## Bước 1 — Lưu credential một lần trên máy

Mở Git Bash tại:

```text
C:\Users\welcome\Documents\vn-quant-system
```

Dán khối sau. Ký tự nhập ở dòng API Secret sẽ không hiện trên màn hình.

```bash
umask 077
read -r -p "DNSE API Key: " DNSE_KEY_INPUT
read -r -s -p "DNSE API Secret: " DNSE_SECRET_INPUT
echo
printf 'DNSE_API_KEY=%q\nDNSE_API_SECRET=%q\n' \
  "$DNSE_KEY_INPUT" "$DNSE_SECRET_INPUT" > .env.dnse
unset DNSE_KEY_INPUT DNSE_SECRET_INPUT

echo "Da tao file local .env.dnse"
read -r -p "Nhan Enter de tiep tuc..."
```

Khối này không đóng Git Bash.

## Bước 2 — Smoke DNSE trước lần chạy đầu

Smoke chỉ đọc HPG và VNINDEX trong khoảng gần nhất. Nó không chạy model, không sửa publication và không ghi credential vào evidence.

```bash
git switch main
git pull --ff-only origin main

set -a
source .env.dnse
set +a

DATA_ROOT="/c/Users/welcome/Documents/vn-quant-data"
RUN_ID="$(date +%Y%m%d_%H%M%S)"
OUTPUT="$DATA_ROOT/dnse-smoke-$RUN_ID"

PYTHONPATH=src uv run --python 3.12 \
  --with dnse==0.5.0 \
  python -m he_thong_dinh_luong.dnse_smoke \
  --output-dir "$OUTPUT"

STATUS=$?
echo
echo "===== MA THOAT ====="
echo "$STATUS"
echo "===== THU MUC SMOKE ====="
echo "$OUTPUT"

if [ -f "$OUTPUT/dnse_smoke_evidence.json" ]; then
  echo
  echo "===== BANG CHUNG DNSE ====="
  cat "$OUTPUT/dnse_smoke_evidence.json"
fi

if [ -f "$OUTPUT/dnse_smoke_evidence.zip" ]; then
  echo
  echo "===== SHA-256 ====="
  sha256sum "$OUTPUT/dnse_smoke_evidence.zip"
fi

echo
read -r -p "Nhan Enter de dong cua so..."
```

Không có lệnh `exit`, nên Git Bash không tự đóng.

Smoke đạt khi JSON có:

```text
"status": "SUCCESS"
"hpg_rows": lớn hơn 0
"vnindex_rows": lớn hơn 0
```

## Bước 3 — Chạy EOD và prediction sau 18:00

Điều kiện local:

```text
C:\Users\welcome\Documents\vn-quant-data\prediction_input.zip
một publication reduced hợp lệ chứa 5 file canonical
.env.dnse trong repository local
```

Dán nguyên khối:

```bash
git switch main
git pull --ff-only origin main

DATA_ROOT="/c/Users/welcome/Documents/vn-quant-data"
RUN_ID="$(date +%Y%m%d_%H%M%S)"
OUTPUT="$DATA_ROOT/eod-daily-$RUN_ID"
STATUS=1

if [ ! -f .env.dnse ]; then
  echo "LOI: khong tim thay .env.dnse"
elif [ ! -f "$DATA_ROOT/prediction_input.zip" ]; then
  echo "LOI: khong tim thay prediction_input.zip"
else
  set -a
  source .env.dnse
  set +a

  PYTHONPATH=src uv run --python 3.12 \
    --with dnse==0.5.0 \
    --with vnstock==4.0.4 \
    --with lightgbm==4.6.0 \
    python -m he_thong_dinh_luong.eod_hang_ngay_cli \
    --data-root "$DATA_ROOT" \
    --output-dir "$OUTPUT" \
    --primary-source dnse \
    --secondary-source kbs \
    --min-coverage 0.95 \
    --price-tolerance-bps 10 \
    --volume-tolerance-ratio 0.05

  STATUS=$?
fi

echo
echo "===== MA THOAT ====="
echo "$STATUS"
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

echo
read -r -p "Nhan Enter de dong cua so..."
```

## Kết quả thành công

Terminal phải có JSON chứa:

```text
"status": "SUCCESS"
"primary_source": "dnse_openapi"
"secondary_source": "vnstock_kbs"
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
raw/primary.json
raw/secondary.json
```

`raw/` lưu bằng chứng nguồn trên máy. `daily_quant_output.zip` không chứa raw hoặc credential.

## File cần gửi vào chat

Gửi đúng file:

```text
C:\Users\welcome\Documents\vn-quant-data\eod-daily-<RUN_ID>\daily_quant_output.zip
```

Kèm phần terminal từ:

```text
===== TOM TAT DU DOAN =====
```

Không gửi:

```text
.env.dnse
raw/primary.json
raw/secondary.json
```

## Các trạng thái lỗi chính

### `DNSE_CREDENTIALS_MISSING`

Thiếu `DNSE_API_KEY` hoặc `DNSE_API_SECRET` trong môi trường local.

### `DNSE_SDK_VERSION_MISMATCH`

Không chạy đúng `dnse==0.5.0`.

### `EOD_NOT_PUBLISHED`

Nguồn chưa có dữ liệu phiên hiện tại. Chờ 30–60 phút rồi chạy lại với output mới.

### `EOD_DATA_NOT_FINAL`

Dưới 95% universe có dữ liệu khớp giữa DNSE và nguồn secondary, hoặc một mã thiếu một phiên cần bắt kịp. Không tạo prediction.

### `FEATURE_COVERAGE_NOT_FINAL`

Dữ liệu EOD đã đủ nhưng dưới 95% mã tạo được feature đầy đủ. Không tạo prediction.

### `HISTORICAL_REVISION_CONFLICT`

Nguồn mới trả dữ liệu khác publication đã khóa cho cùng mã/ngày. Pipeline không tự sửa lịch sử.

## Nguyên tắc vận hành

- Signal ngày `t` chỉ dùng sau khi EOD ngày `t` đã chốt.
- Giao dịch paper sớm nhất là phiên kế tiếp.
- DNSE là primary; KBS mặc định là secondary cross-check.
- Chỉ đối chiếu open/close/volume vì publication hiện dùng hợp đồng reduced.
- Mọi phiên thiếu giữa ngày cuối local và phiên mới nhất phải được bắt kịp, không được nhảy cóc.
- Entrypoint dùng UTC+7 cố định trên Windows.
- Output giữ `research_eligible=false` cho đến khi đóng price basis, corporate actions và PIT universe.
