# Trang thai du an

Cap nhat gan nhat: 2026-07-24

## Kho ma nguon

- Kho: `Tienkhoaa2908/vn-quant-system`.
- Nhanh chinh: `main`.
- Dau `main` da xac minh: `4eba2a77d5864027c84d4350769d95fd4abd5fee`.
- `main` da chua thu muc `tai_lieu_dieu_phoi/`.
- Python muc tieu: 3.12.
- Cong cu moi truong: `uv`.

## Moc 0

Trang thai: **da hoan thanh, da kiem tra va da gop vao main**.

- PR so 1: da gop.
- Commit trien khai chinh: `3385e401532e51457b9e9360e17df7af0e021881`.
- Commit hop nhat: `b132578b763ead96ad172a1ace68acdff6e36007`.

## Bo tai lieu dieu phoi

Trang thai: **da gop vao main**.

- PR so 2: da gop.
- Commit hop nhat: `4eba2a77d5864027c84d4350769d95fd4abd5fee`.

## Moc 1 — Du lieu

Trang thai dieu phoi: **da duoc doan 00 nghiem thu ky thuat; du dieu kien chuyen PR sang san sang ra soat sau khi CI dat tren dau nhanh moi nhat**.

PR so 3:

- nhanh nguon: `m1-du_lieu`;
- nhanh dich: `main`;
- dau truoc quyet dinh nghiem thu: `9552e4641327ba93fa02f1fd0953d378f3f879f1`;
- trang thai truoc quyet dinh: mo, nhap, chua gop;
- mergeable: co;
- nhanh chua dau `main`, cham hon `main` 0 commit;
- 24 tep thay doi;
- khong co tep nao trong `du_lieu/`.

### Tham do that Vnstock 4.0.4

- Ma lan chay: `20260724T152739494769Z_521d23ce`.
- Khoang ngay: `2026-07-01` den `2026-07-10`.
- Cach goi da hoat dong: `Market().equity(symbol=ma).ohlcv(start=..., end=..., interval="1D", source="kbs")`.
- FPT, HPG, MBB: deu thanh cong, moi ma 8 dong.
- Cot that: `time`, `open`, `high`, `low`, `close`, `volume`.
- Kieu: `time=datetime64[ns]`, OHLC=`float64`, `volume=int64`.
- Don vi gia do bo chuyen doi bao cao: `nghin_dong`.
- Chua phat hien tham so chon gia dieu chinh/chua dieu chinh.

### Tai that nho

- Ma lan chay: `20260724T153953222157Z_5383eaab`.
- Nguon: `vnstock_kbs`, phien ban `4.0.4`.
- FPT, HPG, MBB: deu thanh cong, 8 dong, 1 lan thu, khong canh bao, khong loi.
- Moi ma co JSON tho, CSV chuan hoa, CSV san sang, JSON bao cao chat luong, JSON nhat ky va SHA-256.
- Tat ca san pham that nam cuc bo duoi `du_lieu/` va khong duoc commit.

### Kiem thu

- Python: `CPython 3.12.13`, Windows x86-64.
- Unittest: `Ran 30 tests in 0.696s`.
- Ket qua: `OK`.
- GitHub Actions run so 32, ID `30108253709`, da dat tren commit `9552e4641327ba93fa02f1fd0953d378f3f879f1`.
- Job `kiem_tra`, ID `89530965041`: thanh cong; toan bo buoc dong bo, bien dich va kiem thu ngoai tuyen deu dat.

### Phan quyet doan 00

**DAT — PHE DUYET KY THUAT MOC 1.**

1. Cap nhat ba tep dieu phoi bang phan quyet nay.
2. Chay lai GitHub Actions tren dau nhanh sau cap nhat.
3. Neu CI dat, cap nhat PR body va chuyen PR so 3 khoi trang thai nhap.
4. Chua gop PR tu dong; nguoi dung thuc hien buoc gop sau khi nhan bao cao dieu phoi.
5. Khong mo Moc 2 truoc khi PR so 3 duoc gop va dau `main` duoc xac minh lai.

## Pham vi bi khoa

- Chua mo Moc 2.
- Chua them MA250 hoac momentum.
- Chua backtest.
- Chua hoc may.
- Chua chia von.
- Chua tai toan bo VN100.
