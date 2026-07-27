# Đặc tả Mốc 4 — Dữ liệu nhiều năm, đặc trưng, xếp hạng và học máy cơ sở

## 1. Trạng thái

- Trạng thái: **đã được phê duyệt**.
- PR đặc tả: `#9`.
- Merge commit đặc tả: `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`.
- Nhánh triển khai: `m4-dac_trung-xep_hang-hoc_may`.

## 2. Mục tiêu

Mốc 4 xây lớp nghiên cứu cổ phiếu nhiều năm theo quy trình:

```text
universe point-in-time
→ dữ liệu OHLCV nhiều năm
→ kiểm tra độ phủ và chất lượng
→ đặc trưng không nhìn trước
→ nhãn tương lai chỉ dùng khi huấn luyện
→ walk-forward validation
→ Logistic Regression
→ xác suất và xếp hạng cổ phiếu
→ tỷ trọng mục tiêu thử nghiệm
→ backtest bằng engine Mốc 3
```

Mục tiêu không phải ép mô hình tạo lợi nhuận dương. Mục tiêu là một pipeline nghiên cứu có thể kiểm toán, không rò rỉ dữ liệu, tái lập được và đủ rộng để đánh giá trên universe cổ phiếu Việt Nam.

## 3. Phạm vi

### 3.1 Trong phạm vi

- universe VN100 point-in-time khi có nguồn lịch sử được phê duyệt;
- universe thanh khoản cao point-in-time làm phương án thay thế có kiểm soát;
- OHLCV ngày nhiều năm;
- báo cáo độ phủ, lỗi, khoảng trống và lịch sử tối thiểu;
- warm-up cho MA250 và các cửa sổ đặc trưng;
- đặc trưng giá, xu hướng, động lượng, biến động, thanh khoản và market regime;
- nhãn lợi nhuận tương lai không nhìn trước;
- chia tập theo thời gian và walk-forward có purge/embargo;
- baseline heuristic và Logistic Regression;
- xác suất dự báo, stock ranking và `top_k`;
- tích hợp engine Mốc 3 để đánh giá ngoài mẫu;
- báo cáo mô hình, ranking, backtest và chi phí;
- sản phẩm bất biến, SHA-256, Git commit và cấu hình lần chạy.

### 3.2 Ngoài phạm vi

- LightGBM trong lần triển khai đầu tiên;
- deep learning;
- dữ liệu cơ bản doanh nghiệp nếu chưa có nguồn point-in-time đáng tin cậy;
- inverse volatility, giới hạn 15% mỗi mã và 25% mỗi ngành;
- tối ưu danh mục sản xuất;
- paper trading hằng ngày;
- kết nối SSI, đọc tài khoản hoặc gửi lệnh.

Phân bổ vốn thuộc Mốc 5. Paper trading thuộc Mốc 6.

## 4. Nguyên tắc bắt buộc

1. Không dùng danh sách VN100 hiện tại để áp ngược cho lịch sử.
2. Không chỉ giữ các mã còn tồn tại ở hiện tại.
3. Không tự tạo lịch sử thành viên khi thiếu nguồn hợp lệ.
4. Không dùng feature từ dữ liệu sau ngày đánh giá.
5. Không fit scaler, imputer, bộ chọn feature hoặc mô hình trên validation/test.
6. Không random split dữ liệu chuỗi thời gian.
7. Nhãn tương lai không được trộn vào feature.
8. Không backfill giá, volume, membership hoặc feature bị thiếu.
9. Không commit dữ liệu thị trường thật, sản phẩm thật hoặc credential.
10. CI hoàn toàn ngoại tuyến.
11. Cùng dữ liệu và cấu hình phải cho cùng kết quả.
12. Mọi kết luận phải ghi rõ khoảng thời gian, universe, chi phí và giới hạn.

## 5. Các quyết định kiến trúc cần phê duyệt

### QĐ-M4-01 — Universe nghiên cứu

Universe ưu tiên là **VN100 point-in-time**.

Hợp đồng tối thiểu:

```text
ngay_hieu_luc,ma,thuoc_universe,nguon,phien_ban,thoi_diem_cong_bo
```

Tại ngày đánh giá `T`:

- chỉ dùng bản ghi đã có hiệu lực;
- chỉ dùng thông tin đã được công bố không muộn hơn `T`;
- mã vào/rời universe đúng ngày hiệu lực;
- không suy đoán thành viên nếu nguồn không cho phép;
- nguồn và phiên bản phải truy vết được.

Nếu chưa có nguồn VN100 lịch sử đáng tin cậy, dùng **universe thanh khoản cao point-in-time** được tái tạo theo kỳ từ toàn bộ mã niêm yết hợp lệ. Phải gọi rõ là universe proxy, không gọi là VN100 lịch sử.

