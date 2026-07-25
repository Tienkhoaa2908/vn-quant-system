# Trang thai du an

Cap nhat gan nhat: 2026-07-25

## Kho ma nguon

- Kho: `Tienkhoaa2908/vn-quant-system`.
- Nhanh chinh: `main`.
- Base Moc 3: `f52e06ffd4dde26e8af9d6451ec1e64f5a61b35d`.
- Nhanh chuyen mon: `m3-mo_phong-giao_dich`.
- Python muc tieu: 3.12; cong cu moi truong: `uv`.
- GitHub la nguon su that ve nhanh, commit, PR va CI.

## Moc 0–Moc 2

Trang thai: **da dong hoan toan**.

- PR Moc 2 so 5 gop bang merge commit `6e8d2ed49c2ef57e43c9f0f2249361b26b838b33`.
- FPT, HPG, MBB da duoc xac minh Moc 2: moi ma 287 phien va 38 dong MA250.
- Nguon lich su thanh vien that van chua duoc phe duyet.

## Moc 3 — Mo phong giao dich va backtest

Trang thai: **PR so 7 dang Draft; ma, kiem thu va xac minh ky thuat tren du lieu that da hoan tat; chua duoc Ready hoac gop**.

Da hoan thanh:

- sua quyen co tuc tien mat theo ngay chot quyen va ngay thanh toan;
- dinh co suc mua sau ban, tinh gia khop, phi, slippage va lot;
- hoan thien realized/unrealized P&L, chi phi va doi soat NAV;
- eligibility fail closed cho mo/tang vi the;
- validation bien chi phi, so nguyen, don vi va lam sach credential;
- 121 test: 60 test Moc 3 va 61 test hoi quy Moc 0–2;
- tai lieu kien truc, README va ban giao;
- xac minh ky thuat engine tren FPT, HPG va MBB.

## Xac minh ky thuat tren du lieu that

- Ma lan chay: `xac_minh_fpt_hpg_mbb_20260725T074736Z`.
- Nguon Moc 1: `20260724T190515274806Z_6cd15c6d`.
- 287 phien moi ma; 861 dong sau khi ghep gia Moc 1 voi trang thai Moc 2.
- Moi truong: Python `3.12.10`, uv `0.11.32`.
- Kich ban: FPT/HPG/MBB moi ma 30%, giu 10% tien mat; mua 2025-06-30 va dong het 2026-07-23.
- Engine tao 287 dong NAV, 287 dong so cai, 6/6 lenh khop, khong het han/tu choi.
- Tien mat khong am; ba vi the duoc dong het; chenh lech doi soat `0.0000000`.
- Tao dung 9 san pham, xac minh SHA-256 manifest va khong co canh bao.

Chi tiet so lieu va phuong phap: `tai_lieu/ket_qua_xac_minh_that_moc_3.md`.

## Gioi han nghiem thu

- Ket qua chi xac minh ky thuat engine, khong phai bang chung hieu qua dau tu.
- Ty trong 30% moi ma la kich ban kiem tra; khong su dung baseline MA250-dong-luong.
- Snapshot membership chua phai lich su thanh vien that.
- Nguong thanh khoan chua phai cau hinh san xuat.
- Co so gia `khong_dieu_chinh` chua duoc nguon xac nhan doc lap.
- Khong truyen corporate actions that.
- Chi co ba ma va mot khoang thoi gian; khong dien giai loi nhuan nhu danh gia chien luoc.
- Chua co ML, walk-forward, inverse volatility hoac gioi han nganh.

## Cua kiem soat

- Doan 00 xac minh diff, 121 test va CI tren head moi.
- PR so 7 tiep tuc Draft; khong Ready, khong gop va khong force-push.
- Khong commit du lieu, san pham backtest hay log that; diff khong duoc co tep duoi `du_lieu/`.
- Khong mo Moc 4.
- Khong tich hop SSI, khong doc tai khoan va khong gui lenh.
- Head, Run ID, Job ID va merge commit tam moi nhat duoc ghi trong mo ta PR so 7.
