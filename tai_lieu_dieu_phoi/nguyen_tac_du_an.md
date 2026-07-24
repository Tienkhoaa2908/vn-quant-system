# Nguyên tắc dự án

## Mục tiêu

Xây hệ thống định lượng cho cổ phiếu Việt Nam theo luồng:

dữ liệu → kiểm tra chất lượng → tập cổ phiếu theo từng thời điểm → đặc trưng → chấm điểm → chia vốn → mô phỏng giao dịch → giao dịch giả lập.

## Quy tắc kỹ thuật bắt buộc

1. GitHub, đặc biệt là trạng thái đã gộp vào `main`, là nguồn sự thật.
2. Không sửa trực tiếp nhánh `main`.
3. Mỗi mốc dùng một nhánh riêng, có kiểm thử và yêu cầu gộp.
4. Không dùng dữ liệu tương lai.
5. Tín hiệu hình thành sau phiên `t`; lệnh sớm nhất ở phiên `t+1`.
6. Không chia ngẫu nhiên dữ liệu chuỗi thời gian.
7. Không dùng danh sách cổ phiếu hiện tại thay cho lịch sử thành phần.
8. Không tự điền dữ liệu thiếu khi chưa có lịch giao dịch đáng tin cậy.
9. Không bịa dữ liệu, giao diện nguồn, tham số nguồn hoặc kết quả kiểm thử.
10. Không tuyên bố hoàn thành khi chưa có log chạy thật.
11. Không đưa khóa, mật khẩu, `.env` hoặc dữ liệu thị trường thật lên GitHub.
12. Ưu tiên kiến trúc đơn khối có mô-đun, chạy theo lô và chạy trên máy cá nhân.
13. Chỉ tăng độ phức tạp sau khi lát cắt đơn giản đã chạy đúng.
14. Chưa dùng học sâu trước khi đường cơ sở và LightGBM đáng tin cậy.
15. Không chuyển sang mốc mới khi mốc hiện tại chưa được gộp và xác minh trên `main`.

## Quy ước ngôn ngữ

- Giải thích bằng tiếng Việt, hạn chế chêm tiếng Anh.
- Tên tệp, thư mục, hàm và cấu trúc tự đặt dùng tiếng Việt không dấu, viết thường và nối bằng dấu gạch dưới.
- Tên bắt buộc theo công cụ như `README.md`, `pyproject.toml`, `.gitignore`, `uv.lock`, `.github` được giữ nguyên.

## Phạm vi các đoạn chat

- `00 Điều phối trung tâm`: trạng thái, kế hoạch, giao việc, rà soát, nghiệm thu và bàn giao.
- `01 Dữ liệu`: thu thập, lưu, chuẩn hóa và kiểm tra dữ liệu.
- `02 Mô phỏng giao dịch`: tín hiệu, lệnh, phí, thuế, tiền mặt và vị thế.
- `03 Đặc trưng và học máy`: đặc trưng, nhãn và xếp hạng cổ phiếu.
- `04 Chia vốn`: tỷ trọng, giới hạn mã, ngành và tiền mặt.
- `05 Kiểm toán hệ thống`: tìm rò rỉ dữ liệu, thiên lệch và giả định phi thực tế.
- `06 Giao dịch giả lập`: vận hành hằng ngày mà chưa dùng tiền thật.
