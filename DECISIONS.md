# Cac quyet dinh kien truc

Tai lieu nay tom tat cac quyet dinh da khoa tu Moc 0 den Moc 4. Dac ta chi tiet tung moc nam trong `tai_lieu/`.

## QD-0001 den QD-0011 — Nen Moc 0 va Moc 1

- Trien khai theo lat doc nho, chay duoc va co kiem thu.
- Ten noi bo dung tieng Viet khong dau; du lieu trong test chi la fixture.
- Nguon du lieu duoc tach qua giao dien chung; chi adapter nguon biet Vnstock/KBS.
- Du lieu tho bat bien, khong ghi de; san pham JSON/CSV UTF-8 co chat luong va SHA-256.
- Khoang ngay bat thuong chi la canh bao, khong tu dien phien.
- Vnstock Community khoa 4.0.4 khi chay that; CI khong cai Vnstock va khong goi mang.
- FPT, HPG, MBB la tap bat buoc cua xac minh Moc 1; VNINDEX la phan mo rong.

## QD-0012 den QD-0020 — Universe va feature Moc 2

- Snapshot universe co khoa `ngay_hieu_luc,ma`, co nguon/phien ban va duoc chon point-in-time.
- Snapshot tuong lai khong duoc dung; thieu snapshot thi fail closed, khong suy doan lich su.
- Gia tri giao dich bang `close*volume`; bo loc thanh khoan tinh theo cua so tung ma va khong nhin truoc.
- MA250 la SMA dung 250 quan sat; momentum N la `close_t/close_t-N-1` va can N+1 quan sat.
- Khong tu dien gia, volume, ngay, membership hoac feature; khoa `ma,ngay` phai duy nhat.
- Moc 2 khong backtest, khong ML va khong chia von.
- So nen Vnstock phai duoc truyen ro; cau hinh lan chay la mot phan cua san pham bat bien.

## QD-0021 den QD-0035 — Engine Moc 3

- Tin hieu close T chi khop open dung T+1; lenh DAY het han neu thieu bar/open, khong tim phien xa hon.
- Gia khop gom slippage; phi theo chieu, thue chi phia ban; ban chay truoc mua va ma sap tang dan.
- Long-only, khong margin, khong tien mat/vi the am; pre-trade sizing khong phai market partial fill.
- Corporate actions MVP ap dung point-in-time; gia dieu chinh kem corporate actions bi tu choi de tranh tinh hai lan.
- Gia von, realized/unrealized P&L va phuong trinh doi soat NAV duoc khoa; slippage khong bi tru lan hai.
- Eligibility mo/tang vi the la fail closed; giam/dong van duoc phep kem canh bao.
- Bien chi phi, so nguyen va don vi gia/tien duoc xac thuc nghiem ngat.
- Baseline Moc 3 chi kiem tra engine, khong la chien luoc san xuat.
- Chin san pham Moc 3 duoc staging, fsync, rename nguyen tu, rollback va SHA-256.
- Loi do CLI kiem soat duoc lam sach credential truoc khi cong bo.

## QD-0036: Cutoff point-in-time theo timestamp tin hieu

Moi universe record, corporate action, benchmark metadata va event point-in-time chi duoc dung khi:

```text
thoi_diem_cong_bo <= thoi_diem_tao_tin_hieu
```

Hai timestamp phai co mui gio. Cong bo truoc tin hieu cung ngay duoc dung; cong bo sau tin hieu cung ngay bi loai; timestamp thieu mui gio bi tu choi.

## QD-0037: Mau model chi tai phien benchmark cuoi thang

```text
tan_suat_mau_mo_hinh = cuoi_thang
```

Train, validation va test chi gom phien benchmark cuoi cung cua thang. MVP khong dung mau ngay thuong.

## QD-0038: Nhan T+H theo lich benchmark

T+H la phien thi truong thu H sau T tren lich benchmark/VNINDEX. Khong dung bar thu H con ton tai cua tung ma. Thieu stock hoac benchmark dung T/T+H thi nhan rong; khong forward-fill va khong tim phien thay the.

## QD-0039: Walk-forward expanding monthly

Test moi fold dung mot thang va khong chong lan. Purge train–validation toi thieu bang horizon; embargo validation–test theo lich benchmark. Mau chi vao train/validation/refit khi `ngay_ket_thuc_nhan` khong sau cutoff cua tap. Test khong chon feature, C, threshold, preprocessing hoac refit.

## QD-0040: Logistic Regression MVP

Dependency khoa `scikit-learn==1.9.0`. Pipeline dung `StandardScaler(with_mean=True, with_std=True)` va Logistic Regression L2, `lbfgs`, `max_iter=1000`, `class_weight=None`, `C_grid=[0.1,1.0,10.0]`, seed `20260725`. Khong pandas va khong LightGBM.

C duoc chon bang validation log loss; hoa chon C nho hon. ConvergenceWarning lam candidate/refit khong hop le. Train/refit mot lop lam fold fail closed; validation mot lop van tinh log loss voi `labels=[0,1]`, AUC null.

## QD-0041: Model clock va san pham theo fold

Moi model ghi `thoi_diem_huan_luyen`, `thoi_diem_tao_tin_hieu`, `cutoff_feature`, `cutoff_nhan` va phai dat:

```text
thoi_diem_huan_luyen <= thoi_diem_tao_tin_hieu
```

Feature sau tien xu ly va prediction ghi fold/model/vai tro. Chi prediction test vao metric cuoi, ranking, target weights va backtest.

## QD-0042: Ranking, top-K va metric

Probability sap giam, tie-break ma tang, moi ma duoc chon co `1/top_k`, phan thieu la tien mat. Precision@K, hit rate, average relative return top-K, decile spread, Spearman average-rank IC va set turnover duoc tinh theo ngay test truoc, sau do trung binh khong trong so tren ngay non-null; khong mean-of-fold-means.

Calibration dung 10 bin equal-width, bo bin rong va khong co probability calibrator.

## QD-0043: OOS la mot chuoi backtest lien tuc

Khoang test khong chong lan; `(ngay,ma)` prediction test va `(ngay_tin_hieu,ma)` target weight phai duy nhat. Target weights test duoc ghep theo thoi gian. Engine Moc 3 duoc goi mot lan, von khoi tao mot lan; khong cong hoac trung binh NAV cua fold rieng.

## QD-0044: Muc dich lan chay

`kiem_tra_ky_thuat` duoc phep khi co so gia chua xac nhan nhung bat buoc canh bao va cam ket khong ket luan hieu qua. `nghien_cuu` fail closed neu co so gia/corporate actions/metadata PIT khong dat hop dong; khong tu ha muc dich.

## QD-0045: Cong bo Moc 4 va cua du lieu that

Moc 4 cong bo 17 tep bang staging, fsync, atomic rename, rollback va SHA-256; khong ghi de va khong tron thanh cong/that bai. Toan bo trien khai hien tai chi dung fixture ngoai tuyen. Tier A/Tier B va du lieu that chi duoc chay sau phe duyet rieng cua doan 00.
