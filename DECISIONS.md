# Cac quyet dinh kien truc

## QD-0001: Khoi tao theo tung lat doc

Moc 0 chi tao mot lat doc chay duoc: doc tep CSV, kiem tra chat luong, xuat bao cao JSON va tra ma thoat.

## QD-0002: Khong phu thuoc thu vien chay ben ngoai

Phan chay cua Moc 0 chi dung thu vien chuan Python de giam rui ro cai dat va giu bo khung nho.

## QD-0003: Ten du an tu dat dung tieng Viet khong dau

Ten thu muc, tep va ham do du an tu dat dung chu thuong, tieng Viet khong dau va dau gach duoi. Ten bat buoc theo cong cu duoc giu nguyen.

## QD-0004: Du lieu gia lap chi phuc vu kiem thu

Moi du lieu trong `tests/du_lieu` la du lieu gia lap, khong duoc su dung nhu du lieu thi truong that.

## QD-0005: Tach nguon du lieu bang giao dien chung

Luon thu thap chi phu thuoc giao dien `nguon_du_lieu`. Chi bo chuyen doi `nguon_vnstock` duoc phep biet chi tiet Vnstock va KBS. Nguon gia lap thuc hien cung giao dien de kiem thu ngoai tuyen.

## QD-0006: Du lieu tho bat bien va trang thai rieng tung ma

Moi tep tho la JSON dang bang va duoc ghi theo ma lan chay duy nhat. Tep da ton tai khong duoc ghi de. Neu mot ma khong co du lieu, khong tao tep tho gia; chi ghi nhat ky that bai da lam sach va tiep tuc ma khac khi an toan.

## QD-0007: Dinh dang san pham Moc 1

Du lieu tho, nhat ky va bao cao chat luong dung JSON. Du lieu chuan hoa va san sang dung CSV UTF-8 voi bay cot cua du an. Du lieu san sang chi duoc tao khi khong co loi chat luong nghiem trong.

## QD-0008: Khoang ngay bat thuong chi la canh bao

Khi hai quan sat lien tiep cach nhau hon bay ngay lich, he thong ghi canh bao. He thong khong tu dien ngay, khong tao ngay giao dich gia va khong chan tep san sang chi vi canh bao nay.

## QD-0009: Vnstock Community 4.0.4 va nguon KBS

Bo chuyen doi khoa dung Vnstock Community `4.0.4`. Giao dien da duoc xac minh tu ma nguon tag `v4.0.4`: `Market().equity/index(symbol).ohlcv(start, end, interval="1D", source="kbs")` tra cac cot `time`, `open`, `high`, `low`, `close`, `volume`.

Vnstock chuyen gia co phieu ve nghin dong, con chi so giu don vi diem. Giao dien cong khai nay khong co tham so chon gia dieu chinh hay chua dieu chinh, vi vay du an khong truyen tham so suy doan.

## QD-0010: VNINDEX la phan mo rong

FPT, HPG va MBB la ba ma bat buoc. VNINDEX duoc thu rieng. That bai, thieu khoi luong hoac y nghia khoi luong chua ro cua VNINDEX khong chan nghiem thu ba ma bat buoc.

## QD-0011: Vnstock khong la phu thuoc mac dinh cua CI

GitHub Actions chi cai moi truong du an va chay kiem thu ngoai tuyen. Nguoi dung chay Vnstock that bang `uv run --with vnstock==4.0.4`. Cach nay giu CI khong can khoa, khong goi nguon thi truong va khong tai du lieu that.

## QD-0012: Dinh dang tap co phieu theo tung thoi diem

Anh chup thanh vien dung CSV UTF-8 voi bon cot bat buoc:

```text
ngay_hieu_luc,ma,nguon,phien_ban
```

`ngay_hieu_luc` dung `YYYY-MM-DD`; `ma` duoc chuan hoa chu hoa; `nguon` khong duoc rong; `phien_ban` co the rong khi nguon khong cung cap. Cap `ngay_hieu_luc,ma` phai duy nhat. Ket qua thanh vien duoc sap xep theo ma de tai lap.

## QD-0013: Chon anh chup va ngan thanh vien tuong lai

Voi moi ngay danh gia `T`, he thong chi xet anh chup co `ngay_hieu_luc <= T` va chon ngay hieu luc lon nhat. Anh chup sau `T` khong duoc su dung. Neu khong co anh chup hop le, quy trinh dung voi loi ro rang; khong suy doan thanh vien va khong gia mao lich su. Khi xuat mot khoang ngay, quy tac nay duoc ap dung rieng cho ngay cua tung dong dau ra.

