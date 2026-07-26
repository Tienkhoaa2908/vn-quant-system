# Bàn giao đoạn chat điều phối

Cập nhật: 2026-07-26

## Nền

- Kho: `Tienkhoaa2908/vn-quant-system`.
- Base: `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`.
- Nhánh: `m4-dac_trung-xep_hang-hoc_may`.
- Head được đoạn 00 rà soát trước vòng: `8652067b99b689eca46636c2617231d7b87f0427`.
- PR #10 phải giữ Draft.

## Final tree vòng này

- Eligibility AND fail closed, thanh khoản PIT `gtgd_tb_20`, open đúng T+1; không tìm T+2.
- OOS metric được cắt khỏi train/warm-up và dữ liệu sau `oos_end`; một vốn và một chuỗi liên tục.
- Fold test rỗng/không prediction không được tính thành công hoặc tạo rebalance.
- Corporate action giữa hai kỳ tín hiệu được áp dụng đúng effective date khi publication cutoff hợp lệ.
- Coverage theo mã point-in-time, không phạt trước listing/entry hoặc sau exit; lỗi giá/volume theo policy B.
- Audit phân biệt selection/refit scaler/model và công bố đầy đủ n_iter/convergence/candidate warning.
- Research mode không công bố run toàn tiền mặt/rỗng như thành công.

## Kiểm thử và giới hạn

Suite cục bộ: 308 test = 187 Mốc 4 + 121 nền; 41 test mới. CI Python 3.12 phải chạy trên commit cuối và merge ref. Tier A/Tier B, dữ liệu thật và phê duyệt nguồn chưa diễn ra; metric fixture không chứng minh hiệu quả chiến lược. Không LightGBM, Ready, merge, Mốc 5 hoặc nhánh sạch trước lệnh đoạn 00.
