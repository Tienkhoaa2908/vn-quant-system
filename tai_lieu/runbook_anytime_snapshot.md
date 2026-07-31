# VN Quant Local Console v3 — snapshot mọi lúc và final EOD

## Nguyên tắc finality

- `AUTO` trước 18:00 giờ Việt Nam: chạy snapshot DNSE provisional.
- `AUTO` từ 18:00: chạy final EOD, quality gate và cập nhật paper.
- `SNAPSHOT`: luôn được phép; không sửa publication final và không cập nhật paper.
- `FINAL`: giữ nguyên gate finality trước 18:00.

Snapshot có thể mang một trong ba trạng thái:

- `PROVISIONAL_INTRADAY`: có nến đang hình thành của phiên hiện tại.
- `LAST_AVAILABLE`: DNSE chưa có nến phiên hiện tại; dùng phiên gần nhất và hiển thị as-of.
- `FINAL_UNCONFIRMED`: DNSE đã có nến ngày hiện tại sau 18:00 nhưng chưa chạy quality gate final.

## Khởi động web

Mở Git Bash trong repository:

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
```

Mở `http://127.0.0.1:8088`.

## Vận hành

Trong tab `Chạy phân tích`:

1. Giữ chế độ `Tự động`.
2. Để trống ngày mục tiêu để dùng ngày hiện tại.
3. Bấm `LẤY DATA NGAY + PHÂN TÍCH + CHIA VỐN`.

Trước 18:00, output nằm trong thư mục `anytime-web-*` và không làm thay đổi paper ledger. Sau 18:00, output final có `daily_quant_output.zip` và paper ledger được cập nhật.

## Phân bổ

Allocator `conviction_inverse_volatility_v1` dùng:

- decision score;
- độ đồng thuận robust;
- inverse volatility 60 phiên;
- MA250 eligibility;
- capital budget động theo regime, validation evidence và breadth;
- trần 15% mỗi mã.

Không áp trần ngành 25% cho đến khi có sector master point-in-time đủ tin cậy. Không tự động gửi lệnh thật.

## Giới hạn nghiên cứu

```text
technical_validation_only=true
research_eligible=false
```

Snapshot là công cụ tham khảo trong phiên. Không dùng snapshot provisional để chấm hiệu quả OOS hoặc sinh fill paper chính thức.
