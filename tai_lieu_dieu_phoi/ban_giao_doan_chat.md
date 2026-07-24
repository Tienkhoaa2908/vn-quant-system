# Bàn giao đoạn chat điều phối

Cập nhật: 2026-07-24

## Bối cảnh

Người dùng xây `VN Quant System` trong Project ChatGPT `Tiến Khoa`.

Kho mã nguồn: `Tienkhoaa2908/vn-quant-system`.

Mô hình làm việc:

- đoạn `00` điều phối trung tâm;
- đoạn `01` đến `06` làm chuyên môn;
- GitHub giữ trạng thái bền vững và là nguồn sự thật.

## Sở thích người dùng

- Trả lời bằng tiếng Việt, hạn chế chêm tiếng Anh.
- Tên tệp và mã tự đặt dùng tiếng Việt không dấu, viết thường và nối bằng dấu gạch dưới.
- Hướng dẫn từng bước, rõ việc tiếp theo.
- Không bịa hướng mới chỉ để tiếp tục.
- Ưu tiên phương pháp có cơ sở, kiểm thử và tái lập.
- Không tuyên bố thành công khi chưa có log thật.

## Trạng thái đã xác minh

- `main` hiện ở commit hợp nhất `b132578b763ead96ad172a1ace68acdff6e36007`.
- Yêu cầu gộp số `1` của Mốc 0 đã được gộp.
- Đầu nhánh Mốc 0 trước khi gộp là `1124e7a7786bffd01a4eea4c8d292c11413ac9f1`.
- Commit triển khai chính của Mốc 0 là `3385e401532e51457b9e9360e17df7af0e021881`.
- Mốc 0 có công cụ kiểm tra CSV và 12 kiểm thử.
- Lần chạy `kiem_tra_tu_dong` số `3`, mã `30094062342`, đã đạt trên đầu nhánh Mốc 0.
- Trước khi tạo nhánh điều phối, không có yêu cầu gộp đang mở.
- `.gitignore` trên `main` chưa có quy tắc riêng cho dữ liệu thị trường thật.

## Trạng thái nhánh điều phối

- Nhánh: `bo_sung-dieu_phoi`.
- Yêu cầu gộp: số `2`, đang mở vào `main`.
- Commit thêm tài liệu ban đầu: `0b3022eacd9087bd60776c5e476e8e9bc9d6674a`.
- Kiểm tra tự động lần `5`, mã `30098791806`, đã đạt trên commit ban đầu.
- Sau cập nhật trạng thái này, phải xác minh lại kiểm tra tự động trên đầu nhánh cuối cùng trước khi đề nghị gộp.

## Phán quyết Mốc 1

Kế hoạch dùng Vnstock Community 4.0.4: **ĐẠT CÓ ĐIỀU KIỆN**.

Điều kiện đầy đủ nằm trong `cong_viec_hien_tai.md`. Các điểm không được bỏ qua:

- thăm dò giao diện thật trước;
- không giả định tham số chọn giá;
- FPT, HPG, MBB là bắt buộc;
- VNINDEX không chặn;
- từng mã có trạng thái riêng;
- không tạo tệp thô lỗi giả;
- đầu ra đúng định dạng đã quy định;
- kiểm tra tự động không dùng mạng;
- dữ liệu thật và khóa không lên GitHub;
- tối thiểu hai commit;
- chưa làm MA250, mô phỏng giao dịch, học máy hoặc chia vốn.

## Quyết định tiếp tục

1. Chỉ đề nghị gộp yêu cầu số `2` khi đầu nhánh cuối cùng kiểm tra tự động đạt.
2. Sau khi tài liệu được gộp và xác minh trên `main`, giao Mốc 1 cho đoạn `01`.
3. Đoạn `01` làm trên nhánh `m1-du_lieu`.
4. Người dùng chạy lần tải thật nhỏ trên máy cá nhân.
5. Kết quả quay về đoạn `00` để rà soát.
6. Không mở Mốc 2 trước khi Mốc 1 được gộp và xác nhận đạt.

## Không được làm trong đoạn 00

- Không tự triển khai Mốc 1.
- Không sửa trực tiếp `main`.
- Không tải toàn bộ VN100.
- Không thêm MA250, mô phỏng giao dịch, học máy hoặc chia vốn.
- Không đưa khóa Vnstock hoặc dữ liệu thật lên GitHub.
- Không ép VNINDEX thành điều kiện chặn.
- Không giả định giao diện nguồn trước bước thăm dò.
