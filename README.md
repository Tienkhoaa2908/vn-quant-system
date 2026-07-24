# vn-quant-system

He thong dinh luong co phieu Viet Nam, dang o Moc 1: thu thap, luu tru, chuan hoa va kiem tra du lieu thi truong theo ngay.

## Pham vi hien tai

Moc 1 gom:

- giao dien chung cho nguon du lieu;
- nguon gia lap de kiem thu khong dung mang;
- bo chuyen doi Vnstock Community dung dung phien ban `4.0.4` va nguon KBS;
- luu du lieu tho JSON dang bang theo cach bat bien;
- chuan hoa ve CSV UTF-8;
- kiem tra chat luong va xuat bao cao JSON;
- tao CSV san sang cho nghien cuu khi khong co loi nghiem trong;
- nhat ky JSON va trang thai doc lap theo tung ma;
- thu lai co gioi han cho loi nguon tam thoi.

Ba ma bat buoc la `FPT`, `HPG` va `MBB`. `VNINDEX` la phan mo rong, khong chan nghiem thu ba ma bat buoc.

Chua trien khai MA250, dong luong, mo phong giao dich, hoc may, LightGBM, chia von, gioi han ty trong hoac tai toan bo VN100.

## Luoc do du lieu chuan

Tep CSV chuan hoa va san sang co cac cot:

```text
ma,ngay,gia_mo_cua,gia_cao_nhat,gia_thap_nhat,gia_dong_cua,khoi_luong
```

Ngay dung dinh dang `YYYY-MM-DD`.

## Cau truc du lieu cuc bo

Moi lan chay tao mot ma rieng trong thu muc `du_lieu/`:

```text
du_lieu/
├── tho/<ma_lan_chay>/<ma>.json
├── chuan_hoa/<ma_lan_chay>/<ma>.csv
├── bao_cao/<ma_lan_chay>/<ma>.json
├── san_sang/<ma_lan_chay>/<ma>.csv
├── nhat_ky/<ma_lan_chay>/<ma>.json
└── nhat_ky/<ma_lan_chay>/tong_hop.json
```

`du_lieu/`, tep moi truong, khoa va tep bi mat da bi loai khoi Git. Du lieu tho khong bi ghi de im lang. Neu nguon khong tra du lieu, he thong chi ghi nhat ky that bai va khong tao tep tho gia.

## Cai dat de phat trien

Yeu cau Python 3.12 tro len va `uv`.

```bash
uv sync --frozen
```

Phu thuoc Vnstock khong nam trong moi truong kiem thu mac dinh. Lenh tai that dung `uv --with` de co lap phu thuoc nguon va giu GitHub Actions khong goi Vnstock.

## Kiem thu ngoai tuyen

```bash
PYTHONPATH=src uv run python -m compileall -q src tests
PYTHONPATH=src uv run python -m unittest discover -s tests -p 'test_*.py' -v
```

Tat ca kiem thu dung nguon gia lap hoac doi tuong gia, khong can khoa va khong goi mang.

## Tham do Vnstock 4.0.4

Chay buoc nay truoc lan tai that de ghi lai ten cot, kieu du lieu, don vi gia va trang thai rieng tung ma:

```bash
PYTHONPATH=src uv run --with vnstock==4.0.4 \
  python -m he_thong_dinh_luong.tham_do_vnstock \
  --ma FPT HPG MBB \
  --ngay_bat_dau 2026-07-01 \
  --ngay_ket_thuc 2026-07-10 \
  --thu_muc_du_lieu du_lieu
```

Bao cao tham do duoc ghi vao `du_lieu/tham_do/<ma_lan_chay>/ket_qua.json`. Cong cu chi ghi tom tat cau truc, khong ghi toan bo du lieu thi truong.

Thu rieng VNINDEX:

```bash
PYTHONPATH=src uv run --with vnstock==4.0.4 \
  python -m he_thong_dinh_luong.tham_do_vnstock \
  --ma VNINDEX \
  --ngay_bat_dau 2026-07-01 \
  --ngay_ket_thuc 2026-07-10
```

## Tai that nho cho FPT, HPG va MBB

Sau khi buoc tham do thanh cong:

```bash
PYTHONPATH=src uv run --with vnstock==4.0.4 \
  python -m he_thong_dinh_luong.tai_du_lieu \
  --ma FPT HPG MBB \
  --ngay_bat_dau 2026-07-01 \
  --ngay_ket_thuc 2026-07-10 \
  --ngay_kiem_tra 2026-07-24 \
  --thu_muc_du_lieu du_lieu
```

Moi ma duoc xu ly doc lap. Mot ma that bai khong xoa ket qua cua ma khac. Lenh tra ma `2` neu mot trong cac ma bat buoc duoc yeu cau khong thanh cong.

Khong dua thu muc `du_lieu/` hoac log tai that vao commit va yeu cau gop.

## Ket qua tham do tinh cua Vnstock 4.0.4

Ma nguon tag `v4.0.4` cho thay:

- khoi tao bang `from vnstock import Market`;
- co phieu: `Market().equity(symbol=ma).ohlcv(...)`;
- chi so: `Market().index(symbol=ma).ohlcv(...)`;
- du lieu ngay dung `interval="1D"`, nguon `source="kbs"`;
- cac cot chuan la `time`, `open`, `high`, `low`, `close`, `volume`;
- kieu du lieu la `datetime64[ns]`, bon cot gia `float64`, khoi luong `int64`;
- gia co phieu da duoc Vnstock chia cho 1.000 va co don vi nghin dong;
- gia VNINDEX duoc giu theo diem chi so;
- khong co tham so cong khai de chon gia dieu chinh hay chua dieu chinh trong giao dien nay.

Y nghia kinh te cua `volume` cho VNINDEX chua duoc coi la da xac nhan cho nghien cuu cho den khi co log tham do that va doi chieu nguon.

Chi tiet xem `tai_lieu/tham_do_vnstock_4_0_4.md`.

## Chay trinh kiem tra CSV cu

```bash
PYTHONPATH=src uv run python -m he_thong_dinh_luong \
  tests/du_lieu/gia_lap_hop_le.csv \
  --ngay_kiem_tra 2026-07-24
```

Ma thoat:

- `0`: du lieu hop le;
- `1`: loi doc tep hoac tham so;
- `2`: du lieu khong dat quy tac chat luong.

## Nguyen tac du an

- GitHub la nguon su that.
- Khong dua khoa truy cap, mat khau, log hoac du lieu thi truong that vao kho ma nguon.
- Khong dung du lieu tuong lai trong nghien cuu.
- Khong tu dien ngay thieu khi chua co lich giao dich dang tin cay.
- Canh bao khoang ngay khong tu dong chan dau ra hop le.
- Du lieu gia lap chi dung cho kiem thu, khong dai dien cho thi truong that.
- Moi thay doi kien truc phai duoc ghi vao `DECISIONS.md`.
