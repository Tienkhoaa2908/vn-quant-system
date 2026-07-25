# Kien truc Moc 4 — Du lieu nhieu nam, dac trung, xep hang va Logistic Regression

## 1. Pham vi va nguyen tac

Moc 4 xay lop nghien cuu ngoai mau tren du lieu OHLCV ngay. Pipeline phai tai lap, kiem toan duoc, fail closed va khong dung thong tin sau ngay danh gia. Moc 4 khong trien khai LightGBM, inverse volatility, gioi han nganh, ket noi SSI, doc tai khoan hoac gui lenh.

Cac quyet dinh M4-01 den M4-12 da duoc phe duyet la rang buoc bat bien. Module M4 moi duoc tach khoi module Moc 1–3, nhung tai su dung hop dong du lieu va engine mo phong Moc 3 thay vi sao chep logic giao dich.

## 2. So do module du kien

```text
src/he_thong_dinh_luong/nghien_cuu_moc_4/
├── __init__.py
├── mo_hinh.py              # dataclass, cau hinh, hang so va hop dong noi bo
├── universe.py             # universe point-in-time va eligibility fail closed
├── do_phu.py               # coverage, gap, loi du lieu va ly do loai
├── dac_trung.py            # feature raw khong nhin truoc
├── nhan.py                 # nhan loi nhuan tuong doi T+H
├── walk_forward.py         # expanding window, purge, validation, embargo, test
├── tien_xu_ly.py           # bo feature bat buoc va pipeline fit tren train
├── baseline.py             # momentum baseline
├── logistic.py             # Logistic Regression, luoi C nho va metadata
├── xep_hang.py             # probability, tie-break, top_k, ty trong deu
├── adapter_mo_phong.py     # chuyen dau ra sang engine Moc 3 va T+1
├── chi_so.py               # model, ranking va backtest OOS metrics
├── cong_bo.py              # san pham bat bien, SHA-256, rollback, manifest
├── dong_lenh.py            # CLI va ma thoat
└── __main__.py
```

Kiem thu du kien:

```text
tests/test_m4_universe.py
tests/test_m4_do_phu.py
tests/test_m4_dac_trung.py
tests/test_m4_nhan.py
tests/test_m4_walk_forward.py
tests/test_m4_tien_xu_ly.py
tests/test_m4_logistic.py
tests/test_m4_xep_hang.py
tests/test_m4_chi_so.py
tests/test_m4_adapter_mo_phong.py
tests/test_m4_cong_bo.py
tests/test_m4_cli.py
```

## 3. Hop dong du lieu

### 3.1 OHLCV co phieu

```text
ma,ngay,gia_mo_cua,gia_cao_nhat,gia_thap_nhat,gia_dong_cua,khoi_luong,nguon,phien_ban,co_so_gia
```

Bat bien:

- khoa `ma,ngay` duy nhat;
- `ma` chuan hoa chu hoa;
- gia la so huu han duong;
- `khoi_luong` la so nguyen khong am;
- khong backfill ngay, gia, volume hoac feature;
- moi lan chay chi co mot `co_so_gia`.

### 3.2 Universe point-in-time

```text
ngay_hieu_luc,ma,thuoc_universe,nguon,phien_ban,thoi_diem_cong_bo
```

Tai ngay T, chi ban ghi co `ngay_hieu_luc <= T` va `thoi_diem_cong_bo <= het_ngay_T` duoc phep tham gia. Ban ghi gan nhat hop le theo tung ma quyet dinh trang thai. `False`, rong, thieu snapshot hoac cong bo sau T deu khong hop le. Khong suy doan membership.

### 3.3 Benchmark

```text
ma_chi_so,ngay,gia_mo_cua,gia_cao_nhat,gia_thap_nhat,gia_dong_cua,khoi_luong,nguon,phien_ban,co_so_gia
```

Benchmark mac dinh ve nghiep vu la VNINDEX, nhung nguon va co so gia phai duoc ghi trong cau hinh lan chay. Co phieu va benchmark phai dung co so gia nhat quan.

### 3.4 Corporate actions

