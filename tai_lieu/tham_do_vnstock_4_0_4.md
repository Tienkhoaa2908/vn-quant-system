# Tham do Vnstock Community 4.0.4

## Trang thai

Tham do tinh da hoan thanh tren ma nguon tag `v4.0.4`. Tham do du lieu that chua hoan thanh trong moi truong phat trien hien tai do moi truong khong phan giai duoc ten mien va khong cai duoc goi tu PyPI. Ket noi nguon chi duoc coi la dat sau khi nguoi dung chay lenh tham do va gui log theo tung ma.

## Giao dien da xac minh

```python
from vnstock import Market

bang_co_phieu = Market().equity(symbol="FPT").ohlcv(
    start="2026-07-01",
    end="2026-07-10",
    interval="1D",
    source="kbs",
)

bang_chi_so = Market().index(symbol="VNINDEX").ohlcv(
    start="2026-07-01",
    end="2026-07-10",
    interval="1D",
    source="kbs",
)
```

`EquityMarket.ohlcv` va `IndexMarket.ohlcv` deu nhan `start`, `end`, `interval`, `count`, `source` va `**kwargs`. Bo cung cap KBS goi `Quote.history` va tra bang du lieu.

## Cot va kieu du lieu

Vnstock chuan hoa ket qua KBS ve:

| Cot | Kieu |
|---|---|
| `time` | `datetime64[ns]` |
| `open` | `float64` |
| `high` | `float64` |
| `low` | `float64` |
| `close` | `float64` |
| `volume` | `int64` |

Bo cung cap sap xep tang dan theo `time`.

## Don vi gia

Trong ma nguon KBS cua Vnstock 4.0.4, bon cot gia cua co phieu va quy ETF duoc chia cho 1.000. Vi vay gia co phieu tra ve co don vi nghin dong. Chi so va phai sinh khong bi chia, nen VNINDEX co don vi diem chi so.

## Gia dieu chinh

Chu ky cong khai cua `ohlcv` va `Quote.history` khong co tham so chon gia dieu chinh hay chua dieu chinh. Du an dat `tham_so_gia` la `null` va khong truyen `dieu_chinh_gia` hoac tham so tu suy doan.

## FPT, HPG va MBB

Theo bo chuyen doi da xac minh, ba ma nay dung cung nhanh `Market().equity` va cung hop dong cot/loai du lieu. So dong, ngay dau, ngay cuoi va gia tri thuc te phai lay tu lenh tham do that.

## VNINDEX

KBS liet ke `VNINDEX` trong tap chi so duoc ho tro va Vnstock dung nhanh `Market().index`. Truong `volume` duoc anh xa truc tiep tu truong `v` cua KBS va ep thanh `int64`. Ma nguon khong mo ta du y nghia kinh te cua truong nay; khong dung no lam khoi luong tong hop cho nghien cuu truoc khi doi chieu log that va tai lieu nguon.

## Lenh tham do that

```bash
PYTHONPATH=src uv run --with vnstock==4.0.4 \
  python -m he_thong_dinh_luong.tham_do_vnstock \
  --ma FPT HPG MBB \
  --ngay_bat_dau 2026-07-01 \
  --ngay_ket_thuc 2026-07-10
```

VNINDEX duoc chay rieng:

```bash
PYTHONPATH=src uv run --with vnstock==4.0.4 \
  python -m he_thong_dinh_luong.tham_do_vnstock \
  --ma VNINDEX \
  --ngay_bat_dau 2026-07-01 \
  --ngay_ket_thuc 2026-07-10
```

Bao cao JSON can duoc gui ve de ra soat, nhung khong dua vao commit.
