# Các kiểm định đã chạy và kết luận hiện tại

## Frozen model

```text
C3_STABLE_3_PAST_IC_SHRUNK
```

Không retune theo HNX hoặc micro-capital.

## HNX cross-market stress

Signal/ranking conditional PASS nhưng execution 1 tỷ thất bại do thanh khoản: mean fill khoảng 59%, ending cash khoảng 66%. Đây không phải bằng chứng model chọn mã thất bại.

## V42 VN100 capacity

Signal 57 tháng: Mean Rank IC 3,0088%, positive ratio 59,6491%, second-half Mean IC 7,6393%.

Một tỷ, một phiên: aggregate fill 97,6604%, worst 80,1719%, max cash drag 9,5508%.

Một tỷ, ba phiên: aggregate fill 99,8314%, P10 100%, worst 92,7162%, max cash drag 0%, max tracking error 2,8080%.

Kết luận: VN100 thanh khoản tốt hơn HNX rất nhiều; quy mô vài trăm nghìn mỗi tuần không có capacity concern đáng kể.

## V43.1 weekly micro-capital

Policy thắng cả 9 tổ hợp 3 mức tiền × 3 mức chi phí:

```text
P1_TOP10_UNDERWEIGHT_BUFFER20
```

Mức 250.000 đồng/tuần, BASE:

```text
Tổng nạp:                  116,25 triệu
Giá trị cuối:              270,16 triệu
Lợi nhuận:                 153,91 triệu
Lãi / tổng tiền nạp:       132,40%
XIRR:                       18,16%/năm
VNINDEX XIRR:               10,96%/năm
XIRR excess:                +7,20 điểm %/năm
Max drawdown:              -24,16%
Win rate vị thế đóng:       47,08%
Average winner:            +27,53%
Average loser:             -11,07%
Profit factor:               2,44
```

## Giới hạn

Point-in-time VN100, corporate actions, independent price-basis verification và odd-lot order-book history vẫn chưa hoàn chỉnh. Kết quả lịch sử không bảo đảm tương lai và không cấp quyền dùng vốn thật.
