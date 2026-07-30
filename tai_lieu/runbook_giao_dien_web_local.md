# Runbook giao diện web local

Cập nhật: 2026-07-30

## Mục tiêu

Chạy một dashboard chỉ trên máy local để:

- xem trạng thái dữ liệu, model và paper trading;
- bấm một nút lấy các phiên DNSE còn thiếu;
- kiểm tra nguồn VCI/KBS theo chế độ advisory;
- tạo feature, chạy momentum/LightGBM và chọn champion;
- xem ranking và danh mục mục tiêu;
- cập nhật paper-trading OOS;
- replay các tín hiệu paper đã ghi nhận với vốn/chi phí khác;
- xem log, dữ liệu giá, NAV và vị thế.

Dashboard không gửi lệnh thật và không dùng Trading API DNSE.

## Bảo mật

Dashboard chỉ bind:

```text
127.0.0.1:8088
```

Không bind LAN hoặc Internet. API Key và API Secret chỉ đi qua environment của process. Giao diện, URL, SQLite, command line và log không ghi credential.

Không gửi các file sau vào chat hoặc GitHub:

```text
.env.dnse
web-local/jobs.sqlite3
raw/primary.json
raw/secondary.json
```

## Mở đúng thư mục

Mở Git Bash tại:

```text
C:\Users\welcome\Documents\vn-quant-system
```

Kiểm tra:

```bash
pwd
test -d src && echo "REPO=OK" || echo "REPO=SAI"
test -s .env.dnse && echo "DNSE_ENV=OK" || echo "DNSE_ENV=MISSING"
```

Kết quả đúng:

```text
/c/Users/welcome/Documents/vn-quant-system
REPO=OK
DNSE_ENV=OK
```

## Khởi động dashboard

Dán nguyên khối:

```bash
git switch main
git pull --ff-only origin main

set -a
source .env.dnse
set +a

DATA_ROOT="/c/Users/welcome/Documents/vn-quant-data"

PYTHONPATH=src uv run --python 3.12 \
  --with nicegui==3.14.0 \
  --with dnse==0.5.0 \
  --with vnstock==4.0.4 \
  --with lightgbm==4.6.0 \
  python -m he_thong_dinh_luong.giao_dien_web \
  --repo-root "$(pwd)" \
  --data-root "$DATA_ROOT" \
  --host 127.0.0.1 \
  --port 8088

STATUS=$?

echo
echo "===== WEB EXIT ====="
echo "$STATUS"
echo
read -r -p "Nhan Enter de dong cua so..."
```

Trình duyệt sẽ mở tại:

```text
http://127.0.0.1:8088
```

Nếu trình duyệt không tự mở, nhập địa chỉ trên bằng tay.

Không đóng Git Bash trong lúc dashboard đang chạy. Để dừng dashboard, quay lại Git Bash và nhấn:

```text
Ctrl+C
```

## Nút chạy hằng ngày

Màn hình `Chạy một nút` có nút:

```text
LẤY DATA + CHẠY MODEL + PAPER
```

Chuỗi thực thi:

```text
DNSE primary
→ VCI/KBS advisory sample
→ cập nhật publication
→ feature
→ momentum + LightGBM
→ champion gate
→ ranking Top K
→ technical allocation
→ paper-trading replay
```

Chỉ một job được chạy tại một thời điểm. Job tiếp theo bị từ chối nếu job trước chưa kết thúc.

Khi ngày mục tiêu để trống, pipeline dùng ngày hiện tại. Với ngày hiện tại, EOD vẫn fail closed trước 18:00 giờ Việt Nam.

## Dữ liệu và state

Dashboard tạo state tại:

```text
C:\Users\welcome\Documents\vn-quant-data\web-local
```

Gồm:

```text
jobs.sqlite3
logs\
```

EOD từ dashboard nằm tại:

```text
C:\Users\welcome\Documents\vn-quant-data\eod-web-<RUN_ID>
```

Paper live nằm tại:

```text
C:\Users\welcome\Documents\vn-quant-data\paper-trading-live
```

Scenario lịch sử nằm tại:

```text
C:\Users\welcome\Documents\vn-quant-data\paper-scenarios\scenario-<RUN_ID>
```

## Ý nghĩa màn hình

### Tổng quan

Hiển thị phiên mới nhất, coverage DNSE, champion, regime, ngân sách vốn, Top ranking và NAV paper.

### Dữ liệu

Đọc trực tiếp file publication mà model sử dụng. Có thể lọc theo mã và xem report chất lượng.

### Dự đoán & vốn

Hiển thị toàn bộ ranking, score, trạng thái MA250, vốn kỹ thuật và danh mục mục tiêu.

### Kiểm định

So sánh validation OOS momentum với LightGBM. Scenario replay chỉ sử dụng các tín hiệu OOS đã được ghi nhận trong `paper-trading-live/signals`; không tự dựng tín hiệu cho những ngày chưa từng chạy.

### Paper trading

Hiển thị NAV, return, drawdown, fill, pending order và vị thế mới nhất.

### Nhật ký

Hiển thị SQLite job ledger và phần cuối log của từng job.

## Giới hạn nghiên cứu

```text
technical_validation_only=true
research_eligible=false
```

Dashboard không làm thay đổi các gate hiện có. Nó không biến technical ranking thành khuyến nghị đầu tư và không che các giới hạn còn mở về price basis, corporate actions hoặc universe point-in-time.