## QD-0014: Gia tri giao dich va bo loc thanh khoan

Gia tri giao dich ngay:

```text
gia_tri_giao_dich = gia_dong_cua * khoi_luong
```

Gia co phieu dau vao co don vi nghin dong moi co phieu, vi vay `gia_tri_giao_dich` va trung binh cua no co don vi nghin dong. Trung binh truot tinh rieng tung ma, gom quan sat hien tai va cac quan sat truoc do trong `cua_so_thanh_khoan`; khong dung quan sat tuong lai. Ba tham so bat buoc la `cua_so_thanh_khoan`, `so_quan_sat_toi_thieu` va `nguong_thanh_khoan`. Dat nguong khi trung binh lon hon hoac bang nguong. Khong co nguong san xuat mac dinh.

## QD-0015: MA250

`ma250` la trung binh cong don gian cua dung 250 quan sat gia dong cua gan nhat theo tung ma, co bao gom quan sat hien tai. Truoc quan sat thu 250, `ma250` va `tren_ma250` de trong. Khong backfill, khong dung ngay lich va khong truyen du lieu giua cac ma. `tren_ma250=true` khi gia dong cua lon hon hoac bang MA250.

## QD-0016: Dong luong

Voi cua so bat buoc `N > 0`:

```text
dong_luong_N = gia_dong_cua_t / gia_dong_cua_t_tru_N - 1
```

Tinh rieng tung ma theo thu tu phien quan sat. Can toi thieu `N + 1` quan sat; neu thieu thi de trong va ghi trang thai thieu lich su. Khong dat nguong chon co phieu, khong xep hang va khong chon top-N trong Moc 2.

## QD-0017: Du lieu thieu, dau vao khong hop le va khong nhin truoc

He thong khong tu dien gia, khoi luong, ngay giao dich, thanh vien hoac chi bao. Gia dong cua phai la so huu han duong; khoi luong phai la so nguyen khong am; cap `ma,ngay` phai duy nhat. Dau vao co the chua sap xep, nhung duoc sap xep theo `ma,ngay` truoc khi tinh. Moi cua so chi gom quan sat tai hoac truoc ngay cua dong dang tinh.

## QD-0018: Dinh dang dau ra va gioi han Moc 2

Dau ra chinh la CSV UTF-8 co thu tu cot on dinh va bao cao JSON. CSV co it nhat `ma`, `ngay`, `thuoc_tap_co_phieu`, `gia_tri_giao_dich`, `gia_tri_giao_dich_trung_binh`, `dat_thanh_khoan`, `ma250`, `tren_ma250`, `dong_luong`, `trang_thai_lich_su`, dong thoi kem ngay hieu luc, nguon va phien ban anh chup de truy vet. San pham khong duoc ghi de im lang.

Moc 2 khong tao co du dieu kien dau tu tong hop, khong backtest, khong mo phong giao dich, khong hoc may va khong chia von. Cho den khi co nguon lich su dang tin cay duoc doan 00 phe duyet, viec chong thien lech song sot chi duoc kiem chung o cap giao dien va du lieu gia lap; khong tuyen bo da co lich su thanh vien that.

## QD-0019: So nen Vnstock phai duoc yeu cau ro rang

Bo chuyen doi Vnstock nhan `so_nen` tu ben ngoai, xac thuc la so nguyen duong va truyen nguyen gia tri do thanh tham so `count` cua `ohlcv`. Bo chuyen doi khong hard-code `400`. Cac CLI Vnstock dung mac dinh duoc cong bo la `400`, ghi gia tri yeu cau trong bao cao va khong con am tham phu thuoc gioi han mac dinh 100 dong cua nguon.

Bao cao Moc 2 canh bao rieng khi mot ma co duoi 250 phien, vi chua du de tinh MA250, va khi co duoi 260 phien, vi chua dat nguong xac minh du lieu that. Hai canh bao nay khong tu dong bien du lieu hop le thanh loi.

## QD-0020: Cau hinh lan chay duoc cong bo cung ket qua quy trinh

Cau hinh anh huong den viec lay du lieu, nhu `so_nen_yeu_cau`, phai duoc truyen vao `chay_quy_trinh` truoc khi tao san pham. `ket_qua_lan_chay` la nguon duy nhat tao noi dung `tong_hop.json`; stdout dung cung noi dung va chi bo sung duong dan tep tong hop. Khong duoc chen cau hinh bang cach doc va ghi de tep bat bien sau khi cong bo. Cac khoa cau hinh khong duoc trung voi khoa he thong cua tong hop.

