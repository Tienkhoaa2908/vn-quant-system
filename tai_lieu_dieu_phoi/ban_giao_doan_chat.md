# Ban giao doan chat dieu phoi

Cap nhat: 2026-07-24

## Vai tro

- Doan `00` la dau moi dieu phoi trung tam.
- Doan `01` phu trach chuyen mon Moc 1 — du lieu.
- GitHub la nguon su that ve nhanh, commit, PR va CI.
- Khong chuyen moc khi Moc 1 chua duoc gop va xac minh sau gop.

## Trang thai ben vung

### Nen dieu phoi

- PR so 2 da gop.
- Dau `main`: `4eba2a77d5864027c84d4350769d95fd4abd5fee`.
- `main` da chua `tai_lieu_dieu_phoi/`.
- Nhanh `m1-du_lieu` da cap nhat tu `main` va cham hon 0 commit.

### PR so 3

- Nhanh: `m1-du_lieu` vao `main`.
- Dau truoc quyet dinh nghiem thu: `9552e4641327ba93fa02f1fd0953d378f3f879f1`.
- Truoc cap nhat: mo, nhap, mergeable, chua gop.
- Co 24 tep thay doi, khong chua tep duoi `du_lieu/`.
- Khong co review thread hoac review submission dang chan.

## Ket qua Moc 1

### Tham do that Vnstock 4.0.4

- Ma lan chay: `20260724T152739494769Z_521d23ce`.
- Khoang ngay: `2026-07-01` den `2026-07-10`.
- Cach goi da hoat dong:

```python
Market().equity(symbol=ma).ohlcv(
    start=ngay_bat_dau,
    end=ngay_ket_thuc,
    interval="1D",
    source="kbs",
)
```

- FPT: thanh cong, 8 dong.
- HPG: thanh cong, 8 dong.
- MBB: thanh cong, 8 dong.
- Cot: `time`, `open`, `high`, `low`, `close`, `volume`.
- Kieu: `datetime64[ns]`, OHLC `float64`, volume `int64`.
- Don vi gia do bo chuyen doi bao cao: nghin dong.
- Chua phat hien tham so cong khai chon gia dieu chinh/chua dieu chinh.

### Tai that nho

- Ma lan chay: `20260724T153953222157Z_5383eaab`.
- Nguon `vnstock_kbs`, phien ban `4.0.4`.
- FPT, HPG, MBB: deu thanh cong, 8 dong, 1 lan thu, khong canh bao, khong loi.
- Moi ma co JSON tho, CSV chuan hoa, CSV san sang, JSON bao cao, JSON nhat ky va SHA-256.
- Du lieu that chi nam cuc bo duoi `du_lieu/`.

### Kiem thu

- Python `CPython 3.12.13`, Windows x86-64.
- `Ran 30 tests in 0.696s`.
- Ket qua `OK`.
- GitHub Actions run so 32, ID `30108253709`, da dat tren commit `9552e4641327ba93fa02f1fd0953d378f3f879f1`.
- Job `kiem_tra`, ID `89530965041`: thanh cong; toan bo buoc deu dat.

## Phan quyet cua doan 00

**MOC 1 DAT DIEU KIEN KY THUAT VA DUOC PHE DUYET.**

Quyet dinh van hanh:

1. Ghi phan quyet vao ba tep dieu phoi.
2. Xac minh CI tren dau nhanh moi sau cap nhat tai lieu.
3. Neu CI dat, cap nhat noi dung PR va chuyen PR so 3 sang san sang ra soat.
4. Khong tu dong gop PR; nguoi dung thuc hien thao tac gop.
5. Sau khi gop, doan 00 xac minh dau `main`, CI va pham vi tep.
6. Chi sau xac minh sau gop moi giao Moc 2.

## Viec nguoi dung can lam sau thong bao dieu phoi

1. Mo PR so 3 tren GitHub.
2. Xac nhan PR da o trang thai san sang ra soat va CI dau nhanh moi nhat da dat.
3. Chon `Merge pull request` va xac nhan gop.
4. Khong xoa nhanh cho den khi doan 00 xac minh xong neu GitHub hoi.
5. Bao lai doan `00`: `Da gop PR so 3`.

## Khong duoc lam

- Khong mo Moc 2 truoc khi PR so 3 duoc gop va xac minh.
- Khong dua du lieu that, nhat ky that hoac khoa len GitHub.
- Khong them MA250, backtest, hoc may hoac chia von trong Moc 1.
