# Bàn giao đoạn chat điều phối

Cập nhật: 2026-07-24

## Vai trò

- Đoạn `00` là đầu mối điều phối trung tâm.
- Đoạn `01` đến `06` phụ trách chuyên môn theo nhiệm vụ được giao.
- GitHub là nguồn sự thật về nhánh, commit, yêu cầu gộp và kiểm tra tự động.
- Không chuyển mốc khi mốc hiện tại chưa được gộp và xác minh.

## Trạng thái bền vững đã xác minh

### Mốc 0

- Yêu cầu gộp số `1`: đã gộp.
- Commit triển khai chính: `3385e401532e51457b9e9360e17df7af0e021881`.
- Commit đầu nhánh trước khi gộp: `1124e7a7786bffd01a4eea4c8d292c11413ac9f1`.
- Đầu `main`: `b132578b763ead96ad172a1ace68acdff6e36007`.
- Kiểm tra tự động Mốc 0: đạt.

### Bộ tài liệu điều phối

- Nhánh: `bo_sung-dieu_phoi`.
- Yêu cầu gộp số `2`: đang mở vào `main`, chưa gộp.
- Commit trước kết quả rà soát Mốc 1: `838bd9b9f746771b8b9b3f0d763da6184fd2b060`.
- Kiểm tra tự động lần `6`, mã `30099007729`: đạt trên commit đó.
- Commit hiện tại cập nhật ba tệp trạng thái theo kết quả rà soát Mốc 1; phải chờ kiểm tra tự động mới trước khi gộp.

### Mốc 1

- Yêu cầu gộp số `3`: mở, nháp, chưa gộp.
- Nhánh: `m1-du_lieu`.
- Đầu nhánh: `e6dd3d8125e092cbee2d956269324a96a543e026`.
- Hai commit đã báo cáo:
  1. `0310e0667f569608676066dfe935fd3f9e782f4f` — lát cắt dữ liệu ngoại tuyến.
  2. `e6dd3d8125e092cbee2d956269324a96a543e026` — nguồn Vnstock và lệnh tải thật nhỏ.
- Báo cáo đoạn `01`: 30/30 kiểm thử đạt trên Python 3.13.
- Không có GitHub Actions hoặc trạng thái commit cho đầu nhánh Mốc 1.
- Chưa có thăm dò và tải thật FPT, HPG, MBB.

## Phán quyết điều phối hiện tại

Yêu cầu gộp số `3`:

**YÊU CẦU THAY ĐỔI — CHƯA ĐỦ ĐIỀU KIỆN GỘP.**

Lý do chính:

1. Bộ tài liệu điều phối chưa được gộp vào `main`, nhưng Mốc 1 đã được triển khai từ nền `main` cũ.
2. Chưa có phản hồi chạy thật của Vnstock cho ba mã bắt buộc.
3. Chưa có kiểm tra tự động GitHub cho đầu nhánh Mốc 1.
4. Chưa chạy kiểm thử trên Python mục tiêu 3.12.
5. Cách gọi giao diện Vnstock trong bộ chuyển đổi chưa được chứng minh bằng chạy thật và có khác biệt với ví dụ công khai của gói 4.0.4.
6. Đơn vị giá và hợp đồng cột chưa được đối chiếu bằng dữ liệu trả về thực tế.

## Điểm kỹ thuật đã rà soát

- Kiến trúc giao diện nguồn, nguồn giả, chuẩn hóa, lưu trữ bất biến và trạng thái từng mã phù hợp hướng đã giao.
- Quy trình không tạo tệp thô giả khi nguồn thất bại.
- Định dạng đầu ra phù hợp yêu cầu Mốc 1.
- Kiểm thử bộ chuyển đổi hiện dựa trên đối tượng giả mô phỏng đúng giả định của chính bộ chuyển đổi; đây không phải bằng chứng giao diện Vnstock thật.
- VNINDEX vẫn là phần mở rộng, không chặn FPT, HPG và MBB.

## Trình tự bắt buộc tiếp theo

1. Chờ kiểm tra tự động của commit tài liệu điều phối cuối cùng đạt.
2. Gộp yêu cầu số `2` vào `main`.
3. Xác minh đầu `main` có `tai_lieu_dieu_phoi/`.
4. Cập nhật nhánh `m1-du_lieu` từ `main` mới.
5. Chạy thăm dò thật Vnstock 4.0.4.
6. Sửa bộ chuyển đổi nếu giao diện thật khác giả định.
7. Chạy tải thật nhỏ cho FPT, HPG, MBB.
8. Chạy kiểm thử Python 3.12 và GitHub Actions.
9. Gửi kết quả mới về đoạn `00` để nghiệm thu.
10. Chỉ chuyển PR số `3` khỏi trạng thái nháp khi đoạn `00` kết luận đủ điều kiện.

## Không được làm

- Không gộp PR số `3` ở trạng thái hiện tại.
- Không mở Mốc 2.
- Không đưa dữ liệu thật, nhật ký thật hoặc khóa lên GitHub.
- Không tự điền ngày thiếu.
- Không thêm MA250, mô phỏng giao dịch, học máy hoặc chia vốn.
