# Bàn giao đoạn chat điều phối

Cập nhật: 2026-07-26

## Nền

- Kho: `Tienkhoaa2908/vn-quant-system`.
- Base: `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`.
- Nhánh: `m4-dac_trung-xep-hang-hoc-may-sach-v2`.
- Head trước vòng: `bb731e6292abf04c78167b59c8488d795d74f493`.
- PR #13 phải giữ Open, Draft, chưa merge.

## Lỗi và hướng sửa

Windows Python 3.12/uv 0.11.32 không frozen-sync được vì lock cũ chỉ chứa wheel manylinux cho NumPy, SciPy và scikit-learn. Đây là lỗi lock platform-specific; PyPI có wheel win_amd64.

Vòng sửa chỉ thêm required environments Linux/Windows, tái khóa cùng phiên bản và mở CI matrix Ubuntu/Windows. Không thay đổi logic Mốc 4 hoặc test nghiệp vụ.

## Cửa hoàn tất

Cả hai job phải checkout `refs/pull/13/merge`, đạt `uv lock --check`, frozen sync, compileall và 308 test với Python 3.12, uv 0.11.32, scikit-learn 1.9.0. Tier A/Tier B chưa chạy và không có dữ liệu thật.
