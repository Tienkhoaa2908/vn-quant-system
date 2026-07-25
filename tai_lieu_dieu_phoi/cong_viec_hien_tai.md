# Cong viec hien tai

Cap nhat: 2026-07-25

## Doan phu trach

Doan `03 Mo phong giao dich va backtest` phu trach Moc 3 duoi dieu phoi cua doan `00 Dieu phoi trung tam`.

## Nen bat buoc

- Kho: `Tienkhoaa2908/vn-quant-system`.
- Base: `f52e06ffd4dde26e8af9d6451ec1e64f5a61b35d`.
- Nhanh: `m3-mo_phong-giao_dich`.
- PR: so 7, bat buoc draft.
- Khong force-push, khong gop, khong Ready va khong mo Moc 4.

## Ket qua vong sua sau ra soat

1. Co tuc tien mat chot quyen tai ngay hieu luc va thanh toan nghia vu da chot.
2. Dinh co suc mua sau khi ban, tinh ca fill price, phi, slippage va lot size.
3. Hoan thien realized/unrealized P&L, co tuc, phi/thue/slippage va doi soat NAV.
4. Eligibility fail closed cho mo/tang vi the; giam/dong van duoc phep kem canh bao.
5. Khoa bien slippage, phi/thue, gia khop, gia tri giao dich va so nguyen cau hinh.
6. Lam sach credential dong nhat trong stdout va `bao_cao_loi.json`.
7. Bat buoc `don_vi_gia` va `don_vi_tien` thong nhat, truy vet trong config/report/manifest.
8. Tach kiem thu nghiep vu thanh cac tep rieng; bo Moc 3 co 60 test.
9. Cap nhat `DECISIONS.md`, README, kien truc va tai lieu dieu phoi.

## Kiem thu

- Tong 121 test: 60 Moc 3 va 61 hoi quy Moc 0–2.
- CI Python 3.12 chay compile va unittest ngoai tuyen tren head va `refs/pull/7/merge`.
- Head, Run ID, Job ID va merge commit tam la du lieu dong, duoc ghi trong mo ta PR so 7.

## Cua kiem soat tiep theo

- Doan 00 xac minh diff, test va CI moi.
- Chi sau phan quyet cua doan 00, nguoi dung moi chay backtest FPT, HPG, MBB that.
- Khong commit san pham du lieu that.
- PR tiep tuc draft; khong Ready va khong gop.

## Gioi han

- Chua chay du lieu that sau vong sua.
- Nguon lich su thanh vien that chua duoc phe duyet.
- Khong market partial fill/participation rate; pre-trade sizing khong phai partial fill.
- Khong quyen mua, sap nhap, hoan doi, huy niem yet cuong buc.
- Khong SSI, ML, chia von san xuat hay Moc 4.
