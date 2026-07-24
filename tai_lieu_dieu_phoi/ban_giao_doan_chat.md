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

- Mã lần chạy: `20260724T152739494769Z_521d23ce`.
- Khoảng ngày: `2026-07-01` đến `2026-07-10`.
- Nguồn: `vnstock_kbs`.
- Cách gọi đã hoạt động:

```python
Market().equity(symbol=ma).ohlcv(
    start=...,
    end=...,
    interval="1D",
    source="kbs",
)
```

- FPT: thành công, 8 dòng.
- HPG: thành công, 8 dòng.
- MBB: thành công, 8 dòng.
- Cột: `time`, `open`, `high`, `low`, `close`, `volume`.
- Kiểu: `datetime64[ns]`, `float64`, `int64`.
- Đơn vị giá được báo cáo: nghìn đồng.
- Chưa phát hiện tham số chọn giá điều chỉnh/chưa điều chỉnh.

## Kết quả tải thật nhỏ

Báo cáo tổng hợp đã xác minh:

- mã lần chạy: `20260724T153953222157Z_5383eaab`;
- khoảng ngày: `2026-07-01` đến `2026-07-10`;
- nguồn: `vnstock_kbs`;
- phiên bản: `4.0.4`.

Kết quả:

- FPT: thành công, 8 dòng, một lần thử, không cảnh báo, không lỗi;
- HPG: thành công, 8 dòng, một lần thử, không cảnh báo, không lỗi;
- MBB: thành công, 8 dòng, một lần thử, không cảnh báo, không lỗi.

Mỗi mã có đường dẫn được ghi nhận cho:

- dữ liệu thô JSON;
- dữ liệu chuẩn hóa CSV;
- dữ liệu sẵn sàng CSV;
- báo cáo chất lượng JSON;
- nhật ký JSON.

Mỗi dữ liệu thô có mã SHA-256 trong bản tổng hợp. Không đưa bất kỳ tệp nào dưới `du_lieu/` lên GitHub.

## Kết quả kiểm thử Python 3.12

- Đã cài `CPython 3.12.13` cho Windows x86-64.
- `uv` đồng bộ môi trường thành công; log ghi `Checked in 1ms`.
- Không phát hiện lỗi biên dịch trong log được cung cấp.
- `Ran 30 tests in 0.696s`.
- Kết quả: `OK`.

## Điều kiện còn thiếu

1. GitHub Actions chưa được xác minh đạt trên đầu nhánh cuối cùng.
2. Cần mã lần chạy, job và trạng thái từng bước của CI.
3. Sau khi CI đạt, cần cập nhật tài liệu điều phối lần cuối và gửi báo cáo đoạn `00`.
4. PR số `3` chưa được phép chuyển khỏi trạng thái nháp nếu chưa có quyết định của đoạn `00`.

## Trình tự tiếp theo

1. Kiểm tra Actions trên commit đầu nhánh mới nhất.
2. Nếu Actions không xuất hiện, kiểm tra `Settings → Actions → General`; không tạo commit rỗng.
3. Nếu Actions chạy, rà soát toàn bộ job và bước.
4. Cập nhật ba tệp điều phối bằng kết quả CI.
5. Gửi báo cáo cuối về đoạn `00`.

## Không được làm

- Không gộp PR số `3`.
- Không mở Mốc 2.
- Không đưa dữ liệu thật, nhật ký thật hoặc khóa lên GitHub.
- Không thêm MA250, mô phỏng giao dịch, học máy hoặc chia vốn.
