# vn-quant-system

He thong dinh luong co phieu Viet Nam, dang o Moc 2: tap co phieu theo tung thoi diem va cac duong co so khong nhin truoc.

## Pham vi hien tai

Moc 2 gom:

- doc anh chup tap co phieu theo ngay hieu luc;
- chon anh chup gan nhat khong lon hon ngay danh gia;
- tinh gia tri giao dich va trung binh thanh khoan theo tung ma;
- tinh MA250 bang dung 250 quan sat gia dong cua;
- tinh dong luong theo cua so bat buoc;
- xuat CSV UTF-8 va bao cao JSON co thu tu on dinh;
- CLI ngoai tuyen, khong tu tai VN100 va khong ghi de san pham.

Khong thuoc Moc 2: backtest, khop lenh, phi, thue, truot gia, hoc may, LightGBM, nhan, chia von, toi uu danh muc va gioi han ty trong.

## Dau vao du lieu gia

Tai su dung CSV san sang cua Moc 1:

```text
ma,ngay,gia_mo_cua,gia_cao_nhat,gia_thap_nhat,gia_dong_cua,khoi_luong
```

Ngay dung `YYYY-MM-DD`. Cap `ma,ngay` phai duy nhat. Gia dong cua phai la so huu han duong; khoi luong phai la so nguyen khong am.

## Tai du lieu Moc 1 voi so nen ro rang

CLI tai du lieu nhan `--so_nen`, la so nguyen duong duoc truyen truc tiep thanh `count` cho Vnstock 4.0.4. Mac dinh la `400`, duoc hien thi trong `--help`; bo chuyen doi khong tu gan cung 400 va khong con phu thuoc gioi han mac dinh 100 dong cua nguon.

```bash
PYTHONPATH=src uv run --with vnstock==4.0.4 \
  python -m he_thong_dinh_luong.tai_du_lieu \
  --ma FPT HPG MBB \
  --ngay_bat_dau 2025-06-01 \
  --ngay_ket_thuc 2026-07-24 \
  --ngay_kiem_tra 2026-07-25 \
  --so_nen 400 \
  --thu_muc_du_lieu du_lieu
```

CLI truyen `so_nen_yeu_cau` vao cau hinh lan chay truoc khi quy trinh cong bo san pham. `du_lieu/nhat_ky/<ma_lan_chay>/tong_hop.json` va JSON in ra terminal dung cung mot mo hinh ket qua, nen cung ghi gia tri nay. He thong khong doc roi ghi de tep tong hop da cong bo. Du lieu that va nhat ky van nam duoi `du_lieu/` va khong duoc commit.

## Dau vao tap co phieu theo thoi diem

CSV UTF-8:

```text
ngay_hieu_luc,ma,nguon,phien_ban
```

Voi ngay `T`, he thong chi chon anh chup co `ngay_hieu_luc <= T` va lay anh chup gan nhat. Anh chup tuong lai khong duoc su dung. Neu khong co anh chup hop le, lenh dung voi ma thoat khac `0`.

Tep trong `tests/du_lieu/tap_co_phieu_gia_lap.csv` chi la du lieu gia lap. Du an chua tuyen bo co lich su thanh vien that hay da giai quyet thien lech song sot bang du lieu that.

## Cong thuc

### Gia tri giao dich va thanh khoan

```text
gia_tri_giao_dich = gia_dong_cua * khoi_luong
```

Gia co phieu Moc 1 co don vi nghin dong moi co phieu, do do gia tri giao dich va trung binh thanh khoan co don vi nghin dong.

Bo loc thanh khoan co ba tham so bat buoc:

- `cua_so_thanh_khoan`;
- `so_quan_sat_toi_thieu`;
- `nguong_thanh_khoan`.

Dat thanh khoan khi trung binh lon hon hoac bang nguong. Khong co nguong san xuat mac dinh.

### MA250

```text
ma250 = trung binh cong cua dung 250 gia dong cua gan nhat
```

Truoc quan sat thu 250, `ma250` va `tren_ma250` de trong. `tren_ma250=true` khi gia dong cua lon hon hoac bang MA250.

### Dong luong

```text
dong_luong_N = gia_dong_cua_t / gia_dong_cua_t_tru_N - 1
```

`N` la tham so bat buoc. Can toi thieu `N + 1` quan sat cua cung ma.

## Dau ra Moc 2

CLI tao hai tep trong thu muc dau ra:

```text
duong_co_so.csv
bao_cao.json
```

CSV co cac cot:

