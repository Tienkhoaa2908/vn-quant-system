# Cong viec hien tai

Cap nhat: 2026-07-25

## Doan phu trach

Doan `00 Dieu phoi trung tam` phu trach dong ho so Moc 3 sau gop va chuan bi cua phe duyet cho dac ta tiep theo.

## Nen bat buoc

- Kho: `Tienkhoaa2908/vn-quant-system`.
- `main`: `79a044d75f3a66e5c636f0a83613fc9af0cac3fc`.
- Nhanh dieu phoi: `cap_nhat-sau-gop-m3`.
- Pham vi nhanh: chi tai lieu dieu phoi sau gop.
- Khong force-push, khong sua truc tiep `main`, khong tu gop.
- Khong commit tep nao duoi `du_lieu/`.
- Khong trien khai ma Moc 4 tren nhanh nay.

## Moc 3 da dong

- PR so 7 da gop bang merge commit `79a044d75f3a66e5c636f0a83613fc9af0cac3fc`.
- Head da phe duyet: `305da62ac54b735a129ab4dc2c66b0826b8953c3`.
- PR da dong va `merged=true`.
- `main` trung khop voi merge commit.

CI sau gop:

- run number `183`;
- Run ID `30150924124`;
- Job ID `89661073156`;
- trigger `push`;
- branch `main`;
- checkout `79a044d75f3a66e5c636f0a83613fc9af0cac3fc`;
- `completed/success`;
- compile va 121 unittest ngoai tuyen dat.

Canh bao Node.js 20 deprecated khong lam thay doi ket qua CI.

## Ket qua chuyen giao Moc 3

1. Engine T/T+1, lenh DAY va xu ly thieu bar/open.
2. Phi, thue, slippage, lot size va dinh co suc mua.
3. Tien mat, vi the, so cai, NAV va doi soat P&L.
4. Corporate actions MVP va chong tinh hai lan.
5. Eligibility fail closed cho mo/tang vi the.
6. Don vi gia/tien va lam sach credential.
7. 121 test, 9 san pham bat bien va manifest SHA-256.
8. Xac minh ky thuat tren FPT, HPG, MBB: 287 phien moi ma, 6/6 lenh khop, doi soat `0.0000000`.

## Gioi han con lai

- Bo ba ma chi la du lieu xac minh ky thuat.
- Chua co lich su thanh vien VN100 point-in-time that.
- Chua co corporate actions that duoc phe duyet.
- Chua co nghien cuu nhieu nam tren toan universe.
- Chua co ML, walk-forward, inverse volatility, gioi han ma va gioi han nganh.
- Khong dien giai ket qua lan chay Moc 3 nhu hieu qua chien luoc.

## Cong viec tiep theo

1. Tao PR dieu phoi chi gom tai lieu sau gop Moc 3.
2. Xac minh CI cua PR dieu phoi.
3. Chi gop PR dieu phoi khi co lenh rieng cua doan 00/nguoi dung.
4. Sau khi PR dieu phoi gop va CI `main` dat, soan dac ta Moc 4 de phe duyet.
5. Dac ta Moc 4 phai chot ro:
   - universe VN100 point-in-time hoac universe thanh khoan cao point-in-time;
   - lich su nhieu nam, muc tieu 5–10 nam neu chat luong du lieu cho phep;
   - warm-up MA250;
   - kiem soat survivorship bias va look-ahead;
   - feature, nhan va walk-forward;
   - Logistic Regression truoc LightGBM.

Moc 4 hien **chua mo** va chua co nhanh trien khai.