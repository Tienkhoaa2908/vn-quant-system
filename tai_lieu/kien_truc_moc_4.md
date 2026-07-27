# Kien truc Moc 4 — Du lieu nhieu nam, dac trung, xep hang va Logistic Regression

## 1. Pham vi

Moc 4 xay pipeline nghien cuu ngoai mau tren OHLCV ngay, fail closed, tai lap va kiem toan duoc. Tai su dung engine Moc 3; khong sao chep logic T/T+1, lenh DAY, chi phi hoac cong bo. Khong co LightGBM, chia von san xuat, SSI hay Moc 5.

Kien truc da duoc khoa va da trien khai bang fixture ngoai tuyen tren PR #10. Du lieu that chi duoc chay sau phe duyet rieng cua doan 00.

Module du kien:

```text
nghien_cuu_moc_4/
  mo_hinh.py phong_ve.py universe.py do_phu.py dac_trung.py nhan.py
  walk_forward.py tien_xu_ly.py baseline.py logistic.py
  xep_hang.py adapter_mo_phong.py chi_so.py cong_bo.py
  runner.py dong_lenh.py __main__.py
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

Coverage bao theo ngay, ma, ly do, gap, warm-up, khoang yeu cau/thuc_te va ngay thieu `top_k`.

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

## 7A. Tan suat mau va ghep OOS

MVP khoa:

```text
tan_suat_mau_mo_hinh = cuoi_thang
```

Moi mau train, validation va test chi nam tai phien benchmark cuoi cung cua thang. Khong sinh mau ngay thuong trong MVP.

Cac khoang test cua fold khong duoc chong lan. Moi khoa `(ngay,ma)` chi co mot prediction `test`; trung khoa bi tu choi. Target weights test duoc ghep theo thu tu thoi gian thanh mot chuoi OOS lien tuc. Backtest chi khoi tao von mot lan; khong cong, noi bang trung binh, hoac trung binh NAV cua cac fold rieng.

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

Khong impute. Feature order on dinh. Dependency da khoa `scikit-learn==1.9.0` trong `pyproject.toml` va `uv.lock`. Khong pandas, khong LightGBM.

Bat `ConvergenceWarning`:

- candidate C warning: danh dau khong hoi tu, khong duoc chon;
- tat ca C warning: fold that bai co kiem soat, khong predict test;
- refit warning: fold that bai, khong metric/backtest test;
- khong an warning, tu tang `max_iter` hay doi solver.

Luu scaler mean/scale, coefficients, intercept, `n_iter_`, convergence, warning, feature order, version va thoi gian fit.

Fold mot lop:

- train mot lop: fold fail closed;
- refit train+validation mot lop: fold fail closed;
- fold fail khong tao prediction test;
- validation mot lop van tinh log loss voi `labels=[0,1]`;
- AUC validation la `null`;
- fold loi va ly do phai xuat hien trong coverage va report.

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

`nghien_cuu` tu choi neu co_so_gia stock/benchmark chua xac nhan, khong nhat quan, gia khong dieu chinh thieu corporate actions point-in-time, gia dieu chinh kem corporate actions, hoac metadata khong dat cutoff. Khong tu ha muc dich.

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

```text
loi_nhuan_tuong_doi_trung_binh_top_k_t
= mean(relative_return_H cua S_t)
```

Chi so la `null` neu `S_t` rong hoac bat ky ma nao trong `S_t` thieu nhan/relative return. Tong the la trung binh khong trong so tren cac ngay test non-null; khong dung mean-of-fold-means.

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

Chi target weight sinh tu prediction `test` vao engine M3. Ke thua NAV, total return, CAGR, drawdown, Sharpe, turnover, phi, thue, slippage; bo sung cash weight, so ma trung binh, so lan tai can bang, ngay thieu top_k, muc dich va canh_bao gia.

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

`scikit-learn==1.9.0` da duoc them bang commit dependency rieng; lock gom day du dependency bac duoi cho Python 3.12. Khong pandas; khong LightGBM.

Truoc du lieu that, doan 00 xac nhan universe/proxy, VNINDEX va lich benchmark, co so gia, corporate actions neu can.

PR #10 giu Draft. Khong force-push, khong merge, khong du lieu that, khong Moc 5.

## 17. Runner dau-cuoi va CLI

Ham `chay_nghien_cuu_moc_4(...)` la cua vao duy nhat cua pipeline nghien cuu. Dau vao toi thieu:

```text
cau_hinh.json
OHLCV co phieu.csv
benchmark.csv
lich_benchmark.csv
universe.csv
corporate_actions_metadata.csv
thu_muc_dau_ra
ma_lan_chay
git_commit
```

Runner chi doc tep cuc bo, khong goi mang. CLI goi truc tiep runner; che do `--kiem-tra-cau-hinh` duoc tach rieng.

Thu tu bat bien:

```text
parse/validate → PIT → coverage → monthly features → labels → samples
→ folds → baseline/logistic → test predictions → ranking/targets
→ M3 backtests → metrics → 16 products → manifest → atomic publish
```

## 18. Calendar alignment cua feature

Lich benchmark chinh thuc la dau vao rieng va khong duoc suy ra tu cac benchmark bar con ton tai. Tai T:

- endpoint return/momentum la dung `calendar[index(T)-N]`;
- MA_N va liquidity_N can du moi bar tren N phien benchmark ket thuc tai T;
- volatility_N can du N+1 bar tren dung lich;
- benchmark regime dung cung lich va endpoint;
- stock/benchmark map theo ngay, khong theo vi tri bar con ton tai.

Thieu bar bat buoc tao ly do co cau truc `thieu_bar_<side>_<feature>`, feature rong va dong bi loai neu feature do bat buoc. Them bar truoc cua so khong the chuyen dong thieu thanh hop le.

## 19. Coverage schema

`bao_cao_do_phu.json` cong bo khoang yeu cau/thuc_te, tong ma universe/co du lieu, danh sach loi hoan toan/warm-up/gap/gia/volume/corporate actions, coverage theo ngay (`tu_so,mau_so,ty_le`), coverage theo ma (`so_phien_co,so_phien_yeu_cau,ty_le`), ngay thieu top_k, ly do loai, loi fold, nguon/phien ban va co so gia.

## 20. Baseline va OOS adapter

Momentum baseline dung `dong_luong_12_1` tren dung test samples da qua eligibility. Baseline va Logistic Regression dung cung test dates, universe, eligibility, top_k, chi phi va engine.

Adapter bat buoc `muc_tieu_bang_0`. Target matrix day du theo `ngay_tai_can_bang × cac_ma_lien_quan`; ma khong duoc chon co target 0. Ngay khong co prediction van tao tai can bang ve tien mat. Moi chien luoc goi engine Moc 3 dung mot lan.

## 21. Manifest va phong ve du lieu

Manifest tu tinh SHA-256/size cho moi dau vao va 16 san pham. Metadata bat buoc gom Git/run/UTC/Python/uv/scikit-learn, nguon/phien ban, co so gia, muc dich, nam nhom cau hinh, canh bao va gioi han. Metadata rong/khuyet, input khong ton tai hoac payload sai hop dong deu rollback.

Moi so trong OHLCV, feature, prediction, relative return, metric va san pham phai dat `math.isfinite`. CSV/JSON chua NaN/Inf bi tu choi truoc publication. Metric cuoi chi nhan test, khoa `(ngay,ma)` duy nhat va fold/model nhat quan.

## 22. Kiem thu fixture

Suite gom 146 test Mốc 4 va 121 test Mốc 0–3, tong 267 test. Cac nhom bo sung bao phu tam kich ban calendar alignment, coverage day du, nam kich ban OOS target/cash, manifest thieu tung metadata, baseline OOS, finite/duplicate/role validation va kich ban vang dau-cuoi.

Kich ban vang:

- tao dung 17 tep;
- co fold, prediction va ranking ngoai mau;
- kiem tra ngay khop la T+1 tren lich benchmark;
- NAV va so lan tai can bang lien tuc;
- input/product hashes trong manifest;
- hai run co timestamp/git/input giong nhau tao byte giong nhau;
- CLI chay cung pipeline tu tep cuc bo.

## 23. Cua kiem soat

Tier A/Tier B chua chay. VN100/VNINDEX, lich benchmark, co so gia va corporate actions that chua duoc phe duyet. Ket qua fixture chi xac minh ky thuat, khong duoc dung de tuyen bo hieu qua chien luoc. Khong LightGBM, SSI, Ready, merge hay Moc 5.

## 24. Eligibility, thanh khoan va open T+1

Eligibility tai T la AND fail closed cua: membership PIT, thanh khoan PIT, warm-up, feature bat buoc hop le, chat luong du lieu, benchmark metadata PIT va open tai dung T+1. Thanh khoan MVP dung `gtgd_tb_20 = mean(close * volume)` tren dung 20 phien benchmark ket thuc tai T, don vi dong/phien, cutoff tai T va nguong cau hinh. `None`, thieu bar hoac duoi nguong ghi `khong_dat_thanh_khoan`. T+1 lay tu lich benchmark chinh thuc; thieu open dung T+1 ghi `thieu_open_t1`, khong tim xa hon.

## 25. Cua so backtest va metric OOS

Runner khoa ba ngay: `oos_start` la tin hieu test dau tien, `ngay_bat_dau_metric` la phien T+1 dau tien co the thuc thi, `oos_end` la diem ket thuc nhan/nam giu can thiet cua tin hieu test cuoi. Engine chi nhan gia trong pham vi OOS can thiet; ket qua NAV/lenh/su_kien duoc cat truoc khi tinh metric. Du lieu warm-up/train truoc OOS va du lieu sau `oos_end` khong vao metric. Mot engine call, mot von ban dau, mot chuoi lien tuc.

## 26. Fold rong va model audit

Fold refit thanh cong nhung test sample rong fail `test_rong`; co test sample nhung khong tao prediction fail `khong_co_prediction_test`. Ca hai khong tao ranking/target/rebalance va duoc ghi coverage/mo_hinh.

Audit co hai stage:

- `validation_selection`: pipeline fit train, dung de bien doi validation va chon C;
- `final_refit`: pipeline fit train+validation, dung de bien doi/predict test.

Moi stage co model ID rieng, scaler mean/scale, C, coefficients, intercept, n_iter, converged, warning, candidate errors, feature order, cutoff train/validation/test va scikit-learn version.

## 27. Corporate action cutoff

Corporate action khong duoc loc theo viec co ngay tin hieu nam giua publication/effective date. Su kien co timestamp cong bo co mui gio, cong bo khong sau cutoff bao thu cua ngay hieu luc, ngay hieu luc nam trong `oos_start..oos_end`, khong hoi to va phu hop co so gia thi duoc dua vao engine. Su kien giua hai ky tai can bang van duoc ap dung. Cong bo sau hieu luc, su kien trung va gia dieu chinh kem su kien bi tu choi.

## 28. Coverage PIT va policy du lieu loi

Mau so theo ma la `research range ∩ tu phien quan sat du lieu hop le/loi dau tien ∩ membership PIT ∩ phien can kiem tra`; neu ma khong co bat ky quan sat nao, membership PIT dau tien la fallback de ma that bai hoan toan van co mau so, gom T+1 khi can open. Ma moi khong bi phat truoc ngay bat dau; ma roi universe khong bi phat sau ngay roi; gap chi xet ben trong tap yeu cau. Policy B loai dong/ma loi gia/volume co kiem soat, ghi danh sach/khoa loi va coverage, khong cong bo bao cao thanh cong mau thuan voi exception.

## 29. Research fail closed va kiem thu final tree

Benchmark file co dung mot identity bang `config.benchmark`; MVP VNINDEX. Run `nghien_cuu` chi duoc cong bo khi co benchmark metadata PIT, it nhat mot fold test hop le, prediction test OOS, ngay tai can bang, coverage/universe dat nguong va hop dong gia/corporate actions dat. Technical run ghi canh bao thay vi tuyen bo nghien cuu thanh cong.

Suite final tree gom 187 test Mốc 4 va 121 test Mốc 0–3, tong 308 test. 41 test moi cua vong nay tach rieng cho eligibility, OOS metamorphic, fold rong, corporate action cutoff, coverage PIT/data error, model audit stage va research fail closed. Tier A/Tier B va du lieu that chua chay; metric fixture khong chung minh hieu qua chien luoc. PR #10 tiep tuc Draft.

## 30. Durability cong bo da nen tang

Hop dong publication final theo QD-0060:

- 16 san pham va `manifest.json` deu duoc ghi bang mode tao moi, `flush()` va file fsync tren Ubuntu va Windows;
- tren POSIX/Linux, `_fsync_dir` dung `O_RDONLY`, them `O_DIRECTORY` khi co, goi `os.fsync(fd)`, luon dong descriptor trong `finally` va propagate loi `os.open`/`os.fsync`;
- tren Windows MVP, Python khong mo directory bang `os.open(..., O_RDONLY)`; implementation khong goi `os.open` tren directory va tra capability `False`/unsupported;
- staging nam cung parent filesystem voi destination, publication dung dung mot `os.replace`, tu choi ghi de destination va rollback staging khi loi;
- file fsync, atomic replace va rollback ap dung tren ca hai nen tang, nhung khong tuyen bo Windows co directory-entry crash durability tuong duong POSIX.

Final source ky thuat `5aec6ace8423fbf30442aa77db6ff63adb3c854e` da dat CI run #334 tren Ubuntu va Windows voi 320 test discovery. PR clean-history #14 tiep tuc Draft; Tier A/Tier B chua chay va khong co du lieu that trong repository.

## Cap nhat QD-0061: contract benchmark close-only

PR canonical hien tai la #16 tren nhanh `m4-dac_trung-xep-hang-hoc_may-sach-final-v2`. Giai doan 2A da hoan tat voi `D.OFFICIAL_VALUES_UNAVAILABLE`, `SEMANTICS_DEFINITION_NOT_FOUND` va `CLOSE_ONLY_BENCHMARK_CONTRACT`; cac tham chieu PR #14/CI cu o phan lich su khong phai trang thai current-head. CI #347 chi la baseline cua head cu truoc patch nay.

Co phieu tiep tuc dung `ThanhOHLCV` strict. Benchmark dung `ThanhBenchmarkDongCua` va schema CSV dung sau cot `ma,ngay,gia_dong_cua,nguon,phien_ban,co_so_gia`; open/high/low/volume benchmark khong duoc dua vao canonical input, sua, suy dien hoac dung trong feature/label. Raw KBS va ho so audit run `m4_tier_a_20260727T081753Z_e2c866db` giu bat bien; khong co correction overlay hay replacement values. Manifest/bao cao cong bo `benchmark_contract=close_only`, hai canh bao bat buoc va gioi han chi kiem tra ky thuat. Exact official OHLC van chua co; dieu nay khong xac nhan co so gia co phieu. Normalization, Tier A pipeline, Tier B va Moc 5 chua chay.
