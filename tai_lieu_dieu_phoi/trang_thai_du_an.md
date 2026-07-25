# Trang thai du an

Cap nhat gan nhat: 2026-07-25

## Kho ma nguon

- Kho: `Tienkhoaa2908/vn-quant-system`.
- Nhanh chinh: `main`.
- Dau `main`: `f52e06ffd4dde26e8af9d6451ec1e64f5a61b35d` tai thoi diem mo Moc 3.
- Python muc tieu: 3.12; cong cu moi truong: `uv`.
- GitHub la nguon su that ve nhanh, commit, PR va CI.

## Moc 0–Moc 2

Trang thai: **da dong hoan toan**.

- Mốc 0: nen Python/uv, goi, kiem tra du lieu va CI.
- Mốc 1: du lieu OHLCV, luu tru bat bien, chat luong, SHA-256, Vnstock 4.0.4/KBS.
- Mốc 2: tap co phieu point-in-time, thanh khoan, MA250, dong luong va dau ra bat bien.
- PR số 5 gop bang merge commit `6e8d2ed49c2ef57e43c9f0f2249361b26b838b33`.
- FPT, HPG, MBB da duoc xac minh Mốc 2: moi ma 287 phien va 38 dong MA250.
- Nguon lich su thanh vien that van chua duoc phe duyet.

## Nen Mốc 3

- PR dieu phoi số 6 da gop bang merge commit `f52e06ffd4dde26e8af9d6451ec1e64f5a61b35d`.
- CI sau gop: run 86, Run ID `30123567224`, Job ID `89581624420`, thanh cong.
- Dac ta `tai_lieu/dac_ta_moc_3.md` va tam quyet dinh da duoc phe duyet.
- Nhanh chuyen mon `m3-mo_phong-giao_dich` duoc tao truc tiep tu base tren.
- Bon commit dieu phoi dau nhanh duoc giu nguyen; khong reset hoac sua lich su.

## Mốc 3 — Mo phong giao dich va backtest

Trang thai: **ma va kiem thu da trien khai; PR số 7 dang draft; chua duoc phep Ready hoac gop**.

Da hoan thanh tren nhanh:

- cap nhat workflow cho `main` va `m3-mo_phong-giao_dich`, giu `pull_request`;
- domain model cho cau hinh, ty trong, lenh, khop lenh, vi the, so cai va NAV;
- tin hieu T khop som nhat tai open phien ke tiep, lenh DAY, khong tu dien du lieu;
- phi mua/ban, thue ban, truot gia, lot size va thu tu ban-truoc/mua-sau xac dinh;
- bat bien long-only, khong margin, khong tien mat am, khong ban vuot vi the;
- corporate actions MVP va co che chong tinh hai lan;
- baseline mua-va-giu, can-bang-deu, MA250/dong-luong chi de kiem tra engine;
- chi so loi nhuan, CAGR, maximum drawdown, Sharpe, turnover va chi phi;
- CLI, chin san pham bat bien, manifest SHA-256, cong bo nguyen tu va rollback;
- tai lieu kien truc, DECISIONS, README va bo kiem thu ngoai tuyen.

Bang chung hien tai:

- PR: số 7, `M3: mo phong giao dich va backtest`, draft.
- CI da thanh cong tren cac head trien khai; head cuoi can duoc ghi lai sau commit tai lieu ban giao.
- Kiem thu Mốc 3 trong kho gom 17 phuong thuc nhom, bao phu 33 kich ban bat buoc; CI dong thoi chay toan bo hoi quy Mốc 0–2.

Chua hoan thanh:

- chua chay xac minh backtest du lieu that FPT, HPG, MBB trong moi truong connector hien tai;
- chua co phan quyet nghiem thu cua doan 00;
- chua chuyen PR Ready va chua gop.

## Pham vi van bi khoa

- Khong mo Mốc 4.
- Khong Logistic Regression, LightGBM, walk-forward ML hay feature store mo rong.
- Khong inverse volatility san xuat, tran 15% moi ma hay 25% moi nganh.
- Khong commit du lieu thi truong that, log that, danh sach thanh vien bi han che, khoa hoac token.
- Khong tich hop SSI, khong doc tai khoan va khong gui lenh.
