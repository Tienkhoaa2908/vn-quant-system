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

## Quy tắc điều phối tăng tốc

16. Đơn vị giao việc mặc định là `WORK_PACKAGE` theo kết quả, không phải lát cắt thao tác nhỏ.
17. Một work package mặc định dùng một prompt, một nhánh, một Draft PR và một báo cáo cuối.
18. Đoạn chuyên môn được tự đọc, thiết kế, triển khai, test, tự rà soát, sửa lỗi, commit, push, mở Draft PR và sửa CI trong cùng phạm vi mà không xin lại phép sau từng bước.
19. Chỉ quay lại đoạn `00` khi cần đổi contract, mở scope, dùng quyền truy cập mới, thực hiện thao tác phá hủy, nâng noncanonical thành canonical, đổi research gate hoặc mở mốc mới.
20. Mọi work package phải thực hiện capability preflight sớm. Capability bị chặn do môi trường chỉ được thử một fallback độc lập; sau đó phải dừng lặp, tạo action kit và tiếp tục các lane độc lập.
21. Blocker của một lane không tự động dừng toàn bộ package.
22. Tối đa hai work package active: một trên đường găng và một package song song không làm tăng rủi ro tích hợp.
23. Mỗi package có failure budget ba vòng tự sửa trong cùng Draft PR: implementation review, local/full test repair và CI repair.
24. Không tạo prompt hoặc PR điều phối chỉ để ghi nhận từng thao tác nhỏ. Trạng thái được gom theo batch.
25. Prompt chuyên môn tham chiếu tài liệu canonical, không lặp toàn bộ lịch sử dự án.
26. `tai_lieu_dieu_phoi/ban_dieu_phoi_hien_hanh.md` là snapshot current-state; Git history và `DECISIONS.md` giữ lịch sử.
27. Trước khi push phải tự kiểm scope, contract, negative tests, boundary dates, look-ahead, survivorship, stable ordering, finite values, hash/manifest, cross-platform và backward compatibility.
28. Mọi claim phải phân biệt rõ `implemented`, `locally_verified`, `ci_verified`, `observed_external`, `reported_not_verified` và `blocked`.
29. Khi work package có code cần chạy trên workstation, trợ lý phải hoàn tất code trên nhánh GitHub trước; người vận hành chỉ nhận lệnh Git Bash để `fetch/switch/pull` nhánh rồi chạy runner trong repo. Không dùng ZIP/patch thủ công hoặc yêu cầu giải nén code nếu GitHub vẫn ghi được. Nếu connector GitHub bị chặn, phải nói rõ blocker và chỉ dùng action kit như fallback cuối cùng.

Chi tiết thực thi nằm tại:

- `tai_lieu_dieu_phoi/giao_thuc_goi_cong_viec_lon.md`;
- `tai_lieu_dieu_phoi/mau_prompt_goi_cong_viec_lon.md`;
- `tai_lieu_dieu_phoi/ban_dieu_phoi_hien_hanh.md`.

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
