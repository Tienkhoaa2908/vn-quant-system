# Ket qua xac minh du lieu that Moc 3

Ngay xac minh: 2026-07-25

## Muc dich

Lan chay nay chi xac minh ky thuat engine mo phong giao dich va backtest Moc 3 tren du lieu thi truong that da co trong moi truong cuc bo. Ket qua khong phai bang chung ve hieu qua dau tu, khong phai danh gia chien luoc va khong duoc dung de suy dien kha nang sinh loi.

Khong co du lieu dau vao, san pham backtest hay log that nao duoc dua vao repository.

## Dinh danh va nguon

- Ma lan chay: `xac_minh_fpt_hpg_mbb_20260725T074736Z`.
- Nguon du lieu Moc 1: `20260724T190515274806Z_6cd15c6d`.
- Ma: FPT, HPG, MBB.
- So phien: 287 phien moi ma.
- Tong so dong sau khi ghep gia Moc 1 voi trang thai Moc 2: 861.

## Moi truong

- Python: `3.12.10`.
- uv: `0.11.32`.
- Git head: `74d50ca68381338d44d18c1bb16b55fe0ff1245a`.

## Cau hinh ky thuat

- `von_ban_dau`: `1000000` nghin dong.
- `phi_mua_bps`: `15`.
- `phi_ban_bps`: `15`.
- `thue_ban_bps`: `10`.
- `truot_gia_bps`: `10`.
- `kich_thuoc_lo`: `100`.
- `don_vi_gia`: `nghin_dong`.
- `don_vi_tien`: `nghin_dong`.
- `co_so_gia`: `khong_dieu_chinh`.
- Khong truyen corporate actions.

## Kich ban kiem tra

- FPT: 30%.
- HPG: 30%.
- MBB: 30%.
- Tien mat muc tieu: 10%.
- Tin hieu mua: 2025-06-27.
- Khop mua: 2025-06-30.
- Tin hieu ban: 2026-07-22.
- Khop ban: 2026-07-23.

Ty trong 30% moi ma chi la kich ban kiem tra engine. Lan chay nay khong su dung baseline MA250-dong-luong.

## Ket qua engine

- 287 dong NAV.
- 287 dong so cai.
- 6 lenh duoc tao.
- 6 lenh duoc khop.
- 0 lenh het han.
- 0 lenh bi tu choi.
- Dong het vi the FPT, HPG va MBB.
- Tien mat khong am.
- Chenh lech doi soat: `0.0000000`.
- Tao dung 9 san pham theo dac ta.
- SHA-256 trong manifest da duoc xac minh.
- Khong co canh bao.

## Chi so

| Chi so | Gia tri |
|---|---:|
| NAV dau | `1000000` |
| NAV cuoi | `953262.1635925` |
| Tong loi nhuan | `-0.0467378364075` |
| CAGR | `-0.04115714989183274` |
| Maximum drawdown | `-0.2277264317329378149930296782` |
| Sharpe | `-0.09901929867928617` |
| Turnover | `0.7985599774522802253095657015` |
| Realized P&L luy ke | `-43243.12500` |
| Phi mua | `1351.0572075` |
| Phi ban | `1286.192520` |
| Thue ban | `857.46168` |
| Chi phi truot gia | `1758.12500` |

## Gioi han va cach dien giai

- Day chi la xac minh ky thuat engine, khong phai bang chung hieu qua dau tu.
- Ty trong 30% moi ma la kich ban kiem tra, khong phai phan bo san xuat.
- Khong su dung baseline MA250-dong-luong cho lan chay nay.
- Snapshot membership chua phai lich su thanh vien that.
- Nguong thanh khoan chua phai cau hinh san xuat.
- Co so gia `khong_dieu_chinh` chua duoc nguon xac nhan doc lap.
- Khong co corporate actions that trong lan chay.
- Mau chi gom ba ma va mot khoang thoi gian.
- Khong duoc dien giai loi nhuan am hoac duong nhu danh gia chien luoc.
- Chua co ML, walk-forward, inverse volatility hoac gioi han nganh.

## Cua kiem soat

PR so 7 tiep tuc giu Draft. Khong gop, khong force-push va khong mo Moc 4. Moi du lieu dau vao, san pham backtest va log cua lan chay that phai tiep tuc nam ngoai repository.
