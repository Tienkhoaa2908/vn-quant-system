# Xac minh cuc bo Moc 2 tren FPT, HPG va MBB

Muc tieu cua buoc nay la kiem tra MA250, dong luong va thanh khoan tren du lieu that gioi han. Day khong phai bang chung ve lich su thanh vien that.

## 1. Ket qua tham do count

Loi goi Vnstock 4.0.4 voi `count=400`:

```python
Market().equity(symbol=ma).ohlcv(
    start="2025-06-01",
    end="2026-07-24",
    interval="1D",
    source="kbs",
    count=400,
)
```

da tra:

- FPT: 287 dong, tu 2025-06-02 den 2026-07-23;
- HPG: 287 dong, tu 2025-06-02 den 2026-07-23;
- MBB: 287 dong, tu 2025-06-02 den 2026-07-23.

Gioi han 100 dong cua lan chay truoc den tu `count` mac dinh cua nguon. CLI cua du an nhan `--so_nen`, mac dinh ro rang la `400`, va truyen gia tri nay truc tiep cho Vnstock. `--so_nen` phai la so nguyen duong.

## 2. Ket qua xac minh that da dat

Lan chay Moc 1: `20260724T190515274806Z_6cd15c6d`; Python `3.12.10`.

- FPT, HPG, MBB moi ma 287 phien, tu 2025-06-02 den 2026-07-23;
- moi ma co 38 dong MA250;
- MA250 cuoi: FPT `87.70488`, HPG `24.16668`, MBB `24.61656`;
- dong luong 20 phien cuoi: FPT `-0.08873239436619718`, HPG `-0.11111111111111105`, MBB `-0.07157894736842108`;
- thanh khoan co gia tri, khong co loi, tong dau ra 861 dong.

Canh bao khoang trong 2026-02-13 den 2026-02-23 xuat hien o ca ba ma va khong chan. Quy trinh khong tu dien du lieu.

Lan chay nay duoc tao truoc ban sua truy vet cau hinh, nen `du_lieu/nhat_ky/20260724T190515274806Z_6cd15c6d/tong_hop.json` chua co `so_nen_yeu_cau`. Khong sua tep cu. Can chay lai bang ma lan chay moi de xac nhan san pham bat bien moi.

## 3. Tham do lai neu can

```bash
PYTHONPATH=src uv run --with vnstock==4.0.4 \
  python -m he_thong_dinh_luong.tham_do_vnstock \
  --ma FPT HPG MBB \
  --ngay_bat_dau 2025-06-01 \
  --ngay_ket_thuc 2026-07-24 \
  --so_nen 400 \
  --thu_muc_du_lieu du_lieu
```

Bao cao tham do ghi `so_nen_yeu_cau`. Khong commit bao cao nay.

## 4. Tai lai du lieu Moc 1

Dung mot ma lan chay moi; khong ghi de lan tai cu:

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

Khong them ma khac va khong tai toan bo VN100. Ghi lai `<ma_lan_chay_moi>` duoc tao trong `du_lieu/san_sang/`. Mo `du_lieu/nhat_ky/<ma_lan_chay_moi>/tong_hop.json` va xac nhan co `"so_nen_yeu_cau": 400`; JSON in terminal phai co cung gia tri va cung `trang_thai_tung_ma`.

Kiem tra rieng tung ma:

- so dong san sang phai it nhat 260;
- voi ket qua tham do neu tren, ky vong 287 dong va khoang ngay 2025-06-02 den 2026-07-23;
- neu nguon tra duoi 250 phien, MA250 khong the duoc tinh;
- neu co tu 250 den 259 phien, MA250 co the tinh nhung chua dat nguong xac minh 260 phien.

## 5. Tao anh chup chi de kiem tra ky thuat

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

## 6. Chay Moc 2 tren lan tai moi

Dung thu muc dau ra moi de tranh ghi de san pham cu:

```bash
PYTHONPATH=src uv run --python 3.12 \
  python -m he_thong_dinh_luong.duong_co_so \
  --du_lieu_san_sang du_lieu/san_sang/<ma_lan_chay_moi> \
  --anh_chup_tap_co_phieu du_lieu/tap_co_phieu/kiem_tra_fpt_hpg_mbb.csv \
  --ngay_bat_dau 2025-06-01 \
  --ngay_ket_thuc 2026-07-24 \
  --cua_so_thanh_khoan 20 \
  --so_quan_sat_toi_thieu 20 \
  --nguong_thanh_khoan 0 \
  --cua_so_dong_luong 20 \
  --thu_muc_dau_ra du_lieu/duong_co_so/kiem_tra_count_400_<ma_lan_chay_moi>
```

`nguong_thanh_khoan=0` va `cua_so_dong_luong=20` chi la tham so kiem tra ky thuat, khong phai cau hinh san xuat.

CLI khong ghi de. Neu thu muc dau ra da co `duong_co_so.csv`, `bao_cao.json` hoac `bao_cao_loi.json`, dung mot thu muc moi.

## 7. Doc bao cao

Mo:

```text
du_lieu/duong_co_so/kiem_tra_count_400_<ma_lan_chay_moi>/bao_cao.json
```

Kiem tra rieng FPT, HPG va MBB:

- `so_phien` phai it nhat 260;
- `ngay_dau` va `ngay_cuoi` khop du lieu san sang;
- `so_dong_co_ma250` phai lon hon 0;
- `ma250_cuoi` khong rong;
- `dong_luong_cuoi` khong rong neu du cua so;
- `trang_thai_thanh_khoan` co gia tri khi du so quan sat toi thieu;
- `canh_bao` phai rong ve nguong 250/260 khi co it nhat 260 phien;
- `loi` duoc xem rieng tung ma.

Bao cao can gui ve doan 00 gom ca lenh da chay, Python version, ma lan chay Moc 1, `so_nen_yeu_cau`, tham so Moc 2 va ket qua tung ma.

## 8. Bao mat va pham vi

- Khong commit `du_lieu/`, log that hay dau ra that.
- Khong commit tep thanh vien neu nguon co han che ban quyen.
- Khong nang `vnstock` tu `4.0.4` len `4.0.5` trong buoc nay.
- Khong them VN100 vao buoc xac minh nay.
- Khong mo Moc 3.
