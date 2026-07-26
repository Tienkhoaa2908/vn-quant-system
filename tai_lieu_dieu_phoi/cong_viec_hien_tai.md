# Công việc hiện tại

Cập nhật: 2026-07-26

## Đoạn phụ trách

Đoạn `04` hoàn thiện Mốc 4 trên PR #10; đoạn `00` rà soát và quyết định cửa dữ liệu thật.

## Đã hoàn tất bằng fixture ngoại tuyến

1. Runner `chay_nghien_cuu_moc_4(...)` và CLI đầu-cuối từ tệp cục bộ.
2. Lịch benchmark chính thức làm trục cho toàn bộ cửa sổ/endpoint feature; không forward-fill hoặc nén thời gian.
3. Coverage schema đầy đủ theo yêu cầu.
4. Momentum baseline và Logistic Regression dùng cùng OOS test set/engine/chi phí.
5. Adapter bắt `muc_tieu_bang_0`, target 0 cho mã rời top_k và ngày rỗng về tiền mặt.
6. Manifest bắt metadata, input/product SHA-256 và rollback.
7. NaN/Inf, duplicate, role/fold/model validation fail closed.
8. 146 test Mốc 4; toàn suite 267 test cùng 121 test hồi quy.

## Cửa tiếp theo thuộc đoạn 00

- Rà soát diff/CI/PR #10 trong trạng thái Draft.
- Nguồn thật chỉ được xác nhận và chạy Tier A/Tier B sau phê duyệt riêng.

## Cấm hiện hành

Không force-push, không Ready/merge, không dữ liệu thật, không LightGBM, không SSI và không mở Mốc 5. Không diễn giải fixture như hiệu quả chiến lược.
