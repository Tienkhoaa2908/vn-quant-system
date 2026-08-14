# Mô tả chi tiết hệ thống VN Quant Local

## 1. Mục tiêu

Workstation gom toàn bộ thành phần cần cho việc vận hành, tái kiểm định và phát triển tiếp vào một thư mục độc lập. Dữ liệu lớn được lưu local nhưng bị loại khỏi Git; code, cấu hình và tài liệu được version-control.

## 2. Vì sao dùng web localhost không phụ thuộc framework

Phiên bản đầu dùng HTTP server trong thư viện chuẩn Python, chỉ bind `127.0.0.1`:

- không cần cài thêm package hoặc truy cập Internet;
- giảm lỗi môi trường trên Windows/Git Bash;
- dữ liệu và thao tác không rời máy;
- backend tách thành module, nên sau này có thể thay web layer mà không thay model và kho dữ liệu.

## 3. Tần suất dữ liệu, model và mua tiền mới

- Kho OHLCV: cập nhật incremental sau phiên hoặc khi mở hệ thống.
- C3 canonical: phiên cuối của tháng đã hoàn tất.
- `LATEST_PREVIEW`: phiên mới nhất, chỉ để theo dõi.
- Kế hoạch tuần: ranking tháng gần nhất + holdings + cash + tiền nạp tuần.

Nạp tiền mỗi tuần không yêu cầu retrain hoặc đổi ranking mỗi tuần. Tín hiệu và giải ngân là hai tầng khác nhau.

## 4. Kho dữ liệu

- `data/market/dnse_ohlcv.sqlite3`: OHLCV local khoảng 11 năm, tiếp tục ghi thêm dữ liệu mới.
- `data/reference/daily_prediction_input_v22.zip`: feature và label history dùng khóa adaptive weights C3.
- `data/state/workstation.sqlite3`: run, ranking, holdings, cash và kế hoạch tuần.
- `validation/`: source snapshot, artifact V42/V43.1 và SHA-256.

## 5. Model C3

Ba component:

```text
low_volatility       = percentile của -volatility_60
relative_strength    = percentile của stock_return_120 - VNINDEX_return_120
high_52_week         = percentile của close / max(close_250)
```

Adaptive weights chỉ dùng label quá khứ đã hoàn tất, co 50% về equal weight, giới hạn mỗi component 50%, rồi chuẩn hóa.

Eligibility hiện tại yêu cầu đủ history chính xác theo lịch VNINDEX, giá trên MA250, ADV20 đạt ngưỡng và không có quá nhiều phiên volume 0.

## 6. Portfolio P1

```text
P1_TOP10_UNDERWEIGHT_BUFFER20
```

- Top-10 C3;
- inverse-volatility target weights, cap 15%;
- tối đa một lệnh mua lô lẻ mỗi tuần;
- mua mã có target gap lớn nhất;
- bán khi ngoài Top-20 hai tháng liên tiếp;
- tiền bán được tái sử dụng;
- dynamic cap chỉ dùng trong giai đoạn khởi tạo danh mục.

## 7. Audit trail

Mỗi model run tạo JSON/CSV riêng trong `outputs/`, lưu cùng run ID trong state database và ghi hash input. Pipeline headless tạo ZIP để tải lên phân tích độc lập.
