# Cong viec hien tai

Cap nhat: 2026-07-25

## Doan phu trach

Doan `00 Dieu phoi trung tam` dang phu trach dong Moc 2 ve mat dieu phoi va trinh dac ta Moc 3 de phe duyet.

Doan `02 Tap co phieu va duong co so` da hoan thanh pham vi chuyen mon cua Moc 2. Khong con nhiem vu ma tren nhanh cu.

## Trang thai Moc 2

- PR: `#5 — M2: tap co phieu va duong co so`.
- Nhanh: `m2-tap_co_phieu-duong_co_so`.
- PR da gop bang merge commit.
- Merge commit: `6e8d2ed49c2ef57e43c9f0f2249361b26b838b33`.
- `main` hien tai trung khop merge commit.
- GitHub Actions sau gop: run so 84, `push` vao `main`, trang thai `Success`.
- Job `kiem_tra` thanh cong.
- Moc 2 da dong hoan toan.

## Bang chung nghiem thu Moc 2

1. Tap co phieu theo thoi diem va quy tac ngan nhin truoc da co.
2. Thanh khoan, MA250 va dong luong da co.
3. Tinh toan ven san pham CLI da duoc sua.
4. Adapter va CLI ho tro `--so_nen`, mac dinh ro rang 400, truyen dung `count` va van dung Vnstock 4.0.4.
5. `so_nen_yeu_cau` duoc dua vao cau hinh lan chay truoc khi cong bo `tong_hop.json`.
6. `tong_hop.json` va stdout dung cung mot mo hinh ket qua; khong doc lai va ghi de tep da cong bo.
7. Hoi quy truy vet va tinh bat bien da dat.
8. FPT, HPG va MBB moi ma co 287 phien va 38 dong MA250.
9. CI Python 3.12 da dat truoc va sau gop.
10. Khong co du lieu that duoi `du_lieu/` trong PR.

## Cong viec dang mo

Nhanh dieu phoi:

`cap_nhat-sau-gop-m2-va-dac-ta-m3`

Pham vi nhanh nay chi gom:

- cap nhat bon tai lieu dieu phoi sau khi Moc 2 duoc gop;
- tao `tai_lieu/dac_ta_moc_3.md`;
- mo PR dieu phoi de doan 00 va nguoi dung ra soat;
- khong them ma nguon backtest;
- khong tao nhanh chuyen mon Moc 3.

## Cua kiem soat de mo Moc 3

Chi duoc mo trien khai Moc 3 khi tat ca dieu kien sau dat:

1. dac ta Moc 3 duoc nguoi dung va doan 00 phe duyet;
2. PR dieu phoi sau gop Moc 2 duoc gop vao `main`;
3. CI tren `main` sau PR dieu phoi thanh cong;
4. doan 00 chi dinh doan chuyen mon phu trach;
5. nhanh Moc 3 duoc tao tu dung dau `main` da xac minh.

## Nguyen tac bat buoc

- Khong commit `du_lieu/` hoac log that.
- Khong dung danh sach thanh vien hien tai cho toan bo lich su.
- Khong tu dien quan sat thieu.
- Nguon lich su thanh vien that chua duoc phe duyet; khong tuyen bo da loai bo thien lech song sot thuc te.
- Khong force-push.
- Khong trien khai ma Moc 3 trong PR dieu phoi.
- Khong tich hop SSI FastConnect; he thong chi sinh ket qua phan tich va lenh de xuat de nguoi dung dat lenh thu cong.
