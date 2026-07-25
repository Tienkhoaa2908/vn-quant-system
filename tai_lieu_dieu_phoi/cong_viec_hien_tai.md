# Cong viec hien tai

Cap nhat: 2026-07-25

## Doan phu trach

Doan `03 Mo phong giao dich va backtest` phu trach Moc 3 duoi dieu phoi cua doan `00 Dieu phoi trung tam`.

## Nen bat buoc

- Kho: `Tienkhoaa2908/vn-quant-system`.
- Base: `f52e06ffd4dde26e8af9d6451ec1e64f5a61b35d`.
- Nhanh: `m3-mo_phong-giao_dich`.
- PR: so 7, bat buoc Draft.
- Khong force-push, khong gop, khong Ready va khong mo Moc 4.
- Khong commit tep nao duoi `du_lieu/`.

## Ket qua vong sua va nghiem thu

1. Co tuc tien mat chot quyen tai ngay hieu luc va thanh toan nghia vu da chot.
2. Dinh co suc mua sau khi ban, tinh ca fill price, phi, slippage va lot size.
3. Hoan thien realized/unrealized P&L, co tuc, phi/thue/slippage va doi soat NAV.
4. Eligibility fail closed cho mo/tang vi the; giam/dong van duoc phep kem canh bao.
5. Khoa bien slippage, phi/thue, gia khop, gia tri giao dich va so nguyen cau hinh.
6. Lam sach credential dong nhat trong stdout va `bao_cao_loi.json`.
7. Bat buoc `don_vi_gia` va `don_vi_tien` thong nhat, truy vet trong config/report/manifest.
8. Bo Moc 3 co 60 test; toan repository co 121 test.
9. Da chay xac minh ky thuat tren FPT, HPG va MBB bang du lieu that ngoai repository.

## Ket qua xac minh du lieu that

- Ma lan chay: `xac_minh_fpt_hpg_mbb_20260725T074736Z`.
- Nguon Moc 1: `20260724T190515274806Z_6cd15c6d`.
- 287 phien moi ma; 861 dong sau khi ghep voi trang thai Moc 2.
- Python `3.12.10`; uv `0.11.32`.
- FPT/HPG/MBB moi ma 30%, giu 10% tien mat.
- Tin hieu mua 2025-06-27, khop mua 2025-06-30.
- Tin hieu ban 2026-07-22, khop ban 2026-07-23.
- 287 dong NAV, 287 dong so cai, 6 lenh tao va 6 lenh khop.
- 0 lenh het han, 0 lenh tu choi, dong het ba vi the, tien mat khong am.
- Chenh lech doi soat `0.0000000`; 9 san pham dung dac ta; manifest SHA-256 dat; khong canh bao.

Chi tiet: `tai_lieu/ket_qua_xac_minh_that_moc_3.md`.

## Gioi han

- Day chi la xac minh ky thuat engine, khong phai bang chung hieu qua dau tu.
- Ty trong 30% moi ma chi la kich ban kiem tra; khong dung baseline MA250-dong-luong.
- Snapshot membership chua phai lich su thanh vien that.
- Nguong thanh khoan chua phai cau hinh san xuat.
- Co so gia `khong_dieu_chinh` chua duoc nguon xac nhan doc lap.
- Khong co corporate actions that; chi co ba ma va mot khoang thoi gian.
- Khong dien giai loi nhuan am hoac duong nhu danh gia chien luoc.
- Chua co ML, walk-forward, inverse volatility hoac gioi han nganh.

## Cua kiem soat tiep theo

- Doan 00 xac minh diff khong co `du_lieu/`, 121 test va CI tren head moi.
- CI phai checkout `refs/pull/7/merge`.
- Head, Run ID, Job ID va merge commit tam la du lieu dong, duoc ghi trong mo ta PR so 7.
- PR tiep tuc Draft; khong Ready, khong gop va khong mo Moc 4.
