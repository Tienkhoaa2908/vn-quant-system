# Trang thai du an

Cap nhat gan nhat: 2026-07-25

## Kho ma nguon

- Kho: `Tienkhoaa2908/vn-quant-system`.
- Nhanh chinh: `main`.
- Python muc tieu: 3.12; cong cu moi truong: `uv`.
- GitHub la nguon su that ve nhanh, commit, PR va CI.

## Moc 0–Moc 2

Trang thai: **da dong hoan toan**.

- Moc 0 gop qua PR so 1.
- Moc 1 dong sau PR so 4.
- Moc 2 gop qua PR so 5, merge commit `6e8d2ed49c2ef57e43c9f0f2249361b26b838b33`.
- FPT, HPG, MBB da duoc xac minh Moc 2: moi ma 287 phien va 38 dong MA250.
- Nguon lich su thanh vien VN100 that van chua duoc phe duyet.

## Moc 3 — Mo phong giao dich va backtest

Trang thai: **da dong hoan toan, da gop vao `main` va CI sau gop dat**.

Git va PR:

- PR: so 7, `M3: mo phong giao dich va backtest`.
- Head duoc phe duyet: `305da62ac54b735a129ab4dc2c66b0826b8953c3`.
- Merge commit: `79a044d75f3a66e5c636f0a83613fc9af0cac3fc`.
- PR da dong va `merged=true` luc `2026-07-25T08:20:18Z`.
- `main` trung khop hoan toan voi merge commit tren.

CI sau gop:

- Workflow: `kiem_tra_tu_dong`.
- Run number: `183`.
- Run ID: `30150924124`.
- Job `kiem_tra` ID: `89661073156`.
- Trigger: `push`.
- Branch: `main`.
- Commit checkout: `79a044d75f3a66e5c636f0a83613fc9af0cac3fc`.
- Ket qua: `completed/success`.
- Tat ca buoc cai Python, dong bo moi truong, compile va unittest ngoai tuyen deu dat.
- Canh bao Node.js 20 deprecated la canh bao cua action runtime, khong lam CI that bai.

Da hoan thanh:

- tin hieu sau close T va khop som nhat tai open phien ke tiep;
- lenh DAY, khong tu doi phien khi thieu bar/open;
- lenh, khop lenh, vi the, tien mat, so cai va NAV;
- phi mua/ban, thue ban, truot gia, lot size va dinh co suc mua;
- long-only, khong short, khong margin, khong tien mat am, khong ban vuot vi the;
- corporate actions MVP: chia tach, co phieu thuong va co tuc tien mat;
- realized/unrealized P&L, doi soat NAV va truy vet don vi;
- 121 test: 60 test Moc 3 va 61 test hoi quy Moc 0–2;
- 9 san pham bat bien, manifest SHA-256, cong bo nguyen tu va rollback;
- xac minh ky thuat engine tren du lieu that FPT, HPG va MBB.

## Xac minh ky thuat tren du lieu that

- Ma lan chay: `xac_minh_fpt_hpg_mbb_20260725T074736Z`.
- Nguon Moc 1: `20260724T190515274806Z_6cd15c6d`.
- 287 phien moi ma; 861 dong sau khi ghep gia Moc 1 voi trang thai Moc 2.
- Moi truong: Python `3.12.10`, uv `0.11.32`.
- Kich ban: FPT/HPG/MBB moi ma 30%, giu 10% tien mat; mua 2025-06-30 va dong het 2026-07-23.
- 287 dong NAV, 287 dong so cai, 6/6 lenh khop, 0 het han, 0 tu choi.
- Tien mat khong am; dong het ba vi the; chenh lech doi soat `0.0000000`.
- Tao dung 9 san pham, SHA-256 manifest dat va khong co canh bao.

Chi tiet: `tai_lieu/ket_qua_xac_minh_that_moc_3.md`.

## Gioi han da ghi nhan

- Ket qua tren chi xac minh ky thuat engine, khong phai bang chung hieu qua dau tu.
- Ty trong 30% moi ma la kich ban kiem tra, khong phai phan bo san xuat.
- Snapshot membership chua phai lich su thanh vien VN100 point-in-time that.
- Nguong thanh khoan chua phai cau hinh san xuat.
- Co so gia `khong_dieu_chinh` chua duoc nguon xac nhan doc lap.
- Khong co corporate actions that trong lan chay.
- Chi co ba ma va mot khoang thoi gian.
- Chua co ML, walk-forward, inverse volatility hoac gioi han nganh.

## Cua kiem soat tiep theo

- Nhanh dieu phoi sau gop: `cap_nhat-sau-gop-m3`.
- Chi cap nhat tai lieu; khong chua ma Moc 4.
- Moc 4 van **chua mo**.
- Truoc khi viet ma Moc 4, phai co dac ta duoc phe duyet.
- Dac ta tiep theo phai lam ro dieu kien du lieu nghien cuu: universe VN100 point-in-time hoac universe thanh khoan cao point-in-time, lich su nhieu nam va kiem soat survivorship bias.
- Khong tich hop SSI, khong doc tai khoan va khong gui lenh.