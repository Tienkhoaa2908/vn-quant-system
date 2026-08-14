# V49 — DNSE Source Integrity

## Phạm vi

V49 chỉ sửa lớp biên dữ liệu DNSE và cách trình bày độ mới của nguồn.

Không thay đổi:

- model C3;
- canonical tháng và latest preview;
- purchase guard;
- capital planner;
- sell gate hai tháng;
- shadow portfolio;
- event ledger và correction V48.

## Lỗi được sửa

### Cache OHLC gần nhất

Cơ chế cũ ghi toàn bộ cửa sổ yêu cầu vào `fetched_ranges` dù DNSE có thể chưa
trả bar của phiên cuối. Lần đồng bộ sau có thể coi ngày thiếu là đã covered và
không gọi lại API.

V49 bỏ `fetched_ranges` khỏi quyết định refresh gần nhất. Mỗi lần đồng bộ:

1. đọc lịch giao dịch từ `/market/working-dates`;
2. xác định phiên EOD kỳ vọng;
3. gọi lại `/price/ohlc` cho cửa sổ gần nhất;
4. chèn bar còn thiếu;
5. cho phép nguồn hiệu chỉnh bar trong cửa sổ gần nhất và ghi audit;
6. cách ly bar của phiên chưa hoàn tất;
7. báo rõ freshness và coverage.

### Parser vị thế

Cơ chế cũ dùng biểu thức kiểu:

```python
openQuantity or accumulateQuantity
```

Do đó `openQuantity = 0` bị coi là thiếu dữ liệu và `accumulateQuantity` lịch
sử có thể làm vị thế đã đóng xuất hiện lại. `tradeQuantity = 0` cũng có thể bị
thay bằng tổng số lượng.

V49 coi số 0 là giá trị hợp lệ:

- `openQuantity = 0`: không còn vị thế mở;
- `tradeQuantity = 0`: chưa có cổ phiếu có thể bán;
- chỉ fallback khi trường thực sự không có hoặc là `null`.

## Tiểu khoản DNSE

V49 chỉ dùng một tiểu khoản cơ sở làm nguồn planner và danh mục.

- Nếu chỉ có một tiểu khoản đọc được, hệ thống tự chọn.
- Nếu chỉ một tiểu khoản có vị thế mở, hệ thống tự chọn tiểu khoản đó.
- Nếu còn mơ hồ, hệ thống dừng và yêu cầu chọn tại tab **Dữ liệu & API**.
- Chỉ token băm và số đã che được lưu; không lưu số tiểu khoản đầy đủ trong file
  lựa chọn.

## Tiền mặt

Ba trường được hiển thị riêng:

- `availableCash`: tiền DNSE cho phép sử dụng; planner dùng trường này;
- `withdrawableCash`: tiền có thể rút, chỉ để đối chiếu;
- `plannerCash`: nguồn thực tế planner đang dùng.

Không còn lấy `min(availableCash, withdrawableCash)` rồi gắn nhãn mơ hồ là tiền
khả dụng.

## Hai lớp định giá

### Broker snapshot

Dùng `marketPrice` DNSE tại thời điểm gọi API, fallback sang EOD local khi broker
không trả giá. Dùng để đối chiếu gần nhất với ứng dụng DNSE.

### Research EOD

Dùng close trong kho OHLC local của phiên EOD đã hoàn tất. Dùng cho model và
chuỗi kiểm định nhất quán.

Hai NAV được hiển thị riêng; không trộn tiền broker mới với giá local cũ trong
cùng một nhãn.

## Freshness

- `CURRENT_FINAL_EOD`: VNINDEX đúng phiên kỳ vọng và coverage cổ phiếu đạt ngưỡng.
- `PARTIAL_STOCK_COVERAGE`: VNINDEX đã có nhưng universe chưa đủ coverage.
- `SOURCE_LAGGING_OR_EMPTY`: hệ thống đã gọi lại API nhưng nguồn chưa trả đủ
  phiên kỳ vọng.
- `EXPECTED_SESSION_UNKNOWN`: không đọc được lịch DNSE; hệ thống dùng ngày làm
  việc trong tuần làm fallback và hiển thị rõ.

Sau khi thị trường đóng cửa, bấm **Cập nhật đánh giá mới nhất**. Nếu vẫn hiện
`SOURCE_LAGGING_OR_EMPTY`, đó là kết quả của lần gọi API mới chứ không còn là
cache `fetched_ranges` cũ.
