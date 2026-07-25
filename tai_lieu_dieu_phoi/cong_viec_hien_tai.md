# Công việc hiện tại

Cập nhật: 2026-07-25

## Đoạn phụ trách

Đoạn `04` phụ trách triển khai Mốc 4 theo đặc tả đã phê duyệt; đoạn `00` tiếp tục điều phối và nghiệm thu.

## Nền bắt buộc

- Kho: `Tienkhoaa2908/vn-quant-system`.
- `main`: `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`.
- Nhánh chuyên môn: `m4-dac_trung-xep_hang-hoc_may`.
- Base đã duyệt: `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`.
- Tài liệu bắt buộc: `tai_lieu/dac_ta_moc_4.md`.
- Không force-push.
- Không sửa trực tiếp `main`.
- Không commit tệp dưới `du_lieu/`.
- Không mở Mốc 5.

## Cửa đã hoàn tất

- PR đặc tả số 9 đã được phê duyệt và gộp bằng merge commit.
- CI sau gộp trên `main`:
  - run `#187`;
  - Run ID `30162993192`;
  - Job ID `89691237408`;
  - checkout `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`;
  - `completed/success`.
- Nhánh Mốc 4 đã được tạo đúng từ merge commit đặc tả.

## Công việc Mốc 4

1. Đọc toàn bộ đặc tả và mã Mốc 1–Mốc 3.
2. Chốt kiến trúc module trước khi viết phần lớn mã.
3. Mở CI cho nhánh Mốc 4 mà không làm giảm kiểm tra hiện có.
4. Xây hợp đồng universe point-in-time và báo cáo coverage.
5. Xây feature không nhìn trước.
6. Xây nhãn lợi nhuận tương đối 20 phiên.
7. Xây walk-forward expanding window có purge/embargo.
8. Triển khai momentum baseline và Logistic Regression.
9. Xây ranking, `top_k` và adapter sang engine Mốc 3.
10. Bổ sung chỉ số model, ranking và backtest ngoài mẫu.
11. Bổ sung công bố bất biến, SHA-256 và kiểm thử chống leakage.
12. Mở PR Draft và giữ Draft đến khi đoạn 00 phê duyệt.
13. Chỉ chạy dữ liệu thật sau khi kiểm thử ngoại tuyến và CI đạt, đồng thời được đoạn 00 mở cửa.

## Cửa kiểm soát

- Chưa có mã Mốc 4 tại thời điểm bàn giao nhánh.
- Chưa mở PR triển khai.
- LightGBM không nằm trong lần triển khai đầu tiên.
- Không kết nối SSI, không đọc tài khoản và không gửi lệnh.
- Mốc 5 chưa mở.
