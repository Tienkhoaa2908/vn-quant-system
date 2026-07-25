# Trang thai du an

Cap nhat gan nhat: 2026-07-25

## Kho ma nguon

- Kho: `Tienkhoaa2908/vn-quant-system`.
- Nhanh chinh: `main`.
- Base Moc 3: `f52e06ffd4dde26e8af9d6451ec1e64f5a61b35d`.
- Nhanh chuyen mon: `m3-mo_phong-giao_dich`.
- Python muc tieu: 3.12; cong cu moi truong: `uv`.
- GitHub la nguon su that ve nhanh, commit, PR va CI.

## Moc 0–Moc 2

Trang thai: **da dong hoan toan**.

- PR Moc 2 so 5 gop bang merge commit `6e8d2ed49c2ef57e43c9f0f2249361b26b838b33`.
- FPT, HPG, MBB da duoc xac minh Moc 2: moi ma 287 phien va 38 dong MA250.
- Nguon lich su thanh vien that van chua duoc phe duyet.

## Moc 3 — Mo phong giao dich va backtest

Trang thai: **PR so 7 dang draft; da sua theo vong ra soat cua doan 00; chua duoc Ready hoac gop**.

Da hoan thanh vong sua:

- co tuc tien mat chot quyen tai `ngay_hieu_luc`, luu nghia vu va tra tai `ngay_thanh_toan`;
- giao dich sau ngay chot quyen khong thay doi so luong duoc huong;
- ban truoc, sau do dinh co lenh mua theo tien mat sau ban, gia khop, phi, slippage va lot;
- lenh va khop lenh ghi khoi luong yeu cau, chap nhan, bi giam va ly do;
- so cai ghi realized/unrealized P&L, co tuc, slippage, phi mua/ban va thue ban;
- doi soat NAV theo quy uoc gia von da chot trong `DECISIONS.md`;
- eligibility fail closed cho mo/tang vi the; giam/dong duoc phep kem canh bao;
- validation nghiem ngat cho slippage, phi/thue, gia tri giao dich va tham so nguyen;
- stdout va bao cao loi dung chung co che lam sach credential;
- hop dong `don_vi_gia`/`don_vi_tien` bat buoc va truy vet trong ba san pham JSON;
- bo test Moc 3 tang tu 17 len 60 test tach rieng theo loi nghiep vu.

Bang chung kiem thu:

- Tong 121 test: 60 Moc 3 va 61 hoi quy Moc 0–2.
- CI Python 3.12 chay compile va unittest ngoai tuyen tren head va `refs/pull/7/merge`.
- Head, Run ID, Job ID va merge commit tam moi nhat la du lieu dong, duoc ghi trong mo ta PR so 7 de khong tao commit tai lieu lam cu bang chung.

## Chua hoan thanh

- Chua chay backtest FPT, HPG, MBB that sau vong sua nay.
- Chua co phan quyet nghiem thu moi cua doan 00.
- Chua chuyen PR Ready va chua gop.

## Pham vi van bi khoa

- Khong mo Moc 4.
- Khong Logistic Regression, LightGBM, walk-forward ML, inverse volatility san xuat, tran 15% moi ma hay 25% moi nganh.
- Khong commit du lieu thi truong that, log that, danh sach thanh vien bi han che, khoa hoac token.
- Khong tich hop SSI, khong doc tai khoan va khong gui lenh.
