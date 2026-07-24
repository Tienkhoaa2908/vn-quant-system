# Trạng thái dự án

Cập nhật gần nhất: 2026-07-24

## Kho mã nguồn

- Kho: `Tienkhoaa2908/vn-quant-system`
- Nhánh chính: `main`
- Thư mục cục bộ của người dùng: `C:\Users\welcome\Documents\vn-quant-system`
- Môi trường người dùng: Windows và Git Bash.
- Python mục tiêu: 3.12.
- Công cụ môi trường: `uv`.

## Trạng thái đã xác minh trên GitHub trước nhánh điều phối

- Commit mới nhất của `main`: `b132578b763ead96ad172a1ace68acdff6e36007`.
- Nội dung commit: hợp nhất yêu cầu gộp số `1` từ nhánh `m0-khoi_tao`.
- Yêu cầu gộp số `1`: đã gộp vào `main`.
- Commit đầu nhánh Mốc 0 trước khi gộp: `1124e7a7786bffd01a4eea4c8d292c11413ac9f1`.
- Commit triển khai chính của Mốc 0: `3385e401532e51457b9e9360e17df7af0e021881`.
- Kiểm tra tự động `kiem_tra_tu_dong`, lần chạy `3`, mã lần chạy `30094062342`: hoàn tất và đạt trên commit đầu nhánh Mốc 0.
- Không có yêu cầu gộp đang mở trước khi tạo nhánh `bo_sung-dieu_phoi`.

## Nhánh điều phối

- Nhánh: `bo_sung-dieu_phoi`.
- Commit thêm bộ tài liệu ban đầu: `0b3022eacd9087bd60776c5e476e8e9bc9d6674a`.
- Yêu cầu gộp: số `2`, đang mở vào `main`.
- Lần chạy `kiem_tra_tu_dong` số `5`, mã `30098791806`, đã đạt trên commit thêm bộ tài liệu ban đầu.
- Chênh lệch ban đầu chỉ gồm tám tệp trong `tai_lieu_dieu_phoi/`; không sửa mã Python hoặc kiểm thử.
- Mọi commit bổ sung trên yêu cầu gộp số `2` phải được kiểm tra lại trước khi gộp.

## Mốc 0

Trạng thái: **đã hoàn thành, đã kiểm tra và đã gộp vào `main`**.

Phạm vi đã có trên `main`:

- Bộ khung Python 3.12 và `uv`.
- Gói `he_thong_dinh_luong`.
- Công cụ kiểm tra tệp CSV giá.
- Dữ liệu giả lập hợp lệ và có lỗi.
- Mười hai kiểm thử.
- Quy trình kiểm tra tự động trên GitHub.

Bằng chứng mã nguồn:

- Tệp hợp lệ có hai dòng dữ liệu và cho phép khối lượng bằng `0`.
- Tệp có lỗi chứa lỗi trùng mã/ngày, giá cao nhất, giá thấp nhất, giá không dương, khối lượng âm và ngày tương lai.
- Bộ kiểm thử có 12 trường hợp tương ứng.
- Quy trình tự động cài Python 3.12, đồng bộ bằng `uv`, kiểm tra cú pháp và chạy `unittest`.

## Mốc 1

Trạng thái: **kế hoạch đạt có điều kiện, chưa triển khai**.

Nguồn dự kiến: Vnstock Community phiên bản 4.0.4, nhưng phải thăm dò giao diện thật trước khi xây bộ chuyển đổi.

Phạm vi bắt buộc:

- FPT.
- HPG.
- MBB.

VNINDEX là phần mở rộng; thất bại hoặc khác biệt cấu trúc của VNINDEX không được chặn nghiệm thu Mốc 1.

## Đoạn chat

- `00`: đầu mối điều phối trung tâm.
- `01`: chỉ bắt đầu triển khai sau khi tài liệu điều phối được gộp và nhận lời giao việc có điều kiện.
- `02` đến `06`: chưa được phép triển khai.

## Rủi ro và việc phải xử lý ở Mốc 1

1. Chưa xác minh tên cột, kiểu dữ liệu, đơn vị giá và cách lấy dữ liệu ngày của Vnstock 4.0.4.
2. Chưa xác minh cấu trúc VNINDEX và ý nghĩa trường khối lượng.
3. Không được giả định tham số `dieu_chinh_gia=false` hoặc tham số tương đương tồn tại.
4. `.gitignore` hiện tại chưa có quy tắc riêng cho thư mục dữ liệu thật; nhánh Mốc 1 phải bổ sung quy tắc bỏ qua trước lần tải thật.
5. Kiểm tra tự động không được gọi mạng hoặc yêu cầu khóa Vnstock.
6. Không đưa dữ liệu thật hoặc khóa truy cập lên GitHub.
