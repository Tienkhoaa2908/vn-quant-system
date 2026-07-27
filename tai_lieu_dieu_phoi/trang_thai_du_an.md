# Trạng thái dự án

Cập nhật gần nhất: 2026-07-27

## Kho mã nguồn

- Kho: `Tienkhoaa2908/vn-quant-system`.
- Base Mốc 4: `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`.
- Nhánh chính thức: `m4-dac_trung-xep-hang-hoc_may-sach-v2`.
- Head nền vóng portability: `d0886947cf33ebe7fc2b4eae99676218b1b01c11`.
- PR #13 tiếp tục Open, Draft, chưa merge và mergeable.

## Portability công bố Mốc 4

Dependency lock đa nền tảng đã đạt frozen sync trên Ubuntu và Windows. Blocker côn lại là directory fsync: POSIX tiếp tục mở directory với `O_DIRECTORY` khi có, fsync và propagate lỗi; Windows không gọi `os.open` trên directory và báo capability unsupported. File fsync cho 16 sản phẩm cùng manifest, atomic replace, chống ghi đè và rollback staging được giữ nguyên.

Bổ sung test riêng cho file fsync, POSIX error propagation, Windows unsupported capability, publication 17 file, manifest hash, one-shot replace, cùng parent filesystem, rollback, tính tái lập và dọn staging.

## Cửa kiểm soát

- CI cuối phải xanh trên `ubuntu-24.04` và `windows-2025` tại merge ref PR #13.
- Tier A/Tier B chưa chạy; chưa có raw data thật.
- Không thay đổi feature, label, folds, model, ranking, adapter, backtest hoặc dependency version.
- Không LightGBM, SSI, Ready, merge hoặc Mốc 5.
