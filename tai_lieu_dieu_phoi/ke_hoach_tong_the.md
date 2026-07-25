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

Trạng thái: **đã triển khai kỹ thuật trên nhánh chuyên môn; PR số 7 đang ở trạng thái draft để đoạn 00 nghiệm thu**.

Nền và điều phối:

- Đặc tả: `tai_lieu/dac_ta_moc_3.md`.
- Base đã duyệt: `f52e06ffd4dde26e8af9d6451ec1e64f5a61b35d`.
- Nhánh: `m3-mo_phong-giao_dich`.
- PR draft: số 7, tiêu đề `M3: mo phong giao dich va backtest`.

Đã triển khai:

- tín hiệu sau close T, khớp sớm nhất tại open phiên kế tiếp;
- lệnh DAY, không tự dời khi thiếu bar/open;
- mô hình lệnh, khớp lệnh, vị thế, tiền mặt, sổ cái và NAV;
- phí mua/bán, thuế bán, trượt giá, lot size và chế độ mã vắng mặt bằng cấu hình;
- long-only, không short, không margin, không tiền mặt âm, không bán vượt vị thế;
- corporate actions MVP: chia tách, cổ phiếu thưởng, cổ tức tiền mặt và chống tính hai lần;
- baseline mua-và-giữ, cân-bằng-đều, MA250/động lượng chỉ để kiểm tra engine;
- CAGR, drawdown, Sharpe, turnover, chi phí và tỷ trọng tiền mặt;
- chín sản phẩm bất biến, manifest SHA-256, công bố nguyên tử và rollback;
- kiểm thử ngoại tuyến, hồi quy Mốc 0–2 và kịch bản vàng.

Cửa nghiệm thu còn lại:

- giữ PR draft;
- xác minh CI trên head cuối và merge ref;
- chạy cục bộ dữ liệu thật FPT, HPG, MBB khi có môi trường/dữ liệu phù hợp;
- đoạn 00 rà soát, yêu cầu sửa hoặc phê duyệt.

Không tích hợp SSI, không học máy và không triển khai lớp chia vốn sản xuất.

## Mốc 4 — Đặc trưng và học máy

Trạng thái: **chưa mở**.

- Đặc trưng giá, động lượng, biến động, thanh khoản và thị trường.
- Nhãn và walk-forward validation.
- Logistic Regression trước, LightGBM sau.

## Mốc 5 — Chia vốn

Trạng thái: **chưa mở**.

- Inverse volatility.
- Tối đa 15% mỗi mã, 25% mỗi ngành.
- Tiền mặt theo market regime.

## Mốc 6 — Kiểm toán và giao dịch giả lập

Trạng thái: **chưa mở**.

- Rà soát rò rỉ dữ liệu, thiên lệch sống sót và tối ưu quá mức.
- Paper trading hằng ngày, chỉ sinh lệnh đề xuất để người dùng tự đặt trên SSI.
