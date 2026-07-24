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

## Việc đang hoạt động

Theo đúng thứ tự:

1. Chạy tải thật nhỏ cho FPT, HPG, MBB.
2. Rà soát `du_lieu/nhat_ky/<ma_lan_chay>/tong_hop.json` theo từng mã.
3. Chạy đồng bộ, biên dịch và toàn bộ kiểm thử trên Python 3.12.
4. Kiểm tra GitHub Actions trên commit đầu nhánh cuối cùng.
5. Nếu Actions không chạy, xác minh trạng thái kích hoạt Actions của kho; không tạo commit rỗng.
6. Cập nhật ba tệp điều phối bằng kết quả tải thật, Python 3.12 và CI.
7. Gửi báo cáo đầy đủ về đoạn `00`.

## Điều kiện nghiệm thu còn lại

- Tải thật phải tạo đúng dữ liệu thô, chuẩn hóa, sẵn sàng, báo cáo chất lượng và nhật ký cho từng mã.
- Không được commit thư mục `du_lieu/`.
- Python 3.12 phải chạy đủ bộ kiểm thử và báo số kiểm thử thực tế.
- GitHub Actions phải có mã lần chạy và toàn bộ bước đạt.
- PR số `3` tiếp tục ở trạng thái nháp cho đến khi đoạn `00` kết luận đủ điều kiện.

## Phạm vi bị khóa

- Chưa mở Mốc 2.
- Chưa thêm MA250 hoặc động lượng.
- Chưa mô phỏng giao dịch.
- Chưa học máy.
- Chưa chia vốn.
- Chưa tải toàn bộ VN100.
