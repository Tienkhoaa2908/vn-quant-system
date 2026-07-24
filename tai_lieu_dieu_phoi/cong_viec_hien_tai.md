# Cong viec hien tai

Cap nhat: 2026-07-25

## Doan phu trach

`02 Tap co phieu va duong co so` dang phu trach PR so 5 cua Moc 2 duoi dieu phoi cua doan `00 Dieu phoi trung tam`.

## Trang thai PR so 5

- PR: `#5 — M2: tap co phieu va duong co so`.
- Nhanh: `m2-tap_co_phieu-duong_co_so`.
- Phan quyet hien tai: **YEU CAU THAY DOI — GIU DRAFT**.
- Khong duoc gop, khong chuyen ready va khong mo Moc 3 neu chua co phan quyet moi cua doan 00.

## Phan da dat

1. Tap co phieu theo thoi diem va quy tac ngan nhin truoc da co.
2. Thanh khoan, MA250 va dong luong da co.
3. Tinh toan ven san pham CLI da duoc sua.
4. Adapter va CLI ho tro `--so_nen`, mac dinh ro rang 400, truyen dung `count` va van dung Vnstock 4.0.4.
5. `so_nen_yeu_cau` duoc dua vao cau hinh lan chay truoc khi cong bo `tong_hop.json`.
6. `tong_hop.json` va stdout dung cung mot mo hinh ket qua; khong doc lai va ghi de tep da cong bo.
7. Hoi quy truy vet va tinh bat bien da dat.
8. GitHub Actions run 75, ID `30120599648`, job `89571991558` da `success` tren merge ref `7b68c7a09d5ae2cdcdf7592224482ea485d71433`.

## Xac minh that da dat

Lan chay chi bao `20260724T190515274806Z_6cd15c6d` tren Python `3.12.10`:

- FPT, HPG, MBB moi ma 287 phien, tu 2025-06-02 den 2026-07-23;
- moi ma 38 dong MA250;
- MA250 cuoi: FPT `87.70488`, HPG `24.16668`, MBB `24.61656`;
- dong luong 20 phien cuoi: FPT `-0.08873239436619718`, HPG `-0.11111111111111105`, MBB `-0.07157894736842108`;
- thanh khoan co gia tri, khong co loi, tong 861 dong dau ra;
- canh bao khoang trong 2026-02-13 den 2026-02-23 xuat hien o ca ba ma, khong chan va khong duoc tu dien.

Lan chay truy vet `20260724T194007268318Z_1ade6129`:

- stdout co `so_nen_yeu_cau == 400`;
- `tong_hop.json` co `so_nen_yeu_cau == 400`;
- `trang_thai_tung_ma` tren dia va stdout giong nhau;
- ca ba ma deu thanh cong va moi ma co 287 phien.

## Cong viec con lai

Khong con loi ma hoac buoc tai du lieu bat buoc trong pham vi PR so 5. Cong viec con lai la:

1. ghi nhan ket qua xac minh truy vet trong tai lieu va mo ta PR;
2. cho CI cua commit tai lieu cuoi;
3. gui bao cao lai doan 00;
4. cho phan quyet co chuyen PR khoi draft hay khong.

## Nguyen tac bat buoc

- Khong commit `du_lieu/` hoac log that.
- Khong dung danh sach thanh vien hien tai cho toan bo lich su.
- Khong tu dien quan sat thieu.
- Nguon lich su thanh vien that chua duoc phe duyet; khong tuyen bo da loai bo thien lech song sot thuc te.
- Khong force-push, khong tu gop va khong mo Moc 3.
