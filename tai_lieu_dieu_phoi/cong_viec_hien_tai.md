# Công việc hiện tại

Cập nhật: 2026-07-27

## Mục tiêu vòng

Sửa `BLOCKED_WINDOWS_DIRECTORY_FSYNC` trên PR #13 bằng commit nối tiếp, không viết lại lịch sử và không dùng workflow để commit/push.

## Phạm vi

1. `_fsync_dir` trả `False` trên Windows mà không gọi `os.open` trên directory.
2. POSIX dùng `O_RDONLY | O_DIRECTORY` khi có, fsync descriptor, đóng descriptor trong `finally` và propagate lỗi.
3. Giữ file fsync cho 16 sản phẩm cùng manifest, staging cùng parent, một `os.replace`, rollback và chống ghi đè.
4. Thêm test portability dùng filesystem thật kết hợp mock hẹp theo capability.
5. Giữ nguyên lock/dependency và CI matrix Ubuntu/Windows.

## Cửa hoàn tất

Cả hai job phải checkout `refs/pull/13/merge`, đạt lock check, frozen sync, version gate, compileall và toàn bộ suite cũ cộng test mới. Sau CI xanh chỉ báo đoạn 00; không chạy Tier A.

## Cấm hiện hành

Không sửa feature, label, folds, Logistic Regression, ranking, adapter, backtest Mốc 3, eligibility, coverage nghiệp vụ, dependency version hoặc dữ liệu thật; không force-push/rebase/squash; không Tier A/Tier B, Ready, merge, LightGBM hoặc Mốc 5.
