# Danh mục DNSE và kế hoạch tuần V44.2

## 1. Nguồn danh mục

Nút **Đồng bộ danh mục DNSE** dùng API Key/Secret theo cơ chế HMAC của DNSE OpenAPI. Workstation chỉ đọc danh sách tiểu khoản cơ sở, số dư tiền, vị thế cổ phiếu và số lượng có thể bán.

Không yêu cầu trading token, không gửi lệnh và không lưu số tiểu khoản đầy đủ trong giao diện. Snapshot được lưu trong `data/state/workstation.sqlite3`.

Sau khi đồng bộ thành công, holdings DNSE là nguồn mặc định cho planner. Dữ liệu nhập tay chỉ là fallback và sẽ bị thay thế ở lần đồng bộ broker tiếp theo.

## 2. Ngân sách tuần

`Ngân sách mua tuần` là trần chi tiêu của tuần:

```text
spendable = min(ngân sách tuần, tiền khả dụng an toàn từ DNSE)
```

Không tự cộng tiền bán dự kiến. Sau khi thực sự bán và DNSE cập nhật tiền, cần đồng bộ danh mục lại rồi tạo kế hoạch mới.

## 3. Đề xuất mua nhiều mã

V43.1 đã kiểm định baseline một lệnh mua mỗi tuần. V44.2 cho phép nghiên cứu tối đa 1–5 mã, mặc định 3. Planner mua tối thiểu một cổ phiếu cho từng mã Top-10 đang thiếu tỷ trọng mà ngân sách cho phép, sau đó phân bổ phần tiền còn lại nhưng không vượt target gap hoặc concentration cap.

Đây là biến thể mới, chưa được tuyên bố tốt hơn baseline V43.1 trên lịch sử. Mỗi kế hoạch vẫn lưu `single_order_baseline` để so sánh.

## 4. Đề xuất bán

- Top-10: có thể mua thêm nếu thiếu tỷ trọng.
- Hạng 11–20: giữ, không mua thêm.
- Ngoài Top-20 một tháng: theo dõi.
- Ngoài Top-20 hai tháng liên tiếp: `EXIT_CANDIDATE`.
- Quá tỷ trọng rõ rệt: `REVIEW_TRIM`, không phải lệnh bán bắt buộc.
- Chưa có cổ phiếu khả dụng: `WAIT_SELLABLE`.

Mọi nhãn đều là nghiên cứu. Workstation không gửi lệnh broker.