### QĐ-M4-02 — Khoảng lịch sử

- nghiệm thu kỹ thuật: tối thiểu 3 năm dữ liệu hữu dụng sau warm-up;
- mục tiêu nghiên cứu: ít nhất 5 năm;
- ưu tiên 7–10 năm khi chất lượng dữ liệu cho phép.

```text
khoang_tai = khoang_danh_gia + warm_up + label_horizon
```

Không kéo dài lịch sử bằng dữ liệu chất lượng thấp chỉ để đạt số năm.

### QĐ-M4-03 — Warm-up và eligibility

Warm-up tối thiểu là giá trị lớn nhất của:

- 250 phiên cho MA250;
- cửa sổ momentum dài nhất;
- cửa sổ volatility dài nhất;
- cửa sổ liquidity dài nhất;
- cửa sổ market regime.

Một mã chỉ được xếp hạng tại `T` khi:

- thuộc universe;
- đạt thanh khoản;
- đủ warm-up;
- feature bắt buộc hợp lệ;
- không có lỗi dữ liệu nghiêm trọng;
- có giá thực thi hợp lệ tại phiên kế tiếp khi backtest.

Thiếu điều kiện phải fail closed và ghi lý do.

### QĐ-M4-04 — Cơ sở giá và corporate actions

Mỗi lần chạy chọn đúng một chế độ:

1. `gia_dieu_chinh`, không áp dụng lại corporate actions; hoặc
2. `gia_khong_dieu_chinh`, có corporate actions point-in-time đầy đủ.

Không trộn hai chế độ. Nếu nguồn không xác nhận cơ sở giá hoặc corporate actions chưa đủ, lần chạy chỉ được coi là kiểm tra kỹ thuật.

### QĐ-M4-05 — Feature MVP

#### Xu hướng

- khoảng cách đến MA20, MA60, MA120 và MA250;
- `gia_tren_ma250`;
- tỷ lệ giá so với đỉnh 52 tuần khi đủ dữ liệu.

#### Động lượng

- lợi nhuận 20, 60, 120 và 250 phiên;
- động lượng 12-1;
- relative strength so với chỉ số chuẩn.

#### Biến động

- volatility 20 và 60 phiên;
- downside volatility 60 phiên;
- biên độ high-low chuẩn hóa khi high/low hợp lệ.

#### Thanh khoản

- giá trị giao dịch trung bình 20 và 60 phiên;
- tỷ lệ hiện tại so với trung bình 60 phiên;
- số phiên volume bằng 0 trong cửa sổ 60 phiên.

#### Market regime

- VNINDEX trên/dưới MA250;
- momentum 60 phiên;
- volatility 20 và 60 phiên.

Không thêm hàng trăm chỉ báo tương quan cao trong MVP. Mỗi feature phải có công thức, cửa sổ, đơn vị và quy tắc thiếu dữ liệu.

### QĐ-M4-06 — Tiền xử lý

- lưu feature raw;
- winsorization, clipping, imputation và standardization chỉ fit trên train của từng fold;
- MVP ưu tiên loại dòng thiếu feature bắt buộc, không impute ngầm;
- Logistic Regression dùng standardization fit trong pipeline train;
- không dùng thống kê toàn lịch sử để chuẩn hóa quá khứ.

### QĐ-M4-07 — Nhãn MVP

```text
loi_nhuan_tuong_doi_H = loi_nhuan_co_phieu_H - loi_nhuan_chi_so_chuan_H
nhan = 1 khi loi_nhuan_tuong_doi_H > 0, nguoc_lai 0
```

MVP dùng `H = 20` phiên, nhưng phải cấu hình được.

- mốc đầu là close ngày tín hiệu `T`;
- mốc cuối là close sau đúng `H` quan sát;
- không tự tìm phiên xa hơn khi thiếu dữ liệu;
- dòng cuối không đủ horizon để nhãn trống;
- chỉ số chuẩn dự kiến là VNINDEX, nhưng nguồn và cơ sở giá phải được phê duyệt.

Xác suất `P(nhan=1)` dùng làm điểm ranking, không phải cam kết lợi nhuận.

### QĐ-M4-08 — Walk-forward validation

Không random split. Cấu hình tối thiểu:

```text
ngay_bat_dau_train
so_thang_train_toi_thieu
so_thang_validation
so_thang_test
tan_suat_tai_huan_luyen
label_horizon
embargo_phien
```

Quy tắc:

```text
train quá khứ
→ purge tối thiểu bằng label horizon
→ validation
→ embargo
→ test tương lai
→ dịch cửa sổ
```

MVP dùng expanding window và tái huấn luyện hằng tháng. Test không được dùng chọn feature, `C` hoặc threshold.

