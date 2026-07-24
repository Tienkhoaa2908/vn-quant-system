# Trạng thái dự án

Cập nhật gần nhất: 2026-07-24

## Kho mã nguồn

- Kho: `Tienkhoaa2908/vn-quant-system`.
- Nhánh chính: `main`.
- Commit đầu `main` đã xác minh: `4eba2a77d5864027c84d4350769d95fd4abd5fee`.
- Đầu `main` đã chứa toàn bộ thư mục `tai_lieu_dieu_phoi/`.
- Thư mục cục bộ của người dùng: `C:\Users\welcome\Documents\vn-quant-system`.
- Môi trường người dùng: Windows và Git Bash.
- Python mục tiêu: 3.12.
- Công cụ môi trường: `uv`.

## Mốc 0

Trạng thái: **đã hoàn thành, đã kiểm tra và đã gộp vào `main`**.

- Yêu cầu gộp số `1`: đã gộp.
- Commit triển khai chính: `3385e401532e51457b9e9360e17df7af0e021881`.
- Commit hợp nhất trên `main`: `b132578b763ead96ad172a1ace68acdff6e36007`.
- Kiểm tra tự động Mốc 0: đạt.

## Bộ tài liệu điều phối

Trạng thái: **đã gộp vào `main`**.

- Yêu cầu gộp số `2`: đã gộp.
- Commit hợp nhất trên `main`: `4eba2a77d5864027c84d4350769d95fd4abd5fee`.
- Nhánh Mốc 1 đã được cập nhật từ commit này.

## Mốc 1

Trạng thái điều phối: **toàn bộ điều kiện kỹ thuật bắt buộc đã đạt; chờ đoạn `00` nghiệm thu và quyết định trạng thái PR**.

Yêu cầu gộp số `3`:

- Nhánh nguồn: `m1-du_lieu`.
- Nhánh đích: `main`.
- Trạng thái: mở, nháp, chưa gộp.
- Commit lát cắt dữ liệu ngoại tuyến: `0310e0667f569608676066dfe935fd3f9e782f4f`.
- Commit nguồn Vnstock và lệnh tải nhỏ: `e6dd3d8125e092cbee2d956269324a96a543e026`.
- Commit đồng bộ `origin/main` vào nhánh: `5ae994df47ce34a5ab5d3c5dd1e3d206d864811c`.
- Commit sửa workflow cuối đã được xác minh: `ad1c54c41e2fc31d7a4327043b21f02b35b4603d`.
- Nhánh đã chứa đầu `main` mới; so sánh GitHub xác nhận chậm hơn `main` 0 commit.

### Thăm dò thật Vnstock Community 4.0.4

- Mã lần chạy: `20260724T152739494769Z_521d23ce`.
- Khoảng ngày: `2026-07-01` đến `2026-07-10`.
- Cách gọi đã hoạt động:
  `Market().equity(symbol=ma).ohlcv(start=..., end=..., interval="1D", source="kbs")`.
- `FPT`, `HPG`, `MBB`: đều thành công, mỗi mã 8 dòng, từ `2026-07-01` đến `2026-07-10`.
- Cột thật: `time`, `open`, `high`, `low`, `close`, `volume`.
- Kiểu dữ liệu: `time=datetime64[ns]`, OHLC=`float64`, `volume=int64`.
- Đơn vị giá do bộ chuyển đổi báo cáo: `nghin_dong`.
- Chưa phát hiện tham số chọn giá điều chỉnh/chưa điều chỉnh.

### Tải thật nhỏ

- Mã lần chạy: `20260724T153953222157Z_5383eaab`.
- Nguồn: `vnstock_kbs`, phiên bản `4.0.4`.
- `FPT`: thành công, 8 dòng, một lần thử, không cảnh báo, không lỗi.
- `HPG`: thành công, 8 dòng, một lần thử, không cảnh báo, không lỗi.
- `MBB`: thành công, 8 dòng, một lần thử, không cảnh báo, không lỗi.
- Mỗi mã có đường dẫn được ghi nhận cho dữ liệu thô, chuẩn hóa, sẵn sàng, báo cáo chất lượng và nhật ký.
- Mỗi tệp dữ liệu thô có mã SHA-256 được ghi nhận trong bản tổng hợp.
- Thư mục `du_lieu/` là sản phẩm cục bộ và không được commit.

### Kiểm thử Python 3.12

- Python đã cài: `CPython 3.12.13` cho Windows x86-64.
- Đồng bộ môi trường bằng `uv` hoàn thành; log ghi `Checked in 1ms`.
- Không phát hiện lỗi biên dịch trong phần log được cung cấp.
- Bộ kiểm thử: `30/30` đạt.
- Thời gian unittest: `0.696s`.
- Kết quả cuối: `OK`.

### GitHub Actions

Đã xác minh trên commit `ad1c54c41e2fc31d7a4327043b21f02b35b4603d`:

- run đẩy nhánh số `25`, ID `30107975081`: `success`;
- run đồng bộ pull request số `26`, ID `30107980910`: `success`;
- job `kiem_tra`: `completed`, `success`;
- toàn bộ bước `Lay ma nguon`, `Cai dat uv`, `Cai dat Python`, `Dong bo moi truong`, `Kiem tra cu phap`, `Chay kiem thu ngoai tuyen` đều đạt;
- cảnh báo Node.js 20 bị loại bỏ dần là cảnh báo không chặn và không làm thay đổi kết luận CI.

### Điều kiện còn lại

1. Đoạn `00` rà soát báo cáo bàn giao và quyết định có chuyển PR số `3` khỏi trạng thái nháp hay không.
2. Không gộp PR số `3` trong đoạn `01`.
3. Không mở Mốc 2 trước quyết định của đoạn `00`.

## Phạm vi bị khóa

- Không mở Mốc 2.
- Không thêm MA250 hoặc động lượng.
- Không mô phỏng giao dịch.
- Không học máy.
- Không chia vốn.
- Không tải toàn bộ VN100.