```text
ma,ngay,thuoc_tap_co_phieu,ngay_hieu_luc_tap_co_phieu,nguon_tap_co_phieu,phien_ban_tap_co_phieu,gia_tri_giao_dich,gia_tri_giao_dich_trung_binh,dat_thanh_khoan,ma250,tren_ma250,dong_luong,trang_thai_lich_su
```

Bao cao JSON ghi cau hinh, don vi va tom tat rieng tung ma: so phien dau vao, ngay dau, ngay cuoi, so dong dau ra, so dong co MA250, MA250 cuoi, dong luong cuoi, trang thai thanh khoan, canh bao va loi. Bao cao canh bao rieng khi mot ma co duoi 250 phien, va khi co duoi nguong xac minh 260 phien.

Tep da ton tai khong bi ghi de. Loi dau vao duoc ghi vao `bao_cao_loi.json` khi co the va duoc lam sach thong tin nhay cam.

## Chay CLI Moc 2

Theo mot ngay danh gia:

```bash
PYTHONPATH=src uv run --python 3.12 \
  python -m he_thong_dinh_luong.duong_co_so \
  --du_lieu_san_sang du_lieu/san_sang/<ma_lan_chay> \
  --anh_chup_tap_co_phieu du_lieu/tap_co_phieu/anh_chup.csv \
  --ngay_danh_gia 2026-07-24 \
  --cua_so_thanh_khoan 20 \
  --so_quan_sat_toi_thieu 20 \
  --nguong_thanh_khoan 0 \
  --cua_so_dong_luong 20 \
  --thu_muc_dau_ra du_lieu/duong_co_so/kiem_tra_2026-07-24
```

Theo khoang ngay, thay `--ngay_danh_gia` bang:

```text
--ngay_bat_dau YYYY-MM-DD --ngay_ket_thuc YYYY-MM-DD
```

Gia tri `0` trong vi du chi dung de kiem tra ky thuat luong chay, khong phai nguong thanh khoan san xuat. Cua so dong luong trong vi du cung chua phai quyet dinh san xuat.

## Kiem thu ngoai tuyen

```bash
uv sync --frozen --python 3.12
PYTHONPATH=src uv run --python 3.12 python -m compileall -q src tests
PYTHONPATH=src uv run --python 3.12 \
  python -m unittest discover -s tests -p 'test_*.py' -v
```

CI khong goi mang, khong goi Vnstock va chi dung du lieu gia lap.

## Xac minh cuc bo FPT, HPG va MBB

Huong dan day du nam trong `tai_lieu/xac_minh_cuc_bo_moc_2.md`. Buoc nay chi tai ba ma, yeu cau it nhat 260 phien hop le, khong tai toan bo VN100 va khong commit dau ra that.

## Ket qua xac minh that FPT, HPG va MBB

Lan chay `20260724T190515274806Z_6cd15c6d` tren Python `3.12.10` da dat nghiem thu ky thuat:

- moi ma co 287 phien, tu 2025-06-02 den 2026-07-23;
- moi ma co 38 dong MA250;
- MA250 cuoi: FPT `87.70488`, HPG `24.16668`, MBB `24.61656`;
- dong luong 20 phien cuoi: FPT `-0.08873239436619718`, HPG `-0.11111111111111105`, MBB `-0.07157894736842108`;
- trang thai thanh khoan co gia tri, khong co loi, tong dau ra 861 dong.

Canh bao khoang trong 2026-02-13 den 2026-02-23 xuat hien o ca ba ma. Quy trinh khong tu dien cac phien thieu; canh bao nay khong chan nghiem thu ky thuat. Lan chay cu chua co `so_nen_yeu_cau` trong `tong_hop.json`; sau ban sua truy vet, can chay mot ma lan chay moi de xac nhan san pham bat bien co khoa nay.

## Cau truc du lieu cuc bo

San pham that nam duoi `du_lieu/`, thu muc nay da bi Git bo qua. Khong commit du lieu thi truong that, danh sach thanh vien bi han che ban quyen, nhat ky that, khoa hoac token.

## Nguyen tac du an

- GitHub la nguon su that ve nhanh, commit, PR va CI.
- Khong dung du lieu tuong lai.
- Khong tu dien gia, khoi luong, ngay giao dich hay thanh vien thieu.
- Khong coi danh sach thanh vien hien tai la dung cho toan bo lich su.
- Khong tao co du dieu kien dau tu tong hop khi chua co quyet dinh rieng.
- Moi thay doi kien truc phai duoc ghi vao `DECISIONS.md`.
- Khong mo Moc 3 trong nhanh Moc 2.
