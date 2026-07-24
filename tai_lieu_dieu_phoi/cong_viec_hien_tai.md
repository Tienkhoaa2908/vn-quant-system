# Cong viec hien tai

Cap nhat: 2026-07-25

## Doan phu trach

`02 Tap co phieu va duong co so` dang phu trach chuyen mon Moc 2 duoi dieu phoi cua doan `00 Dieu phoi trung tam`.

## Trang thai PR so 5

- PR: `#5 — M2: tap co phieu va duong co so`.
- Nhanh: `m2-tap_co_phieu-duong_co_so`.
- Dau nhanh truoc sua truy vet: `d49f8d032998ef22095ac13be763a5d539ea0415`.
- Phan quyet: **YEU CAU THAY DOI — GIU DRAFT**.
- PR khong duoc gop, khong duoc chuyen ready va khong mo Moc 3.

## Phan da dat

1. Tap co phieu theo thoi diem, thanh khoan, MA250 va dong luong khong nhin truoc da co.
2. Tinh toan ven san pham CLI da duoc sua.
3. Adapter va CLI da ho tro `--so_nen`, mac dinh ro rang 400, truyen dung `count` va van dung Vnstock 4.0.4.
4. CI gan nhat truoc sua truy vet: run 71, ID `30118752282`, job `kiem_tra` ID `89565826727`, ket luan `success`.

## Xac minh that da dat

Lan chay `20260724T190515274806Z_6cd15c6d` tren Python `3.12.10`:

- FPT, HPG, MBB moi ma 287 phien, tu 2025-06-02 den 2026-07-23;
- moi ma 38 dong MA250;
- MA250 cuoi: FPT `87.70488`, HPG `24.16668`, MBB `24.61656`;
- dong luong 20 phien cuoi: FPT `-0.08873239436619718`, HPG `-0.11111111111111105`, MBB `-0.07157894736842108`;
- thanh khoan co gia tri, khong co loi, tong 861 dong dau ra;
- canh bao khoang trong 2026-02-13 den 2026-02-23 xuat hien o ca ba ma, khong chan va khong duoc tu dien.

## Cong viec con lai trong PR

1. Dua `so_nen_yeu_cau` vao cau hinh lan chay tai lop quy trinh/mo hinh ket qua.
2. Dung cung doi tuong ket qua de tao `tong_hop.json` bat bien va JSON in stdout.
3. Khong doc lai va ghi de tep tong hop sau cong bo.
4. Hoi quy voi `so_nen=400`: tren dia va stdout cung gia tri, trang thai tung ma khong doi, ghi lai bi tu choi.
5. Cap nhat tai lieu va chay GitHub Actions tren dau nhanh cung merge ref moi.

Sau cac buoc nay, PR van giu draft de bao cao lai doan 00. Khong con yeu cau tai them du lieu de nghiem thu ky thuat M2.

## Nguyen tac bat buoc

- Khong commit `du_lieu/` hoac log that.
- Khong dung danh sach thanh vien hien tai cho toan bo lich su.
- Khong tu dien quan sat thieu.
- Nguon lich su thanh vien that chua duoc phe duyet; khong tuyen bo da loai bo thien lech song sot thuc te.
- Khong force-push, khong tu gop va khong mo Moc 3.