### QĐ-M4-09 — Model và baseline

Thứ tự bắt buộc:

1. baseline động lượng;
2. Logistic Regression cấu hình đơn giản;
3. Logistic Regression với lưới `C` nhỏ, chỉ chọn bằng validation;
4. LightGBM chỉ mở bằng quyết định riêng sau khi baseline tuyến tính đạt.

Phải ghi version thư viện, seed, feature order, hệ số, intercept và pipeline tiền xử lý.

### QĐ-M4-10 — Ranking và tái cân bằng

Tại ngày `T`:

1. lấy universe point-in-time;
2. lọc eligibility;
3. tạo feature đến `T`;
4. dùng mô hình đã huấn luyện trước `T`;
5. tính xác suất;
6. xếp hạng giảm dần;
7. hòa điểm dùng mã tăng dần;
8. chọn `top_k`;
9. chia đều chỉ để kiểm tra ranking;
10. khớp bằng engine Mốc 3 ở open phiên kế tiếp.

MVP tái cân bằng hằng tháng vào phiên cuối tháng. `top_k` cấu hình được. Chia vốn sản xuất để Mốc 5.

### QĐ-M4-11 — Chỉ số đánh giá

#### Model

- ROC-AUC khi có đủ hai lớp;
- log loss;
- Brier score;
- calibration;
- tỷ lệ lớp dương;
- số quan sát và số mã theo fold.

#### Ranking

- precision@K;
- hit rate top-K;
- lợi nhuận tương đối trung bình top-K;
- top decile minus bottom decile khi đủ mã;
- Spearman rank IC;
- turnover thứ hạng.

#### Backtest ngoài mẫu

- NAV, total return, CAGR, maximum drawdown và Sharpe;
- turnover, phí, thuế và trượt giá;
- tỷ trọng tiền mặt;
- số mã trung bình;
- số lần không đủ `top_k`.

Không gộp hiệu năng train với out-of-sample.

### QĐ-M4-12 — Sản phẩm và truy vết

Mỗi lần chạy tạo thư mục mới, tối thiểu:

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

Yêu cầu:

- UTF-8;
- thứ tự cột ổn định;
- không ghi đè;
- công bố nguyên tử hoặc tương đương;
- rollback;
- SHA-256;
- Git commit;
- Python, `uv` và version thư viện;
- nguồn dữ liệu, universe và benchmark;
- cơ sở giá;
- cấu hình feature, nhãn, fold, model và ranking;
- lý do loại dữ liệu.

## 6. Hợp đồng dữ liệu

### OHLCV

```text
ma,ngay,gia_mo_cua,gia_cao_nhat,gia_thap_nhat,gia_dong_cua,khoi_luong,nguon,phien_ban,co_so_gia
```

### Universe point-in-time

```text
ngay_hieu_luc,ma,thuoc_universe,nguon,phien_ban,thoi_diem_cong_bo
```

### Chỉ số thị trường

```text
ma_chi_so,ngay,gia_mo_cua,gia_cao_nhat,gia_thap_nhat,gia_dong_cua,khoi_luong,nguon,phien_ban
```

### Corporate actions

```text
ma,loai_su_kien,ngay_hieu_luc,ngay_thanh_toan,ty_le,gia_tri_tien_mat,nguon,phien_ban,thoi_diem_cong_bo
```

## 7. Báo cáo độ phủ

Mỗi lần chuẩn bị dataset phải báo:

- khoảng yêu cầu và khoảng thực tế;
- tổng mã từng xuất hiện trong universe;
- mã có dữ liệu, thất bại hoàn toàn, thiếu warm-up, có khoảng trống;
- mã có giá/volume lỗi;
- mã thiếu corporate actions khi dùng giá không điều chỉnh;
- số mã bị loại theo từng ngày và theo lý do;
- coverage theo ngày và theo mã;
- số ngày có ít hơn `top_k` mã hợp lệ;
- nguồn và phiên bản từng bảng.

Không báo thành công chung chung khi coverage thấp.

## 8. Cửa chất lượng

- không trùng `ma,ngay`;
- không giá không dương hoặc volume âm;
- không dùng membership công bố sau ngày đánh giá;
- không feature tương lai;
- không nhãn rò vào feature;
- scaler/imputer chỉ fit train;
- purge và embargo được kiểm chứng;
- feature order ổn định;
- dự đoán trong `[0,1]`;
- tie-break xác định;
- cùng đầu vào cho cùng SHA-256.

## 9. Kiểm thử bắt buộc

### Universe và dữ liệu