## QD-0021: Dong ho giao dich va lenh DAY Moc 3

Tin hieu ngay T chi duoc tao sau khi close T da biet. Lenh chi duoc khop tai open cua dung phien thi truong ke tiep. Neu ma thieu bar hoac thieu open tai ngay do, lenh DAY het han; khong tim phien xa hon va khong thay open bang gia khac.

## QD-0022: Gia khop, phi, thue va partial fill

Mua dung `open * (1 + truot_gia_bps/10000)`; ban dung `open * (1 - truot_gia_bps/10000)`. Phi tinh theo tung chieu; thue chi ap dung phia ban. MVP khong partial fill va khong participation rate: lenh khop toan bo khoi luong hop le hoac bi tu choi.

## QD-0023: Thu tu xu ly tien mat xac dinh

Trong mot ngay, lenh ban duoc xu ly truoc lenh mua; trong moi chieu sap xep ma tang dan. Lenh mua canh tranh tien mat duoc xu ly theo thu tu nay. Khong duoc lam tien mat am, ban vuot vi the hoac tao vi the am.

## QD-0024: Corporate actions MVP va co so gia

Chia tach/co phieu thuong ap dung truoc giao dich va dinh gia trong ngay hieu luc; so luong va lenh cho nhan he so, gia von chia cho cung he so. Co tuc tien mat chi tang tien vao ngay thanh toan. Neu gia da dieu chinh ma van cung cap corporate actions, lan chay bi tu choi de tranh tinh hai lan.

## QD-0025: Chi so Moc 3

Loi nhuan phien la `NAV_t/NAV_(t-1)-1`; maximum drawdown la `min(NAV_t/peak_t-1)`; Sharpe dung do lech chuan mau va lai phi rui ro quy doi theo phien; turnover la `(tong_mua+tong_ban)/(2*NAV_trung_binh)`. Sharpe tra null khi khong du quan sat hoac phuong sai bang 0.

## QD-0026: Cong bo thu muc ket qua nguyen tu

Chin san pham Moc 3 duoc tao trong thu muc tam, fsync va rename nguyen tu sang thu muc lan chay moi. Khong ghi de. Neu cong bo loi, thu muc tam bi xoa. Thu muc thanh cong va that bai khong duoc tron; manifest ghi Git commit, co so gia, dau vao va SHA-256 san pham.

## QD-0027: Baseline khong phai chien luoc san xuat

Mua-va-giu, can-bang-deu va MA250-dong-luong chi la baseline kiem tra engine. Moc 3 khong ket noi SSI, khong hoc may va khong chia von san xuat.

## QD-0028: Co tuc tien mat chot quyen tai ngay hieu luc

Voi `co_tuc_tien_mat`, `ngay_hieu_luc`, `ngay_thanh_toan`, `gia_tri_tien_mat` va `nguon` deu bat buoc. Engine chot so luong duoc huong tai `ngay_hieu_luc`, luu nghia vu theo khoa su kien va chi thanh toan nghia vu do tai `ngay_thanh_toan`. Mua, ban hoac thay doi vi the sau ngay hieu luc khong thay doi quyen. Cung mot su kien khong duoc chot hoac thanh toan hai lan.

## QD-0029: Dinh co lenh mua truoc khop khong phai partial fill

`so_luong_yeu_cau` duoc tao tu NAV, ty trong va close T. Sau khi ban truoc, engine tinh `so_luong_toi_da` tu tien mat kha dung, gia khop open T+1, phi mua, slippage va lot size. `so_luong_chap_nhan` co the nho hon nhu cau va duoc ghi cung `so_luong_bi_giam`/`ly_do_giam`. Day la pre-trade sizing; engine van khong mo phong market partial fill hay participation rate.

## QD-0030: Quy uoc gia von va P&L

Gia von binh quan gom gia khop da co slippage nhung khong gom phi mua. Realized P&L khi ban mot phan hoac toan bo la `(gia_khop_ban - gia_von_binh_quan) * so_luong_ban`, truoc phi ban va thue. Unrealized P&L la `(close - gia_von_binh_quan) * so_luong_con_lai`. Phan vi the con lai giu nguyen gia von; khi dong het, gia von ve 0.

