# Kế hoạch tổng thể

## Mốc 0 — Nền tảng và kiểm tra dữ liệu

Trạng thái: **đã hoàn thành và đã gộp**.

## Mốc 1 — Dữ liệu thị trường thật

Trạng thái: **đã hoàn thành và đã đóng hoàn toàn**.

- Vnstock Community 4.0.4/KBS.
- JSON thô bất biến, SHA-256, chuẩn hóa, chất lượng và CSV sẵn sàng.
- FPT, HPG, MBB được xác minh cục bộ; không commit dữ liệu thật.

## Mốc 2 — Tập cổ phiếu và đường cơ sở

Trạng thái: **đã hoàn thành và đã đóng hoàn toàn**.

- Tập cổ phiếu point-in-time, thanh khoản, MA250 và động lượng.
- Không dùng ảnh chụp tương lai; đầu ra CSV/JSON ổn định.
- Merge commit: `6e8d2ed49c2ef57e43c9f0f2249361b26b838b33`.

## Mốc 3 — Mô phỏng giao dịch và backtest

Trạng thái: **đã hoàn thành và đã đóng hoàn toàn**.

- PR triển khai số 7, merge commit `79a044d75f3a66e5c636f0a83613fc9af0cac3fc`.
- PR điều phối số 8, merge commit `bb25ff16761b7c79e701fbd4f3a5af02f1644e07`.
- CI cuối trên `main`: run `#185`, Run ID `30151712433`, Job ID `89663090052`, `completed/success`.
- Engine T/T+1, lệnh DAY, phí, thuế, trượt giá, lot size, tiền mặt, vị thế, sổ cái, NAV và corporate actions MVP.
- 121 kiểm thử ngoại tuyến.
- Xác minh kỹ thuật trên FPT, HPG, MBB; không dùng kết quả làm bằng chứng hiệu quả đầu tư.

## Mốc 4 — Dữ liệu nhiều năm, đặc trưng, xếp hạng và học máy cơ sở

Trạng thái: **đặc tả đã phê duyệt và gộp; nhánh chuyên môn đã mở; chưa triển khai mã**.

- Đặc tả: `tai_lieu/dac_ta_moc_4.md`.
- PR đặc tả số 9 đã gộp bằng merge commit `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`.
- CI sau gộp trên `main`:
  - workflow `kiem_tra_tu_dong`;
  - run `#187`;
  - Run ID `30162993192`;
  - Job ID `89691237408`;
  - trigger `push`;
  - checkout `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`;
  - `completed/success`.
- Nhánh chuyên môn: `m4-dac_trung-xep_hang-hoc_may`.
- Base nhánh: `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`.

Phạm vi đã phê duyệt:

- VN100 point-in-time hoặc universe thanh khoản cao point-in-time được phê duyệt;
- dữ liệu nhiều năm, mục tiêu ít nhất 5 năm và ưu tiên 7–10 năm khi chất lượng cho phép;
- kiểm soát survivorship bias, look-ahead, mã mới niêm yết và warm-up MA250;
- feature giá, xu hướng, động lượng, biến động, thanh khoản và market regime;
- nhãn lợi nhuận tương đối 20 phiên;
- walk-forward có purge/embargo;
- baseline momentum và Logistic Regression;
- ranking, `top_k` và backtest ngoài mẫu qua engine Mốc 3;
- LightGBM chỉ sau quyết định riêng.

Mã Mốc 4 chỉ được triển khai trên nhánh chuyên môn và PR phải giữ Draft đến khi đoạn 00 phê duyệt.

## Mốc 5 — Chia vốn

Trạng thái: **chưa mở**.

- Inverse volatility.
- Tối đa 15% mỗi mã, 25% mỗi ngành.
- Tiền mặt theo market regime.

## Mốc 6 — Kiểm toán và giao dịch giả lập

Trạng thái: **chưa mở**.

- Rà soát rò rỉ dữ liệu, thiên lệch sống sót và tối ưu quá mức.
- Paper trading hằng ngày, chỉ sinh lệnh đề xuất để người dùng tự đặt trên SSI.
