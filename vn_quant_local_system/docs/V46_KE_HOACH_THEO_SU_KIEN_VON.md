# V46 — Kế hoạch theo sự kiện vốn

## Mục tiêu

V46 bỏ ràng buộc mỗi tuần chỉ có một kế hoạch. Người dùng có thể tạo kế hoạch
bất kỳ lúc nào có tiền mới, tiền bán đã khả dụng hoặc muốn rà soát danh mục.

Mỗi lần bấm **Tạo kế hoạch ngay** tạo một `capital cycle` bất biến gồm:

- thời điểm tạo;
- snapshot DNSE được dùng;
- số tiền mới của lần này;
- ranking C3 tháng đang có hiệu lực;
- danh sách mua;
- rà soát toàn bộ vị thế bán;
- giả định chi phí;
- output JSON để audit.

## Công thức vốn

```text
Tiền có thể giải ngân
= tiền khả dụng DNSE tại snapshot
+ tiền mới dự kiến cho capital cycle hiện tại
```

Không gọi khoản tiền mới là ngân sách tuần. Giá trị mặc định trong state database
chỉ giúp điền nhanh form; mỗi lần bấm vẫn tạo một cycle riêng.

## Shadow performance

Sau khi Observatory đã bắt đầu, mọi capital cycle được tạo sau snapshot mở đầu
đều được chọn làm shadow plan độc lập. Không còn giới hạn một plan mỗi tuần.

```text
Capital cycle được tạo
→ shadow nhận đúng số tiền mới của cycle
→ giả lập bán trước, mua sau
→ khớp giá mở cửa phiên kế tiếp
→ tính NAV, TWR, XIRR và đối soát actual
```

Plan tạo trước snapshot mở đầu không được đưa vào shadow. Plan không có tiền mới
vẫn có thể rà soát hoặc sử dụng tiền khả dụng đang tồn tại; shadow không tự cộng
thêm dòng tiền cho cycle đó.

## Tổng quan thị trường

Tab **Thị trường** là read-only:

- hiển thị VNINDEX và MA250;
- hiển thị Risk-on/Risk-off;
- hiển thị Top 10, Top 20 hoặc Top 30 C3;
- so sánh hạng với canonical run trước;
- đánh dấu mã đang sở hữu.

Trang này không tạo plan, không thay đổi shadow và không gửi lệnh.

## Tần suất model

C3 canonical tiếp tục chạy theo tháng. Người dùng có thể mở tab Thị trường bất kỳ
lúc nào để xem ranking tháng đang có hiệu lực. Việc tạo nhiều capital cycle trong
tháng không làm model retrain hoặc thay ranking.

## Quy trình vận hành

Khi có tiền:

1. Đồng bộ giá.
2. Đồng bộ danh mục DNSE.
3. Nhập số tiền mới của lần này.
4. Bấm Tạo kế hoạch ngay.
5. Xem đề xuất mua và sell review.
6. Sau khi tiền thật vào DNSE, ghi actual deposit trong tab Hiệu quả.
7. Sau khi lệnh khớp, ghi actual fill.

Khi chỉ muốn xem thị trường:

1. Mở tab Thị trường.
2. Chọn Top 10, Top 20 hoặc Top 30.
3. Không cần tạo kế hoạch.

## Giới hạn

- Không đặt lệnh broker.
- Không lưu trading token.
- Multi-buy vẫn là biến thể nghiên cứu, chưa có kiểm định lịch sử độc lập tốt hơn
  baseline một mã mỗi lần.
- Kết quả phụ thuộc chất lượng dữ liệu, snapshot DNSE và việc xác nhận fill thật.
