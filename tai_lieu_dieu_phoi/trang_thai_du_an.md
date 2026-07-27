# Trạng thái dự án

Cập nhật gần nhất: 2026-07-27

## Kho mã nguồn

- Kho: `Tienkhoaa2908/vn-quant-system`.
- Base Mốc 4: `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`.
- Source kỹ thuật cuối: `5aec6ace8423fbf30442aa77db6ff63adb3c854e`.
- Commit thứ tư của nhánh clean-history có đúng tree source: `8452cfb8ddc521c80d7f1128acd72039b1fca0eb`.
- Nhánh chính thức hiện tại: `m4-dac_trung-xep-hang-hoc_may-sach-final`.
- Head trước vòng sửa tài liệu: `07bc48075be5e44cd410ff8fc2ef02828fc8fd73`.
- PR chính thức: #14, Open, Draft, chưa merge và chưa Ready.
- PR #13 là PR nguồn kỹ thuật, tiếp tục Open, Draft và chưa merge.

## Portability công bố Mốc 4

Dependency lock đa nền tảng đã đạt frozen sync trên Ubuntu và Windows. Publication giữ file fsync cho 16 sản phẩm cùng manifest, atomic replace, chống ghi đè và rollback staging.

POSIX/Linux mở directory bằng `O_RDONLY`, thêm `O_DIRECTORY` khi có, fsync descriptor, đóng descriptor trong `finally` và propagate lỗi thật. Windows không gọi `os.open` trên directory và trả capability unsupported; không tuyên bố directory-entry crash durability tương đương POSIX.

Bổ sung test riêng cho file fsync, POSIX error propagation, Windows unsupported capability, publication 17 file, manifest hash, one-shot replace, cùng parent filesystem, rollback, tính tái lập và dọn staging.

## CI kỹ thuật đã phê duyệt

- Source run: #334, `completed/success`.
- Ubuntu Job: `89890344314`, success.
- Windows Job: `89890344310`, success.
- Python `3.12.13`, uv `0.11.32`, scikit-learn `1.9.0`.
- Tổng 320 test được discovery.

## CI clean-history trước correction tài liệu

- PR #14 run #335, Run ID `30241263742`, `completed/success`.
- Ubuntu Job `89898799819`, success.
- Windows Job `89898799861`, success.
- Merge ref đã kiểm tra: `refs/pull/14/merge`.

## Blocker tài liệu và cửa kiểm soát

Commit thứ năm đã rút gọn tài liệu tích lũy. Vòng hiện tại phục hồi đầy đủ nội dung từ commit thứ tư và nối QD-0060/trạng thái final, chỉ trong bảy tệp tài liệu được phê duyệt.

- Code, workflow, dependency và test phải tiếp tục giống source `5aec6ace8423fbf30442aa77db6ff63adb3c854e`.
- Tier A/Tier B chưa chạy; chưa có raw data thật.
- Không thay đổi feature, label, folds, model, ranking, adapter, backtest hoặc dependency version.
- Không LightGBM, SSI, Ready, merge hoặc Mốc 5.
