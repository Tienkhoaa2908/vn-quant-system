# Kien truc Moc 4 — Du lieu nhieu nam, dac trung, xep hang va Logistic Regression

## 1. Pham vi

Moc 4 xay pipeline nghien cuu ngoai mau tren OHLCV ngay, fail closed, tai lap va kiem toan duoc. Tai su dung engine Moc 3; khong sao chep logic T/T+1, lenh DAY, chi phi hoac cong bo. Khong co LightGBM, chia von san xuat, SSI hay Moc 5.

Vong nay chi khoa kien truc. Chua them ma nghiep vu, fixture, test, `scikit-learn`, hoac sua `pyproject.toml`/`uv.lock`.

Module du kien:

```text
nghien_cuu_moc_4/
  mo_hinh.py universe.py do_phu.py dac_trung.py nhan.py
  walk_forward.py tien_xu_ly.py baseline.py logistic.py
  xep_hang.py adapter_mo_phong.py chi_so.py cong_bo.py
  dong_lenh.py __main__.py
```

## 2. Cutoff point-in-time

Moi tin hieu T co `thoi_diem_tao_tin_hieu`, la timestamp ISO-8601 co mui gio, sau close T va truoc khi tao prediction/ranking.

Moi timestamp point-in-time phai timezone-aware:

```text
thoi_diem_tao_tin_hieu
thoi_diem_cong_bo
thoi_diem_huan_luyen
cutoff_feature
cutoff_nhan
```

Timestamp thieu UTC offset hoac timezone da resolve bi tu choi; khong ngam hieu theo timezone may chay.

Quy tac duy nhat:

```text
thoi_diem_cong_bo <= thoi_diem_tao_tin_hieu
```

Ap dung cho universe, corporate actions, benchmark metadata, du lieu su kien point-in-time va metadata ngoai OHLCV co the cong bo trong ngay.

Neu nhieu ban ghi hop le: chon `ngay_hieu_luc` moi nhat, sau do `thoi_diem_cong_bo` moi nhat; neu van trung thi tu choi.

Kiem thu thiet ke:

1. cong bo truoc tin hieu cung ngay: duoc dung;
2. cong bo sau tin hieu cung ngay: bi loai;
3. timestamp thieu mui gio: bi tu choi;
4. cung instant voi UTC offset khac nhau: cung ket qua;
5. them ban ghi cong bo sau tin hieu: khong doi ket qua tai T.

## 3. Hop dong du lieu

OHLCV:

```text
ma,ngay,gia_mo_cua,gia_cao_nhat,gia_thap_nhat,gia_dong_cua,khoi_luong,nguon,phien_ban,co_so_gia
```

Universe:

```text
ngay_hieu_luc,ma,thuoc_universe,nguon,phien_ban,thoi_diem_cong_bo
```

Tai T, membership chi hop le khi:

```text
ngay_hieu_luc <= T
thoi_diem_cong_bo <= thoi_diem_tao_tin_hieu
```

`False`, rong, thieu snapshot hoac cong bo muon deu fail closed. Khong suy doan membership.

Benchmark:

```text
ma_chi_so,ngay,gia_mo_cua,gia_cao_nhat,gia_thap_nhat,gia_dong_cua,khoi_luong,nguon,phien_ban,co_so_gia,thoi_diem_cong_bo
```

Benchmark mac dinh VNINDEX. Nguon, phien ban va co so gia chi duoc dung khi dat cutoff point-in-time.

Corporate actions/su kien:

```text
ma,loai_su_kien,ngay_hieu_luc,ngay_thanh_toan,ty_le,gia_tri_tien_mat,nguon,phien_ban,thoi_diem_cong_bo
```

Su kien cong bo sau tin hieu khong duoc ap dung hoi to. `gia_dieu_chinh` khong kem corporate actions; `gia_khong_dieu_chinh` can corporate actions point-in-time day du khi chay nghien cuu.

