# V47 — Canonical tháng và latest preview guard

## Mục tiêu

V47 giữ nguyên tín hiệu C3 canonical theo tháng đã được nghiên cứu, đồng thời cập
nhật tình hình mới nhất trước mỗi planning cycle. Hai lớp tín hiệu không được
trộn lẫn:

- `MONTHLY_CANONICAL`: quyết định Top-10, target weights, buffer Top-20 và sell
  gate hai tháng;
- `LATEST_SESSION_WITH_CANONICAL_WEIGHTS`: quan sát phiên mới nhất và chỉ chặn
  mua thêm khi mã canonical đã suy yếu rõ.

## Quy tắc lịch tháng

Canonical là phiên cuối của tháng lịch đã hoàn tất gần nhất. Nếu kho dữ liệu dừng
ở ngày 31/07 và hôm nay đã sang tháng 8, ngày 31/07 vẫn là canonical; hệ thống
không chờ bar tháng 8 mới nhận diện tháng 7 đã hoàn tất.

## Purchase guard

Một mã được đề xuất mua khi đồng thời:

1. nằm trong canonical Top-10;
2. latest preview vẫn eligible;
3. latest preview còn trong Top-20;
4. danh mục thực tế đang thiếu tỷ trọng;
5. ngân sách mua được ít nhất một cổ phiếu lô lẻ.

Mã canonical Top-10 nhưng không vượt guard được ghi là `Tạm hoãn mua`. Nó không bị
loại khỏi canonical và không tự trở thành ứng viên bán.

Mã chỉ xuất hiện trong preview Top-10 nhưng không nằm trong canonical Top-10 chỉ
được hiển thị để quan sát, không được dùng làm lệnh mua.

## Sell policy

Preview không kích hoạt bán. Ứng viên bán vẫn phải ngoài Top-20 ở hai tháng
canonical hoàn tất liên tiếp. Hard-risk events chưa được tự động hóa trong V47.

## Trang Thị trường

- `Cập nhật đánh giá mới nhất`: đồng bộ OHLCV, bảo đảm canonical đúng tháng và
  tính lại preview;
- `Chạy canonical tháng`: chỉ hoạt động khi canonical đang thiếu hoặc cũ;
- bảng canonical và preview được hiển thị riêng;
- trang này không tạo plan và không thay đổi shadow.

## Tạo kế hoạch vốn

Nút tạo kế hoạch tự thực hiện tuần tự:

1. đồng bộ dữ liệu giá;
2. đồng bộ danh mục DNSE read-only;
3. bảo đảm canonical tháng hiện hành;
4. tạo hoặc tái sử dụng preview snapshot của phiên mới nhất;
5. tính tỷ trọng theo danh mục DNSE;
6. áp purchase guard;
7. ghi capital cycle và audit metadata;
8. cập nhật Performance Observatory nếu đã khởi tạo.

Mỗi cycle lưu `canonical_signal_day`, `preview_signal_day`, `preview_snapshot_id`,
canonical rank, preview rank, eligibility và lý do chặn mua.

## Đánh giá hiệu quả

- signal scorecard tiếp tục đánh giá canonical tháng;
- plan shadow đánh giá capital cycle sau purchase guard;
- actual sleeve dùng dòng tiền và fill thật;
- chênh lệch canonical-only và canonical-plus-preview-guard sẽ được tích lũy để
  kiểm định sau khi có đủ mẫu thực tế.

## Giới hạn

V47 chưa chứng minh lịch sử rằng preview guard tăng lợi nhuận. Guard được triển
khai theo hướng fail-closed để hạn chế mua mã đã mất trạng thái trung hạn; hiệu
quả của nó phải được đánh giá bằng shadow và actual observatory trong tương lai.
