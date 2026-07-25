# Kế hoạch tổng thể

## Mốc 0 — Nền tảng và kiểm tra dữ liệu

Trạng thái: **đã hoàn thành, kiểm tra tự động đạt và đã gộp vào `main` qua yêu cầu gộp số 1**.

Kết quả: Python 3.12, `uv`, gói `he_thong_dinh_luong`, kiểm tra CSV giá, dữ liệu giả lập và GitHub Actions.

## Mốc 1 — Dữ liệu thị trường thật

Trạng thái: **đã hoàn thành, đã gộp và đã đóng hoàn toàn sau PR số 4**.

- Vnstock Community 4.0.4/KBS.
- JSON thô bất biến, SHA-256, chuẩn hóa, chất lượng và CSV sẵn sàng.
- FPT, HPG, MBB được xác minh cục bộ; không commit dữ liệu thật.
- Đầu `main` khi đóng Mốc 1: `97399e291b0d3d237f247f58ffa03049826d40bd`.

## Mốc 2 — Tập cổ phiếu và đường cơ sở

Trạng thái: **đã hoàn thành, đã gộp qua PR số 5 và đã xác minh CI sau gộp**.

- Tập cổ phiếu point-in-time, thanh khoản, MA250 và động lượng.
- Không dùng ảnh chụp tương lai; đầu ra CSV/JSON ổn định.
- CLI truy vết `so_nen`; FPT, HPG, MBB mỗi mã 287 phiên và 38 dòng MA250.
- Merge commit: `6e8d2ed49c2ef57e43c9f0f2249361b26b838b33`.

## Mốc 3 — Mô phỏng giao dịch và backtest

Trạng thái: **đã hoàn thành, đã gộp qua PR số 7 và CI sau gộp trên `main` đã đạt**.

Git và CI:

- Head được phê duyệt: `305da62ac54b735a129ab4dc2c66b0826b8953c3`.
- Merge commit: `79a044d75f3a66e5c636f0a83613fc9af0cac3fc`.
- CI sau gộp: run `#183`, Run ID `30150924124`, Job ID `89661073156`, `completed/success`.

Đã triển khai:

- tín hiệu sau close T, khớp sớm nhất tại open phiên kế tiếp;
- lệnh DAY, không tự dời khi thiếu bar/open;
- mô hình lệnh, khớp lệnh, vị thế, tiền mặt, sổ cái và NAV;
- phí mua/bán, thuế bán, trượt giá, lot size và định cỡ sức mua;
- long-only, không short, không margin, không tiền mặt âm, không bán vượt vị thế;
- corporate actions MVP: chia tách, cổ phiếu thưởng, cổ tức tiền mặt và chống tính hai lần;
- realized/unrealized P&L, đối soát NAV và truy vết đơn vị;
- baseline mua-và-giữ, cân-bằng-đều, MA250/động lượng chỉ để kiểm tra engine;
- CAGR, drawdown, Sharpe, turnover, chi phí và tỷ trọng tiền mặt;
- chín sản phẩm bất biến, manifest SHA-256, công bố nguyên tử và rollback;
- 121 kiểm thử ngoại tuyến;
- xác minh kỹ thuật trên FPT, HPG, MBB bằng dữ liệu thật ngoài repository.

Giới hạn:

- bộ ba mã chỉ dùng xác minh kỹ thuật;
- chưa có lịch sử thành viên VN100 point-in-time thật;
- chưa có corporate actions thật được phê duyệt đầy đủ;
- chưa có nghiên cứu nhiều năm trên toàn universe;
- không tích hợp SSI, không đọc tài khoản và không gửi lệnh.

## Điều kiện dữ liệu trước nghiên cứu chiến lược

Trước khi đánh giá chiến lược hoặc huấn luyện mô hình, đặc tả tiếp theo phải chốt:

- universe VN100 point-in-time hoặc universe thanh khoản cao point-in-time;
- không dùng danh sách VN100 hiện tại áp ngược cho toàn bộ lịch sử;
- lịch sử nhiều năm, mục tiêu 5–10 năm nếu chất lượng dữ liệu cho phép;
- warm-up tối thiểu cho MA250;
- kiểm soát survivorship bias, look-ahead và mã mới niêm yết;
- cơ sở giá và corporate actions nhất quán;
- báo cáo độ phủ dữ liệu, mã lỗi, mã thiếu lịch sử và mã bị loại.

## Mốc 4 — Đặc trưng và học máy

Trạng thái: **chưa mở; chưa có nhánh triển khai và chưa được phép viết mã**.

Phạm vi dự kiến, phải được đặc tả và phê duyệt trước:

- đặc trưng giá, động lượng, biến động, thanh khoản và thị trường;
- nhãn không nhìn trước;
- walk-forward validation;
- Logistic Regression trước;
- LightGBM chỉ sau khi baseline tuyến tính và pipeline đánh giá đạt;
- ranking trên universe point-in-time nhiều năm.

## Mốc 5 — Chia vốn

Trạng thái: **chưa mở**.

- Inverse volatility.
- Tối đa 15% mỗi mã, 25% mỗi ngành.
- Tiền mặt theo market regime.

## Mốc 6 — Kiểm toán và giao dịch giả lập

Trạng thái: **chưa mở**.

- Rà soát rò rỉ dữ liệu, thiên lệch sống sót và tối ưu quá mức.
- Paper trading hằng ngày, chỉ sinh lệnh đề xuất để người dùng tự đặt trên SSI.