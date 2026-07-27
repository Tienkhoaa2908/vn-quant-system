# Bàn giao đoạn chat điều phối

Cập nhật: 2026-07-27

## Nền

- Kho: `Tienkhoaa2908/vn-quant-system`.
- Base: `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`.
- Nhánh: `m4-dac_trung-xep-hang-hoc_may-sach-v2`.
- Head nền portability: `d0886947cf33ebe7fc2b4eae99676218b1b01c11`.
- PR #13 phải giữ Open, Draft, chưa merge.

## Trạng thái kỹ thuật

Lock đa nền tảng đã đạt frozen sync trên Ubuntu/Windows với Python 3.12.13, uv 0.11.32 và scikit-learn 1.9.0. Lỗi Windows còn lại đến từ `os.open(directory, O_RDONLY)` trong `_fsync_dir`.

Patch portability giữ file fsync và atomic publication, chỉ phân nhánh capability directory fsync: POSIX thực hiện và propagate lỗi; Windows trả unsupported mà không giả lập thành công. Test mới kiểm tra 17 file, hash manifest, không ghi đè, rollback, one-shot replace, same-parent staging, deterministic output và không để staging rác.

## Cửa tiếp theo

Chờ CI merge ref PR #13 xanh trên Ubuntu và Windows. Sau đó báo đoạn 00 để xác minh final tree; không tự chạy Tier A/Tier B, không tạo PR clean-history, không Ready/merge và không mở Mốc 5.
