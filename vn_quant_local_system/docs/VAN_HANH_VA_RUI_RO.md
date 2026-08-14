# Hướng dẫn vận hành và quản trị rủi ro

## Quy trình tuần

1. Mở web local.
2. Đồng bộ dữ liệu mới sau EOD.
3. Nếu sang tháng mới, chạy C3 để tạo canonical ranking tháng trước.
4. Cập nhật holdings và cash.
5. Tạo kế hoạch tuần.
6. Xem danh sách bán trước, sau đó mã mua và số lượng lô lẻ ước tính.
7. Tự quyết định lệnh LO; workstation không kết nối broker.

## Kỷ luật

- Không thay policy chỉ vì preview tuần biến động.
- Không ép giải ngân nếu không đủ mua một cổ phiếu hoặc target gap không đủ.
- Không bán chỉ vì mã rời Top-10 một tháng.
- Chuẩn bị cho drawdown tối thiểu khoảng 25%; stress tương lai có thể lớn hơn.
- Đánh giá theo chu kỳ nhiều năm, không theo vài tuần.

## Dữ liệu và bảo mật

Nếu sync lỗi, dữ liệu cũ giữ nguyên và có thể chạy `--skip-sync`. Web chỉ bind `127.0.0.1`. Credentials DNSE chỉ ở environment, không ghi vào config hoặc output. Dữ liệu local bị `.gitignore`.
