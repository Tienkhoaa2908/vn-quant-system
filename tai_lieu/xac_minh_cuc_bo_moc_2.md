# Xac minh cuc bo Moc 2 tren FPT, HPG va MBB

Muc tieu cua buoc nay la kiem tra MA250, dong luong va thanh khoan tren du lieu that gioi han. Day khong phai bang chung ve lich su thanh vien that.

## 1. Tai du lieu Moc 1

Chon khoang du kien co tren 260 phien giao dich hop le:

```bash
PYTHONPATH=src uv run --with vnstock==4.0.4 \
  python -m he_thong_dinh_luong.tai_du_lieu \
  --ma FPT HPG MBB \
  --ngay_bat_dau 2025-06-01 \
  --ngay_ket_thuc 2026-07-24 \
  --ngay_kiem_tra 2026-07-25 \
  --thu_muc_du_lieu du_lieu
```

Khong them ma khac va khong tai toan bo VN100. Ghi lai `<ma_lan_chay>` duoc tao trong `du_lieu/san_sang/`.

Neu mot ma co duoi 260 phien, mo rong `--ngay_bat_dau` ve truoc va chay lai bang mot ma lan chay moi. Khong ghi de tep cu.

## 2. Tao anh chup chi de kiem tra ky thuat

Tao tep cuc bo duoi `du_lieu/`, khong commit:

```bash
mkdir -p du_lieu/tap_co_phieu
cat > du_lieu/tap_co_phieu/kiem_tra_fpt_hpg_mbb.csv <<'CSV'
ngay_hieu_luc,ma,nguon,phien_ban
2025-06-01,FPT,kiem_tra_cuc_bo,khong_phai_lich_su_that
2025-06-01,HPG,kiem_tra_cuc_bo,khong_phai_lich_su_that
2025-06-01,MBB,kiem_tra_cuc_bo,khong_phai_lich_su_that
CSV
```

Tep nay chi giup chay giao dien. No khong chung minh FPT, HPG va MBB la thanh vien cua mot chi so lich su trong toan bo khoang tren, va khong duoc dung de tuyen bo da loai bo thien lech song sot bang du lieu that.

## 3. Chay Moc 2

```bash
PYTHONPATH=src uv run --python 3.12 \
  python -m he_thong_dinh_luong.duong_co_so \
  --du_lieu_san_sang du_lieu/san_sang/<ma_lan_chay> \
  --anh_chup_tap_co_phieu du_lieu/tap_co_phieu/kiem_tra_fpt_hpg_mbb.csv \
  --ngay_bat_dau 2025-06-01 \
  --ngay_ket_thuc 2026-07-24 \
  --cua_so_thanh_khoan 20 \
  --so_quan_sat_toi_thieu 20 \
  --nguong_thanh_khoan 0 \
  --cua_so_dong_luong 20 \
  --thu_muc_dau_ra du_lieu/duong_co_so/kiem_tra_fpt_hpg_mbb
```

`nguong_thanh_khoan=0` va `cua_so_dong_luong=20` trong lenh tren chi la tham so kiem tra ky thuat. Khong coi day la cau hinh san xuat.

Neu thu muc dau ra da co `duong_co_so.csv` hoac `bao_cao.json`, dung mot thu muc moi. CLI se khong ghi de.

## 4. Doc bao cao

Mo:

```text
du_lieu/duong_co_so/kiem_tra_fpt_hpg_mbb/bao_cao.json
```

Kiem tra rieng FPT, HPG va MBB:

- `so_phien` phai it nhat 260;
- `ngay_dau` va `ngay_cuoi` khop du lieu san sang;
- `so_dong_co_ma250` phai lon hon 0;
- `ma250_cuoi` khong rong;
- `dong_luong_cuoi` khong rong neu du cua so;
- `trang_thai_thanh_khoan` co gia tri khi du so quan sat toi thieu;
- `canh_bao` va `loi` duoc xem rieng tung ma.

Bao cao can gui ve doan 00 gom ca lenh da chay, Python version, ma lan chay Moc 1, tham so Moc 2 va ket qua tung ma.

## 5. Bao mat va pham vi

- Khong commit `du_lieu/`, log that hay dau ra that.
- Khong commit tep thanh vien neu nguon co han che ban quyen.
- Khong them VN100 vao buoc xac minh nay.
- Khong mo Moc 3.
