# Bản bàn giao lịch sử — 2026-07-24

## Nguồn bàn giao

Tổng hợp từ đoạn chat hỗ trợ:

- kết nối GitHub;
- tạo và nhân bản kho;
- khởi tạo Mốc 0;
- cài và chạy `uv`;
- chạy kiểm thử trong Git Bash;
- thiết kế các đoạn 00 đến 06;
- rà soát kế hoạch Mốc 1.

## Sự kiện chính theo bản bàn giao ban đầu

1. Kho `Tienkhoaa2908/vn-quant-system` được tạo và nhân bản.
2. Mốc 0 triển khai trên `m0-khoi_tao`.
3. Commit được báo: `3385e401532e51457b9e9360e17df7af0e021881`.
4. Mốc 0 có 12 kiểm thử và công cụ kiểm tra CSV.
5. Người dùng dùng Git Bash; lệnh kiểm thử có `PYTHONPATH=src`.
6. Đoạn `01 Dữ liệu` lập kế hoạch Mốc 1.
7. Đoạn 01 chọn Vnstock Community và lưu dữ liệu bất biến.
8. Kế hoạch được chấp nhận có điều kiện.

## Xác minh lại với GitHub

Các mã và trạng thái sau đã được xác minh, không chỉ dựa vào bản bàn giao:

- Commit triển khai chính: `3385e401532e51457b9e9360e17df7af0e021881`.
- Commit đầu nhánh trước khi gộp: `1124e7a7786bffd01a4eea4c8d292c11413ac9f1`.
- Yêu cầu gộp Mốc 0: số `1`, trạng thái đã gộp.
- Commit hợp nhất trên `main`: `b132578b763ead96ad172a1ace68acdff6e36007`.
- Kiểm tra tự động trên đầu nhánh Mốc 0: lần chạy `3`, mã `30094062342`, kết quả đạt.
- Trước nhánh điều phối không có yêu cầu gộp đang mở.

## Kiến trúc

- Đơn khối có mô-đun.
- Chạy theo lô.
- Chạy trên máy cá nhân.
- GitHub là nguồn sự thật.
- Mỗi mốc là một lát cắt chạy được.
- Đoạn `00` điều phối; đoạn `01` đến `06` làm chuyên môn.

## Bài học

- Nhân bản kho không đồng nghĩa một công cụ khác có quyền đọc kho.
- Kết nối GitHub phải được cấp quyền cho đúng kho.
- PowerShell và Git Bash có cú pháp biến môi trường khác nhau.
- Không nhầm lỗi môi trường với lỗi logic.
- Mã commit trong tài liệu bàn giao phải được xác minh với GitHub.
- Trạng thái phải nằm trong GitHub để thay đoạn chat mà không mất ngữ cảnh.
