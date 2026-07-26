# Trạng thái dự án

Cập nhật gần nhất: 2026-07-26

## Kho mã nguồn

- Kho: `Tienkhoaa2908/vn-quant-system`.
- Base Mốc 4: `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`.
- Nhánh: `m4-dac_trung-xep_hang-hoc_may`.
- Head nền vòng final tree: `8652067b99b689eca46636c2617231d7b87f0427`.
- PR #10 tiếp tục Draft; không reset/rebase/squash/force-push/merge.
- Python mục tiêu 3.12; `uv`; `scikit-learn==1.9.0`.

## Mốc 0–Mốc 3

Đã đóng. 121 test ngoại tuyến và engine Mốc 3 tiếp tục là nền hồi quy bắt buộc.

## Mốc 4 — final tree đang hoàn thiện

Pipeline đầu-cuối bằng fixture ngoại tuyến hiện khóa thêm:

- eligibility là AND fail closed của membership PIT, `gtgd_tb_20`, warm-up, feature, chất lượng dữ liệu, benchmark metadata PIT và open đúng T+1;
- metric backtest chỉ tính trong `ngay_bat_dau_metric..oos_end`, không đưa tiền mặt thời train/warm-up vào OOS;
- fold test rỗng hoặc không có prediction test thất bại và không tạo ranking/tái cân bằng;
- corporate action giữa hai kỳ tái cân bằng vẫn áp dụng theo publication/effective cutoff, không phụ thuộc lịch tín hiệu;
- coverage theo mã dùng mẫu số point-in-time và policy B loại dữ liệu lỗi có kiểm soát;
- model audit tách `validation_selection` và `final_refit` cùng scaler/model ID riêng;
- research mode từ chối run rỗng, sai benchmark, thiếu metadata hoặc coverage/universe dưới ngưỡng.

Suite cục bộ final tree: 187 test Mốc 4 + 121 test Mốc 0–3 = 308 test. Compileall và toàn suite đang đạt trên runtime ngoại tuyến hiện có; CI Python 3.12 phải xác nhận lại sau commit/push.

## Cửa kiểm soát

- Tier A/Tier B chưa chạy.
- Chưa tải dữ liệu thật; nguồn VN100/VNINDEX/lịch/cơ sở giá/corporate actions thật chưa được phê duyệt.
- Metric fixture không chứng minh hiệu quả chiến lược.
- Không LightGBM, SSI, đọc tài khoản hoặc gửi lệnh.
- Không Ready, không merge và không mở Mốc 5.
- Chưa tạo nhánh sạch; chỉ thực hiện khi đoạn 00 có lệnh sau khi phê duyệt final tree.
