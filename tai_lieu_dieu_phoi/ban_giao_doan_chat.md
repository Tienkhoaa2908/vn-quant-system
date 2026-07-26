# Bàn giao đoạn chat điều phối

Cập nhật: 2026-07-26

## Nền

- Kho: `Tienkhoaa2908/vn-quant-system`.
- Base: `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`.
- Nhánh: `m4-dac_trung-xep_hang-hoc_may`.
- PR #10 giữ Draft; không force-push và không tự gộp.

## Nội dung bàn giao

Mốc 4 đã có runner/CLI đầu-cuối ngoại tuyến. Pipeline thực hiện parse/validate, PIT, coverage, monthly calendar-aligned feature, T+H label, walk-forward, momentum baseline, Logistic Regression, OOS ranking/target/backtest, metrics và công bố 17 tệp.

Các sửa khóa cuối:

- lịch benchmark truyền riêng; thiếu bar đúng cửa sổ/endpoint không được bù;
- coverage theo ngày/mã cùng nguồn, phiên bản, cơ sở giá và lỗi fold;
- baseline và Logistic dùng cùng OOS dates/universe/eligibility/top_k/engine/chi phí;
- adapter bắt `muc_tieu_bang_0`, đóng mã rời top_k và xử lý ngày danh mục rỗng;
- manifest bắt metadata và SHA-256 từng input/product;
- NaN/Inf và duplicate/role/fold/model bị từ chối.

Suite: 146 test Mốc 4 + 121 test nền = 267 test. Fixture vàng xác minh runner, CLI, 17 tệp, fold, prediction, ranking, T+1, NAV, manifest và reproducibility.

## Giới hạn

Tier A/Tier B chưa chạy; chưa tải hoặc phê duyệt nguồn thật; không tuyên bố hiệu quả chiến lược. Không LightGBM, SSI, Ready, merge hoặc Mốc 5.
