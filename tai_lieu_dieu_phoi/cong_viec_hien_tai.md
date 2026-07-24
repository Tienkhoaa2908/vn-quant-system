# Công việc hiện tại

## Công việc điều phối đang hoạt động

Đoạn phụ trách: `00 Điều phối trung tâm`.

- Nhánh `bo_sung-dieu_phoi` đã được tạo từ `main`.
- Yêu cầu gộp số `2` đang mở vào `main`.
- Commit thêm bộ tài liệu ban đầu: `0b3022eacd9087bd60776c5e476e8e9bc9d6674a`.
- Lần kiểm tra tự động số `5`, mã `30098791806`, đã đạt trên commit ban đầu.
- Commit cập nhật trạng thái này phải được kiểm tra lại trước khi đề nghị gộp.
- Không sửa mã Python hoặc logic kiểm tra dữ liệu.
- Không triển khai Mốc 1 trong đoạn `00`.
- Sau khi yêu cầu gộp số `2` được gộp, phải xác minh lại `main` và cập nhật trạng thái trước khi Mốc 1 bắt đầu.

## Phán quyết kế hoạch Mốc 1

**ĐẠT CÓ ĐIỀU KIỆN.**

Đoạn `01 Dữ liệu` chỉ được triển khai sau khi bộ tài liệu điều phối đã được gộp vào `main` và nhận lời giao việc từ đoạn `00`.

## Điều chỉnh bắt buộc cho Mốc 1

1. Trước khi xây toàn bộ bộ chuyển đổi, phải làm một bước thăm dò nhỏ với Vnstock Community 4.0.4 để xác minh:
   - tên cột;
   - kiểu dữ liệu;
   - đơn vị giá;
   - cách lấy dữ liệu ngày;
   - cấu trúc VNINDEX;
   - khả năng chọn giá điều chỉnh hoặc chưa điều chỉnh.
2. Không được giả định tham số `dieu_chinh_gia=false` tồn tại trước khi chạy thăm dò.
3. FPT, HPG và MBB là phạm vi bắt buộc.
4. VNINDEX là phần mở rộng và không được chặn Mốc 1.
5. Mỗi mã phải có trạng thái riêng để một mã lỗi không che mất mã khác.
6. Khi nguồn không trả dữ liệu, chỉ ghi nhật ký thất bại đã làm sạch; không tạo tệp dữ liệu thô lỗi giả.
7. Cảnh báo khoảng ngày bất thường không được tự điền dữ liệu và không được chặn đầu ra.
8. Định dạng đầu ra:
   - dữ liệu thô: JSON dạng bảng;
   - nhật ký: JSON;
   - báo cáo chất lượng: JSON;
   - dữ liệu chuẩn hóa: CSV UTF-8;
   - dữ liệu sẵn sàng: CSV UTF-8.
9. Khóa Vnstock là tùy chọn; kiểm tra tự động không cần khóa.
10. Chia ít nhất hai commit:
    - commit 1: giao diện nguồn, lưu trữ, chuẩn hóa và nguồn giả;
    - commit 2: bộ chuyển đổi Vnstock và lần tải thật nhỏ.
11. Kiểm tra tự động không dùng mạng.
12. Không đưa dữ liệu thật hoặc khóa truy cập lên GitHub.
13. Chưa thêm MA250, mô phỏng giao dịch, học máy hoặc chia vốn.
14. Trước lần tải thật, phải bổ sung quy tắc `.gitignore` phù hợp cho dữ liệu và nhật ký cục bộ.

## Đầu ra bắt buộc từ đoạn 01

- Nhánh `m1-du_lieu`.
- Các commit nhỏ, tối thiểu hai commit theo phạm vi trên.
- Kết quả kiểm thử thật không dùng mạng.
- Hướng dẫn để người dùng chạy một lần tải thật nhỏ trên máy cá nhân.
- Báo cáo riêng cho FPT, HPG và MBB: thành công hoặc thất bại, số dòng, khoảng ngày, đường dẫn đầu ra và lỗi đã làm sạch.
- Báo cáo VNINDEX riêng nếu đã thử; thất bại của VNINDEX không chặn Mốc 1.
- Yêu cầu gộp vào `main`, nhưng chưa gộp.
- Toàn bộ kết quả quay lại đoạn `00` để rà soát.
