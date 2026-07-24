# Quy trình điều phối

## Vai trò đoạn 00

Đoạn `00` là đầu mối quản lý dự án, không phải nơi viết toàn bộ mã nguồn.

1. Đọc trạng thái thật từ GitHub.
2. Xác định mốc đang hoạt động.
3. Phê duyệt, phê duyệt có điều kiện hoặc yêu cầu sửa kế hoạch chuyên môn.
4. Tạo lời giao việc có phạm vi và điều kiện nghiệm thu rõ ràng.
5. Rà soát nhánh, commit, yêu cầu gộp và kết quả kiểm tra tự động.
6. Yêu cầu kết quả từ các đoạn chuyên môn quay lại đoạn `00`.
7. Cập nhật tài liệu điều phối sau thay đổi trạng thái quan trọng.
8. Quyết định có đủ điều kiện gộp và chuyển mốc hay không.

## Vòng đời công việc

1. Đoạn chuyên môn lập kế hoạch, chưa sửa mã.
2. Đoạn `00` rà soát kế hoạch.
3. Đoạn `00` ghi phán quyết và điều kiện vào `cong_viec_hien_tai.md`.
4. Đoạn `00` tạo lời giao việc.
5. Đoạn chuyên môn tạo nhánh riêng và triển khai.
6. Người dùng chạy các bước cần dữ liệu thật hoặc mạng trên máy cá nhân.
7. Đoạn chuyên môn sửa đến khi đạt điều kiện nghiệm thu.
8. Đoạn chuyên môn mở yêu cầu gộp nhưng không tự gộp.
9. Toàn bộ kết quả quay lại đoạn `00`.
10. Đoạn `00` rà soát phạm vi, thay đổi, log và kiểm tra tự động.
11. Chỉ khi đạt mới đề nghị gộp.
12. Sau khi gộp, xác minh lại `main` rồi mới cập nhật mốc tiếp theo.

## Ba tệp phải cập nhật sau thay đổi trạng thái quan trọng

- `trang_thai_du_an.md`
- `cong_viec_hien_tai.md`
- `ban_giao_doan_chat.md`

## Báo cáo bắt buộc từ đoạn chuyên môn

- Việc đã hoàn thành và chưa hoàn thành.
- Danh sách tệp thay đổi và tác dụng của từng tệp.
- Nhánh, các commit và số yêu cầu gộp.
- Lệnh đã chạy và kết quả thực tế.
- Dữ liệu thật đã dùng trên máy cá nhân.
- Kết quả theo từng mã hoặc từng đơn vị công việc.
- Hạn chế còn lại.
- Quyết định cần ghi vào `DECISIONS.md`.
- Kết luận có đủ điều kiện gộp hay chưa.

## Thay đoạn điều phối

1. Cập nhật `ban_giao_doan_chat.md`.
2. Lưu bản lịch sử trong `lich_su_ban_giao/`.
3. Gộp tài liệu cập nhật vào `main`.
4. Đoạn điều phối mới đọc toàn bộ thư mục này, `DECISIONS.md`, các yêu cầu gộp và kết quả kiểm tra tự động.
5. Không dựa vào trí nhớ ngoài kho mã nguồn.
