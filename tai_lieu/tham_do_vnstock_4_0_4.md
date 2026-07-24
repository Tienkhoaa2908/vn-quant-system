# Tham do Vnstock Community 4.0.4

## Trang thai

Tham do tinh da hoan thanh tren ma nguon tag `v4.0.4`. Tham do du lieu that voi `count=400` da xac nhan FPT, HPG va MBB deu tra 287 dong trong khoang yeu cau 2025-06-01 den 2026-07-24. Gioi han 100 dong truoc do den tu `count` mac dinh.

## Giao dien da xac minh

```python
from vnstock import Market

bang_co_phieu = Market().equity(symbol="FPT").ohlcv(
    start="2025-06-01",
    end="2026-07-24",
    interval="1D",
    source="kbs",
    count=400,
)

bang_chi_so = Market().index(symbol="VNINDEX").ohlcv(
    start="2025-06-01",
    end="2026-07-24",
    interval="1D",
    source="kbs",
    count=400,
)
```

`EquityMarket.ohlcv` va `IndexMarket.ohlcv` deu nhan `start`, `end`, `interval`, `count`, `source` va `**kwargs`. Bo cung cap KBS goi `Quote.history` va tra bang du lieu.

Bo chuyen doi chi truyen gia tri `so_nen` duoc cung cap tu ben ngoai thanh `count`; khong hard-code 400. Hai CLI Vnstock dung mac dinh ro rang `--so_nen 400` va tu choi gia tri khong phai so nguyen duong.

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

Ket qua tham do that voi `count=400`:

- FPT: 287 dong, 2025-06-02 den 2026-07-23;
- HPG: 287 dong, 2025-06-02 den 2026-07-23;
- MBB: 287 dong, 2025-06-02 den 2026-07-23.

Ket qua nay xac nhan du lich su de tinh MA250 va vuot nguong xac minh 260 phien, nhung chua thay the buoc tai qua pipeline Moc 1 va chay Moc 2.

## VNINDEX

KBS liet ke `VNINDEX` trong tap chi so duoc ho tro va Vnstock dung nhanh `Market().index`. Truong `volume` duoc anh xa truc tiep tu truong `v` cua KBS va ep thanh `int64`. Ma nguon khong mo ta du y nghia kinh te cua truong nay; khong dung no lam khoi luong tong hop cho nghien cuu truoc khi doi chieu log that va tai lieu nguon.

## Lenh tham do that

```bash
PYTHONPATH=src uv run --with vnstock==4.0.4 \
  python -m he_thong_dinh_luong.tham_do_vnstock \
  --ma FPT HPG MBB \
  --ngay_bat_dau 2025-06-01 \
  --ngay_ket_thuc 2026-07-24 \
  --so_nen 400 \
  --thu_muc_du_lieu du_lieu
```

VNINDEX duoc chay rieng:

```bash
PYTHONPATH=src uv run --with vnstock==4.0.4 \
  python -m he_thong_dinh_luong.tham_do_vnstock \
  --ma VNINDEX \
  --ngay_bat_dau 2025-06-01 \
  --ngay_ket_thuc 2026-07-24 \
  --so_nen 400 \
  --thu_muc_du_lieu du_lieu
```

Bao cao JSON ghi `so_nen_yeu_cau`, can duoc gui ve de ra soat, nhung khong dua vao commit.
