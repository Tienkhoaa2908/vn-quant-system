# Trạng thái dự án

Cập nhật gần nhất: 2026-07-25

## Kho mã nguồn

- Kho: `Tienkhoaa2908/vn-quant-system`.
- Nhánh chính: `main`.
- Đầu `main`: `bb25ff16761b7c79e701fbd4f3a5af02f1644e07`.
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

Trạng thái: **đang chuẩn bị đặc tả; chưa mở triển khai**.

- Nhánh điều phối: `dac_ta-moc-4`.
- Base: `bb25ff16761b7c79e701fbd4f3a5af02f1644e07`.
- Tài liệu dự thảo: `tai_lieu/dac_ta_moc_4.md`.
- Nhánh chỉ được chứa tài liệu.
- Chưa tạo nhánh `m4-dac_trung-xep_hang-hoc_may`.
- Chưa viết mã Mốc 4.

Các cửa phải phê duyệt:

1. nguồn VN100 point-in-time hoặc universe proxy;
2. mục tiêu lịch sử tối thiểu 5 năm, ưu tiên 7–10 năm khi chất lượng cho phép;
3. warm-up và coverage;
4. cơ sở giá và corporate actions;
5. bộ feature MVP;
6. nhãn lợi nhuận tương đối 20 phiên;
7. walk-forward có purge/embargo;
8. Logistic Regression trước LightGBM;
9. ranking và lịch tái cân bằng;
10. chỉ số đánh giá ngoài mẫu;
11. sản phẩm và truy vết;
12. tiêu chí xác minh universe mở rộng.
