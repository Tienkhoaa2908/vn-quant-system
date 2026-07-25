# Bàn giao đoạn chat điều phối

Cập nhật: 2026-07-25

## Vai trò và nền

- Đoạn `00`: điều phối và nghiệm thu.
- Đoạn `04`: triển khai Mốc 4.
- Kho: `Tienkhoaa2908/vn-quant-system`.
- Base: `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`.
- Nhánh: `m4-dac_trung-xep_hang-hoc_may`.
- PR: #10, Draft, không force-push và không tự gộp.

## Trạng thái bàn giao

- Kiến trúc đã được đoạn 00 phê duyệt tại head `391ef1e99e0e1dd4a20931c1762090530ada2304`.
- Đã bổ sung hợp đồng monthly sample/OOS/top-K/one-class.
- Đã thêm `scikit-learn==1.9.0`, không pandas và không LightGBM.
- Đã triển khai 16 module và 97 test Mốc 4 bằng fixture ngoại tuyến.
- CI mã/test run #204, Run ID `30166974542`, Job ID `89701563209`, merge ref `4fcf21d296b739f9f7884339773be0df57a86cac`, thành công.

## Hợp đồng chính đã triển khai

1. PIT cutoff bằng timestamp có múi giờ.
2. Mẫu train/validation/test tại phiên benchmark cuối tháng.
3. T+H theo lịch benchmark, không forward-fill hoặc tìm endpoint khác.
4. Expanding monthly walk-forward, purge/embargo, test không chồng lấn và model clock.
5. StandardScaler + Logistic Regression L2/lbfgs; C chọn bằng validation; one-class/convergence fail closed.
6. Chỉ prediction test vào metric/ranking/target weights/backtest.
7. OOS stitching liên tục và gọi engine Mốc 3 một lần.
8. 17 sản phẩm bất biến với staging, fsync, rollback và SHA-256.

## Cửa tiếp theo

Đoạn `00` rà soát PR #10. Chưa được chạy Tier A/Tier B, chưa tải VN100/VNINDEX thật, chưa chuyển Ready, chưa gộp và chưa mở Mốc 5. Không kết nối SSI, không đọc tài khoản và không gửi lệnh.
