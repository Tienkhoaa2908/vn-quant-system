# Cua du lieu VN100 toan phan

## Trang thai

- Base bat buoc: `e59dca55fa37d88bd0e0f6e8e78bc6d282e4996b`.
- Nhanh: `du_lieu-vn100-toan-phan`.
- Pham vi: chi thu thap, truy vet, kiem tra chat luong va bao cao du lieu.
- Khong chay lai Moc 4, khong huan luyen mo hinh, khong trien khai Moc 5.
- Du lieu that va checkpoint van hanh nam ngoai kho ma; thu muc `/du_lieu/` da duoc `.gitignore` loai tru.

## Bo dieu phoi tai hang loat

Lenh:

```bash
PYTHONPATH=src python -m he_thong_dinh_luong.tai_du_lieu_vn100 \
  --danh-sach-ma /duong/dan/danh_sach_hop_ma_vn100.csv \
  --ngay-bat-dau 2016-01-01 \
  --ngay-ket-thuc 2026-07-24 \
  --ngay-kiem-tra 2026-07-24 \
  --thu-muc-du-lieu /duong/dan/ngoai-kho/du_lieu \
  --ma-lan-chay vn100_20260724 \
  --so-nen 5000 \
  --yeu-cau-moi-phut 18
```

Bo dieu phoi tai tung ma qua `nguon_vnstock` va `chay_quy_trinh` cua Moc 1, khong tao mot luong luu tru moi. Moi lan goi nguon, ke ca lan thu lai, deu di qua gioi han toc do. Loi mot ma duoc ghi vao `loi_tung_ma.jsonl` va khong chan ma tiep theo.

## Tiep tuc sau loi

Checkpoint nam tai:

```text
<thu_muc_du_lieu>/dieu_phoi_vn100/<ma_lan_chay>/checkpoint.json
```

Mot ma chi duoc bo qua khi:

1. checkpoint ghi `thanh_cong`;
2. tep raw van ton tai;
3. SHA-256 tinh lai khop SHA-256 da ghi.

Neu hash khong khop, ma duoc tai lai vao mot `ma_lan_chay` con moi. Raw cu khong bi ghi de hoac sua. Tuy chon `--khong-tiep-tuc` bat buoc tao them mot lan tai cho moi ma, van khong ghi de raw cu.

## Dau ra van hanh

Ngoai cac san pham raw/chuan hoa/bao cao/san sang cua Moc 1, bo dieu phoi tao:

```text
dieu_phoi_vn100/<ma_lan_chay>/checkpoint.json
dieu_phoi_vn100/<ma_lan_chay>/loi_tung_ma.jsonl
dieu_phoi_vn100/<ma_lan_chay>/tong_hop.json
```

Khong tep nao trong ba tep tren duoc dung de sua nguoc raw. Khong dien du lieu thieu, khong correction overlay va khong tu dong ap hanh dong doanh nghiep.

## Kiem thu

`tests/test_tai_du_lieu_vn100.py` chi dung nguon va runner gia lap, khong goi mang. Cac truong hop khoa:

- chuan hoa va bo trung danh sach ma;
- gioi han toc do;
- loi tung ma khong chan toan bo lo;
- resume chi bo qua khi raw hash con khop;
- raw bi thay doi buoc tai lai, khong chap nhan checkpoint cu.

## Cua chap nhan du lieu that

Chua duoc chay Moc 4 cho toi khi dong thoi dat:

1. danh sach VN100 hien tai dung 100 ma, khong trung, co nguon HOSE;
2. lich su thanh phan point-in-time lien tuc tu 2021-01-01;
3. OHLCV day du cho hop ma lich su, khong dien thieu;
4. raw bat bien va hash kiem tra lai khop;
5. doi chieu mau EOD HOSE dat;
6. kiem ke hanh dong doanh nghiep co bang chung VSDC/HOSE/doanh nghiep;
7. co so gia raw/adjusted duoc xac nhan;
8. manifest va `sha256.txt` khop toan bo san pham.

Neu mot cua khong dat, trang thai phai la `FAIL` va dung truoc huan luyen/backtest.