Bat bien chung: khoa duy nhat, ngay ISO, timestamp co mui gio, gia duong, volume nguyen khong am, khong backfill/forward-fill, CSV UTF-8 va thu tu cot on dinh.

## 4. Feature MVP

Feature chi dung du lieu den `cutoff_feature`.

```text
khoang_cach_ma20/60/120/250 = close/SMA_N - 1
gia_tren_ma250 = close >= SMA250
ty_le_dinh_52_tuan = close/max(close_250)
loi_nhuan_20/60/120/250 = close[t]/close[t-N] - 1
dong_luong_12_1 = close[t-20]/close[t-250] - 1
suc_manh_tuong_doi_120 = ret_stock_120 - ret_benchmark_120
bien_dong_20/60 = sample_std(daily_return)
bien_dong_giam_60 = sample_std(min(daily_return,0))
bien_do_cao_thap_chuan_hoa = (high-low)/close tai T
gtgd_tb_20/60 = SMA(close*volume)
gtgd_hien_tai_tren_tb60 = close*volume/gtgd_tb_60
so_phien_volume_0_60 = count(volume==0)
vnindex_tren_ma250
vnindex_momentum_60
vnindex_bien_dong_20/60
```

Dinh nghia da duyet: momentum 12-1 nhu tren; relative strength 120 phien; high-low tai T; calibration 10 bin equal-width, bo bin rong, khong probability calibrator.

Feature bat buoc co order co dinh. Thieu bat ky feature bat buoc nao thi loai; khong impute ngam.

## 5. Eligibility va coverage

Eligibility la AND fail closed cua membership, thanh khoan, warm-up, feature bat buoc, chat luong du lieu, cutoff metadata va open T+1 khi backtest.

Ma ly do toi thieu:

```text
khong_thuoc_universe
membership_chua_cong_bo
thieu_snapshot
timestamp_thieu_mui_gio
khong_dat_thanh_khoan
thieu_warm_up
thieu_feature_bat_buoc
loi_gia
loi_volume
khong_nhat_quan_co_so_gia
thieu_open_t1
```

Coverage bao theo ngay, ma, ly do, gap, warm-up, khoang yeu cau/thuc te va ngay thieu `top_k`.

## 6. Lich T+H va nhan

`T+H` la phien thi truong thu H sau T tren lich benchmark/thi truong, mac dinh lich VNINDEX da xac thuc:

```text
T_H = lich_benchmark[index(T) + H]
```

Khong dung bar thu H con ton tai cua rieng tung ma.

```text
ret_stock_H = close_stock[T_H]/close_stock[T] - 1
ret_benchmark_H = close_benchmark[T_H]/close_benchmark[T] - 1
loi_nhuan_tuong_doi_H = ret_stock_H - ret_benchmark_H
nhan = 1 neu loi_nhuan_tuong_doi_H > 0, nguoc_lai 0
ngay_ket_thuc_nhan = T_H
```

Thieu stock hoac benchmark tai dung T/T_H, T khong thuoc lich, hoac khong du H phien: nhan rong; khong tim xa hon; khong forward-fill; khong vao train/validation/refit.

## 7. Walk-forward

MVP:

```text
expanding_window = true
tan_suat_tai_huan_luyen = hang_thang
so_thang_test = 1
purge_phien >= label_horizon
embargo_phien >= 0
```

Do dai test bang tan suat retrain: moi model chi phuc vu mot thang test; thang sau tao fold/model moi. `so_thang_test != 1` bi tu choi trong MVP.

Moi fold luu:

```text
train_feature_start,train_feature_end,cutoff_train
validation_feature_start,validation_feature_end,cutoff_validation
embargo_start,embargo_end
test_feature_start,test_feature_end
```

Tat ca moc phien lay tren lich benchmark.

- `train_feature_end` cach `validation_feature_start` it nhat `purge_phien`.
- `cutoff_train` la phien truoc validation start.
- embargo la `embargo_phien` phien ngay truoc test start.
- validation ket thuc truoc embargo; neu embargo=0, truoc test start.
- `cutoff_validation` va `cutoff_refit` la phien truoc test start.
- khong co feature sample trong purge/embargo.

