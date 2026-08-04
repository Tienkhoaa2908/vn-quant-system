# Danh mục DNSE và kế hoạch tuần V44.3

## 1. Nguồn danh mục

Nút **Đồng bộ danh mục DNSE** dùng API Key/Secret theo cơ chế HMAC của DNSE OpenAPI. Workstation chỉ đọc danh sách tiểu khoản, số dư tiền, vị thế cổ phiếu và số lượng có thể bán.

Không yêu cầu trading token, không gửi lệnh và không lưu số tiểu khoản đầy đủ trong giao diện. Snapshot được lưu trong `data/state/workstation.sqlite3`.

Sau khi đồng bộ thành công, holdings DNSE là nguồn mặc định cho planner. Dữ liệu nhập tay chỉ là fallback và sẽ bị thay thế ở lần đồng bộ broker tiếp theo.

## 2. Cách nhận diện tiểu khoản cơ sở

Payload danh sách tiểu khoản của DNSE có trường `derivativeAccount`. Trường này biểu thị khách hàng đã đăng ký giao dịch phái sinh; nó không chứng minh tiểu khoản đang xét là một tiểu khoản phái sinh.

V44.3 vì vậy không còn loại tài khoản chỉ vì `derivativeAccount=true`. Hệ thống chỉ loại một tài khoản khi tên hoặc loại tài khoản ghi rõ `phái sinh`/`derivative`. Với schema chưa rõ, hệ thống thử đọc endpoint số dư và positions ở chế độ STOCK rồi ghi lại chẩn đoán đã che số tài khoản.

Mỗi snapshot lưu:

- số tiểu khoản DNSE trả về;
- số tiểu khoản được xét;
- số tiểu khoản đọc thành công;
- lỗi balance/positions theo từng tài khoản đã che số;
- chế độ lựa chọn tài khoản.

## 3. Ngân sách tuần

`Ngân sách mua tuần` là trần chi tiêu của tuần:

```text
spendable = min(ngân sách tuần, tiền khả dụng an toàn từ DNSE)
```

Không tự cộng tiền bán dự kiến. Sau khi thực sự bán và DNSE cập nhật tiền, cần đồng bộ danh mục lại rồi tạo kế hoạch mới.

## 4. Đề xuất mua nhiều mã

V43.1 đã kiểm định baseline một lệnh mua mỗi tuần. V44.2/V44.3 cho phép nghiên cứu tối đa 1–5 mã, mặc định 3. Planner mua tối thiểu một cổ phiếu cho từng mã Top-10 đang thiếu tỷ trọng mà ngân sách cho phép, sau đó phân bổ phần tiền còn lại nhưng không vượt target gap hoặc concentration cap.

Đây là biến thể mới, chưa được tuyên bố tốt hơn baseline V43.1 trên lịch sử. Mỗi kế hoạch vẫn lưu `single_order_baseline` để so sánh.

## 5. Đề xuất bán

- Top-10: có thể mua thêm nếu thiếu tỷ trọng.
- Hạng 11–20: giữ, không mua thêm.
- Ngoài Top-20 một tháng: theo dõi.
- Ngoài Top-20 hai tháng liên tiếp: `EXIT_CANDIDATE`.
- Quá tỷ trọng rõ rệt: `REVIEW_TRIM`, không phải lệnh bán bắt buộc.
- Chưa có cổ phiếu khả dụng: `WAIT_SELLABLE`.

Mọi nhãn đều là nghiên cứu. Workstation không gửi lệnh broker.

## 6. Dashboard

Trang **Tổng quan** là nơi thao tác chính. Các nút đồng bộ giá, đồng bộ danh mục, chạy C3 và tạo kế hoạch tuần đều hiển thị kết quả ngay trong trang này. Kết quả vẫn đồng thời được giữ trong các tab chuyên biệt để xem chi tiết.
