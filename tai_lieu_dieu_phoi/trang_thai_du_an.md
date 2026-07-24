# Trang thai du an

Cap nhat gan nhat: 2026-07-25

## Kho ma nguon

- Kho: `Tienkhoaa2908/vn-quant-system`.
- Nhanh chinh: `main`.
- Dau `main` khi mo Moc 2: `97399e291b0d3d237f247f58ffa03049826d40bd`.
- Nhanh Moc 2: `m2-tap_co_phieu-duong_co_so`.
- Dau nhanh truoc ghi nhan xac minh cuoi: `5e5a2c143805805b4af9b6b099ec5262d2c4006d`.
- Python muc tieu: 3.12; cong cu moi truong: `uv`.
- GitHub la nguon su that ve nhanh, commit, PR va CI.

## Moc 0 va Moc 1

- Moc 0 da hoan thanh va da gop.
- Bo tai lieu dieu phoi da gop.
- Moc 1 da dong hoan toan.
- PR so 3 va PR so 4 da gop; dau `main` khi mo Moc 2 la commit neu tren.

## Moc 2 — Tap co phieu va duong co so

Trang thai: **ma, kiem thu, xac minh that va CI da dat; PR so 5 van giu draft cho doan 00 ra phan quyet**.

Da hoan thanh:

- tap co phieu theo tung thoi diem va quy tac ngan nhin truoc;
- thanh khoan, MA250 va dong luong;
- sua tinh toan ven san pham CLI;
- ho tro `--so_nen`, mac dinh cong khai 400, truyen thanh `count` cho Vnstock 4.0.4;
- luu ben vung `so_nen_yeu_cau` trong `tong_hop.json` va dung cung noi dung cho stdout;
- giu tinh bat bien, khong doc roi ghi de san pham da cong bo.

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

## CI va trang thai nghiem thu

- CI truoc ghi nhan tai lieu: run so 75, ID `30120599648`, job `kiem_tra` ID `89571991558`, ket luan `success` tren merge ref `7b68c7a09d5ae2cdcdf7592224482ea485d71433`.
- PR so 5 tiep tuc giu draft.
- Khong tu gop PR va khong mo Moc 3.
- Buoc tiep theo chi la gui bao cao ve doan 00 va cho phan quyet.

## Gioi han du lieu thanh vien

- Giao dien chong nhin truoc da co.
- Xac minh gia va chi bao that da dat.
- Nguon lich su thanh vien that van chua duoc phe duyet.
- Khong tuyen bo da loai bo thien lech song sot bang du lieu thanh vien thuc te.

## Pham vi bi khoa

- Khong backtest, mo phong giao dich, phi, thue, truot gia hoac lot size.
- Khong hoc may, LightGBM, nhan, chia von, toi uu danh muc hoac gioi han ty trong.
- Khong tai toan bo VN100.
- Khong commit du lieu thi truong that, nhat ky that, danh sach thanh vien bi han che hoac khoa.
