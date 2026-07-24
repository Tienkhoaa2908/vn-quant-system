# Công việc hiện tại

Cập nhật: 2026-07-24

## Đoạn phụ trách

`00 Điều phối trung tâm`.

## Việc ưu tiên số 1 — hoàn tất bộ tài liệu điều phối

Yêu cầu gộp số `2` từ nhánh `bo_sung-dieu_phoi` vào `main` đang mở.

- Đầu nhánh trước cập nhật rà soát Mốc 1: `838bd9b9f746771b8b9b3f0d763da6184fd2b060`.
- Kiểm tra tự động lần `6`, mã `30099007729`, đã đạt trên commit đó.
- Commit hiện tại bổ sung kết quả rà soát yêu cầu gộp số `3` vào ba tệp trạng thái.
- Chỉ gộp yêu cầu số `2` sau khi kiểm tra tự động của commit tài liệu cuối cùng đạt.
- Sau khi gộp, phải xác minh đầu `main` mới có nguyên thư mục `tai_lieu_dieu_phoi/`.

## Phán quyết triển khai Mốc 1

Yêu cầu gộp số `3` — `m1-du_lieu` vào `main`:

**YÊU CẦU THAY ĐỔI — CHƯA ĐỦ ĐIỀU KIỆN GỘP.**

### Nội dung đã đạt ở mức rà soát mã

- Có giao diện nguồn chung và nguồn giả ngoại tuyến.
- Có lưu JSON thô bất biến, JSON nhật ký và JSON báo cáo chất lượng.
- Có CSV chuẩn hóa và CSV sẵn sàng.
- Có trạng thái độc lập theo từng mã.
- Không tạo tệp thô giả khi nguồn không trả dữ liệu.
- Có cơ chế làm sạch lỗi và thử lại lỗi tạm thời.
- Có cảnh báo khoảng ngày không chặn đầu ra.
- Có hai commit tách theo lát cắt đã giao.
- Có hướng dẫn thăm dò và tải thật nhỏ.
- Không có dữ liệu thật hoặc khóa truy cập trong danh sách tệp thay đổi.
- Không triển khai MA250, mô phỏng giao dịch, học máy hoặc chia vốn.

### Điều kiện chặn bắt buộc

1. Yêu cầu gộp số `2` phải được gộp và xác minh trước.
2. Nhánh `m1-du_lieu` phải được cập nhật từ đầu `main` mới sau khi yêu cầu số `2` được gộp.
3. Ba tệp trạng thái trong `tai_lieu_dieu_phoi/` phải được cập nhật trên nhánh Mốc 1 khi trạng thái thay đổi.
4. Phải chạy thăm dò thật Vnstock Community 4.0.4 cho FPT, HPG và MBB.
5. Phải xác minh bằng phản hồi thật:
   - cách gọi giao diện;
   - tên cột;
   - kiểu dữ liệu;
   - đơn vị giá;
   - khả năng chọn giá điều chỉnh hoặc chưa điều chỉnh.
6. Cần xử lý bất nhất giao diện: bộ chuyển đổi hiện dùng `Market().equity(symbol=ma).ohlcv(...)`, trong khi tài liệu gói của phiên bản 4.0.4 có ví dụ `Market().equity.ohlcv(symbol=ma, ...)`. Không được đoán; kết quả chạy thật quyết định cách gọi.
7. Phải chạy tải thật nhỏ cho FPT, HPG và MBB và gửi nhật ký riêng từng mã.
8. GitHub Actions phải được tạo và đạt trên commit đầu nhánh cuối cùng của yêu cầu gộp số `3`.
9. Phải chạy lại kiểm thử trên Python 3.12; kết quả Python 3.13 chỉ là bằng chứng bổ sung.
10. PR số `3` tiếp tục ở trạng thái nháp và không được gộp cho đến khi đoạn `00` rà soát lại.

## Việc giao lại cho đoạn 01

Theo đúng thứ tự:

1. Chờ yêu cầu số `2` được gộp.
2. Cập nhật `m1-du_lieu` từ `main` mới.
3. Chạy bước thăm dò thật trước khi sửa hoặc xác nhận bộ chuyển đổi.
4. Sửa giao diện và kiểm thử theo phản hồi thật nếu cần.
5. Chạy tải thật nhỏ cho FPT, HPG, MBB trên máy người dùng.
6. Không commit thư mục `du_lieu/` hoặc nhật ký thật.
7. Đẩy các commit sửa nhỏ, giữ PR số `3` ở trạng thái nháp.
8. Chờ GitHub Actions đạt.
9. Gửi về đoạn `00`:
   - mã commit đầu nhánh mới;
   - kết quả kiểm thử Python 3.12;
   - trạng thái CI;
   - báo cáo riêng FPT, HPG, MBB;
   - các điểm đã sửa sau thăm dò;
   - kết luận đề nghị gộp hay chưa.

## Phạm vi bị khóa

- Chưa mở Mốc 2.
- Chưa thêm MA250 hoặc động lượng.
- Chưa mô phỏng giao dịch.
- Chưa học máy.
- Chưa chia vốn.
- Chưa tải toàn bộ VN100.