Mau train chi hop le khi:

```text
ngay <= train_feature_end
ngay_ket_thuc_nhan <= cutoff_train
```

Mau validation chi hop le khi:

```text
validation_feature_start <= ngay <= validation_feature_end
ngay_ket_thuc_nhan <= cutoff_validation
```

Mau refit train+validation chi hop le khi:

```text
ngay_ket_thuc_nhan <= cutoff_refit
```

Chon C:

1. moi C tao pipeline rieng;
2. fit chi train;
3. predict validation;
4. chon validation log loss nho nhat;
5. hoa trong `1e-12`: chon C nho hon.

Sau khi chon C, refit pipeline moi tren train+validation hop le; scaler cung refit. Test tuyet doi khong chon C, feature, threshold, preprocessing, fold hay refit.

Moi model ghi:

```text
fold,model_id
thoi_diem_huan_luyen
thoi_diem_tao_tin_hieu
cutoff_feature
cutoff_nhan
train_start,train_end
validation_start,validation_end
test_start,test_end
purge_phien,embargo_phien,C
```

Bat bien:

```text
cutoff_feature <= thoi_diem_tao_tin_hieu
cutoff_nhan <= thoi_diem_huan_luyen
thoi_diem_huan_luyen <= thoi_diem_tao_tin_hieu
```

## 8. Logistic Regression

Cau hinh khoa:

```text
StandardScaler(with_mean=True, with_std=True)

LogisticRegression(
  penalty="l2",
  solver="lbfgs",
  max_iter=1000,
  class_weight=None,
  C=<C da chon>,
  random_state=20260725
)

C_grid = [0.1, 1.0, 10.0]
seed = 20260725
```

Khong impute. Feature order on dinh. Duoc phep `scikit-learn==1.9.0`; chua sua dependency trong vong nay. Khong LightGBM.

Bat `ConvergenceWarning`:

- candidate C warning: danh dau khong hoi tu, khong duoc chon;
- tat ca C warning: fold that bai co kiem soat, khong predict test;
- refit warning: fold that bai, khong metric/backtest test;
- khong an warning, tu tang `max_iter` hay doi solver.

Luu scaler mean/scale, coefficients, intercept, `n_iter_`, convergence, warning, feature order, version va thoi gian fit.

## 9. Ranking va T+1

Tai tin hieu cuoi thang:

1. universe tai cutoff;
2. eligibility;
3. feature den cutoff;
4. model da train truoc tin hieu;
5. `P(nhan=1)`;
6. sort giam, hoa theo ma tang;
7. top_k;
8. moi ma `1/top_k`;
9. thieu ma thi phan thieu la tien mat;
10. engine M3 khop open dung phien ke tiep.

Khong tim phien xa hon.

## 10. San pham theo fold

`feature_sau_tien_xu_ly.csv` co cac cot dau:

```text
fold,model_id,vai_tro_du_lieu,ngay,ma
```

Vai tro:

```text
train
validation
refit_train_validation
test
```

`du_doan.csv` co:

```text
fold,model_id,vai_tro_du_lieu,ngay,ma,xac_suat_nhan_1
```

Vai tro prediction chi la `validation` hoac `test`.

Chi prediction test duoc dung cho metric cuoi, ranking cuoi, target weight va backtest. Validation chi chon C/chan doan.

Danh sach san pham giu theo dac ta: config, coverage, universe, feature raw/processed, label, folds, model, coefficients, prediction, ranking, target weights, ba nhom metrics, report va manifest SHA-256.

## 11. Muc dich lan chay

Cau hinh bat buoc:

```text
muc_dich_lan_chay = kiem_tra_ky_thuat | nghien_cuu
```

`kiem_tra_ky_thuat`:

- duoc phep khi co so gia chua xac nhan hoac corporate actions chua day du;
- config/report/manifest bat buoc canh bao;
- metric/backtest ghi `chi_de_xac_minh_ky_thuat=true`;
- cam ket khong ket luan hieu qua, sinh loi hay chat luong chien luoc.

