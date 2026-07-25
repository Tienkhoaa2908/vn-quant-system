# Trạng thái dự án

Cập nhật gần nhất: 2026-07-25

## Kho mã nguồn

- Kho: `Tienkhoaa2908/vn-quant-system`.
- Nhánh chính: `main`.
- Đầu `main`/base Mốc 4: `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`.
- Python mục tiêu: 3.12; môi trường: `uv`.
- GitHub là nguồn sự thật về nhánh, commit, PR và CI.

## Mốc 0–Mốc 3

Trạng thái: **đã đóng hoàn toàn**. Engine Mốc 3 và 121 kiểm thử ngoại tuyến tiếp tục là nền hồi quy bắt buộc.

## Mốc 4

Trạng thái: **đã triển khai bằng fixture ngoại tuyến; PR #10 đang Draft và chờ đoạn 00 rà soát**.

- PR đặc tả #9 đã gộp tại `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`.
- Nhánh: `m4-dac_trung-xep_hang-hoc_may`.
- PR triển khai: #10 — `M4: du lieu nhieu nam, dac trung, xep hang va Logistic Regression`.
- Dependency: `scikit-learn==1.9.0`; không pandas, không LightGBM.
- Đã tạo 16 module Mốc 4 và 97 test mới.
- CI mã/test đầu tiên: run #204, Run ID `30166974542`, Job ID `89701563209`, merge ref `4fcf21d296b739f9f7884339773be0df57a86cac`, `completed/success`.
- Compileall và toàn bộ unittest Python 3.12 đạt; 121 test Mốc 0–3 vẫn chạy cùng suite.

## Phạm vi đã triển khai

- cutoff PIT theo timestamp có múi giờ;
- universe/coverage fail closed và survivorship fixture;
- toàn bộ feature MVP tại phiên benchmark cuối tháng;
- nhãn T+20 theo lịch benchmark;
- expanding monthly walk-forward, purge/embargo và test không chồng lấn;
- StandardScaler + Logistic Regression, C selection, refit, convergence/one-class fail closed;
- ranking/top-K, model/ranking metric và OOS stitching;
- adapter tái sử dụng engine Mốc 3;
- công bố 17 tep bằng staging, fsync, atomic rename, rollback và SHA-256.

## Giới hạn và cửa kiểm soát

- Chưa chạy Tier A hoặc Tier B.
- Chưa có lịch sử VN100 point-in-time thật được phê duyệt.
- Chưa xác nhận nguồn/lịch VNINDEX và cơ sở giá/corporate actions thật.
- Không có dữ liệu, sản phẩm hoặc log thị trường thật được commit.
- Không tích hợp SSI, không đọc tài khoản và không gửi lệnh.
- PR #10 phải giữ Draft; không Ready, không tự gộp và không mở Mốc 5.
