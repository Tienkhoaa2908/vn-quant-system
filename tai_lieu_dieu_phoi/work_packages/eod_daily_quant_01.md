# EOD-DAILY-QUANT-01

## Mục tiêu

Đưa hệ thống từ dữ liệu tĩnh sang vòng dự đoán EOD hằng ngày bằng nguồn mở, không dùng realtime và không yêu cầu SSI API.

## Phạm vi

```text
KBS + VCI EOD
→ rate limit/retry
→ xác định phiên chung mới nhất
→ bắt kịp toàn bộ phiên còn thiếu
→ đối chiếu open/close/volume từng phiên
→ coverage gate 95%
→ publication reduced bất biến
→ feature ngày mới nhất
→ daily_prediction_input.zip
→ forward prediction
→ paper portfolio
→ daily_quant_output.zip
```

## Quyết định kiến trúc

- KBS là primary.
- VCI là nguồn cross-check.
- Chỉ dùng dữ liệu sau 18:00 giờ Việt Nam.
- Không dùng high/low làm blocker vì pipeline hiện tại đã khóa hợp đồng `reduced_open_close_volume_v1`.
- Không được nhảy từ ngày cuối local thẳng đến phiên mới nhất; mọi phiên giao dịch trung gian phải có và khớp hai nguồn.
- Một mã thiếu hoặc mismatch ở bất kỳ phiên cần bắt kịp nào sẽ bị loại khỏi toàn bộ increment của lần chạy.
- Không tự ghi đè lịch sử nếu cùng mã/ngày có giá trị khác.
- Không đưa raw KBS/VCI vào ZIP gửi qua chat.
- Không sửa `pyproject.toml`, `uv.lock` hoặc workflow.
- `vnstock==4.0.4` và `lightgbm==4.6.0` chỉ được cài tạm bằng `uv run --with`.

## Input tự động tìm

Trong `data_root`:

```text
prediction_input.zip
publication reduced hợp lệ mới nhất
```

Publication chỉ được nhận khi ba product hash khớp manifest và CSV đúng schema canonical.

## Output

```text
data_quality_report.json
daily_prediction_summary.txt
daily_prediction_input.zip
updated_publication/
prediction/latest_prediction.csv
prediction/model_comparison.json
paper_portfolio.csv
manifest.json
daily_quant_output.zip
raw/kbs.json
raw/vci.json
```

## Gate fail-closed

Dừng trước prediction khi:

- chạy trước 18:00;
- VNINDEX chưa có phiên chung KBS/VCI;
- ngày làm việc hiện tại chưa được nguồn công bố;
- coverage EOD phiên mới nhất dưới 95%;
- thiếu một phiên trung gian cần bắt kịp;
- open/close lệch quá 10 bps;
- volume lệch quá 5%;
- historical revision conflict;
- feature coverage dưới 95%;
- input ZIP hoặc publication sai hash/schema.

## Kiểm thử synthetic

Không gọi mạng:

1. high/low không chặn hợp đồng reduced;
2. bắt kịp hai phiên liên tiếp;
3. thiếu một phiên thì loại toàn bộ increment của mã;
4. pipeline đầu-cuối với fake KBS/VCI;
5. chặn trước 18:00;
6. khóa phiên bản Vnstock;
7. ZIP cuối không chứa raw;
8. publication mới chứa đủ các dòng incremental.

## Trạng thái implementation

```text
branch: eod-daily-quant-01
base: 852df470cc64c569a4ef7f45ee26e045ea9ca508
module vận hành: he_thong_dinh_luong.eod_hang_ngay_v2
PR: #32
```

## Giới hạn

```text
technical_validation_only=true
research_eligible=false
```

Các cửa PIT universe, price basis và corporate actions chưa được đóng. Package này giải quyết vòng dữ liệu và dự đoán hằng ngày, không tự tuyên bố alpha hoặc khuyến nghị đầu tư.
