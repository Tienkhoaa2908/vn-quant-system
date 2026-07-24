# Cong viec hien tai

Cap nhat: 2026-07-24

## Doan phu trach

`00 Dieu phoi trung tam` dang thuc hien nghiem thu cuoi cho PR so 3 cua `01 Du lieu`.

## Trang thai nen

- PR so 2 da duoc gop vao `main`.
- Dau `main` da xac minh: `4eba2a77d5864027c84d4350769d95fd4abd5fee`.
- Nhanh `m1-du_lieu` da dong bo `main` va cham hon 0 commit.
- PR so 3 mo, mergeable va chua gop.
- Dau nhanh truoc cap nhat nghiem thu: `9552e4641327ba93fa02f1fd0953d378f3f879f1`.
- PR co 24 tep thay doi va khong chua thu muc `du_lieu/`.

## Ket qua ky thuat da nghiem thu

### Tham do that

- Vnstock Community `4.0.4`.
- Ma lan chay: `20260724T152739494769Z_521d23ce`.
- FPT, HPG, MBB deu thanh cong, moi ma 8 dong.
- Khoang ngay that: `2026-07-01` den `2026-07-10`.
- Cot that: `time`, `open`, `high`, `low`, `close`, `volume`.
- Kieu that: `datetime64[ns]`, `float64`, `int64`.
- Cach goi da hoat dong: `Market().equity(symbol=ma).ohlcv(...)`.
- Khong can sua giao dien bo chuyen doi sau tham do.

### Tai that nho

- Ma lan chay: `20260724T153953222157Z_5383eaab`.
- FPT, HPG, MBB deu thanh cong, 8 dong, 1 lan thu, 0 canh bao, khong loi.
- Moi ma co du lieu tho JSON, CSV chuan hoa, CSV san sang, JSON bao cao chat luong, JSON nhat ky va SHA-256.
- San pham that chi nam cuc bo duoi `du_lieu/`.

### Python va CI

- Python `3.12.13`.
- `30/30` kiem thu dat; `Ran 30 tests in 0.696s`; `OK`.
- GitHub Actions run so 32, ID `30108253709`: `success` tren commit `9552e4641327ba93fa02f1fd0953d378f3f879f1`.
- Job `kiem_tra`, ID `89530965041`: `success`.

## Phan quyet

**DAT — PHE DUYET KY THUAT MOC 1.**

Cac dieu kien ky thuat bat buoc da duoc dap ung:

1. Nhanh chua dau `main` hien hanh.
2. Tham do that FPT, HPG, MBB dat.
3. Tai that nho FPT, HPG, MBB dat.
4. Python 3.12 dat 30/30 kiem thu.
5. GitHub Actions dat tren dau nhanh da bao cao.
6. Khong commit du lieu that.
7. Khong vuot pham vi sang Moc 2.

## Viec dang hoat dong

1. Cap nhat ba tep dieu phoi bang phan quyet doan 00.
2. Cho GitHub Actions chay lai tren dau nhanh moi nhat sau cap nhat tai lieu.
3. Neu CI dat, cap nhat PR body bang ket qua that.
4. Chuyen PR so 3 khoi trang thai nhap sang san sang ra soat.
5. Nguoi dung gop PR so 3 vao `main`.
6. Sau khi gop, doan 00 phai xac minh commit hop nhat va CI tren `main`.
7. Chi sau xac minh sau gop moi duoc tao loi giao viec Moc 2.

## Pham vi bi khoa

- Khong tu dong gop PR trong buoc cap nhat tai lieu nay.
- Khong mo Moc 2 truoc khi gop va xac minh PR so 3.
- Khong them MA250, momentum, backtest, hoc may hoac chia von.
- Khong tai toan bo VN100.
