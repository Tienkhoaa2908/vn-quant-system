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
30. Phạm vi nghiên cứu và học máy mặc định tập trung vào cổ phiếu HOSE. Dữ liệu huấn luyện chuẩn phải được dựng từ kho dữ liệu local đã tích lũy thành master panel HOSE tổng hợp theo thời gian; không dùng candidate list, Top-N snapshot hoặc V22 làm nguồn huấn luyện chính nếu bài toán có thể dựng lại từ kho tổng hợp. Membership HOSE phải point-in-time khi đánh giá lịch sử; nếu chỉ có mapping hiện tại thì phải đánh dấu survivorship blocker thay vì âm thầm dùng.
31. Champion/model nền mặc định là `C3_STABLE_3_PAST_IC_SHRUNK` cho đến khi có quyết định promotion riêng dựa trên causal OOS, stability, portfolio simulation và paper OOS. Logistic Regression, HistGradientBoosting, LightGBM hoặc model khác chỉ là challenger/augmentation; không được tự thay C3 vì đã triển khai được model mới.
32. Canonical workstation environment hiện hành là `vn_quant_local_system/.venv`. Thay đổi dependency/environment và thay đổi model architecture là hai việc độc lập; không được đổi model nền chỉ vì thiếu package trong môi trường chạy.
33. CI xanh chỉ chứng minh code/contract đã qua kiểm tra tự động; không được coi CI là kết quả nghiên cứu. Kết luận research bắt buộc dựa trên artifact chạy thật trên workstation data và audit provenance/output.
34. Trước mọi research architecture mới liên quan C3/HOSE, phải đọc `tai_lieu_dieu_phoi/anti_regression_c3_hose.md`; các lỗi và guardrail trong tài liệu đó là ràng buộc bắt buộc, không phải ghi chú tham khảo.
35. Phải giữ nguyên semantics của nhãn học trọng số C3: relative return từ `close(T)` đến `close(T+20)` trên lịch benchmark. Đây là training label của C3, khác với tradable execution/outcome được đánh giá từ `open(T+1)`; không được trộn hai contract này.
36. OHLCV dài nhiều năm không chứng minh point-in-time universe. Trước full-HOSE research phải xác minh venue/membership lịch sử và `price_basis`; nếu thiếu thì data gate fail-closed. `listing_date + current exchange` không được coi là exchange history.
37. Runner workstation có log qua `tee` phải giữ fail-fast bên trong subshell/function có `set -euo pipefail`; lỗi test/compile không được phép bị command chạy sau che mất rồi báo success.
38. Khi dùng SQLite file tạm trên Windows, connection phải được đóng rõ ràng trước cleanup; `with sqlite3.connect(...)` chỉ quản lý transaction và không được mặc định là đã giải phóng file handle.
39. Data gate fail-closed ở quy tắc 36 chặn **canonical research claim, policy/model promotion và paper/live use**, nhưng không được làm blocker của một lane dừng toàn bộ research package. Được phép chạy `diagnostic sensitivity` bằng C3 trên universe provisional nếu output ghi rõ `provisional`, source store không bị sửa, không dùng kết quả để tuyên bố HOSE point-in-time chuẩn, và luôn chạy song song các biến thể loại symbol có price/basis anomaly. Diagnostic này dùng để đo độ nhạy và tăng tốc phát hiện vấn đề; không tự đóng data gate và không tự cho phép promotion.
40. Mọi hành vi phụ thuộc hệ điều hành nhưng nằm trên đường chạy workstation phải có **CI cùng hệ điều hành** trước khi giao runner. Ubuntu/Linux CI không được dùng thay cho xác minh Windows đối với file locking, path conversion, PowerShell/Git Bash hoặc SQLite temporary-file lifetime. Với runner tạo SQLite tạm, bắt buộc có Windows end-to-end test chứng minh source DB và temp variant đều cleanup được ngay sau run.

Chi tiết thực thi nằm tại:

- `tai_lieu_dieu_phoi/giao_thuc_goi_cong_viec_lon.md`;
- `tai_lieu_dieu_phoi/mau_prompt_goi_cong_viec_lon.md`;
- `tai_lieu_dieu_phoi/ban_dieu_phoi_hien_hanh.md`;
- `tai_lieu_dieu_phoi/anti_regression_c3_hose.md`;
- `tai_lieu_dieu_phoi/anti_regression_v67_data_gate.md`.

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