1. không dùng snapshot tương lai;
2. không áp danh sách hiện tại ngược quá khứ;
3. mã vào/rời đúng ngày;
4. công bố sau `T` bị loại;
5. thiếu snapshot thì fail closed;
6. mã mới niêm yết không backfill;
7. thiếu warm-up bị loại;
8. trùng khóa bị từ chối;
9. khoảng trống được báo cáo, không tự điền;
10. cơ sở giá và corporate actions không nhất quán bị từ chối.

### Feature

11. MA250 chỉ có từ quan sát 250;
12. momentum, volatility, liquidity và regime không nhìn trước;
13. feature thiếu không impute ngầm;
14. feature order ổn định;
15. standardization chỉ fit train;
16. validation/test không ảnh hưởng thống kê train.

### Nhãn

17. dùng đúng close T và close T+H;
18. không đủ H thì nhãn trống;
19. thiếu phiên cuối không tìm phiên xa hơn;
20. benchmark cùng khoảng;
21. nhãn không xuất hiện trong feature;
22. horizon chưa hoàn tất không được huấn luyện.

### Walk-forward

23. không random split;
24. train trước validation/test;
25. purge đủ label horizon;
26. embargo được áp dụng;
27. test không chọn `C`;
28. mô hình dùng tại T được huấn luyện trước T;
29. expanding window đúng;
30. fold thiếu hai lớp có xử lý rõ.

### Model và ranking

31. xác suất trong `[0,1]`;
32. cùng seed cho cùng kết quả;
33. lưu hệ số và feature order;
34. ranking giảm dần;
35. hòa điểm dùng mã tăng dần;
36. thiếu mã cho `top_k` được báo cáo;
37. chỉ mã hợp lệ được chọn;
38. tổng tỷ trọng không vượt 1;
39. tín hiệu T khớp T+1 qua Mốc 3.

### Chỉ số và sản phẩm

40. AUC null khi một lớp;
41. log loss và Brier đúng kịch bản tính tay;
42. precision@K đúng kịch bản tính tay;
43. rank IC đúng kịch bản nhỏ;
44. chỉ số chỉ dùng out-of-sample;
45. sản phẩm không ghi đè;
46. rollback khi lỗi;
47. SHA-256 đúng;
48. không trộn thành công/thất bại;
49. hồi quy toàn bộ Mốc 0–3 tiếp tục đạt.

## 10. Xác minh dữ liệu thật

### Tầng A — Bộ nhỏ kiểm toán được

- FPT, HPG, MBB;
- ít nhất 3 năm nếu nguồn cung cấp;
- kiểm tra thủ công một số feature, nhãn, fold và ranking.

### Tầng B — Universe mở rộng

- VN100 point-in-time hoặc universe proxy đã được phê duyệt;
- mục tiêu ít nhất 5 năm sau warm-up;
- báo cáo đầy đủ coverage và mã lỗi;
- không commit dữ liệu hoặc sản phẩm thật.

Nghiệm thu không yêu cầu mô hình có lợi nhuận dương. Nghiệm thu yêu cầu pipeline đúng, không rò rỉ và báo cáo trung thực.

## 11. Tiêu chí hoàn thành

1. Đặc tả được phê duyệt và gộp trước khi viết mã.
2. Nguồn universe point-in-time hoặc proxy được phê duyệt.
3. Nguồn benchmark và cơ sở giá được ghi rõ.
4. Pipeline dữ liệu nhiều năm chạy được.
5. Báo cáo coverage đạt.
6. Feature và nhãn vượt kiểm thử look-ahead.
7. Walk-forward có purge/embargo chạy được.
8. Baseline momentum và Logistic Regression chạy được.
9. Ranking và `top_k` tích hợp Mốc 3.
10. Toàn bộ kiểm thử Python 3.12 đạt.
11. CI ngoại tuyến thành công.
12. Xác minh Tầng A và Tầng B hoàn tất.
13. PR triển khai giữ Draft đến khi đoạn 00 duyệt.
14. CI sau gộp trên `main` thành công.

## 12. Giới hạn phải công bố

- lịch sử VN100 có thể không sẵn từ nguồn miễn phí;
- universe proxy không tương đương VN100 chính thức;
- corporate actions thiếu có thể làm sai lợi nhuận;
- dữ liệu KBS chưa được xác nhận độc lập là điều chỉnh hay không;
- Logistic Regression chỉ là baseline;
- kết quả tốt một giai đoạn không chứng minh tương lai;
- nhiều feature và nhiều lần thử tăng nguy cơ overfitting;
- không tích hợp SSI và không gửi lệnh.

## 13. Quy trình Git dự kiến

Nhánh chuyên môn dự kiến:

```text
m4-dac_trung-xep_hang-hoc_may
```

PR dự kiến:

```text
M4: du lieu nhieu nam, dac trung, xep hang va Logistic Regression
```

PR triển khai phải Draft, không force-push, không tự gộp và không mở Mốc 5.
