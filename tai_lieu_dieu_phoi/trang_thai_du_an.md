# Trang thai du an

Cap nhat gan nhat: 2026-07-25

## Kho ma nguon

- Kho: `Tienkhoaa2908/vn-quant-system`.
- Nhanh chinh: `main`.
- Dau `main` hien tai: `f52e06ffd4dde26e8af9d6451ec1e64f5a61b35d`.
- Python muc tieu: 3.12; cong cu moi truong: `uv`.
- GitHub la nguon su that ve nhanh, commit, PR va CI.

## Moc 0 va Moc 1

- Moc 0 da hoan thanh va da gop.
- Bo tai lieu dieu phoi da gop.
- Moc 1 da dong hoan toan.
- Dau `main` khi mo Moc 2 la `97399e291b0d3d237f247f58ffa03049826d40bd`.

## Moc 2 — Tap co phieu va duong co so

Trang thai: **da dong hoan toan**.

- PR so 5 da gop bang merge commit `6e8d2ed49c2ef57e43c9f0f2249361b26b838b33`.
- `main` da duoc xac minh sau gop bang GitHub Actions run so 84.
- Da hoan thanh tap co phieu theo thoi diem, thanh khoan, MA250, dong luong, tinh toan ven CLI va truy vet cau hinh.
- Xac minh that FPT, HPG va MBB dat: moi ma 287 phien va 38 dong MA250.
- Nguon lich su thanh vien that van chua duoc phe duyet; khong tuyen bo da loai bo thien lech song sot thuc te.

## PR dieu phoi va dac ta Moc 3

- PR so 6: `Dieu phoi: dong Moc 2 va dac ta Moc 3`.
- Dac ta da duoc nguoi dung va doan `00` phe duyet toan bo 8 quyet dinh kien truc.
- Dau nhanh PR so 6: `164f49b35f5167cfe21e3d85d32ee3656a1b95e8`.
- CI truoc gop: run so 85, Run ID `30123231682`, job ID `89580559878`, thanh cong.
- PR so 6 da gop bang merge commit `f52e06ffd4dde26e8af9d6451ec1e64f5a61b35d`.
- `main` trung khop merge commit tren.
- CI sau gop: run so 86, Run ID `30123567224`, job `kiem_tra` ID `89581624420`, `completed/success`.
- Tat ca buoc cai Python 3.12, dong bo, compile va kiem thu ngoai tuyen deu dat.
- Canh bao Node.js 20 deprecation la canh bao khong chan.

## Moc 3 — Mo phong giao dich va backtest

Trang thai: **da mo; chua co ma nghiep vu va chua co PR trien khai**.

- Dac ta chinh thuc: `tai_lieu/dac_ta_moc_3.md`.
- Nhanh chuyen mon: `m3-mo_phong-giao_dich`.
- Base duoc phe duyet: `f52e06ffd4dde26e8af9d6451ec1e64f5a61b35d`.
- Nhanh da duoc tao truc tiep tu base tren sau khi CI `main` dat.
- Doan phu trach: `03 Mo phong giao dich va backtest`.
- Cac commit hien tai tren nhanh chi la cap nhat dieu phoi; chua trien khai engine.

Pham vi chinh:

- tin hieu tai `T`, khop som nhat tai mo cua phien ke tiep;
- lenh `DAY`, khong tu dời khi thieu bar;
- tien mat, vi the, lenh, khop lenh va so cai;
- phi, thue ban, truot gia va lot size la cau hinh;
- long-only, khong short, khong margin;
- corporate actions MVP gom chia tach/co phieu thuong va co tuc tien mat;
- baseline mua-va-giu, can bang deu va MA250/dong luong de kiem tra engine;
- NAV, loi nhuan, drawdown, Sharpe, turnover va chi phi;
- dau ra bat bien va kiem thu ngoai tuyen.

## Pham vi van bi khoa

- Khong mo Moc 4.
- Khong trien khai Logistic Regression hoac LightGBM.
- Khong trien khai chia von san xuat, tran 15% moi ma hoac 25% moi nganh trong Moc 3.
- Khong commit du lieu thi truong that, nhat ky that, danh sach thanh vien bi han che hoac khoa.
- Khong tich hop tai khoan SSI hay API dat lenh; nguoi dung tu giao dich thu cong.
- PR Moc 3 phai giu draft cho den khi doan `00` ra phan quyet.
