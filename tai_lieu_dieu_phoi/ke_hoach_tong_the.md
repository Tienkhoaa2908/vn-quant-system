# Kế hoạch tổng thể

## Mốc 0 — Nền tảng và kiểm tra dữ liệu

Trạng thái: **đã hoàn thành, kiểm tra tự động đạt và đã gộp vào `main` qua yêu cầu gộp số 1**.

Kết quả:

- Python 3.12 và `uv`.
- Gói `he_thong_dinh_luong`.
- Công cụ kiểm tra CSV giá.
- Dữ liệu giả lập hợp lệ và có lỗi.
- 12 kiểm thử.
- Quy trình kiểm tra tự động trên GitHub.

## Mốc 1 — Dữ liệu thị trường thật

Trạng thái: kế hoạch đạt có điều kiện, chưa triển khai.

- Thăm dò Vnstock Community 4.0.4 trước khi xây bộ chuyển đổi đầy đủ.
- Kết nối một nguồn thật cho FPT, HPG và MBB.
- VNINDEX là phần mở rộng, không phải điều kiện chặn.
- Lưu dữ liệu thô bất biến dưới dạng JSON dạng bảng.
- Ghi nhật ký JSON và mã SHA-256.
- Chuẩn hóa về bảy cột trong CSV UTF-8.
- Tạo dữ liệu sẵn sàng trong CSV UTF-8.
- Dùng lại kiểm tra chất lượng Mốc 0 và xuất báo cáo JSON.
- Kiểm thử bằng nguồn giả, không cần mạng hoặc khóa.
- Người dùng chạy lần tải thật nhỏ trên máy cá nhân.
- Không đưa dữ liệu thật hoặc khóa lên GitHub.

Không thuộc Mốc 1: MA250, mô phỏng giao dịch, học máy, chia vốn hoặc tải toàn bộ VN100.

## Mốc 2 — Tập cổ phiếu và đường cơ sở

Chỉ bắt đầu sau khi Mốc 1 đã được gộp và xác minh.

- Tập cổ phiếu theo từng thời điểm.
- Bộ lọc thanh khoản.
- MA250 và động lượng.
- Chưa dùng học máy.

## Mốc 3 — Mô phỏng giao dịch

- Khớp lệnh từ phiên kế tiếp.
- Phí, thuế bán, trượt giá và lô giao dịch.
- Tiền mặt, vị thế, lệnh, khớp lệnh và nhật ký.
- Báo cáo lợi nhuận, mức giảm, Sharpe, chi phí và vòng quay.

## Mốc 4 — Đặc trưng và học máy

- Đặc trưng giá, động lượng, biến động, thanh khoản và thị trường.
- Nhãn lợi nhuận vượt chỉ số và hàng rào ba mức.
- Chia cuốn chiếu theo thời gian.
- Hồi quy lô-gic trước, LightGBM sau.

## Mốc 5 — Chia vốn

- Chọn nhóm mã đứng đầu.
- Chia vốn ngược theo độ biến động.
- Tối đa 15% mỗi mã, 25% mỗi ngành.
- Tiền mặt theo trạng thái thị trường.

## Mốc 6 — Kiểm toán và giao dịch giả lập

- Rà soát rò rỉ dữ liệu, thiên lệch sống sót và tối ưu quá mức.
- Chạy danh mục giả lập hằng ngày.
- Chỉ cân nhắc tiền thật sau thời gian giả lập ổn định.
