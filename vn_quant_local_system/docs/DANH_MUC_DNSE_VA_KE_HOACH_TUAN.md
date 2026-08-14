# Danh mục DNSE và kế hoạch tuần V44.5

## 1. Nguồn danh mục

Nút **Đồng bộ danh mục DNSE** dùng API Key/Secret theo cơ chế HMAC của DNSE OpenAPI. Workstation chỉ đọc danh sách tiểu khoản, số dư tiền, vị thế cổ phiếu và số lượng có thể bán.

Không yêu cầu trading token, không gửi lệnh và không lưu số tiểu khoản đầy đủ trong giao diện. Snapshot được lưu trong `data/state/workstation.sqlite3`.

Sau khi đồng bộ thành công, holdings DNSE là nguồn mặc định cho planner. Dữ liệu nhập tay chỉ là fallback và sẽ bị thay thế ở lần đồng bộ broker tiếp theo.

## 2. Cách nhận diện tiểu khoản cơ sở

Payload danh sách tiểu khoản của DNSE có trường `derivativeAccount`. Trường này biểu thị khách hàng đã đăng ký giao dịch phái sinh; nó không chứng minh tiểu khoản đang xét là một tiểu khoản phái sinh.

V44.3 trở đi không còn loại tài khoản chỉ vì `derivativeAccount=true`. Hệ thống chỉ loại một tài khoản khi tên hoặc loại tài khoản ghi rõ `phái sinh`/`derivative`. Với schema chưa rõ, hệ thống thử đọc endpoint số dư và positions ở chế độ STOCK rồi ghi lại chẩn đoán đã che số tài khoản.

## 3. Tiền dự kiến nạp tuần

Trường trên dashboard là khoản tiền người dùng dự kiến nạp thêm trong tuần và chưa nằm trong số dư broker tại thời điểm lập kế hoạch.

```text
tiền có thể giải ngân
= tiền khả dụng DNSE hiện tại
+ tiền dự kiến nạp tuần
```

Nếu khoản tiền đã được nạp và đã xuất hiện trong số dư DNSE trước khi tạo kế hoạch, nhập `0` ở trường tiền dự kiến nạp để tránh tính hai lần.

Tỷ trọng hiện tại, target gap và concentration cap đều được tính trên giá trị danh mục dự kiến sau khi cộng khoản nạp mới.

## 4. Đề xuất mua nhiều mã

V43.1 đã kiểm định baseline một lệnh mua mỗi tuần. V44.2–V44.5 cho phép nghiên cứu tối đa 1–5 mã, mặc định 3. Planner mua tối thiểu một cổ phiếu cho từng mã Top-10 đang thiếu tỷ trọng mà tổng tiền có thể giải ngân cho phép, sau đó phân bổ phần tiền còn lại nhưng không vượt target gap hoặc concentration cap.

Đây là biến thể mới, chưa được tuyên bố tốt hơn baseline V43.1 trên lịch sử. Mỗi kế hoạch vẫn lưu `single_order_baseline` để so sánh.

## 5. Rà soát bán bằng lịch sử đã có

V44.5 không chờ workstation chạy qua hai tháng mới bắt đầu đánh giá bán. Mỗi lần tạo kế hoạch, hệ thống tái dựng ba ranking tháng hoàn tất gần nhất trực tiếp từ:

- kho OHLCV local khoảng 11 năm;
- reference ZIP frozen;
- đúng C3 components, adaptive weights và eligibility của từng tháng.

Tất cả mã đang nắm giữ được rà soát. Gate bán chỉ dùng hai tháng hoàn tất gần nhất:

```text
tháng gần nhất ngoài Top-20
VÀ tháng ngay trước cũng ngoài Top-20
→ EXIT_CANDIDATE
```

Tháng thứ ba được lưu làm ngữ cảnh kiểm định nhưng không phải điều kiện bổ sung.

Trạng thái `INELIGIBLE` do dưới MA250, ADV20 thấp hoặc quá nhiều phiên volume bằng 0 được xem là không thuộc Top-20 eligible. Ngược lại, nếu thiếu lịch sử giá chính xác hoặc mã nằm ngoài frozen reference universe, hệ thống trả `DATA_REVIEW_REQUIRED`, không tự gắn nhãn bán.

Mỗi vị thế lưu:

- ngày của ba snapshot tháng;
- hạng tại từng tháng nếu có;
- trạng thái Top-20, ngoài Top-20, ineligible hoặc thiếu dữ liệu;
- lý do ineligible;
- hai tháng được dùng cho sell gate;
- nguồn đánh giá `RECOMPUTED_FROM_LOCAL_MARKET_AND_REFERENCE_HISTORY`.

## 6. Quy tắc hành động

- Top-10 tháng gần nhất: có thể mua thêm nếu thiếu tỷ trọng.
- Hạng 11–20: giữ, không mua thêm.
- Ngoài Top-20 một tháng: `WATCH`.
- Ngoài Top-20 hai tháng hoàn tất liên tiếp: `EXIT_CANDIDATE`.
- Đủ điều kiện bán nhưng cổ phiếu chưa khả dụng: `WAIT_SELLABLE`.
- Dữ liệu lịch sử không đủ tin cậy: `DATA_REVIEW_REQUIRED`.
- Quá tỷ trọng rõ rệt: `REVIEW_TRIM`, không phải lệnh bán bắt buộc.

Mọi nhãn đều là nghiên cứu. Workstation không gửi lệnh broker.

## 7. Dashboard

Trang **Tổng quan** là nơi thao tác chính. Các nút đồng bộ giá, đồng bộ danh mục, chạy C3 và tạo kế hoạch tuần đều hiển thị kết quả ngay trong trang này. Kết quả vẫn đồng thời được giữ trong các tab chuyên biệt để xem chi tiết.
