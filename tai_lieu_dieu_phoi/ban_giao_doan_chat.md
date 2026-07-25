# Bàn giao đoạn chat điều phối

Cập nhật: 2026-07-25

## Vai trò và nền

- Đoạn `00` là đầu mối điều phối trung tâm.
- Kho: `Tienkhoaa2908/vn-quant-system`.
- `main`: `bb25ff16761b7c79e701fbd4f3a5af02f1644e07`.
- Nhánh điều phối hiện tại: `dac_ta-moc-4`.
- Nhánh chỉ chứa tài liệu; không triển khai mã Mốc 4.
- Không force-push, không commit `du_lieu/`, không tự gộp PR.

## Mốc 3 đã đóng hoàn toàn

- PR triển khai số 7, merge commit `79a044d75f3a66e5c636f0a83613fc9af0cac3fc`.
- PR điều phối số 8, merge commit `bb25ff16761b7c79e701fbd4f3a5af02f1644e07`.
- CI cuối:
  - run `#185`;
  - Run ID `30151712433`;
  - Job ID `89663090052`;
  - checkout đúng `bb25ff16761b7c79e701fbd4f3a5af02f1644e07`;
  - `completed/success`.
- 121 kiểm thử và xác minh kỹ thuật trên FPT, HPG, MBB đã đạt.

## Đặc tả Mốc 4

Tệp:

```text
tai_lieu/dac_ta_moc_4.md
```

Các quyết định cần phê duyệt:

1. VN100 point-in-time là universe ưu tiên.
2. Universe thanh khoản cao point-in-time là proxy khi chưa có lịch sử VN100 tin cậy.
3. Mục tiêu ít nhất 5 năm dữ liệu hữu dụng; ưu tiên 7–10 năm khi chất lượng cho phép.
4. Warm-up theo cửa sổ dài nhất, tối thiểu MA250.
5. Giá điều chỉnh hoặc giá không điều chỉnh cộng corporate actions; không trộn hai chế độ.
6. Feature MVP gồm xu hướng, động lượng, biến động, thanh khoản và regime.
7. Nhãn nhị phân dựa trên lợi nhuận tương đối 20 phiên.
8. Walk-forward expanding window, purge/embargo và tái huấn luyện hằng tháng.
9. Momentum baseline và Logistic Regression trước LightGBM.
10. Ranking xác suất, `top_k`, tái cân bằng tháng và tỷ trọng đều để kiểm tra.
11. Đánh giá model, ranking và backtest ngoài mẫu.
12. Sản phẩm bất biến, SHA-256 và báo cáo coverage.

## Cửa kiểm soát

- PR đặc tả phải giữ Draft đến khi đoạn 00 xác minh.
- Không viết mã trước khi đặc tả được phê duyệt, gộp và CI `main` đạt.
- Không mở Mốc 5.
- Không kết nối SSI, không đọc tài khoản và không gửi lệnh.
