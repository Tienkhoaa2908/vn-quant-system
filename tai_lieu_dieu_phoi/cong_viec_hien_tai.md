# Công việc hiện tại

Cập nhật: 2026-07-26

## Đoạn phụ trách

Đoạn `04` hoàn thiện final tree Mốc 4 trên PR #10; đoạn `00` rà soát kỹ thuật và quyết định bước tạo nhánh sạch/dữ liệu thật.

## Nội dung final tree

1. Eligibility PIT với thanh khoản `gtgd_tb_20`, ngưỡng cấu hình, lý do `khong_dat_thanh_khoan` và open đúng T+1 (`thieu_open_t1`).
2. Cửa sổ OOS khóa `oos_start`, `ngay_bat_dau_metric`, `oos_end`; train/warm-up và dữ liệu tương lai không ảnh hưởng metric.
3. Fold test rỗng/không có prediction test fail closed.
4. Corporate actions lọc theo publication/effective cutoff và cửa sổ backtest, không theo lịch tín hiệu tháng.
5. Coverage point-in-time; gap chỉ trong phiên yêu cầu; policy B cho lỗi giá/volume.
6. Model audit hai stage với scaler, hệ số, n_iter, warning, candidate error, cutoff và version.
7. Research mode fail closed cho benchmark identity/metadata, fold, prediction, rebalance và ngưỡng coverage/universe.
8. Giữ runner/CLI, baseline, adapter zero target, manifest SHA-256, finite protection, publication atomic và hồi quy Mốc 0–3.

## Kiểm thử

- Trước vòng: 267 test.
- Bổ sung: 41 test tách riêng.
- Hiện tại: 308 test, gồm 187 test Mốc 4 và 121 test nền.
- Cần CI Python 3.12 trên head mới và merge ref PR #10 trước khi báo đoạn 00.

## Cấm hiện hành

Không workflow/payload chẩn đoán mới, không force-push/reset/rebase/squash, không Ready/merge, không Tier A/Tier B, không dữ liệu thật, không LightGBM và không Mốc 5. Chưa tạo nhánh sạch.
