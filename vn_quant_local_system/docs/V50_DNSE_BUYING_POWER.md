# V50 — DNSE Authoritative Buying Power

## Vấn đề

`availableCash` không đồng nghĩa với sức mua.

Sau khi một lệnh bán khớp, DNSE có thể cho tái sử dụng tiền bán chờ về để mua
mã khác ngay, trong khi `availableCash` vẫn chỉ phản ánh phần tiền mặt đã khả
dụng. Vì vậy dùng riêng `availableCash` làm ngân sách planner sẽ đánh giá thiếu
vốn và tạo đề xuất mua thấp hơn khả năng thực tế.

Không được sửa bằng cách lấy chênh lệch số lượng vị thế nhân với giá hiện tại.
Cách đó không biết chính xác giá khớp, phí, thuế, trạng thái lệnh, gói vay hoặc
quy tắc ứng sức mua của DNSE.

## Nguồn V50

V50 dùng hai GET endpoint read-only:

```text
/order-service/v2/accounts/{accountNo}/loan-packages
/order-service/accounts/{accountNo}/ppse
```

Quy trình:

1. dùng đúng tiểu khoản đã chọn ở V49;
2. lấy danh sách gói vay;
3. chỉ chọn gói `type=N` — không margin;
4. lấy canonical Top-10 và giá đang dùng để lập kế hoạch;
5. gọi PPSE cho từng mã, giá và gói không margin;
6. lưu `ppse` và `qmax` theo mã;
7. dùng mức PPSE bảo thủ làm ngân sách chung;
8. khóa số lượng từng mã bằng `qmax`;
9. cộng khoản tiền mới của capital cycle sau cùng.

Không dùng Trading Token, không gọi POST/PUT/DELETE và không đặt lệnh.

## Ba khái niệm tiền

### Tiền khả dụng DNSE

Trường `availableCash` từ balance. Đây là tiền mặt khả dụng, không nhất thiết gồm
đầy đủ tiền bán chờ về có thể tái sử dụng.

### Sức mua planner

PPSE gói không margin. Đây là số được planner dùng khi endpoint đọc thành công.

### Tiền bán chờ về tái sử dụng

```text
max(sức mua planner - availableCash, 0)
```

Chỉ là phép trình bày chênh lệch giữa hai số do DNSE trả. Hệ thống không tự suy
ra số tiền bán từ position delta.

## Fail-closed

Nếu API loan-package hoặc PPSE không đọc được bằng credentials hiện tại:

```text
status = UNAVAILABLE
source = AVAILABLE_CASH_FALLBACK
planner = availableCash + new capital
```

Hệ thống vẫn đồng bộ danh mục nhưng không tự phỏng đoán tiền bán chờ về. Giao
diện phải hiển thị rõ đang fallback.

Nếu chỉ một số mã có PPSE thành công:

- ngân sách chung lấy theo các probe thành công;
- mã không có `qmax` hợp lệ bị chặn mua;
- không dùng sức mua margin để lấp khoảng trống.

## Tác động lên plan

Mỗi plan mới lưu thêm:

```text
buying_power_snapshot_id
buying_power_status
buying_power_source
dnse_buying_power_vnd
reusable_unsettled_proceeds_vnd
candidate_qmax_enforced
margin_buying_power_allowed=false
```

Plan cũ không bị viết lại.

## Vận hành

Sau khi bán hoặc nạp tiền:

```text
Đồng bộ danh mục DNSE
→ kiểm tra Tiền khả dụng và Sức mua planner
→ Tạo kế hoạch ngay
```

Nút tạo kế hoạch vẫn tự đồng bộ broker trước khi phân tích. Do đó planning cycle
mới sẽ dùng PPSE gắn với snapshot broker mới nhất.
