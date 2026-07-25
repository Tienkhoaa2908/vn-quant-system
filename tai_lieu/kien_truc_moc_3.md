# Kien truc Moc 3 — Mo phong giao dich va backtest

## Pham vi

Moc 3 bien ty trong muc tieu thanh lenh DAY, khop lenh gia lap, tien mat, vi the, so cai, NAV va chi so. Day la lop nghien cuu long-only; khong ket noi SSI, khong doc tai khoan, khong gui lenh, khong hoc may va khong phai lop chia von san xuat.

## Dong ho mo phong

1. Corporate actions cua ngay duoc xu ly truoc giao dich va dinh gia.
2. Lenh tu tin hieu sau close `T` chi khop tai open cua dung phien thi truong ke tiep.
3. Thieu bar hoac thieu open tai ngay thuc thi lam lenh DAY het han; khong tim phien xa hon va khong thay open bang close.
4. Lenh ban chay truoc lenh mua; trong moi chieu sap xep ma va ma lenh tang dan.
5. Vi the duoc dinh gia bang close cua chinh ngay; khong forward-fill.
6. Sau close, engine tao nhu cau tai can bang cho phien ke tiep.

## Phan bo suc mua

Nhu cau muc tieu va khoi luong co the thuc thi la hai dai luong rieng:

```text
gia_tri_muc_tieu = NAV_tham_chieu * ty_trong_muc_tieu
so_luong_yeu_cau = lam_tron_lo(gia_tri_muc_tieu / close_T - so_luong_hien_tai)
chi_phi_moi_co_phieu = gia_khop_mua * (1 + phi_mua_bps / 10000)
so_luong_toi_da = lam_tron_lo(tien_mat_kha_dung / chi_phi_moi_co_phieu)
so_luong_chap_nhan = min(so_luong_yeu_cau, so_luong_toi_da)
```

Engine ban truoc, cap nhat tien mat sau ban, sau do dinh co tung lenh mua theo thu tu xac dinh. Giam khoi luong truoc khi khop la pre-trade sizing, khong phai market partial fill. `lenh.csv` va `khop_lenh.csv` ghi `so_luong_yeu_cau`, `so_luong`, `so_luong_bi_giam` va `ly_do_giam`.

## Eligibility fail closed

Mo hoac tang vi the chi duoc phep khi dong tin hieu thoa dong thoi:

```text
thuoc_tap_co_phieu is True
dat_thanh_khoan is True
```

`False` va `None` deu bi tu choi. Giam hoac dong vi the van duoc phep de quan tri rui ro, nhung bao cao ghi canh bao voi trang thai membership va liquidity.

## Corporate actions

### Chia tach va co phieu thuong

Tai `ngay_hieu_luc`, so luong vi the va lenh cho duoc nhan `ty_le`; gia von binh quan duoc chia cho cung he so. Moi su kien chi duoc ap dung mot lan.

### Co tuc tien mat

Co tuc bat buoc co `ngay_hieu_luc`, `ngay_thanh_toan`, `gia_tri_tien_mat` va `nguon`.

- Tai `ngay_hieu_luc`, engine chot so luong duoc huong va luu nghia vu theo khoa su kien.
- Giao dich sau ngay chot quyen khong thay doi nghia vu.
- Tai `ngay_thanh_toan`, engine cong dung so tien da chot.
- Mua sau ngay hieu luc khong duoc huong; ban truoc thanh toan van duoc nhan.
- Su kien trung lap bi tu choi; gia dieu chinh kem corporate actions bi tu choi de tranh tinh hai lan.

## Quy uoc ke toan

- Gia von binh quan gom gia khop, nen da phan anh slippage; khong gom phi mua.
- Realized P&L khi ban mot phan hoac toan bo: `(gia_khop_ban - gia_von_binh_quan) * so_luong_ban`, truoc phi ban va thue.
- Phan vi the con lai giu nguyen gia von binh quan; khi dong het, gia von ve 0.
- Unrealized P&L: `(close - gia_von_binh_quan) * so_luong_con_lai`.
- Phi mua, phi ban, thue ban, co tuc va slippage duoc cong bo rieng.
- Slippage khong bi tru lan hai trong doi soat vi da nam trong gia khop.

Phuong trinh doi soat cuoi moi phien:

```text
NAV
= von_ban_dau
+ lai_lo_da_thuc_hien_luy_ke
+ lai_lo_chua_thuc_hien
+ co_tuc_tien_mat_luy_ke
- phi_mua_luy_ke
- phi_ban_luy_ke
- thue_ban_luy_ke
```

`chenh_lech_doi_soat` phai bang 0 trong sai so tien mat da dinh nghia.

## Bien chi phi va bat bien

- `0 <= truot_gia_bps < 10000`.
- Gia khop mua va ban phai duong.
- `phi_ban_bps + thue_ban_bps <= 10000`; tien ban rong khong am.
- Gia tri giao dich khong duoc am.
- `kich_thuoc_lo` va `so_phien_moi_nam` phai la so nguyen thuc su va duong; float va bool bi tu choi.
- Khong short, margin, tien mat am, ban vuot vi the hoac vi the am.

## Don vi

Cau hinh bat buoc co:

```json
{
  "don_vi_gia": "nghin_dong",
  "don_vi_tien": "nghin_dong"
}
```

Gia va tien phai dung cung don vi (`dong/dong` hoac `nghin_dong/nghin_dong`). Quan he la `gia_tri = gia * so_luong`. Cau hinh tron nghin dong voi dong bi tu choi. Hop dong don vi duoc luu trong `cau_hinh.json`, `bao_cao.json` va `manifest.json`.

## Lam sach loi

Mot ham `lam_sach_loi` duoc dung chung cho `bao_cao_loi.json`, stdout va moi thong bao loi do CLI kiem soat. Mau token, secret, password, API key va Bearer credential bi thay bang `[DA_AN]`.

## Chi so

- Loi nhuan phien: `NAV_t / NAV_(t-1) - 1`.
- CAGR: `(NAV_cuoi/NAV_dau)^(so_phien_moi_nam/so_quan_sat)-1` khi du dieu kien.
- Maximum drawdown: `min(NAV_t/peak_t-1)`.
- Sharpe dung do lech chuan mau va lai phi rui ro quy doi theo phien; tra `null` khi thieu quan sat hoac phuong sai bang 0.
- Turnover: `(tong_mua+tong_ban)/(2*NAV_trung_binh)`.

## San pham

Lan chay thanh cong tao dung chin tep: `cau_hinh.json`, `lenh.csv`, `khop_lenh.csv`, `vi_the.csv`, `so_cai.csv`, `nav.csv`, `chi_so.json`, `bao_cao.json`, `manifest.json`.

San pham duoc tao trong thu muc tam, fsync va rename nguyen tu. Khong ghi de; rollback khi loi; thu muc thanh cong va that bai khong tron.

## Kiem thu va gioi han

Bo kiem thu Moc 3 tach rieng cac loi ve co tuc, suc mua, so cai, eligibility, bien chi phi, bao mat va don vi; dong thoi giu kich ban vang va hoi quy cu. CI hoan toan ngoai tuyen.

Chua chay backtest FPT, HPG, MBB that sau vong sua nay. Khong partial fill theo thanh khoan thi truong, participation rate, quyen mua, sap nhap, hoan doi hoac huy niem yet cuong buc. PR so 7 phai giu draft cho den khi doan 00 nghiem thu.
