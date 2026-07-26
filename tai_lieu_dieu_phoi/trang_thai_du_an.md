# Trạng thái dự án

Cập nhật gần nhất: 2026-07-26

## Kho mã nguồn

- Kho: `Tienkhoaa2908/vn-quant-system`.
- Base Mốc 4: `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`.
- Nhánh chính thức: `m4-dac_trung-xep-hang-hoc-may-sach-v2`.
- Head trước vòng sửa lock: `bb731e6292abf04c78167b59c8488d795d74f493`.
- PR #13 tiếp tục Open, Draft, chưa merge.

## Sửa dependency lock đa nền tảng

Preflight Tier A trên Windows xác nhận lock cũ chỉ có wheel Linux cho NumPy, SciPy và scikit-learn. Vòng hiện tại chỉ sửa `pyproject.toml`, `uv.lock`, CI và tài liệu: khai báo Linux x86_64/Windows AMD64, giữ nguyên toàn bộ phiên bản dependency và chạy cùng 308 test trên Ubuntu/Windows.

Không thay đổi logic feature, model, ranking, backtest hoặc fixture nghiệp vụ.

## Cửa kiểm soát

- Tier A/Tier B chưa chạy; chưa có raw data thật.
- Không LightGBM, SSI, Ready, merge hoặc Mốc 5.
- CI matrix phải đạt trên merge ref PR #13 trước khi báo hoàn tất.
