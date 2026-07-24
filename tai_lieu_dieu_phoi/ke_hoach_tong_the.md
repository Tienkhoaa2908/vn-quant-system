# Kế hoạch tổng thể

## Mốc 0 — Nền tảng và kiểm tra dữ liệu

Trạng thái: **đã hoàn thành, kiểm tra tự động đạt và đã gộp vào `main` qua yêu cầu gộp số 1**.

Kết quả:

- Python 3.12 và `uv`.
- Gói `he_thong_dinh_luong`.
- Công cụ kiểm tra CSV giá.
- Dữ liệu giả lập hợp lệ và có lỗi.
- 12 kiểm thử.
- Quy trình kiểm tra tự động trên GitHub.

## Mốc 1 — Dữ liệu thị trường thật

Trạng thái: **đã hoàn thành, đã gộp và đã đóng hoàn toàn sau PR số 4**.

- Thăm dò Vnstock Community 4.0.4.
- Kết nối nguồn thật giới hạn cho FPT, HPG và MBB.
- Lưu JSON thô bất biến, nhật ký và SHA-256.
- Chuẩn hóa và tạo CSV sẵn sàng.
- Kiểm thử ngoại tuyến và CI Python 3.12.
- Không đưa dữ liệu thật hoặc khóa lên GitHub.
- Đầu `main` khi đóng Mốc 1: `97399e291b0d3d237f247f58ffa03049826d40bd`.
- GitHub Actions run số 44, ID `30111176831`, job `kiem_tra` ID `89540796877`: thành công.

## Mốc 2 — Tập cổ phiếu và đường cơ sở

Trạng thái: **đã hoàn thành, đã gộp qua PR số 5 và đã xác minh CI sau gộp trên `main`**.

- Tập cổ phiếu theo từng thời điểm, không dùng ảnh chụp tương lai.
- Bộ lọc thanh khoản có tham số.
- MA250 đủ đúng 250 quan sát.
- Động lượng có cửa sổ bắt buộc.
- CSV và báo cáo JSON ổn định.
- Kiểm thử hoàn toàn ngoại tuyến bằng dữ liệu giả lập.
- CLI tải dữ liệu hỗ trợ `--so_nen`, mặc định công khai 400 và lưu bền vững cấu hình lần chạy.
- Đã xác minh dữ liệu thật FPT, HPG và MBB: mỗi mã 287 phiên, 38 dòng MA250.
- Không dùng học máy và chưa tuyên bố có dữ liệu thành viên lịch sử thật.
- PR số 5 dùng merge commit `6e8d2ed49c2ef57e43c9f0f2249361b26b838b33`.
- GitHub Actions sau gộp: run số 84, kích hoạt bởi `push` vào `main`, commit trên, trạng thái `Success`; job `kiem_tra` thành công.

## Mốc 3 — Mô phỏng giao dịch và backtest

Trạng thái: **đã có đặc tả đề xuất, chưa phê duyệt và chưa mở triển khai mã**.

Đặc tả đề xuất nằm tại `tai_lieu/dac_ta_moc_3.md`.

Phạm vi dự kiến:

- Tín hiệu tại phiên `T` chỉ được khớp sớm nhất từ phiên kế tiếp.
- Tiền mặt, vị thế, lệnh, khớp lệnh và sổ cái danh mục.
- Phí mua/bán, thuế bán, trượt giá và lô giao dịch đều là cấu hình truy vết được.
- Long-only, không short và không margin.
- Xử lý chia tách/cổ phiếu thưởng và cổ tức tiền mặt bằng dữ liệu sự kiện rõ nguồn.
- Báo cáo lợi nhuận, mức giảm vốn, Sharpe, chi phí và vòng quay.
- Baseline mua-và-giữ, cân bằng đều và quy tắc MA250/động lượng để kiểm tra bộ máy.
- Kiểm thử ngoại tuyến, kịch bản vàng có kết quả biết trước và CI Python 3.12.

Không được triển khai mã Mốc 3 cho đến khi đoạn `00 Điều phối trung tâm` phê duyệt đặc tả và chỉ định đoạn chuyên môn.

## Mốc 4 — Đặc trưng và học máy

- Đặc trưng giá, động lượng, biến động, thanh khoản và thị trường.
- Nhãn lợi nhuận vượt chỉ số và hàng rào ba mức.
- Chia cuốn chiếu theo thời gian.
- Hồi quy lô-gic trước, LightGBM sau.

## Mốc 5 — Chia vốn

- Chọn nhóm mã đứng đầu.
- Chia vốn ngược theo độ biến động.
- Tối đa 15% mỗi mã, 25% mỗi ngành.
- Tiền mặt theo trạng thái thị trường.

## Mốc 6 — Kiểm toán và giao dịch giả lập

- Rà soát rò rỉ dữ liệu, thiên lệch sống sót và tối ưu quá mức.
- Chạy danh mục giả lập hằng ngày.
- Sinh danh mục và lệnh đề xuất để người dùng tự đặt lệnh trên SSI.
- Không tích hợp tài khoản hoặc API đặt lệnh công ty chứng khoán trong phạm vi hiện tại.
- Chỉ cân nhắc tiền thật sau thời gian giả lập ổn định.