`nghien_cuu` tu choi neu co so gia stock/benchmark chua xac nhan, khong nhat quan, gia khong dieu chinh thieu corporate actions point-in-time, gia dieu chinh kem corporate actions, hoac metadata khong dat cutoff. Khong tu ha muc dich.

## 12. Metric model va calibration

Metric validation va test tach rieng; metric cuoi chi test.

- AUC null neu mot lop.
- Log loss, Brier, positive rate, observation/symbol count.
- Calibration 10 bin `[0,.1) ... [.9,1]`; 1.0 vao bin cuoi; bo bin rong; luu count, mean probability, positive rate; khong calibrator.

Theo fold: pooled tren test observation cua fold. Tong the: pooled tren moi test observation cua tat ca fold, khong trung binh fold metric khi size khac nhau.

## 13. Metric ranking

Tai ngay test t, `S_t` la tap top_k da chon.

```text
precision@K_t = so nhan duong trong S_t / |S_t|
```

Null neu `S_t` rong. Neu mot ma trong `S_t` thieu nhan, metric ngay null va ghi coverage; khong doi mau so.

```text
hit_rate_topK_t = 1 neu S_t co it nhat mot nhan duong, nguoc lai 0
```

Null neu `S_t` rong hoac co ma thieu nhan.

```text
turnover_t = 1 - |S_t giao S_t-1| / max(|S_t|,|S_t-1|)
```

Ky dau null; ca hai rong=0; mot rong=1.

Spearman rank IC:

- average rank cho ties;
- Pearson correlation giua rank prediction va rank relative return;
- null neu duoi 3 ma;
- null neu mot phia variance=0;
- tie-break ma chi dung giao dich, khong thay average rank.

Decile spread:

- toi thieu 10 ma co prediction va nhan;
- sort score giam, tie-break ma;
- voi `n=10q+r`, `r` decile dau co `q+1`, con lai `q`;
- spread = mean relative return decile 1 - decile 10.

Aggregation ranking:

- tinh theo ngay truoc;
- fold = mean khong trong so cua ngay non-null;
- tong the = mean khong trong so cua tat ca ngay test non-null tren moi fold;
- khong mean-of-fold-means;
- cong bo valid/null days, ngay thieu top_k va so ma trung binh;
- khong tron validation.

## 14. Backtest ngoai mau

Chi target weight sinh tu prediction `test` vao engine M3. Ke thua NAV, total return, CAGR, drawdown, Sharpe, turnover, phi, thue, slippage; bo sung cash weight, so ma trung binh, so lan tai can bang, ngay thieu top_k, muc dich va canh bao gia.

Tin hieu close T khop open T+1. Thieu bar/open thi DAY het han.

## 15. Kiem thu thiet ke

Bat buoc bao phu:

- point-in-time truoc/sau tin hieu cung ngay va timezone;
- survivorship, ma vao/roi/huy niem yet;
- T+H theo benchmark, missing endpoint;
- no-look-ahead va leakage sentinel;
- label cutoff train/validation/refit;
- purge, embargo, expanding monthly folds;
- C selection, refit va test isolation;
- model clock;
- convergence warning;
- fold product roles;
- metric tinh tay va aggregation;
- muc dich lan chay;
- T+1 M3;
- publication/rollback/SHA-256/reproducibility;
- toan bo 121 test Moc 0–3.

CI ngoai tuyen, khong goi Vnstock trong test.

## 16. Phu thuoc va cua kiem soat

Sau khi doan 00 xac minh kien truc, duoc them `scikit-learn==1.9.0` bang commit dependency rieng. Khong pandas neu chua co ly do moi; khong LightGBM.

Truoc du lieu that, doan 00 xac nhan universe/proxy, VNINDEX va lich benchmark, co so gia, corporate actions neu can.

PR #10 giu Draft. Khong force-push, khong merge, khong du lieu that, khong Moc 5.
