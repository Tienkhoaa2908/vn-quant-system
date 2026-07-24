# Ket qua xac minh truy vet cau hinh Moc 2

Cap nhat: 2026-07-25

## Muc tieu

Xac nhan cau hinh `--so_nen 400` duoc luu ben vung trong san pham bat bien cua lan tai du lieu, dong thoi JSON in ra terminal va `tong_hop.json` dung cung mot noi dung cau hinh va trang thai tung ma.

## Moi truong va lenh

- Nhanh: `m2-tap_co_phieu-duong_co_so`.
- Dau nhanh truoc lan chay: `5e5a2c143805805b4af9b6b099ec5262d2c4006d`.
- Vnstock: `4.0.4`; thong bao co phien ban `4.0.5` khong lam thay doi phien ban dang chay.
- Lenh dung `--so_nen 400`, ba ma FPT, HPG, MBB, khoang 2025-06-01 den 2026-07-24.
- Du lieu va log that nam duoi `du_lieu/`, khong commit.

## Lan chay xac minh truy vet

Ma lan chay:

```text
20260724T194007268318Z_1ade6129
```

San pham tong hop:

```text
du_lieu/nhat_ky/20260724T194007268318Z_1ade6129/tong_hop.json
```

Ket qua doi chieu:

```json
{
  "so_nen_yeu_cau_stdout": 400,
  "so_nen_yeu_cau_tren_dia": 400,
  "trang_thai": {
    "FPT": "thanh_cong",
    "HPG": "thanh_cong",
    "MBB": "thanh_cong"
  }
}
```

Cac khang dinh da dat:

- stdout co `so_nen_yeu_cau == 400`;
- `tong_hop.json` co `so_nen_yeu_cau == 400`;
- `trang_thai_tung_ma` tren dia va stdout giong nhau;
- ca ba ma thanh cong;
- moi ma co 287 phien, tu 2025-06-02 den 2026-07-23;
- canh bao khoang trong 2026-02-13 den 2026-02-23 duoc giu nguyen va quy trinh khong tu dien du lieu;
- san pham cu khong bi sua.

## Ket qua Moc 2 tren du lieu that

Lan chay tham chieu `20260724T190515274806Z_6cd15c6d` tren Python `3.12.10` da cho:

| Ma | So phien | So dong MA250 | MA250 cuoi | Dong luong 20 cuoi |
|---|---:|---:|---:|---:|
| FPT | 287 | 38 | 87.70488 | -0.08873239436619718 |
| HPG | 287 | 38 | 24.16668 | -0.11111111111111105 |
| MBB | 287 | 38 | 24.61656 | -0.07157894736842108 |

Thanh khoan co gia tri, khong co loi va tong dau ra la 861 dong.

## Ket luan

Loi truy vet cau hinh da duoc xac minh la da sua tren du lieu that. Cau hinh so nen duoc cong bo cung luc voi `tong_hop.json`, khong co buoc doc roi ghi de san pham. Xac minh gia va chi bao that da dat.

Nguon lich su thanh vien that van chua duoc phe duyet; ket qua nay khong duoc dung de tuyen bo da loai bo thien lech song sot bang du lieu thanh vien thuc te. PR so 5 tiep tuc giu draft, khong gop va khong mo Moc 3 cho den khi doan 00 ra phan quyet.
