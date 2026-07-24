# Trang thai du an

Cap nhat gan nhat: 2026-07-25

## Kho ma nguon

- Kho: `Tienkhoaa2908/vn-quant-system`.
- Nhanh chinh: `main`.
- Dau `main` hien tai: `6e8d2ed49c2ef57e43c9f0f2249361b26b838b33`.
- Python muc tieu: 3.12; cong cu moi truong: `uv`.
- GitHub la nguon su that ve nhanh, commit, PR va CI.

## Moc 0 va Moc 1

- Moc 0 da hoan thanh va da gop.
- Bo tai lieu dieu phoi da gop.
- Moc 1 da dong hoan toan.
- Dau `main` khi mo Moc 2 la `97399e291b0d3d237f247f58ffa03049826d40bd`.

## Moc 2 — Tap co phieu va duong co so

Trang thai: **da dong hoan toan**.

- PR so 5 da duoc chuyen khoi draft sau nghiem thu.
- PR so 5 da gop bang merge commit, khong squash va khong rebase.
- Merge commit: `6e8d2ed49c2ef57e43c9f0f2249361b26b838b33`.
- PR da `closed`, `merged=true`.
- `main` trung khop merge commit tren.

Da hoan thanh:

- tap co phieu theo tung thoi diem va quy tac ngan nhin truoc;
- thanh khoan, MA250 va dong luong;
- sua tinh toan ven san pham CLI;
- ho tro `--so_nen`, mac dinh cong khai 400, truyen thanh `count` cho Vnstock 4.0.4;
- luu ben vung `so_nen_yeu_cau` trong `tong_hop.json` va dung cung noi dung cho stdout;
- giu tinh bat bien, khong doc roi ghi de san pham da cong bo;
- cap nhat tai lieu xac minh va dieu phoi.

## Xac minh that FPT, HPG va MBB

Lan chay chi bao: `20260724T190515274806Z_6cd15c6d`; Python `3.12.10`.

- Moi ma co 287 phien, tu 2025-06-02 den 2026-07-23.
- Moi ma co 38 dong MA250.
- MA250 cuoi: FPT `87.70488`, HPG `24.16668`, MBB `24.61656`.
- Dong luong 20 phien cuoi: FPT `-0.08873239436619718`, HPG `-0.11111111111111105`, MBB `-0.07157894736842108`.
- Thanh khoan co gia tri, khong co loi, tong dau ra 861 dong.
- Canh bao khoang trong 2026-02-13 den 2026-02-23 xuat hien o ca ba ma; quy trinh khong tu dien du lieu va canh bao khong chan nghiem thu ky thuat.

Lan chay xac minh truy vet: `20260724T194007268318Z_1ade6129`.

- stdout co `so_nen_yeu_cau == 400`;
- `du_lieu/nhat_ky/20260724T194007268318Z_1ade6129/tong_hop.json` co cung gia tri;
- `trang_thai_tung_ma` tren dia va stdout giong nhau;
- FPT, HPG va MBB deu `thanh_cong`, moi ma 287 phien.

## CI sau gop

- Workflow: `kiem_tra_tu_dong`.
- Run number: `84`.
- Kich hoat: `push` vao `main`.
- Commit: `6e8d2ed49c2ef57e43c9f0f2249361b26b838b33`.
- Trang thai: `Success`.
- Job `kiem_tra`: thanh cong.
- Tong thoi gian hien tren giao dien: 17 giay; job 13 giay.
- Giao dien co canh bao Node.js 20 da bi ngung ho tro; day la canh bao khong chan, CI van thanh cong.
- Run ID va job ID khong hien trong anh xac minh va connector hien tai khong liet ke run `push` theo commit, nen khong tu suy doan hai gia tri nay.

## Moc 3 — Mo phong giao dich va backtest

Trang thai: **da co dac ta de nghi, chua phe duyet, chua trien khai ma**.

- Dac ta: `tai_lieu/dac_ta_moc_3.md`.
- Nhanh dieu phoi: `cap_nhat-sau-gop-m2-va-dac-ta-m3`.
- Nhanh chuyen mon Moc 3 chua duoc tao.
- Chua co PR ma Moc 3.
- Chi duoc mo trien khai sau khi doan 00 phe duyet dac ta va chi dinh doan chuyen mon.

## Gioi han du lieu thanh vien

- Giao dien chong nhin truoc da co.
- Xac minh gia va chi bao that da dat.
- Nguon lich su thanh vien that van chua duoc phe duyet.
- Khong tuyen bo da loai bo thien lech song sot bang du lieu thanh vien thuc te.

## Pham vi van bi khoa

- Chua trien khai backtest hoac mo phong giao dich cho den khi dac ta Moc 3 duoc phe duyet.
- Chua hoc may, LightGBM, nhan, chia von, toi uu danh muc hoac gioi han ty trong.
- Chua tai toan bo VN100.
- Khong commit du lieu thi truong that, nhat ky that, danh sach thanh vien bi han che hoac khoa.
- Khong tich hop tai khoan SSI hay API dat lenh; nguoi dung tu giao dich thu cong.
