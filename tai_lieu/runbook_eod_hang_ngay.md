# Runbook cập nhật EOD và chạy dự đoán hằng ngày

Cập nhật: 2026-07-30

## Kiến trúc nguồn

```text
DNSE Market Data API: primary canonical
VCI/KBS qua vnstock: secondary advisory cross-check
```

DNSE quyết định phiên EOD, dữ liệu publication và feature. Nguồn secondary chỉ kiểm tra chất lượng trên mẫu đều; nguồn phụ thiếu, chậm hoặc không đủ coverage không được phép làm mất dữ liệu DNSE hợp lệ.

Hai chế độ:

```text
advisory: mặc định, kiểm tra mẫu, không chặn primary hợp lệ
strict: audit toàn bộ hai nguồn, mismatch hoặc thiếu secondary sẽ chặn
```

Mặc định advisory lấy mẫu 20 mã phân bố đều trong universe. Pipeline vẫn fail closed khi chính DNSE thiếu phiên, lỗi schema/auth/pagination, primary coverage dưới 95%, feature coverage dưới 95% hoặc có historical revision conflict.

## Bảo mật credential

Credential nằm trong file local:

```text
C:\Users\welcome\Documents\vn-quant-system\.env.dnse
```

File cần chứa hai biến:

```text
DNSE_API_KEY
DNSE_API_SECRET
```

Không gửi `.env.dnse`, API Key hoặc API Secret vào chat, issue, pull request hoặc commit.

## Thư mục chạy

Luôn mở Git Bash tại:

```text
C:\Users\welcome\Documents\vn-quant-system
```

Kiểm tra:

```bash
pwd
test -d src && echo "PROJECT_DIR=OK" || echo "PROJECT_DIR=SAI"
test -s .env.dnse && echo "DNSE_ENV=OK" || echo "DNSE_ENV=THIEU"
```

Kết quả đúng:

```text
/c/Users/welcome/Documents/vn-quant-system
PROJECT_DIR=OK
DNSE_ENV=OK
```

## Smoke DNSE

Smoke chỉ đọc HPG và VNINDEX. Nó không chạy model, không sửa publication và không ghi credential vào evidence.

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

echo
read -r -p "Nhan Enter de dong cua so..."
```

Smoke đạt khi:

```text
status = SUCCESS
hpg_rows > 0
vnindex_rows > 0
MA THOAT = 0
```

## Chạy EOD và prediction

Điều kiện local:

```text
C:\Users\welcome\Documents\vn-quant-data\prediction_input.zip
một publication reduced hợp lệ
.env.dnse trong repository local
chạy sau 18:00 giờ Việt Nam
```

Dán nguyên khối:

```bash
git switch main
git pull --ff-only origin main

set -a
source .env.dnse
set +a

DATA_ROOT="/c/Users/welcome/Documents/vn-quant-data"
RUN_ID="$(date +%Y%m%d_%H%M%S)"
OUTPUT="$DATA_ROOT/eod-dnse-$RUN_ID"
LOG="$DATA_ROOT/eod-dnse-$RUN_ID.log"

(
  PYTHONPATH=src uv run --python 3.12 \
    --with dnse==0.5.0 \
    --with vnstock==4.0.4 \
    --with lightgbm==4.6.0 \
    python -m he_thong_dinh_luong.eod_hang_ngay_cli \
    --data-root "$DATA_ROOT" \
    --output-dir "$OUTPUT" \
    --primary-source dnse \
    --secondary-source vci \
    --crosscheck-policy advisory \
    --crosscheck-sample-size 20 \
    --min-coverage 0.95 \
    --price-tolerance-bps 10 \
    --volume-tolerance-ratio 0.05
) 2>&1 | tee "$LOG"

STATUS=${PIPESTATUS[0]}

echo
echo "===== MA THOAT ====="
echo "$STATUS"
echo "===== THU MUC KET QUA ====="
echo "$OUTPUT"
echo "===== FILE LOG ====="
echo "$LOG"

if [ -f "$OUTPUT/daily_prediction_summary.txt" ]; then
  echo
  echo "===== TOM TAT DU DOAN ====="
  cat "$OUTPUT/daily_prediction_summary.txt"
fi

if [ -f "$OUTPUT/daily_quant_output.zip" ]; then
  echo
  echo "===== ZIP KET QUA ====="
  echo "$OUTPUT/daily_quant_output.zip"
  echo
  echo "===== SHA-256 ====="
  sha256sum "$OUTPUT/daily_quant_output.zip"
fi

if [ "$STATUS" -ne 0 ]; then
  echo
  echo "===== 120 DONG LOI CUOI ====="
  tail -n 120 "$LOG"
fi

echo
read -r -p "Nhan Enter de dong cua so..."
```

Không có lệnh `exit`, nên Git Bash không tự đóng.

## Kết quả thành công

JSON cuối phải có:

```text
"status": "SUCCESS"
"primary_source": "dnse_openapi"
"crosscheck_policy": "advisory"
```

Tóm tắt phải ghi:

```text
Data quality tier: PRIMARY_VALIDATED_SECONDARY_ADVISORY
Primary data coverage: ...
Secondary sample available: ...
Secondary sample matched: ...
Feature coverage: ...
Champion model: ...
Market regime: ...
Top 10: ...
```

Nguồn secondary có thể thấp hoặc chậm mà pipeline vẫn thành công, miễn chính DNSE đạt primary coverage tối thiểu 95% và các cửa feature/historical consistency đều đạt.

## File kết quả

Gửi đúng file:

```text
C:\Users\welcome\Documents\vn-quant-data\eod-dnse-<RUN_ID>\daily_quant_output.zip
```

Không gửi:

```text
.env.dnse
raw/primary.json
raw/secondary.json
API Key
API Secret
```

## Trạng thái lỗi chính

### `DNSE_CREDENTIALS_MISSING`

Thiếu API Key hoặc API Secret trong môi trường local.

### `EOD_NOT_PUBLISHED_PRIMARY`

DNSE chưa có phiên mục tiêu. Chờ DNSE công bố rồi chạy output mới.

### `EOD_PRIMARY_DATA_NOT_FINAL`

Dưới 95% universe có đầy đủ dữ liệu primary DNSE cho mọi phiên cần bắt kịp. Không tạo prediction.

### `FEATURE_COVERAGE_NOT_FINAL`

Primary EOD đủ nhưng dưới 95% mã tạo được feature đầy đủ. Không tạo prediction.

### `HISTORICAL_REVISION_CONFLICT`

Dữ liệu primary mới xung đột publication đã khóa cho cùng mã/ngày. Pipeline không tự sửa lịch sử.

### `EOD_DATA_NOT_FINAL`

Chỉ xuất hiện trong `strict` mode khi hai nguồn không đủ coverage hoặc mismatch.

## Nguyên tắc vận hành

- Signal ngày `t` chỉ được tạo sau khi EOD ngày `t` đã chốt.
- Giao dịch paper sớm nhất là phiên kế tiếp.
- DNSE là canonical source cho vòng daily hiện tại.
- Secondary advisory là giám sát chất lượng, không phải nguồn thay thế âm thầm.
- Mọi phiên thiếu giữa ngày cuối local và phiên mới nhất phải được bắt kịp.
- Output vẫn giữ `technical_validation_only=true` và `research_eligible=false` cho đến khi đóng price basis, corporate actions và point-in-time universe.
