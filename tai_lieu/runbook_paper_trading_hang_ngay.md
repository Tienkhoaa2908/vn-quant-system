# Runbook paper-trading OOS hằng ngày

Cập nhật: 2026-07-30

## Mục tiêu

Sau mỗi lần EOD thành công, ghi tín hiệu vào sổ paper bất biến và replay toàn bộ chuỗi tín hiệu bằng engine Mốc 3:

```text
signal sau close T
→ lệnh DAY
→ khớp tại open đúng phiên kế tiếp
→ lot 100
→ phí mua/bán, thuế bán, slippage
→ vị thế, tiền mặt, NAV, drawdown, turnover
```

Không gọi Trading API và không gửi lệnh thật.

## Cấu hình mặc định

```text
Vốn giả định: 1.000.000.000 VND
Phí mua: 15 bps
Phí bán: 15 bps
Thuế bán: 100 bps
Slippage: 10 bps
Lot: 100 cổ phiếu
Đơn vị engine: nghìn đồng
Price basis: CHUA_XAC_NHAN
Corporate actions: chưa áp dụng
```

## Chạy sau khi EOD thành công

Mở Git Bash tại:

```text
C:\Users\welcome\Documents\vn-quant-system
```

Thay `<THU_MUC_EOD>` bằng thư mục vừa tạo, ví dụ `eod-dnse-20260730_214500`.

```bash
git switch main
git pull --ff-only origin main

DATA_ROOT="/c/Users/welcome/Documents/vn-quant-data"
EOD_RUN="$DATA_ROOT/<THU_MUC_EOD>"
PAPER_STATE="$DATA_ROOT/paper-trading-live"

PYTHONPATH=src uv run --python 3.12 \
  python -m he_thong_dinh_luong.paper_trading_daily \
  --daily-output "$EOD_RUN/daily_quant_output.zip" \
  --publication-dir "$EOD_RUN/updated_publication" \
  --state-dir "$PAPER_STATE" \
  --initial-capital-vnd 1000000000 \
  --buy-fee-bps 15 \
  --sell-fee-bps 15 \
  --sell-tax-bps 100 \
  --slippage-bps 10 \
  --lot-size 100

STATUS=$?

echo
echo "===== MA THOAT PAPER ====="
echo "$STATUS"

echo
echo "===== SNAPSHOT MOI NHAT ====="
if [ -f "$PAPER_STATE/LATEST.txt" ]; then
  cat "$PAPER_STATE/LATEST.txt"
  LATEST="$(cat "$PAPER_STATE/LATEST.txt")"
  if [ -f "$LATEST/paper_status.txt" ]; then
    echo
    cat "$LATEST/paper_status.txt"
  fi
fi

echo
read -r -p "Nhan Enter de dong cua so..."
```

## Lần chạy đầu

Vì chưa có open T+1, kết quả đúng là:

```text
Paper status: PENDING_FIRST_EXECUTION
Fills: 0
Pending orders: 10
Current positions: 0
```

Đây không phải lỗi. Sau EOD phiên kế tiếp, chạy lại bằng output mới; tín hiệu cũ sẽ được replay và khớp tại open của phiên kế tiếp.

## Cấu trúc state

```text
paper-trading-live/
├── signals/                  # tín hiệu từng ngày, bất biến
├── snapshots/                # snapshot sổ paper theo ngày thị trường
└── LATEST.txt                # đường dẫn snapshot mới nhất
```

Mỗi snapshot có:

```text
signals.csv
orders.csv
fills.csv
positions_daily.csv
nav.csv
ledger.csv
metrics.json
paper_status.txt
manifest.json
paper_state.zip
```

## Quy tắc fail closed

Pipeline dừng khi:

- ZIP EOD hoặc hash `paper_portfolio.csv` sai;
- cùng ngày có hai tín hiệu khác nhau;
- publication thiếu giá/open cho mã được chọn;
- tín hiệu nằm sau ngày dữ liệu mới nhất;
- vốn không phải bội số 1.000 VND;
- engine không đối soát được NAV.

Output vẫn giữ:

```text
technical_validation_only=true
research_eligible=false
```
