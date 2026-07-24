# Bàn giao đoạn chat điều phối

Cập nhật: 2026-07-24

## Vai trò

- Đoạn `00` là đầu mối điều phối trung tâm.
- Đoạn `01` phụ trách chuyên môn Mốc 1 — dữ liệu.
- GitHub là nguồn sự thật về nhánh, commit, yêu cầu gộp và kiểm tra tự động.
- Không chuyển mốc khi Mốc 1 chưa được gộp và xác minh.

## Trạng thái bền vững đã xác minh

### Nền điều phối

- Yêu cầu gộp số `2`: đã gộp.
- Đầu `main`: `4eba2a77d5864027c84d4350769d95fd4abd5fee`.
- `main` đã chứa `tai_lieu_dieu_phoi/`.
- Nhánh `m1-du_lieu` đã cập nhật từ `main` qua commit
  `5ae994df47ce34a5ab5d3c5dd1e3d206d864811c`.

### Mốc 1

- Yêu cầu gộp số `3`: mở, nháp, chưa gộp.
- Hai commit triển khai chính:
  1. `0310e0667f569608676066dfe935fd3f9e782f4f` — lát cắt dữ liệu ngoại tuyến.
  2. `e6dd3d8125e092cbee2d956269324a96a543e026` — nguồn Vnstock và lệnh tải thật nhỏ.
- Kiến trúc nguồn, lưu dữ liệu thô bất biến, chuẩn hóa, kiểm tra chất lượng,
  dữ liệu sẵn sàng và trạng thái từng mã đã có.
- VNINDEX vẫn là phần mở rộng và không chặn ba mã bắt buộc.

## Kết quả thăm dò thật Vnstock 4.0.4

Báo cáo đã xác minh:

- mã lần chạy: `20260724T152739494769Z_521d23ce`;
- khoảng ngày: `2026-07-01` đến `2026-07-10`;
- nguồn: `vnstock_kbs`;
- phiên bản: `4.0.4`.

Cách gọi đã hoạt động:

```python
Market().equity(symbol=ma).ohlcv(
    start=...,
    end=...,
    interval="1D",
    source="kbs",
)
```

Kết quả:

- FPT: thành công, 8 dòng, ngày đầu `2026-07-01`, ngày cuối `2026-07-10`;
- HPG: thành công, 8 dòng, ngày đầu `2026-07-01`, ngày cuối `2026-07-10`;
- MBB: thành công, 8 dòng, ngày đầu `2026-07-01`, ngày cuối `2026-07-10`.

Cả ba mã:

- cột thật: `time`, `open`, `high`, `low`, `close`, `volume`;
- kiểu thật: `datetime64[ns]`, `float64`, `int64`;
- đơn vị giá được báo cáo: nghìn đồng;
- không có lỗi;
- chưa phát hiện tham số chọn giá điều chỉnh/chưa điều chỉnh.

Kết luận chuyên môn của bước này: **giao diện Vnstock hiện tại đã được chứng minh bằng chạy thật cho FPT, HPG và MBB**. Không cần sửa bộ chuyển đổi chỉ vì bất nhất giữa các ví dụ tài liệu.

## Điều kiện còn thiếu

1. Chưa có lần tải thật nhỏ và nhật ký tổng hợp.
2. Chưa có log kiểm thử Python 3.12.
3. GitHub Actions chưa ghi nhận lần chạy trên đầu nhánh hiện tại.
4. Chưa có báo cáo cuối về sản phẩm cục bộ và trạng thái từng mã.
5. PR số `3` chưa được phép chuyển khỏi trạng thái nháp.

## Trình tự tiếp theo

1. Người dùng chạy lệnh tải thật nhỏ cho FPT, HPG, MBB.
2. Người dùng gửi `du_lieu/nhat_ky/<ma_lan_chay>/tong_hop.json`.
3. Người dùng chạy toàn bộ kiểm thử bằng Python 3.12 và gửi log.
4. Đoạn `01` rà soát kết quả, sửa nhỏ nếu cần và kiểm tra Actions.
5. Cập nhật ba tệp điều phối bằng sự thật đã xác minh.
6. Gửi báo cáo cuối về đoạn `00`.

## Không được làm

- Không gộp PR số `3`.
- Không mở Mốc 2.
- Không đưa dữ liệu thật, nhật ký thật hoặc khóa lên GitHub.
- Không thêm MA250, mô phỏng giao dịch, học máy hoặc chia vốn.
