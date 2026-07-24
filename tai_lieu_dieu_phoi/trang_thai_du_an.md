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

Trạng thái điều phối: **đã có bản triển khai nháp, chưa đủ điều kiện gộp**.

Yêu cầu gộp số `3`:

- Nhánh nguồn: `m1-du_lieu`.
- Nhánh đích: `main`.
- Trạng thái: mở, nháp, chưa gộp.
- Commit lát cắt dữ liệu ngoại tuyến: `0310e0667f569608676066dfe935fd3f9e782f4f`.
- Commit nguồn Vnstock và lệnh tải nhỏ: `e6dd3d8125e092cbee2d956269324a96a543e026`.
- Commit đồng bộ `origin/main` vào nhánh: `5ae994df47ce34a5ab5d3c5dd1e3d206d864811c`.
- Nhánh đã chứa đầu `main` mới; so sánh GitHub xác nhận chậm hơn `main` 0 commit.

### Thăm dò thật Vnstock Community 4.0.4

Đã nhận và đối chiếu báo cáo chạy thật:

- Mã lần chạy: `20260724T152739494769Z_521d23ce`.
- Khoảng ngày yêu cầu: `2026-07-01` đến `2026-07-10`.
- Cách gọi đã hoạt động:
  `Market().equity(symbol=ma).ohlcv(start=..., end=..., interval="1D", source="kbs")`.
- Không có khả năng chọn giá điều chỉnh/chưa điều chỉnh được công cụ phát hiện.
- Tên tham số giá điều chỉnh: không có.

Kết quả theo mã:

- `FPT`: thành công, 8 dòng, từ `2026-07-01` đến `2026-07-10`.
- `HPG`: thành công, 8 dòng, từ `2026-07-01` đến `2026-07-10`.
- `MBB`: thành công, 8 dòng, từ `2026-07-01` đến `2026-07-10`.
- Cả ba mã trả các cột `time`, `open`, `high`, `low`, `close`, `volume`.
- Kiểu dữ liệu: `time=datetime64[ns]`, OHLC=`float64`, `volume=int64`.
- Đơn vị giá do bộ chuyển đổi báo cáo: `nghin_dong`.
- Không có lỗi nguồn trong lần thăm dò.

### Điều kiện còn chặn

1. Chưa có lần tải thật nhỏ và nhật ký tổng hợp cho FPT, HPG, MBB.
2. Chưa chạy toàn bộ kiểm thử trên Python mục tiêu 3.12.
3. GitHub chưa ghi nhận lần chạy Actions hoặc commit status cho đầu nhánh đã đồng bộ.
4. Chưa cập nhật báo cáo cuối theo kết quả tải thật và CI.
5. PR số `3` phải tiếp tục ở trạng thái nháp cho đến khi đoạn `00` nghiệm thu.

## Phạm vi bị khóa

- Không mở Mốc 2.
- Không thêm MA250 hoặc động lượng.
- Không mô phỏng giao dịch.
- Không học máy.
- Không chia vốn.
- Không tải toàn bộ VN100.
