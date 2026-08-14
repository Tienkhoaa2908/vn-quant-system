# DNSE historical store v20

## Muc tieu

Tao mot kho OHLCV ngay duy nhat tai local:

```text
C:\Users\welcome\Documents\vn-quant-data\market-data\dnse_ohlcv_v20.sqlite3
```

Lan dau backfill tu `2015-06-29` den ngay hien tai. Cac lan sau cung mot lenh
chi goi nhung khoang ngay chua duoc ghi nhan trong `fetched_ranges`.

Module chi goi market-data endpoint `GET /price/ohlc`. No khong goi account,
balance, position hoac order endpoint; khong phu thuoc local web.

## Contract an toan

- Credential chi doc tu `DNSE_API_KEY` va `DNSE_API_SECRET` trong process local.
- Khong ghi credential vao SQLite, JSON, CSV hay manifest.
- Bar cung ma/ngay trung gia tri: no-op.
- Bar cung ma/ngay khac OHLCV: ghi audit vao bang `conflicts`, fail closed, khong
  ghi de du lieu cu.
- Mot khoang API tra thanh cong duoc ghi vao `fetched_ranges`, ke ca khi khong co
  bar do ma chua niem yet. Lan sau khong goi lai khoang do.
- Mac dinh chia request thanh tung khoang 366 ngay de giam rui ro pagination dai.
- `--force-refresh` chi dung cho audit/reconciliation, khong dung hang ngay.
- Price basis hien la `CHUA_XAC_NHAN`; export chua duoc coi la research-grade
  cho den khi xac nhan adjusted price hoac co corporate actions PIT.
- Khong dat `exit` o cuoi block lenh duoc dan truc tiep vao Git Bash tuong tac;
  `exit` se dong luon terminal cua nguoi dung.

## 1. Tao danh sach ma tu prediction input hien co

```bash
cd ~/Documents/vn-quant-system
export PYTHONPATH="$PWD/src"

DATA_ROOT="/c/Users/welcome/Documents/vn-quant-data"
INPUT_ZIP="$DATA_ROOT/eod-dnse-20260730_214614/daily_prediction_input.zip"
SYMBOLS_FILE="$DATA_ROOT/market-data/vn100-symbols-v20.csv"

mkdir -p "$(dirname "$SYMBOLS_FILE")"

PYTHONPATH=src uv run --python 3.12 \
  python - "$INPUT_ZIP" "$SYMBOLS_FILE" <<'PY'
import csv
import sys
from io import StringIO
from pathlib import Path
from zipfile import ZipFile

source = Path(sys.argv[1])
destination = Path(sys.argv[2])
with ZipFile(source) as archive:
    text = archive.read("feature_raw.csv").decode("utf-8-sig")
rows = list(csv.DictReader(StringIO(text)))
symbols = sorted({str(row.get("ma") or "").strip().upper() for row in rows} - {""})
with destination.open("w", encoding="utf-8-sig", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=["ma"], lineterminator="\n")
    writer.writeheader()
    writer.writerows({"ma": symbol} for symbol in symbols)
print(f"SYMBOL_COUNT={len(symbols)}")
print(destination)
PY
```

Danh sach nay chi la seed de tai du lieu. No khong tu dong duoc coi la universe
point-in-time cho historical research.

## 2. Dat credential cho dung process Git Bash

Khong ghi secret vao file repo.

```bash
read -r -p "DNSE API key: " DNSE_API_KEY
read -r -s -p "DNSE API secret: " DNSE_API_SECRET
echo
export DNSE_API_KEY DNSE_API_SECRET
```

## 3. Backfill lan dau

Block nay an toan de dan truc tiep vao Git Bash. No khong goi `exit`, nen terminal
van mo ke ca khi DNSE tra loi.

