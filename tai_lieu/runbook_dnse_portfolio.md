# DNSE Portfolio Intelligence — read-only

## Mục tiêu

Đồng bộ danh mục thật từ DNSE và ghép với tín hiệu quant, target allocation và bộ chỉ báo tính cục bộ.

## Cam kết read-only

- Chỉ dùng API Key và API Secret đã có trong `.env.dnse`.
- Không yêu cầu OTP.
- Không nhận hoặc sử dụng Trading Token.
- Không gọi endpoint đặt, sửa hoặc hủy lệnh.
- Số tài khoản chỉ được lưu dưới dạng đã che.
- Credential không được ghi vào SQLite, log, JSON, CSV hoặc ZIP.

## Trên web

1. Khởi động VN Quant Local Console.
2. Bấm nút `DANH MỤC DNSE` ở góc phải dưới.
3. Bấm `TẢI TIỂU KHOẢN`.
4. Chọn tiểu khoản đã che.
5. Bấm `ĐỒNG BỘ & PHÂN TÍCH`.

Sau khi thành công, vị thế và tiền khả dụng được đồng bộ vào planner local.

## CLI

```bash
set -a
source .env.dnse
set +a

DATA_ROOT="/c/Users/welcome/Documents/vn-quant-data"

PYTHONPATH=src uv run --python 3.12 \
  --with dnse==0.5.0 \
  python -m he_thong_dinh_luong.dnse_portfolio_cli \
  --data-root "$DATA_ROOT"
```

## Sản phẩm

```text
dnse-portfolio-live/
├── LATEST.txt
└── snapshots/
    └── YYYYMMDD_HHMMSS/
        ├── portfolio_analysis.csv
        ├── portfolio_summary.json
        ├── market_context.json
        ├── indicator_methodology.json
        ├── manifest.json
        └── dnse_portfolio_analysis.zip
```

## Chỉ báo

Chỉ báo được tính từ OHLCV DNSE để công thức live và backtest đồng nhất:

- RSI14 Wilder
- MACD 12-26-9
- Bollinger 20x2
- ATR14 theo phần trăm giá
- Stochastic 14
- OBV change 20
- Volume/current-to-average 20
- MA20/60/120/250
- Return 20/60/120/250
- Drawdown 52 tuần
- Composite trend health

Dữ liệu quote, trade gần nhất và khối ngoại là context tùy chọn. Lỗi ở context không làm mất danh mục hoặc chỉ báo OHLCV.

## Giới hạn

- Không gửi lệnh thật.
- Không tự động bán.
- Trần ngành 25% chưa được enforce khi chưa có sector master point-in-time tin cậy.
- Kết quả vẫn là technical validation, không phải khuyến nghị đầu tư.
