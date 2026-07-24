# Ban giao doan chat dieu phoi

Cap nhat: 2026-07-25

## Vai tro va nen

- Doan `00` la dau moi dieu phoi trung tam.
- Doan `02` phu trach PR so 5 cua Moc 2.
- Kho: `Tienkhoaa2908/vn-quant-system`.
- Nhanh: `m2-tap_co_phieu-duong_co_so`.
- Dau `main` khi mo Moc 2: `97399e291b0d3d237f247f58ffa03049826d40bd`.
- Dau nhanh truoc sua truy vet: `d49f8d032998ef22095ac13be763a5d539ea0415`.
- PR phai giu draft, khong gop va khong mo Moc 3.

## Xac minh that da hoan thanh

Lan chay Moc 1: `20260724T190515274806Z_6cd15c6d`; Python `3.12.10`.

| Ma | So phien | Khoang ngay | So dong MA250 | MA250 cuoi | Dong luong 20 cuoi |
|---|---:|---|---:|---:|---:|
| FPT | 287 | 2025-06-02 den 2026-07-23 | 38 | 87.70488 | -0.08873239436619718 |
| HPG | 287 | 2025-06-02 den 2026-07-23 | 38 | 24.16668 | -0.11111111111111105 |
| MBB | 287 | 2025-06-02 den 2026-07-23 | 38 | 24.61656 | -0.07157894736842108 |

- Thanh khoan co gia tri cho ca ba ma.
- Khong co loi.
- Tong dau ra 861 dong.
- Canh bao khoang trong 2026-02-13 den 2026-02-23 xuat hien dong thoi o ca ba ma, khong chan va khong bi tu dien.

## Loi truy vet cau hinh

`tong_hop.json` cua lan chay tren khong luu `so_nen_yeu_cau`, do CLI chi chen gia tri vao doi tuong stdout sau khi `chay_quy_trinh()` hoan tat.

Ban sua bat buoc:

- truyen cau hinh lan chay vao `chay_quy_trinh()`;
- mo hinh `ket_qua_lan_chay` tao noi dung tong hop duy nhat;
- dung noi dung do de cong bo `tong_hop.json` va tao stdout;
- khong doc/ghi de san pham da cong bo;
- hoi quy xac nhan `so_nen_yeu_cau == 400` tren dia va stdout, trang thai tung ma khong doi va tinh bat bien con nguyen.

## Trang thai ban giao

- Xac minh that FPT/HPG/MBB da dat.
- Giao dien chong nhin truoc da co.
- Nguon lich su thanh vien that van chua duoc phe duyet; khong tuyen bo da loai bo thien lech song sot bang du lieu that.
- PR chi con cho ban sua truy vet cau hinh va CI cuoi tren dau nhanh/merge ref moi.
- Sau CI, gui bao cao lai doan 00; khong tu gop PR.
