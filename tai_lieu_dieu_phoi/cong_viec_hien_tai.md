# Công việc hiện tại

Cập nhật: 2026-07-26

## Mục tiêu vòng

Sửa `BLOCKED_DEPENDENCY_LOCK_LINUX_ONLY_ON_WINDOWS` trên PR #13 bằng một commit nối tiếp, không sửa lịch sử.

## Phạm vi

1. Giữ `package = false` và thêm `required-environments` cho Linux x86_64, Windows AMD64.
2. Giữ nguyên scikit-learn 1.9.0 cùng NumPy 2.3.5, SciPy 1.17.0, joblib 1.5.3, narwhals 2.0.1 và threadpoolctl 3.6.0.
3. Lock phải chứa wheel CPython 3.12 manylinux x86_64 và win_amd64 cho NumPy, SciPy, scikit-learn.
4. CI dùng uv 0.11.32 và chạy `uv lock --check`, frozen sync, compileall, 308 test trên Ubuntu/Windows.
5. Cập nhật tài liệu và mô tả PR #13 sau khi CI đạt.

## Cấm hiện hành

Không sửa logic Mốc 4, fixture nghiệp vụ, dữ liệu thật hoặc dependency version; không force-push/rebase/squash; không Tier A/Tier B, Ready, merge, LightGBM hoặc Mốc 5.