```text
ma,loai_su_kien,ngay_hieu_luc,ngay_thanh_toan,ty_le,gia_tri_tien_mat,nguon,phien_ban,thoi_diem_cong_bo
```

- `gia_dieu_chinh`: khong truyen corporate actions vao engine;
- `gia_khong_dieu_chinh`: chi cho phep khi corporate actions point-in-time day du;
- khong nhat quan thi tu choi hoac danh dau chi la xac minh ky thuat theo cau hinh.

### 3.5 Khoa va thu tu chung

- ngay ISO `YYYY-MM-DD`, thoi diem ISO-8601 co mui gio;
- CSV UTF-8, thu tu cot co dinh;
- dau ra sap xep xac dinh theo `ngay,ma` hoac `fold,ngay,ma` tuy bang;
- khong ep ngam chuoi rong thanh 0/False;
- so thap phan dau ra duoc dinh dang on dinh.

## 4. Dac trung MVP

Feature raw duoc tinh rieng theo ma, chi tu cac quan sat co ngay khong sau T. Feature benchmark cung chi dung du lieu den T.

| Nhom | Ten du kien | Cong thuc tom tat | Cua so / toi thieu | Don vi |
|---|---|---|---|---|
| Xu huong | `khoang_cach_ma20/60/120/250` | `close / SMA_N - 1` | N | ty le |
| Xu huong | `gia_tren_ma250` | `close >= SMA250` | 250 | boolean |
| Xu huong | `ty_le_dinh_52_tuan` | `close / max(close_250)` | 250 | ty le |
| Dong luong | `loi_nhuan_20/60/120/250` | `close_t / close_t-N - 1` | N+1 | ty le |
| Dong luong | `dong_luong_12_1` | `close_t-20 / close_t-250 - 1` | 251 | ty le |
| Dong luong | `suc_manh_tuong_doi_120` | `ret_stock_120 - ret_benchmark_120` | 121 | ty le |
| Bien dong | `bien_dong_20/60` | do lech chuan mau cua daily return | N+1 | ty le/phien |
| Bien dong | `bien_dong_giam_60` | do lech chuan mau cua `min(ret,0)` | 61 | ty le/phien |
| Bien dong | `bien_do_cao_thap_chuan_hoa` | `(high-low)/close` | 1 | ty le |
| Thanh khoan | `gtgd_tb_20/60` | SMA cua `close*volume` | N | don vi gia tri |
| Thanh khoan | `gtgd_hien_tai_tren_tb60` | `close*volume / gtgd_tb_60` | 60 | ty le |
| Thanh khoan | `so_phien_volume_0_60` | dem `volume == 0` | 60 | so phien |
| Regime | `vnindex_tren_ma250` | `index_close >= SMA250` | 250 | boolean |
| Regime | `vnindex_momentum_60` | `close_t/close_t-60-1` | 61 | ty le |
| Regime | `vnindex_bien_dong_20/60` | do lech chuan mau daily return | N+1 | ty le/phien |

Feature bat buoc duoc khai bao bang danh sach co thu tu trong cau hinh. Dòng thieu bat ky feature bat buoc nao bi loai; khong impute ngam.

## 5. Eligibility va bao cao do phu

Eligibility tai T la phep AND fail closed cua:

1. membership point-in-time la `True`;
2. thanh khoan la `True`;
3. du warm-up lon nhat;
4. tat ca feature bat buoc hop le;
5. khong co loi du lieu nghiem trong;
6. khi dua sang backtest, co bar/open hop le o dung phien ke tiep.

Moi ma/ngay bi loai phai co mot hoac nhieu ma ly do xac dinh, vi du:

```text
khong_thuoc_universe
membership_chua_cong_bo
thieu_snapshot
khong_dat_thanh_khoan
thieu_warm_up
thieu_feature_bat_buoc
loi_gia
loi_volume
khong_nhat_quan_co_so_gia
thieu_open_t1
```

Bao cao do phu tong hop theo ma, theo ngay va theo ly do, dong thoi cong bo khoang yeu cau, khoang thuc te, so ma that bai, gap va so ngay thieu `top_k`.

## 6. Nhan

Voi horizon H mac dinh 20 quan sat:

