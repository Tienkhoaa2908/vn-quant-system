# Ban giao doan chat dieu phoi

Cap nhat: 2026-07-25

## Vai tro va nen

- Doan `00` la dau moi dieu phoi trung tam.
- Doan `02` phu trach PR so 5 cua Moc 2.
- Kho: `Tienkhoaa2908/vn-quant-system`.
- Nhanh: `m2-tap_co_phieu-duong_co_so`.
- Dau `main` khi mo Moc 2: `97399e291b0d3d237f247f58ffa03049826d40bd`.
- PR phai giu draft, khong gop va khong mo Moc 3 cho den khi doan 00 ra phan quyet moi.

## Cac sua doi da hoan thanh

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

Lan chay moi: `20260724T194007268318Z_1ade6129`.

San pham:

```text
du_lieu/nhat_ky/20260724T194007268318Z_1ade6129/tong_hop.json
```

Ket qua:

- stdout co `so_nen_yeu_cau == 400`;
- `tong_hop.json` co `so_nen_yeu_cau == 400`;
- `trang_thai_tung_ma` tren dia va stdout giong nhau;
- FPT, HPG va MBB deu `thanh_cong`;
- moi ma van co 287 phien;
- canh bao khoang trong van duoc giu va khong co du lieu tu dien.

## Ma, kiem thu va CI

- Commit sua truy vet: `aee04c81067e51db36492ced7d891e184f10f8ef`.
- Hoi quy hien tai co 61 kiem thu; toan bo kiem thu cu va hoi quy truy vet deu dat.
- GitHub Actions da dat tren dau nhanh va merge ref sau cac thay doi ma va tai lieu.
- Bang chung dau nhanh, merge ref, run number, run ID, job ID va tung buoc nam trong mo ta PR so 5 va bao cao gui doan 00.

## Gioi han va phan quyet

- Xac minh gia va chi bao that da dat.
- Giao dien chong nhin truoc da co.
- Nguon lich su thanh vien that van chua duoc phe duyet; khong tuyen bo da loai bo thien lech song sot bang du lieu thanh vien thuc te.
- Khong con loi ma, loi truy vet, buoc tai du lieu hoac kiem thu bat buoc trong pham vi PR so 5.
- PR tiep tuc giu draft.
- Khong tu gop PR va khong mo Moc 3.
- Gui bao cao chot ve doan 00 de xin phan quyet.
