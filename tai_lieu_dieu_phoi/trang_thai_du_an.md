# Trạng thái dự án

Cập nhật gần nhất: 2026-07-25

## Kho mã nguồn

- Kho: `Tienkhoaa2908/vn-quant-system`.
- Nhánh chính: `main`.
- Đầu `main`: `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`.
- Python mục tiêu: 3.12; công cụ môi trường: `uv`.
- GitHub là nguồn sự thật về nhánh, commit, PR và CI.

## Mốc 0–Mốc 3

Trạng thái: **đã đóng hoàn toàn**.

Mốc 3:

- PR triển khai số 7 đã gộp bằng merge commit `79a044d75f3a66e5c636f0a83613fc9af0cac3fc`.
- PR điều phối số 8 đã gộp bằng merge commit `bb25ff16761b7c79e701fbd4f3a5af02f1644e07`.
- CI sau gộp PR số 8:
  - workflow `kiem_tra_tu_dong`;
  - run number `185`;
  - Run ID `30151712433`;
  - Job ID `89663090052`;
  - trigger `push`;
  - branch `main`;
  - checkout `bb25ff16761b7c79e701fbd4f3a5af02f1644e07`;
  - `completed/success`.
- 121 kiểm thử ngoại tuyến và xác minh kỹ thuật engine trên FPT, HPG, MBB đã đạt.

## Giới hạn dữ liệu hiện tại

- Bộ ba mã chỉ là xác minh kỹ thuật.
- Chưa có lịch sử thành viên VN100 point-in-time thật được phê duyệt.
- Chưa có universe nhiều năm được kiểm toán.
- Cơ sở giá và corporate actions thật chưa được xác nhận đầy đủ.
- Chưa có feature set sản xuất, nhãn, walk-forward hoặc mô hình học máy.
- Không tích hợp SSI, không đọc tài khoản và không gửi lệnh.

## Mốc 4

Trạng thái: **đặc tả đã phê duyệt và gộp; nhánh chuyên môn đã mở; chưa triển khai mã**.

- PR đặc tả số 9 đã gộp bằng merge commit `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`.
- CI sau gộp PR số 9:
  - workflow `kiem_tra_tu_dong`;
  - run number `187`;
  - Run ID `30162993192`;
  - Job ID `89691237408`;
  - trigger `push`;
  - branch `main`;
  - checkout `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`;
  - `completed/success`.
- Tài liệu chính thức: `tai_lieu/dac_ta_moc_4.md`.
- Nhánh chuyên môn: `m4-dac_trung-xep_hang-hoc_may`.
- Base đã duyệt: `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`.
- Chưa mở PR triển khai.
- Chưa viết mã nghiên cứu hoặc học máy.

Các quyết định đã phê duyệt:

1. VN100 point-in-time là universe ưu tiên; universe thanh khoản cao point-in-time là proxy có kiểm soát.
2. Mục tiêu lịch sử tối thiểu 5 năm, ưu tiên 7–10 năm khi chất lượng cho phép.
3. Warm-up theo cửa sổ dài nhất, tối thiểu MA250.
4. Cơ sở giá và corporate actions phải nhất quán.
5. Feature MVP gồm xu hướng, động lượng, biến động, thanh khoản và market regime.
6. Tiền xử lý chỉ fit trên train.
7. Nhãn lợi nhuận tương đối 20 phiên.
8. Walk-forward expanding window có purge và embargo.
9. Momentum baseline và Logistic Regression trước LightGBM.
10. Ranking theo xác suất, `top_k`, tái cân bằng tháng và tỷ trọng đều để kiểm tra.
11. Đánh giá model, ranking và backtest hoàn toàn ngoài mẫu.
12. Sản phẩm bất biến, SHA-256 và truy vết đầy đủ.
