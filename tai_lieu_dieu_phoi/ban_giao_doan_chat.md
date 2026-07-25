# Bàn giao đoạn chat điều phối

Cập nhật: 2026-07-25

## Vai trò và nền

- Đoạn `00` là đầu mối điều phối trung tâm.
- Đoạn `04` là đoạn chuyên môn triển khai Mốc 4.
- Kho: `Tienkhoaa2908/vn-quant-system`.
- `main`: `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`.
- Nhánh chuyên môn: `m4-dac_trung-xep_hang-hoc_may`.
- Base đã duyệt: `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`.
- Không force-push, không commit `du_lieu/`, không tự gộp PR.

## Cửa mở Mốc 4

- PR đặc tả số 9 đã gộp bằng merge commit `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`.
- CI sau gộp:
  - workflow `kiem_tra_tu_dong`;
  - run `#187`;
  - Run ID `30162993192`;
  - Job ID `89691237408`;
  - checkout đúng `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6` trên `main`;
  - `completed/success`.
- Nhánh chuyên môn đã được tạo từ đúng merge commit.
- Chưa có mã Mốc 4 tại thời điểm bàn giao.

## Đặc tả Mốc 4

Tệp chính thức:

```text
tai_lieu/dac_ta_moc_4.md
```

Các quyết định đã phê duyệt:

1. VN100 point-in-time là universe ưu tiên.
2. Universe thanh khoản cao point-in-time là proxy khi chưa có lịch sử VN100 tin cậy.
3. Mục tiêu ít nhất 5 năm dữ liệu hữu dụng; ưu tiên 7–10 năm khi chất lượng cho phép.
4. Warm-up theo cửa sổ dài nhất, tối thiểu MA250.
5. Giá điều chỉnh hoặc giá không điều chỉnh cộng corporate actions; không trộn hai chế độ.
6. Feature MVP gồm xu hướng, động lượng, biến động, thanh khoản và regime.
7. Tiền xử lý chỉ fit trên train.
8. Nhãn nhị phân dựa trên lợi nhuận tương đối 20 phiên.
9. Walk-forward expanding window, purge/embargo và tái huấn luyện hằng tháng.
10. Momentum baseline và Logistic Regression trước LightGBM.
11. Ranking xác suất, `top_k`, tái cân bằng tháng và tỷ trọng đều để kiểm tra.
12. Đánh giá ngoài mẫu, sản phẩm bất biến, SHA-256 và báo cáo coverage.

## Yêu cầu với đoạn 04

- Đọc toàn bộ đặc tả trước khi viết mã.
- Báo kế hoạch kiến trúc trước khi triển khai phần lớn hệ thống.
- Tách module universe, coverage, feature, label, walk-forward, preprocessing, model, ranking, backtest adapter, metrics, publication và CLI.
- CI hoàn toàn ngoại tuyến.
- Không gọi Vnstock trong GitHub Actions.
- Không thêm LightGBM.
- Mở PR Draft và giữ Draft.
- Không chạy universe thật mở rộng trước khi đoạn 00 mở cửa.
- Không mở Mốc 5.
- Không kết nối SSI, không đọc tài khoản và không gửi lệnh.