## QD-0031: Phuong trinh doi soat NAV

Cuoi moi phien, engine doi soat:

```text
NAV = von_ban_dau
    + lai_lo_da_thuc_hien_luy_ke
    + lai_lo_chua_thuc_hien
    + co_tuc_tien_mat_luy_ke
    - phi_mua_luy_ke
    - phi_ban_luy_ke
    - thue_ban_luy_ke
```

Slippage duoc cong bo rieng nhung khong tru lan hai vi da nam trong gia khop va gia von/realized P&L. Chenh lech doi soat ngoai sai so tien mat la loi bat bien.

## QD-0032: Eligibility fail closed

Mo hoac tang vi the chi duoc phep khi `thuoc_tap_co_phieu is True` va `dat_thanh_khoan is True`. `False` va `None` deu khong dat. Giam hoac dong vi the van duoc phep, nhung phai ghi canh bao voi hai trang thai eligibility.

## QD-0033: Bien chi phi va so nguyen nghiem ngat

Bat buoc `0 <= truot_gia_bps < 10000`; gia khop va gia tri giao dich phai duong; `phi_ban_bps + thue_ban_bps <= 10000`; tien ban rong khong am. `kich_thuoc_lo` va `so_phien_moi_nam` phai la so nguyen thuc su va duong; float va bool bi tu choi, khong ep ngam ve int.

## QD-0034: Don vi gia va tien phai thong nhat

Cau hinh bat buoc khai bao `don_vi_gia` va `don_vi_tien`, chi ho tro `dong/dong` hoac `nghin_dong/nghin_dong`. Quan he la `gia_tri = gia * so_luong`. Khong cho tron gia nghin dong voi von bang dong. Hai don vi duoc luu trong `cau_hinh.json`, `bao_cao.json` va `manifest.json`.

## QD-0035: Lam sach loi dung chung

`lam_sach_loi` la ham duy nhat cho `bao_cao_loi.json`, stdout va moi log loi do CLI kiem soat. Token, secret, password, API key va Bearer credential bi thay bang `[DA_AN]` truoc khi cong bo.

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

## QD-0046: Feature can theo lich benchmark chinh thuc

Lich benchmark la dau vao rieng. Moi cua so MA/volatility/liquidity va moi endpoint `T-N` duoc xac dinh tren lich nay. Thieu bar dung phien lam feature tuong ung rong; khong forward-fill, tim phien thay the, nen thoi gian hoac lay them bar cu de bu.

## QD-0047: Runner dau-cuoi la cua vao nghien cuu Moc 4

`chay_nghien_cuu_moc_4(...)` doc cac tep cuc bo, dieu phoi PIT, coverage, feature, label, folds, baseline, Logistic Regression, ranking, target weights, engine Moc 3, metrics va publication. CLI chay cung runner; khong co loi goi mang.

## QD-0048: Tai can bang rong phai dong vi the cu

Backtest Moc 4 bat buoc `che_do_ma_khong_xuat_hien=muc_tieu_bang_0`. Moi ngay tai can bang duoc bieu dien ke ca khi khong co ma hop le; ma roi top_k hoac mat eligibility nhan target 0. Engine Moc 3 chay mot chuoi lien tuc va von chi khoi tao mot lan.

## QD-0049: Momentum baseline la mot chien luoc OOS day du

Baseline dung `dong_luong_12_1` tren cung sample test du eligibility voi Logistic Regression, sort giam dan/tie-break ma tang, top_k, `1/top_k`, tien mat cho phan thieu va cung engine/chi phi. Test khong chon tham so baseline.

## QD-0050: Manifest Moc 4 tu tinh va fail closed

Manifest bat buoc co SHA-256 tung dau vao va san pham, Git commit, ma lan chay, UTC, Python/uv/scikit-learn version, nguon/phien ban/co so gia, muc dich, cau hinh feature/label/fold/model/ranking, canh bao va gioi han. Metadata rong hoac thieu bi tu choi.

## QD-0051: NaN va Inf bi tu choi xuyen suot

OHLCV, feature, probability, relative return, metric input va payload CSV/JSON phai huu han theo `math.isfinite`. Metric model/ranking tu xac thuc vai tro test, khoa `(ngay,ma)`, fold/model, probability va nhan; khong am tham dem trung.

## QD-0052: Eligibility M4 la phep AND fail closed