```text
ret_stock_H = close_stock[T+H] / close_stock[T] - 1
ret_benchmark_H = close_benchmark[T+H] / close_benchmark[T] - 1
loi_nhuan_tuong_doi_H = ret_stock_H - ret_benchmark_H
nhan = 1 neu loi_nhuan_tuong_doi_H > 0, nguoc_lai 0
```

`T+H` la dung quan sat thu H sau T trong lich chung da can chinh. Neu co phieu hoac benchmark thieu dung moc cuoi thi nhan rong; khong tim phien xa hon. Dong nhan chua hoan tat khong duoc dua vao train.

## 7. Walk-forward

MVP dung expanding window va tai huan luyen hang thang. Cau hinh bat buoc phai chi ro:

```text
ngay_bat_dau_train
so_thang_train_toi_thieu
so_thang_validation
so_thang_test
label_horizon
purge_phien
embargo_phien
tan_suat_tai_huan_luyen=hang_thang
```

Bat bien:

- `purge_phien >= label_horizon`;
- train ket thuc truoc validation;
- validation ket thuc truoc embargo;
- test bat dau sau embargo;
- test khong tham gia chon feature, C, threshold hoac preprocessing;
- moi du doan luu `ngay_huan_luyen`, `fold` va model id de chung minh model da ton tai truoc T.

## 8. Tien xu ly va model

Thu tu:

1. momentum baseline khong hoc tham so tu test;
2. Logistic Regression cau hinh don gian;
3. luoi C nho, chi chon theo validation.

Pipeline Logistic Regression dung `StandardScaler` va `LogisticRegression`. Scaler nam trong `sklearn.pipeline.Pipeline`, fit rieng tren train cua tung fold. MVP khong impute; dong thieu feature bat buoc da bi loai truoc pipeline.

Metadata model bat buoc:

- Python, uv, scikit-learn va cac version khoa trong lock;
- seed;
- feature order;
- scaler mean/scale;
- C, solver, max_iter;
- coefficients va intercept;
- convergence status/canh bao;
- fold, train interval, validation interval;
- thoi gian huan luyen.

Canh bao hoi tu bi ghi vao san pham; cau hinh co the chon fail run neu khong hoi tu.

## 9. Ranking va adapter Moc 3

Tai ngay tin hieu cuoi thang T:

1. lay universe point-in-time;
2. loc eligibility;
3. lay feature raw den T;
4. ap pipeline model da huan luyen truoc T;
5. tinh `P(nhan=1)`;
6. sap xep giam dan theo xac suat, hoa diem theo ma tang dan;
7. chon `top_k`;
8. chia deu `1 / so_ma_duoc_chon`, phan con lai la tien mat;
9. ghi canh bao neu so ma nho hon `top_k`;
10. chuyen thanh hop dong `ngay_tin_hieu,ma,ty_trong_muc_tieu,ten_chien_luoc`;
11. goi engine Moc 3 de khop tai open dung phien ke tiep.

Adapter khong sao chep engine va khong tu tim phien thuc thi xa hon.

## 10. Chi so

### Model

- ROC-AUC neu du hai lop, nguoc lai `null`;
- log loss;
- Brier score;
- bang calibration theo bin;
- ty le lop duong;
- so quan sat va so ma theo fold.

### Ranking

- precision@K;
- hit rate top-K;
- loi nhuan tuong doi trung binh top-K;
- top decile minus bottom decile khi du ma;
- Spearman rank IC;
- turnover thu hang;
- so ngay thieu `top_k`.

### Backtest OOS

Ke thua NAV, total return, CAGR, maximum drawdown, Sharpe, turnover, phi, thue va truot gia tu engine Moc 3; bo sung ty trong tien mat, so ma trung binh va so lan tai can bang. Chi cac ngay test ngoai mau duoc tong hop.

## 11. Cong bo san pham

Moi lan chay tao thu muc moi trong thu muc tam, ghi va fsync, tinh SHA-256, sau do rename nguyen tu. Khong ghi de. Neu bat ky buoc nao loi, thu muc tam bi xoa va khong tron voi ket qua thanh cong.

Danh sach toi thieu:

```text
cau_hinh.json
bao_cao_do_phu.json
universe_theo_ngay.csv
feature_raw.csv
feature_sau_tien_xu_ly.csv
nhan.csv
folds.csv
mo_hinh.csv
he_so_logistic.csv
du_doan.csv
xep_hang.csv
ty_trong_muc_tieu.csv
chi_so_mo_hinh.json
chi_so_ranking.json
chi_so_backtest.json
bao_cao.json
manifest.json
```

Manifest ghi Git commit, Python, uv, thu vien, seed, nguon OHLCV/universe/benchmark, co so gia, cau hinh feature/label/fold/model/ranking va SHA-256 tung san pham.

## 12. Chien luoc kiem thu

1. **Unit test tinh tay:** feature, nhan, metric, tie-break, top_k va scaler.
2. **Metamorphic test:** them du lieu sau T khong duoc lam thay doi feature, membership, preprocessing hoac du doan tai T.
3. **Leakage sentinel:** chen gia tri cuc lon vao validation/test va chung minh scaler/train coefficients khong doi.
4. **Temporal invariant:** purge, embargo, expanding window, model cutoff va horizon dung chi so quan sat.
5. **Survivorship fixture:** ma roi universe/huy niem yet van ton tai trong qua khu va khong bi xoa khoi dataset lich su.
6. **Integration:** ty trong T dua vao engine Moc 3 va chi khop tai open T+1.
7. **Publication:** khong ghi de, rollback, manifest SHA-256, thu tu cot va tai lap byte-for-byte.
8. **Regression:** toan bo kiem thu Moc 0–3 tiep tuc chay trong cung workflow ngoai tuyen.

CI khong goi Vnstock, khong goi mang va chi dung fixture gia lap trong repository.

## 13. Phu thuoc du kien

- Them `scikit-learn==1.9.0`, khoa bang `uv.lock` cho Python 3.12.
- Khong them LightGBM.
- Khong them pandas trong MVP; du lieu bien doi bang standard library, model nhan ma tran list co thu tu on dinh.
- NumPy va SciPy la phu thuoc bac duoi cua scikit-learn va duoc truy vet trong lock; ma M4 khong phu thuoc truc tiep vao API NumPy neu khong can.

Ly do them scikit-learn: can `Pipeline`, `StandardScaler`, `LogisticRegression` va metric chuan, giam nguy co tu viet sai tien xu ly/model, dong thoi cho phep luu ro cau hinh va he so.

## 14. Rui ro leakage va survivorship bias

- dung `ngay_hieu_luc` ma bo qua `thoi_diem_cong_bo`;
- ap membership hien tai ve qua khu;
- loai ma da huy niem yet khoi toan bo lich su;
- forward-fill gia, volume, benchmark hoac membership;
- tinh feature sau khi da cat train/test nhung dung thong ke toan lich su;
- nhan T+H giao nhau voi validation do purge ngan;
- chon C/feature theo test;
- dung model duoc retrain sau ngay du doan;
- can chinh benchmark bang cach tim phien xa hon;
- dung close T de lap lenh va cung close T de khop;
- tinh corporate actions hai lan khi gia da dieu chinh.

Moi rui ro tren phai co test am hoac bat bien tuong ung.

## 15. Diem can doan 00 xac nhan truoc khi chay du lieu that

1. Nguon lich su VN100 point-in-time; neu khong co, nguon va phuong phap universe proxy.
2. Nguon VNINDEX va y nghia co so gia cua benchmark.
3. Che do gia cua lan xac minh that: `gia_dieu_chinh` hay `gia_khong_dieu_chinh` kem corporate actions day du.
4. Dinh nghia `dong_luong_12_1` du kien: `close[t-20] / close[t-250] - 1`.
5. Horizon cho feature relative strength du kien: 120 phien.
6. Dinh nghia high-low range du kien: `(high-low)/close` tai T, khong rolling them.
7. Bang calibration du kien: 10 bin xac suat co khoang bang nhau; bin rong duoc bo qua.

Cac diem 1–3 la cua chan du lieu that. Cac diem 4–7 co the duoc khoa trong cau hinh va kiem thu ngoai tuyen, nhung can ghi ro trong PR de tranh dien giai khac nhau.
