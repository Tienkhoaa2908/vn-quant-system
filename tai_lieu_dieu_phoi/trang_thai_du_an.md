# Trang thai du an

Cap nhat gan nhat: 2026-07-25

## Kho ma nguon

- Kho: `Tienkhoaa2908/vn-quant-system`.
- Nhanh chinh: `main`.
- Dau `main` da xac minh khi mo Moc 2: `97399e291b0d3d237f247f58ffa03049826d40bd`.
- Commit nay la merge commit cua PR so `4` tu `cap_nhat-sau-gop-m1` vao `main`.
- Nhanh Moc 2: `m2-tap_co_phieu-duong_co_so`.
- Dau nhanh truoc thay doi truy vet cau hinh: `d49f8d032998ef22095ac13be763a5d539ea0415`.
- Python muc tieu: 3.12.
- Cong cu moi truong: `uv`.
- GitHub la nguon su that ve nhanh, commit, PR va CI.

## Moc 0

Trang thai: **da hoan thanh, da kiem tra va da gop vao main**.

- PR so 1: da gop.
- Commit trien khai chinh: `3385e401532e51457b9e9360e17df7af0e021881`.
- Commit hop nhat: `b132578b763ead96ad172a1ace68acdff6e36007`.

## Bo tai lieu dieu phoi

Trang thai: **da gop vao main**.

- PR so 2: da gop.
- Commit hop nhat: `4eba2a77d5864027c84d4350769d95fd4abd5fee`.

## Moc 1 — Du lieu

Trang thai dieu phoi: **da dong hoan toan**.

- PR so 3 da gop; merge commit `e94d4a340ac734bfabc14f340626c408af33645f`.
- PR so 4 da gop; merge commit va dau `main` khi mo Moc 2 la `97399e291b0d3d237f247f58ffa03049826d40bd`.
- CI dong Moc 1: run so 44, ID `30111176831`; job `kiem_tra` ID `89540796877`; ket luan `success`.

## Moc 2 — Tap co phieu va duong co so

Trang thai: **da mo; PR so 5 dang draft**.

- Doan chuyen mon phu trach: `02 Tap co phieu va duong co so`.
- Phan quyet doan 00: **YEU CAU THAY DOI — GIU DRAFT**.
- Loi toan ven san pham CLI da duoc sua va CI truoc do da dat.
- Ho tro `--so_nen` da duoc them, mac dinh cong khai 400, van khoa `vnstock==4.0.4`.
- Khong mo Moc 3 va khong tu gop PR.

### Xac minh that FPT, HPG va MBB

Lan chay Moc 1: `20260724T190515274806Z_6cd15c6d`.

- Moi ma co 287 phien, tu 2025-06-02 den 2026-07-23.
- Moi ma co 38 dong MA250.
- MA250 cuoi: FPT `87.70488`, HPG `24.16668`, MBB `24.61656`.
- Dong luong 20 phien cuoi: FPT `-0.08873239436619718`, HPG `-0.11111111111111105`, MBB `-0.07157894736842108`.
- Trang thai thanh khoan co gia tri, khong co loi, tong dau ra 861 dong.
- Python cuc bo: `3.12.10`.
- Canh bao khoang trong 2026-02-13 den 2026-02-23 xuat hien dong thoi o ca ba ma; quy trinh khong tu dien du lieu va canh bao khong chan nghiem thu ky thuat.

### Loi truy vet cau hinh con lai

- `tong_hop.json` cua lan chay tren chua co `so_nen_yeu_cau`, trong khi stdout co gia tri 400 do CLI chen sau khi quy trinh da cong bo san pham.
- Ban sua dat cau hinh lan chay tai mo hinh ket qua va lop quy trinh, de `tong_hop.json` va stdout cung dung mot nguon noi dung.
- Khong doc roi ghi de `tong_hop.json`; kho luu tru bat bien van tu choi san pham da ton tai.
- PR chi con cho ban sua truy vet cau hinh duoc day va GitHub Actions cuoi tren dau nhanh/merge ref moi.

### Gioi han du lieu thanh vien

- Giao dien chong nhin truoc da co.
- Xac minh gia va chi bao that da dat, nhung nguon lich su thanh vien that van chua duoc phe duyet.
- Chua tuyen bo da loai bo thien lech song sot bang du lieu thanh vien thuc te.

## Pham vi bi khoa

- Khong mo phong giao dich, khop lenh, phi, thue, truot gia hoac backtest.
- Khong hoc may, LightGBM, nhan, chia von, toi uu danh muc hoac gioi han ty trong.
- Khong tai toan bo VN100.
- Khong commit du lieu thi truong that, danh sach thanh vien bi han che, nhat ky that hoac khoa.