Tai ngay T, ma chi eligible khi dong thoi dat membership PIT, thanh khoan PIT, warm-up, feature bat buoc, chat luong du lieu, benchmark metadata PIT va open hop le tai dung phien T+1 tren lich benchmark. Thanh khoan MVP:

```text
gtgd_tb_20 = mean(gia_dong_cua * khoi_luong)
```

Tinh tren dung 20 phien benchmark ket thuc tai T, don vi dong/phien, khong forward-fill va khong dung du lieu sau T. Gia tri thieu hoac duoi `nguong_gtgd_tb_toi_thieu` ghi `khong_dat_thanh_khoan`. Thieu open dung T+1 ghi `thieu_open_t1`; open T+2 khong thay the.

## QD-0053: Metric backtest chi tinh trong cua so OOS

Moi run khoa `oos_start`, `ngay_bat_dau_metric` va `oos_end`. Engine chi nhan pham vi can de thuc thi tin hieu OOS dau tien; NAV va metric duoc cat tai `ngay_bat_dau_metric..oos_end`. Du lieu train/warm-up truoc OOS khong vao CAGR, Sharpe, turnover hoac cash ratio; du lieu sau `oos_end` khong anh huong metric. Von khoi tao mot lan va chuoi OOS lien tuc.

## QD-0054: Fold test rong fail closed

Sau refit, `selected["test"]` rong tao loi `test_rong`; khong tao prediction test tao loi `khong_co_prediction_test`. Fold khong tang `so_fold_thanh_cong`, khong them test date, ranking hoac ngay tai can bang. Loi duoc cong bo trong coverage va `mo_hinh.csv`.

## QD-0055: Corporate action khong phu thuoc lich tin hieu

Su kien duoc dung khi timestamp cong bo co mui gio, khong sau cutoff bao thu cua ngay hieu luc, ngay hieu luc nam trong cua so backtest va co so gia phu hop. Su kien giua hai ky tai can bang van duoc ap dung dung ngay hieu luc. Cong bo sau ngay hieu luc, ap dung hoi to, su kien trung va gia dieu chinh kem su kien deu bi tu choi.

## QD-0056: Coverage theo ma la point-in-time

Tap phien yeu cau cua tung ma la giao cua khoang nghien cuu, thoi gian tu phien du lieu hop le dau tien, membership PIT va cac phien thuc su can kiem tra. Khong tinh thieu truoc khi ma bat dau hop le hoac sau khi roi universe; `ma_co_gap` chi xet gap ben trong tap phien yeu cau. Chon policy B: dong/ma loi gia hoac volume bi loai co kiem soat, run tiep tuc va coverage ghi ro loi.

## QD-0057: Model audit phan biet selection va refit

`validation_selection` fit scaler/model tren train de chon C va cong bo validation processed rows bang selection scaler/model ID. `final_refit` fit tren train+validation va cong bo test processed rows bang refit scaler/model ID. Audit luu stage, hai model ID, scaler mean/scale, C, coefficients, intercept, n_iter, convergence/warning, candidate errors, feature order, cutoff va scikit-learn version.

## QD-0058: Nghien cuu khong duoc thanh cong rong

Benchmark file phai co dung mot ma va bang `config.benchmark`; MVP khoa VNINDEX. `nghien_cuu` tu choi cong bo neu thieu benchmark metadata PIT, khong co fold test hop le, prediction OOS hoac ngay tai can bang, tat ca fold that bai, coverage/universe duoi nguong, hoac co so gia/corporate actions khong dat. `kiem_tra_ky_thuat` co the tiep tuc nhung bat buoc ghi canh bao.

## QD-0059: Dependency lock bat buoc da nen tang

Preflight Tier A tren Windows phat hien lock cu chi chua wheel manylinux cho NumPy, SciPy va scikit-learn, lam frozen sync that bai voi `BLOCKED_DEPENDENCY_LOCK_LINUX_ONLY_ON_WINDOWS`. Du an giu `package = false` va khai bao `required-environments` cho Linux x86_64 va Windows AMD64; khong dung marker de loai Windows.

Lock da nen tang giu nguyen `scikit-learn==1.9.0`, `numpy==2.3.5`, `scipy==1.17.0`, `joblib==1.5.3`, `narwhals==2.0.1` va `threadpoolctl==3.6.0`. CI bat buoc chay `uv 0.11.32`, `uv lock --check`, frozen sync, compileall va toan bo unittest tren ca `ubuntu-24.04` va `windows-2025`. Sua lock khong thay doi logic Moc 4; Tier A/Tier B va du lieu that van chua chay.
