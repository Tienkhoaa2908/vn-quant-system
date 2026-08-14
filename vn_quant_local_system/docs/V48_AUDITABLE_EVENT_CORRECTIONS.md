# V48 — Auditable Event Corrections

## Phạm vi

V48 chỉ thay đổi phần event ledger của Performance Observatory. Model C3,
canonical/preview, capital planner, sell gate, broker read-only và shadow
portfolio giữ nguyên.

## Nguyên tắc

`performance_events` tiếp tục append-only. Không có thao tác SQL `UPDATE` hoặc
`DELETE` đối với event đã xác nhận.

- Hủy event: ghi thêm `EVENT_VOID` trỏ tới `target_event_id`.
- Sửa event: trong một transaction, ghi event replacement và
  `EVENT_REPLACEMENT` trỏ từ event cũ sang event mới.
- NAV, actual model sleeve, whole-account cash-flow adjustment và
  reconciliation chỉ đọc effective ledger.
- Event gốc và toàn bộ correction event vẫn hiển thị để audit.

## Quyền sửa

Chỉ các event thủ công có nguồn bắt đầu bằng `USER_CONFIRMED` được sửa hoặc
hủy:

- `ACTUAL_CASHFLOW`
- `ACTUAL_FILL`

Opening snapshot, broker snapshot, shadow trade, ranking và event hệ thống không
được sửa.

## Trạng thái định giá

- `APPLIED`: đã có market session tương ứng và đã đi vào NAV.
- `APPLIED_NEXT_SESSION`: cashflow vào ngày nghỉ được áp dụng ở phiên kế tiếp.
- `PENDING_VALUATION`: ngày event mới hơn ngày cuối trong kho giá.
- `INVALID_MARKET_DAY`: fill nằm ở ngày không phải phiên giao dịch đã biết;
  event không được đưa vào effective ledger.
- `VOIDED` / `REPLACED`: event gốc không còn ảnh hưởng kết quả.

## Đơn vị giá fill

UI cho phép nhập:

- `VND`: nhập `72000` cho giá 72.000 đồng.
- `THOUSAND_VND`: nhập `72`, hệ thống chuẩn hóa thành 72.000 đồng.

Giá chuẩn hóa dưới 1.000 đồng bị chặn để tránh lỗi đơn vị.

## Xử lý hai event thử nghiệm ngày 2026-08-04

Trong tab Hiệu quả, tại Event ledger thực tế:

1. Bấm **Hủy có audit** ở cashflow 250.000 đồng, lý do `Nhập thử`.
2. Bấm **Hủy có audit** ở fill `BUY FPT 1 @ 72`, lý do
   `Nhập thử, sai đơn vị giá`.
3. Bấm **Cập nhật hiệu quả**.

Hai row gốc vẫn tồn tại với trạng thái `VOIDED`, nhưng không còn ảnh hưởng NAV,
position hoặc reconciliation.
