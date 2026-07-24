# Công việc hiện tại

Cập nhật: 2026-07-24

## Đoạn phụ trách

`01 Dữ liệu`, dưới sự nghiệm thu của `00 Điều phối trung tâm`.

## Trạng thái nền

- Yêu cầu gộp số `2` đã được gộp vào `main`.
- Đầu `main` đã xác minh: `4eba2a77d5864027c84d4350769d95fd4abd5fee`.
- Nhánh `m1-du_lieu` đã đồng bộ đầu `main` qua commit
  `5ae994df47ce34a5ab5d3c5dd1e3d206d864811c`.
- Yêu cầu gộp số `3` vẫn mở, nháp và chưa gộp.

## Kết quả thăm dò thật đã xác minh

Mã lần chạy: `20260724T152739494769Z_521d23ce`.

| Mã | Số dòng | Ngày đầu | Ngày cuối | Đơn vị giá |
|---|---:|---|---|---|
| FPT | 8 | 2026-07-01 | 2026-07-10 | nghìn đồng |
| HPG | 8 | 2026-07-01 | 2026-07-10 | nghìn đồng |
| MBB | 8 | 2026-07-01 | 2026-07-10 | nghìn đồng |

Cách gọi thật đã hoạt động:

```python
Market().equity(symbol=ma).ohlcv(
    start=ngay_bat_dau,
    end=ngay_ket_thuc,
    interval="1D",
    source="kbs",
)
```

Hợp đồng phản hồi thật:

- cột: `time`, `open`, `high`, `low`, `close`, `volume`;
- `time`: `datetime64[ns]`;
- OHLC: `float64`;
- `volume`: `int64`;
- chưa phát hiện khả năng hoặc tham số chọn giá điều chỉnh/chưa điều chỉnh;
- không có lỗi nguồn trong báo cáo thăm dò.

## Kết quả tải thật nhỏ đã xác minh

Mã lần chạy: `20260724T153953222157Z_5383eaab`.

| Mã | Trạng thái | Số dòng | Số lần thử | Cảnh báo | Lỗi |
|---|---|---:|---:|---:|---|
| FPT | thành công | 8 | 1 | 0 | không |
| HPG | thành công | 8 | 1 | 0 | không |
| MBB | thành công | 8 | 1 | 0 | không |

Bản tổng hợp ghi nhận cho từng mã:

- dữ liệu thô JSON;
- dữ liệu chuẩn hóa CSV;
- dữ liệu sẵn sàng CSV;
- báo cáo chất lượng JSON;
- nhật ký JSON;
- mã SHA-256 của dữ liệu thô.

Các sản phẩm nằm dưới `du_lieu/` trên máy người dùng và không được đưa vào GitHub.

## Kết quả Python 3.12

- Python: `CPython 3.12.13` Windows x86-64.
- Đồng bộ môi trường: hoàn thành, log `Checked in 1ms`.
- Biên dịch: không phát hiện lỗi trong log được cung cấp.
- Unittest: `Ran 30 tests in 0.696s`.
- Kết quả: `OK`.

## Kết quả GitHub Actions

Commit được xác minh: `ad1c54c41e2fc31d7a4327043b21f02b35b4603d`.

- Push run số `25`, ID `30107975081`: thành công.
- Pull-request run số `26`, ID `30107980910`: thành công.
- Job `kiem_tra`: hoàn thành và thành công.
- Các bước lấy mã nguồn, cài uv, cài Python 3.12, đồng bộ môi trường, kiểm tra cú pháp và chạy kiểm thử ngoại tuyến đều thành công.
- Cảnh báo Node.js 20 bị loại bỏ dần là cảnh báo không chặn.

## Việc đang hoạt động

1. Giữ PR số `3` ở trạng thái nháp và chưa gộp.
2. Bàn giao kết quả đầy đủ cho đoạn `00`.
3. Chờ đoạn `00` rà soát và quyết định trạng thái PR.

## Điều kiện nghiệm thu kỹ thuật

- Thăm dò thật: đạt.
- Tải thật nhỏ: đạt.
- Python 3.12: đạt 30/30 kiểm thử.
- GitHub Actions: đạt trên push và pull request.
- PR không chứa thư mục `du_lieu/`.
- Các điều kiện kỹ thuật bắt buộc của Mốc 1 đã hoàn thành.

## Phạm vi bị khóa

- Chưa mở Mốc 2.
- Chưa thêm MA250 hoặc động lượng.
- Chưa mô phỏng giao dịch.
- Chưa học máy.
- Chưa chia vốn.
- Chưa tải toàn bộ VN100.
