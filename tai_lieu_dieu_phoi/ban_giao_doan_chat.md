# Ban giao doan chat dieu phoi

Cap nhat: 2026-07-25

## Vai tro va nen

- Doan `00` la dau moi dieu phoi trung tam.
- Kho: `Tienkhoaa2908/vn-quant-system`.
- Nhanh chinh: `main`.
- Dau `main` sau Moc 2: `6e8d2ed49c2ef57e43c9f0f2249361b26b838b33`.
- Doan `02` da hoan thanh pham vi Moc 2.
- Nhanh dieu phoi hien tai: `cap_nhat-sau-gop-m2-va-dac-ta-m3`.

## Moc 2 da dong

PR so 5 da duoc nghiem thu, chuyen khoi draft va gop bang merge commit.

- PR: `#5 — M2: tap co phieu va duong co so`.
- Dau nhanh da duyet: `3fedf0c29d203b64a3853031b6ca19663de1215b`.
- Merge commit: `6e8d2ed49c2ef57e43c9f0f2249361b26b838b33`.
- Phuong thuc: merge commit; khong squash, khong rebase.
- PR: `closed`, `merged=true`.
- `main` trung khop merge commit.

## Cac sua doi Moc 2 da hoan thanh

- Sua tinh toan ven dau ra CLI Moc 2: khoa ca ba san pham, khong ghi de, rollback thanh cong mot phan va khong de bao cao loi canh san pham thanh cong.
- Them `--so_nen`, mac dinh cong khai 400, truyen thanh `count` cho Vnstock 4.0.4.
- Them canh bao ro khi duoi 250 hoac duoi 260 phien.
- Sua truy vet cau hinh: `ket_qua_lan_chay` tao noi dung tong hop duy nhat; quy trinh cong bo `tong_hop.json` mot lan; stdout dung cung noi dung.
- Khong doc roi ghi de san pham da cong bo; tinh bat bien duoc giu nguyen.

## Xac minh that chi bao

Lan chay `20260724T190515274806Z_6cd15c6d`; Python `3.12.10`.

| Ma | So phien | Khoang ngay | So dong MA250 | MA250 cuoi | Dong luong 20 cuoi |
|---|---:|---|---:|---:|---:|
| FPT | 287 | 2025-06-02 den 2026-07-23 | 38 | 87.70488 | -0.08873239436619718 |
| HPG | 287 | 2025-06-02 den 2026-07-23 | 38 | 24.16668 | -0.11111111111111105 |
| MBB | 287 | 2025-06-02 den 2026-07-23 | 38 | 24.61656 | -0.07157894736842108 |

- Thanh khoan co gia tri cho ca ba ma.
- Khong co loi.
- Tong dau ra 861 dong.
- Canh bao khoang trong 2026-02-13 den 2026-02-23 xuat hien dong thoi o ca ba ma, khong chan va khong bi tu dien.

## Xac minh truy vet cau hinh

Lan chay `20260724T194007268318Z_1ade6129`:

- stdout co `so_nen_yeu_cau == 400`;
- `tong_hop.json` co `so_nen_yeu_cau == 400`;
- `trang_thai_tung_ma` tren dia va stdout giong nhau;
- FPT, HPG va MBB deu `thanh_cong`;
- moi ma van co 287 phien;
- canh bao khoang trong van duoc giu va khong co du lieu tu dien.

## CI sau gop

- Workflow: `kiem_tra_tu_dong`.
- Run number: 84.
- Trigger: `push`.
- Branch: `main`.
- Commit: `6e8d2ed49c2ef57e43c9f0f2249361b26b838b33`.
- Status: `Success`.
- Job `kiem_tra`: thanh cong.
- Giao dien hien tong thoi gian 17 giay va job 13 giay.
- Co mot canh bao Node.js 20 deprecation khong chan ket qua.
- Run ID va job ID chua duoc ghi nhan vi khong hien trong anh va connector khong tra run `push` theo commit; khong duoc tu suy doan.

## Moc 3 — Dac ta dang cho phe duyet

Tai lieu de nghi:

`tai_lieu/dac_ta_moc_3.md`

Dac ta bao gom:

- ngu nghia tin hieu tai `T`, khop som nhat tai `T+1`;
- so cai tien mat, vi the, lenh va khop lenh;
- phi, thue ban, truot gia va lot size la cau hinh;
- long-only, khong short, khong margin;
- xu ly chia tach/co phieu thuong va co tuc tien mat;
- baseline mua-va-giu, can bang deu va MA250/dong luong;
- bao cao NAV, loi nhuan, drawdown, Sharpe, turnover va chi phi;
- dau ra bat bien, truy vet hash va commit;
- bo kiem thu ngoai tuyen va kich ban vang.

## Cua kiem soat tiep theo

- Chua tao nhanh chuyen mon Moc 3.
- Chua mo PR ma Moc 3.
- Chua them module backtest.
- Nguoi dung va doan 00 phai phe duyet dac ta truoc.
- PR dieu phoi sau Moc 2 phai duoc gop va CI tren `main` phai dat.
- Sau do moi chi dinh doan chuyen mon va tao nhanh Moc 3 tu dau `main` moi nhat.

## Gioi han bat buoc

- Nguon lich su thanh vien that van chua duoc phe duyet; khong tuyen bo da loai bo thien lech song sot bang du lieu thanh vien thuc te.
- Khong commit du lieu thi truong that, nhat ky that hoac khoa.
- Khong tich hop tai khoan SSI hoac API dat lenh.
- He thong cuoi cung chi sinh danh muc va lenh de xuat; nguoi dung tu dat lenh thu cong tren SSI.
