# Ban giao doan chat dieu phoi

Cap nhat: 2026-07-25

## Vai tro va nen

- Doan `00` la dau moi dieu phoi trung tam.
- Doan `03 Mo phong giao dich va backtest` phu trach Moc 3.
- Kho: `Tienkhoaa2908/vn-quant-system`.
- Nhanh chuyen mon: `m3-mo_phong-giao_dich`.
- Base da phe duyet: `f52e06ffd4dde26e8af9d6451ec1e64f5a61b35d`.
- PR trien khai: so 7, `M3: mo phong giao dich va backtest`.
- PR phai giu Draft; khong Ready, khong auto-merge, khong gop, khong force-push.
- Khong commit tep nao duoi `du_lieu/`.
- Head va CI cuoi la du lieu dong, duoc ghi trong mo ta PR so 7.

## Ket qua sua ma

### Quyen co tuc tien mat

Engine chot so luong duoc huong tai `ngay_hieu_luc`, luu nghia vu theo khoa su kien va thanh toan dung nghia vu tai `ngay_thanh_toan`. Mua/ban sau ngay chot quyen khong thay doi quyen; su kien trung lap bi tu choi.

### Suc mua

Engine tach `so_luong_yeu_cau` va `so_luong` chap nhan. Ban chay truoc; sau ban, lenh mua duoc dinh co theo tien mat, gia khop open co slippage, phi mua va lot size. Khoi luong bi giam va ly do duoc ghi trong lenh/khop lenh. Day la pre-trade sizing, khong phai market partial fill.

### So cai

So cai co realized/unrealized P&L, co tuc, slippage, phi mua, phi ban va thue ban. Gia von gom gia khop da co slippage, khong gom phi mua. Realized P&L tinh truoc phi ban va thue. Cuoi moi phien engine doi soat:

```text
NAV = von_dau + realized_luy_ke + unrealized + co_tuc_luy_ke
      - phi_mua_luy_ke - phi_ban_luy_ke - thue_ban_luy_ke
```

Slippage khong tru lan hai vi da nam trong gia khop.

### Eligibility, validation, bao mat va don vi

- Mo/tang vi the chi khi membership va liquidity deu `True`; `False` va `None` deu bi tu choi.
- Giam/dong duoc phep, kem canh bao.
- `0 <= slippage_bps < 10000`; gia khop/gia tri giao dich duong; tien ban rong khong am.
- Lot size va so phien nam la integer thuc su, khong ep float/bool.
- `lam_sach_loi` dung chung cho stdout va bao cao loi.
- `don_vi_gia`/`don_vi_tien` bat buoc thong nhat va duoc ghi trong config/report/manifest.

## Kiem thu

- Moc 3 co 60 test: 17 test hoi quy cu va 43 test tach theo quyen co tuc, suc mua, so cai/P&L, eligibility, bien chi phi, lam sach loi va don vi.
- Toan repository co 121 test: 60 Moc 3 va 61 hoi quy Moc 0–2.
- CI Python 3.12 chay compile va unittest ngoai tuyen tren head va `refs/pull/7/merge`.

## Xac minh ky thuat tren du lieu that

- Ma lan chay: `xac_minh_fpt_hpg_mbb_20260725T074736Z`.
- Nguon Moc 1: `20260724T190515274806Z_6cd15c6d`.
- FPT, HPG va MBB; 287 phien moi ma; 861 dong sau khi ghep voi trang thai Moc 2.
- Moi truong: Python `3.12.10`, uv `0.11.32`, Git head xac minh `74d50ca68381338d44d18c1bb16b55fe0ff1245a`.
- Cau hinh: von `1000000` nghin dong; phi mua/ban 15 bps; thue ban 10 bps; slippage 10 bps; lot 100; don vi `nghin_dong/nghin_dong`; co so gia `khong_dieu_chinh`; khong truyen corporate actions.
- Kich ban: FPT/HPG/MBB moi ma 30%, giu 10% tien mat; mua 2025-06-30; dong het 2026-07-23.
- Ket qua: 287 dong NAV, 287 dong so cai, 6 lenh tao/6 lenh khop, 0 het han, 0 tu choi, tien mat khong am, doi soat `0.0000000`, 9 san pham dung dac ta, SHA-256 manifest dat, khong canh bao.
- NAV cuoi `953262.1635925`; tong loi nhuan `-0.0467378364075`; CAGR `-0.04115714989183274`; maximum drawdown `-0.2277264317329378149930296782`; Sharpe `-0.09901929867928617`; turnover `0.7985599774522802253095657015`.

Chi tiet day du: `tai_lieu/ket_qua_xac_minh_that_moc_3.md`.

## Gioi han bat buoc

- Day chi la xac minh ky thuat engine, khong phai bang chung hieu qua dau tu.
- Ty trong 30% moi ma la kich ban kiem tra; khong su dung baseline MA250-dong-luong.
- Snapshot membership chua phai lich su thanh vien that.
- Nguong thanh khoan chua phai cau hinh san xuat.
- Co so gia `khong_dieu_chinh` chua duoc nguon xac nhan doc lap.
- Khong co corporate actions that.
- Chi co ba ma va mot khoang thoi gian.
- Khong dien giai loi nhuan am hoac duong nhu danh gia chien luoc.
- Chua co ML, walk-forward, inverse volatility hoac gioi han nganh.

## Cua kiem soat cuoi

Doan 00 can xac minh diff khong co tep duoi `du_lieu/`, toan bo 121 test, CI tren head moi va checkout `refs/pull/7/merge`. PR so 7 tiep tuc Draft; khong Ready, khong gop va khong mo Moc 4.
