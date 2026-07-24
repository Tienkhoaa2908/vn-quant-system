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

Cả ba mã bắt buộc đều thành công:

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

## Việc đang hoạt động

Theo đúng thứ tự:

1. Kiểm tra GitHub Actions trên commit đầu nhánh sau các cập nhật tài liệu này.
2. Nếu có run, rà soát mã run, job và từng bước.
3. Nếu không có run, xác minh trạng thái kích hoạt Actions của kho; không tạo commit rỗng.
4. Cập nhật ba tệp điều phối bằng trạng thái CI cuối cùng.
5. Gửi báo cáo đầy đủ về đoạn `00`.

## Điều kiện nghiệm thu còn lại

- GitHub Actions phải có mã lần chạy thật trên đầu nhánh cuối cùng.
- Toàn bộ job và bước phải đạt.
- Không được commit thư mục `du_lieu/`.
- PR số `3` tiếp tục ở trạng thái nháp cho đến khi đoạn `00` kết luận đủ điều kiện.

## Phạm vi bị khóa

- Chưa mở Mốc 2.
- Chưa thêm MA250 hoặc động lượng.
- Chưa mô phỏng giao dịch.
- Chưa học máy.
- Chưa chia vốn.
- Chưa tải toàn bộ VN100.
