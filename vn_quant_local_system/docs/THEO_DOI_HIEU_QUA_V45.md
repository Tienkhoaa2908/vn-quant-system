# V45 Live Performance Observatory

## 1. Mục tiêu

V45 bắt đầu kiểm định ngoài mẫu từ ngày người dùng chốt snapshot mở đầu. Hệ thống không dùng lợi nhuận trước ngày bắt đầu để đánh giá C3.

Bốn lớp được tách riêng:

1. **Whole DNSE account**: toàn bộ tài khoản thật, gồm vị thế cũ, tiền mặt và holdings không thuộc model.
2. **Actual model sleeve**: phần tiền và giao dịch được xác nhận là thực thi chiến lược.
3. **Plan shadow**: plan đầu tiên của mỗi ISO week, thực thi giả lập tại giá mở cửa phiên kế tiếp.
4. **C3 signal scorecard**: forward return và Rank IC của ranking, không phụ thuộc người dùng có mua hay không.

VNINDEX benchmark nhận cùng dòng tiền với plan shadow.

## 2. Snapshot mở đầu

Trước khi bắt đầu cần đồng bộ danh mục DNSE sau phiên giao dịch. Snapshot mở đầu lưu bất biến:

- ngày bắt đầu;
- broker snapshot ID;
- tiền mặt đưa vào model sleeve;
- số lượng và giá thị trường từng vị thế;
- phân loại `LEGACY_EXCLUDED` hoặc `ADOPTED_AT_START`;
- phiên bản Observatory và giả định chi phí.

Mặc định mọi holding cũ là `LEGACY_EXCLUDED`. Khi chọn `ADOPTED_AT_START`, vị thế được đánh dấu lại theo giá thị trường tại ngày bắt đầu; giá vốn lịch sử không được đưa vào lợi nhuận model.

## 3. Dòng tiền

Có hai khái niệm khác nhau:

- tiền dự kiến nạp tuần trong planner;
- tiền đã thực sự vào DNSE trong Observatory.

Chỉ ghi `DEPOSIT` khi tiền đã xuất hiện trong tài khoản. Chỉ ghi `WITHDRAWAL` khi tiền đã rời tài khoản. Dòng tiền thực được dùng cho actual sleeve, XIRR và điều chỉnh TWR của whole DNSE.

## 4. Fill thực tế

V45 không suy diễn giá khớp từ average cost của broker vì dữ liệu đó có thể bị ảnh hưởng bởi bán một phần, phí, quyền hoặc chuyển vị thế.

Fill thực tế được xác nhận bằng:

- ngày khớp;
- BUY hoặc SELL;
- mã;
- số lượng;
- giá khớp;
- phí;
- thuế;
- plan ID nếu biết.

Event ledger là append-only. Không sửa quá khứ sau khi biết kết quả.

## 5. Plan shadow

Để chống look-ahead, plan đầu tiên được tạo trong mỗi ISO week là plan canonical của tuần đó. Những lần tạo lại sau đó không thay thế lịch sử shadow.

Quy tắc thực thi:

```text
ngày tạo plan
→ phiên giao dịch kế tiếp
→ bán trước
→ mua sau
→ giá mở cửa
→ phí giả định 50 bps
→ thuế bán 10 bps
```

Nếu dữ liệu phiên kế tiếp chưa có, plan ở trạng thái `PENDING_MARKET_DATA`.

## 6. Chỉ số

Mỗi stream hiển thị:

- NAV;
- cash và invested value;
- TWR tích lũy;
- XIRR;
- max drawdown.

TWR loại ảnh hưởng của thời điểm nạp/rút tiền. XIRR mô tả trải nghiệm tiền thật.

## 7. Reconciliation

Mỗi shadow trade được ghép với actual fill theo plan ID, mã, chiều và thời gian. Các chỉ số gồm:

- số lượng đề xuất và thực tế;
- execution delay;
- quantity compliance;
- actual price so với shadow price;
- price slippage;
- trạng thái executed, partial, missed hoặc unmatched.

## 8. Signal scorecard

Từ mỗi monthly canonical ranking sau ngày bắt đầu, hệ thống tính khi đủ dữ liệu:

- Top-10 mean return ở 5, 20 và 60 phiên;
- excess return so với VNINDEX;
- tỷ lệ mã Top-10 thắng VNINDEX;
- Rank IC của toàn bộ ranking.

Đây là lớp chính để đánh giá C3 độc lập với cash, sizing và execution.

## 9. Giới hạn

- Actual model sleeve chỉ chính xác khi mọi dòng tiền và fill liên quan được xác nhận.
- Whole DNSE TWR chỉ chính xác khi toàn bộ khoản nạp/rút được ghi.
- Plan shadow đánh giá output plan đã phát hành, không đại diện giá khớp lô lẻ thực tế.
- Hệ thống chỉ nghiên cứu, không đặt lệnh và không phê duyệt vốn thật.
