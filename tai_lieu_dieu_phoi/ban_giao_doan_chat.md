# Ban giao doan chat dieu phoi

Cap nhat: 2026-07-25

## Vai tro va nen

- Doan `00` la dau moi dieu phoi trung tam.
- Doan `03 Mo phong giao dich va backtest` phu trach Moc 3.
- Kho: `Tienkhoaa2908/vn-quant-system`.
- Nhanh chuyen mon: `m3-mo_phong-giao_dich`.
- Base da phe duyet: `f52e06ffd4dde26e8af9d6451ec1e64f5a61b35d`.
- Head va CI cuoi la du lieu dong, duoc ghi trong mo ta PR so 7.
- PR trien khai: so 7, `M3: mo phong giao dich va backtest`.
- PR phai giu draft; khong Ready, khong auto-merge, khong gop, khong force-push.

## Yeu cau sua cua doan 00 va ket qua

### Quyen co tuc tien mat

Engine khong con lay vi the tai ngay thanh toan. Tai `ngay_hieu_luc`, engine chot so luong duoc huong va luu nghia vu theo khoa su kien; tai `ngay_thanh_toan`, engine cong dung nghia vu da chot. Mua/ban sau ngay hieu_luc khong thay doi quyen. Duplicate event bi tu choi.

### Suc mua

Engine tach `so_luong_yeu_cau` va `so_luong` chap nhan. Ban chay truoc; sau ban, tung lenh mua duoc dinh co theo tien mat, gia khop open co slippage, phi mua va lot size. Khoi luong bi giam va ly do duoc ghi trong lenh/khop lenh. Day la pre-trade sizing, khong phai market partial fill.

### So cai

So cai da co realized/unrealized P&L, co tuc, slippage, phi mua, phi ban va thue ban. Gia von gom gia khop da co slippage, khong gom phi mua. Realized P&L tinh truoc phi ban va thue. Cuoi moi phien engine doi soat:

```text
NAV = von_dau + realized_luy_ke + unrealized + co_tuc_luy_ke
      - phi_mua_luy_ke - phi_ban_luy_ke - thue_ban_luy_ke
```

Slippage khong tru lan hai vi da nam trong gia khop.

### Eligibility

Mo/tang vi the chi khi membership va liquidity deu `True`; `False` va `None` deu bi tu choi. Giam/dong duoc phep, kem canh bao.

### Validation, bao mat va don vi

- `0 <= slippage_bps < 10000`; gia khop/gia tri giao dich duong; tien ban rong khong am.
- Lot size va so phien nam la integer thuc su, khong ep float/bool.
- `lam_sach_loi` dung chung cho stdout va bao cao loi.
- `don_vi_gia`/`don_vi_tien` bat buoc thong nhat (`dong/dong` hoac `nghin_dong/nghin_dong`) va duoc ghi trong config/report/manifest.

## Cau truc ma bo sung

- `khop_lenh.py`: pre-trade sizing, fill, phi/thue/slippage va realized P&L.
- `su_kien_doanh_nghiep.py`: chia tach, chot quyen va thanh toan co tuc.
- `engine.py`: dong ho, eligibility, so cai va doi soat NAV.
- `mo_hinh.py`: validation, don vi va cac truong audit.
- `bao_cao.py`: cot audit, so cai, don vi va quy uoc ke toan.

## Kiem thu

Bo Moc 3 co 60 test, gom 17 test hoi quy cu va 43 test moi tach theo quyen co tuc, suc mua, so cai/P&L, eligibility, bien chi phi, lam sach loi va don vi.

Toan repository co 121 test: 60 Moc 3 va 61 hoi quy Moc 0–2. CI Python 3.12 chay compile va unittest ngoai tuyen tren head va `refs/pull/7/merge`. Head, Run ID, Job ID va merge commit tam moi nhat duoc ghi trong mo ta PR.

## Du lieu that va cua kiem soat

Chua chay backtest FPT, HPG, MBB that sau vong sua. Chi sau khi doan 00 xac minh ma va CI moi, nguoi dung moi duoc chay xac minh that. Khong commit dau ra that.

Khong mo Moc 4; khong SSI, ML, inverse volatility san xuat, tran ma/nganh hay toi uu danh muc. Nguon lich su thanh vien that chua duoc phe duyet.
