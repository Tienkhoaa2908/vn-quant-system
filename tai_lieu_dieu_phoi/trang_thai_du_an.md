# Trạng thái dự án

Cập nhật gần nhất: 2026-07-24

## Kho mã nguồn

- Kho: `Tienkhoaa2908/vn-quant-system`.
- Nhánh chính: `main`.
- Commit đầu `main` hiện tại: `b132578b763ead96ad172a1ace68acdff6e36007`.
- Thư mục cục bộ của người dùng: `C:\Users\welcome\Documents\vn-quant-system`.
- Môi trường người dùng: Windows và Git Bash.
- Python mục tiêu: 3.12.
- Công cụ môi trường: `uv`.

## Mốc 0

Trạng thái: **đã hoàn thành, đã kiểm tra và đã gộp vào `main`**.

- Yêu cầu gộp số `1`: đã gộp.
- Commit triển khai chính: `3385e401532e51457b9e9360e17df7af0e021881`.
- Commit đầu nhánh trước khi gộp: `1124e7a7786bffd01a4eea4c8d292c11413ac9f1`.
- Commit hợp nhất trên `main`: `b132578b763ead96ad172a1ace68acdff6e36007`.
- Kiểm tra tự động lần `3`, mã `30094062342`: đạt.
- Phạm vi đã có: công cụ kiểm tra CSV, dữ liệu giả lập, 12 kiểm thử và quy trình kiểm tra tự động.

## Bộ tài liệu điều phối

- Nhánh: `bo_sung-dieu_phoi`.
- Yêu cầu gộp số `2`: đang mở vào `main`, có thể gộp nhưng chưa gộp.
- Commit thêm tài liệu ban đầu: `0b3022eacd9087bd60776c5e476e8e9bc9d6674a`.
- Commit cập nhật trạng thái yêu cầu gộp: `838bd9b9f746771b8b9b3f0d763da6184fd2b060`.
- Kiểm tra tự động lần `6`, mã `30099007729`: đạt trên commit `838bd9b9f746771b8b9b3f0d763da6184fd2b060`.
- Nhánh chỉ thay đổi tám tệp trong `tai_lieu_dieu_phoi/`; không sửa mã Python hoặc logic kiểm tra dữ liệu.
- Sau commit cập nhật kết quả rà soát Mốc 1, phải chờ kiểm tra tự động mới đạt trước khi gộp.

## Mốc 1

Trạng thái điều phối: **đã có bản triển khai nháp, chưa đủ điều kiện gộp**.

Yêu cầu gộp số `3`:

- Nhánh nguồn: `m1-du_lieu`.
- Nhánh đích: `main`.
- Trạng thái: mở, nháp, chưa gộp.
- Commit thứ nhất: `0310e0667f569608676066dfe935fd3f9e782f4f`.
- Commit thứ hai và đầu nhánh: `e6dd3d8125e092cbee2d956269324a96a543e026`.
- Số tệp thay đổi: 21.
- Báo cáo từ đoạn `01`: 30/30 kiểm thử ngoại tuyến đạt trên Python 3.13.
- GitHub chưa có lần chạy kiểm tra tự động hoặc trạng thái commit cho đầu nhánh Mốc 1.
- Chưa có lần thăm dò và tải dữ liệu thật cho FPT, HPG và MBB.

## Kết quả rà soát điều phối Mốc 1

Phán quyết: **YÊU CẦU THAY ĐỔI — CHƯA ĐỦ ĐIỀU KIỆN GỘP**.

Các điểm đạt:

- Có giao diện nguồn và nguồn giả.
- Có lưu dữ liệu thô JSON bất biến, nhật ký JSON và báo cáo chất lượng JSON.
- Có CSV chuẩn hóa và CSV sẵn sàng.
- Có trạng thái riêng theo từng mã.
- Không tạo tệp thô giả khi nguồn không trả dữ liệu.
- Có ít nhất hai commit theo lát cắt đã yêu cầu.
- Không thêm MA250, mô phỏng giao dịch, học máy hoặc chia vốn.

Các điểm chặn:

1. Yêu cầu gộp số `2` chưa được gộp, nhưng nhánh `m1-du_lieu` đã được tách từ `main` cũ. Điều này vi phạm thứ tự điều phối đã thống nhất.
2. Nhánh Mốc 1 phải được cập nhật từ `main` sau khi yêu cầu gộp số `2` được gộp; đồng thời phải cập nhật ba tệp trạng thái điều phối.
3. Chưa có log thăm dò và tải thật cho FPT, HPG, MBB.
4. Chưa có GitHub Actions đạt cho đầu nhánh Mốc 1.
5. Giao diện Vnstock 4.0.4 còn điểm bất nhất cần xác minh: tài liệu PyPI của đúng phiên bản minh họa `Market().equity.ohlcv(symbol=...)`, trong khi bộ chuyển đổi hiện gọi `Market().equity(symbol=...).ohlcv(...)`. Không được chấp nhận bộ chuyển đổi trước khi chạy thăm dò thật và sửa theo giao diện thực tế.
6. Kiểm thử nguồn Vnstock hiện dùng đối tượng giả có cùng giả định với bộ chuyển đổi nên không thể chứng minh giả định giao diện là đúng.
7. Đơn vị giá và cấu trúc phản hồi chỉ mới được kết luận từ mã nguồn hoặc tài liệu; phải đối chiếu bằng một vài dòng phản hồi thật trước khi dùng cho nghiên cứu.

## Thứ tự xử lý tiếp theo

1. Gộp yêu cầu số `2` sau khi kiểm tra tự động của commit tài liệu cuối cùng đạt.
2. Xác minh đầu `main` mới có `tai_lieu_dieu_phoi/`.
3. Cập nhật nhánh `m1-du_lieu` từ `main` mới.
4. Chạy thăm dò thật Vnstock 4.0.4 trước; xác nhận đúng cách gọi, cột, kiểu và đơn vị.
5. Sửa bộ chuyển đổi và kiểm thử ngoại tuyến theo kết quả thăm dò nếu cần.
6. Chạy tải thật nhỏ cho FPT, HPG, MBB; không commit dữ liệu thật.
7. Đẩy commit sửa, chờ GitHub Actions đạt và gửi báo cáo theo từng mã về đoạn `00`.
8. Chỉ khi toàn bộ điều kiện đạt mới chuyển PR số `3` khỏi trạng thái nháp và đề nghị gộp.

## Đoạn chat

- `00`: điều phối trung tâm, rà soát và ghi trạng thái.
- `01`: tiếp tục hoàn thiện Mốc 1 theo yêu cầu thay đổi.
- `02` đến `06`: chưa được phép triển khai.