```bash
set +e
cd ~/Documents/vn-quant-system
export PYTHONPATH="$PWD/src"

DATA_ROOT="/c/Users/welcome/Documents/vn-quant-data"
STORE="$DATA_ROOT/market-data/dnse_ohlcv_v20.sqlite3"
SYMBOLS_FILE="$DATA_ROOT/market-data/vn100-symbols-v20.csv"
RUN_ID="$(date +%Y%m%d-%H%M%S)"
REPORT="$DATA_ROOT/market-data/dnse-sync-v20-$RUN_ID.json"
LOG_FILE="$DATA_ROOT/market-data/dnse-sync-v20-$RUN_ID.log"

PYTHONPATH=src uv run --python 3.12 \
  --with dnse==0.5.0 \
  python -m he_thong_dinh_luong.dnse_historical_store_v20 sync \
  --store "$(cygpath -w "$STORE")" \
  --symbols-file "$(cygpath -w "$SYMBOLS_FILE")" \
  --start 2015-06-29 \
  --end "$(date +%F)" \
  --chunk-days 366 \
  --output-json "$(cygpath -w "$REPORT")" \
  2>&1 | tee "$LOG_FILE"

STATUS=${PIPESTATUS[0]}
unset DNSE_API_KEY DNSE_API_SECRET

echo "EXIT_CODE=$STATUS"
echo "STORE=$STORE"
echo "REPORT=$REPORT"
echo "LOG_FILE=$LOG_FILE"

if [ -f "$REPORT" ]; then
  cat "$REPORT"
else
  echo "REPORT_NOT_CREATED"
  tail -n 80 "$LOG_FILE"
fi
```

Lenh co the mat thoi gian vi moi ma duoc chia thanh nhieu khoang nam. Neu dung
giua chung, chay lai cung lenh; cac khoang da thanh cong se duoc bo qua.

## 4. Cap nhat hang ngay sau nay

Khong can truyen `--start`; mac dinh van la 2015-06-29 nhung planner chi goi
phan chua duoc coverage.

```bash
set +e
cd ~/Documents/vn-quant-system
export PYTHONPATH="$PWD/src"

DATA_ROOT="/c/Users/welcome/Documents/vn-quant-data"
STORE="$DATA_ROOT/market-data/dnse_ohlcv_v20.sqlite3"
SYMBOLS_FILE="$DATA_ROOT/market-data/vn100-symbols-v20.csv"
TODAY="$(date +%F)"
RUN_ID="$(date +%Y%m%d-%H%M%S)"
REPORT="$DATA_ROOT/market-data/dnse-sync-v20-$RUN_ID.json"
LOG_FILE="$DATA_ROOT/market-data/dnse-sync-v20-$RUN_ID.log"

PYTHONPATH=src uv run --python 3.12 \
  --with dnse==0.5.0 \
  python -m he_thong_dinh_luong.dnse_historical_store_v20 sync \
  --store "$(cygpath -w "$STORE")" \
  --symbols-file "$(cygpath -w "$SYMBOLS_FILE")" \
  --end "$TODAY" \
  --output-json "$(cygpath -w "$REPORT")" \
  2>&1 | tee "$LOG_FILE"

STATUS=${PIPESTATUS[0]}
unset DNSE_API_KEY DNSE_API_SECRET

echo "EXIT_CODE=$STATUS"
echo "REPORT=$REPORT"
echo "LOG_FILE=$LOG_FILE"
```

Neu kho da phu den hom qua, moi ma chi co toi da mot tail range moi. Neu hom nay
la ngay nghi va request thanh cong khong co bar, khoang ngay van duoc danh dau da
kiem tra va khong bi goi lai.

## 5. Kiem tra coverage

```bash
PYTHONPATH=src uv run --python 3.12 \
  python -m he_thong_dinh_luong.dnse_historical_store_v20 status \
  --store "$(cygpath -w "$STORE")"
```

Can quan sat:

```text
status
coverage[].first_day
coverage[].last_day
coverage[].row_count
coverage[].symbol_count
conflict_count
```

`conflict_count > 0` phai duoc audit truoc khi tiep tuc model.

## 6. Export cho pipeline feature/model

```bash
EXPORT_DIR="$DATA_ROOT/market-data/dnse-export-v20-$(date +%Y%m%d-%H%M%S)"

PYTHONPATH=src uv run --python 3.12 \
  python -m he_thong_dinh_luong.dnse_historical_store_v20 export \
  --store "$(cygpath -w "$STORE")" \
  --output-dir "$(cygpath -w "$EXPORT_DIR")" \
  --start 2015-06-29
```

San pham:

```text
ohlcv_stocks_dnse.csv
vnindex_close_dnse.csv
lich_vnindex_dnse.csv
coverage.json
manifest.json
```

Export nay co schema phu hop lop doc OHLCV/benchmark cua Moc 4, nhung manifest
co `research_eligible=false` cho den khi hoan tat hai contract con thieu:

1. adjusted-price hoac unadjusted-price + corporate-actions PIT;
2. universe membership/dynamic-liquidity universe point-in-time.

Khong duoc doi `research_eligible` bang tay.
