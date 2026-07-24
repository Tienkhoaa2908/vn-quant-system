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

Trạng thái: **đã mở; đoạn 02 đang phụ trách**.

- Tập cổ phiếu theo từng thời điểm, không dùng ảnh chụp tương lai.
- Bộ lọc thanh khoản có tham số.
- MA250 đủ đúng 250 quan sát.
- Động lượng có cửa sổ bắt buộc.
- CSV và báo cáo JSON ổn định.
- Kiểm thử hoàn toàn ngoại tuyến bằng dữ liệu giả lập.
- Chưa dùng học máy và chưa tuyên bố có dữ liệu thành viên lịch sử thật.

## Mốc 3 — Mô phỏng giao dịch

Chưa mở.

- Khớp lệnh từ phiên kế tiếp.
- Phí, thuế bán, trượt giá và lô giao dịch.
- Tiền mặt, vị thế, lệnh, khớp lệnh và nhật ký.
- Báo cáo lợi nhuận, mức giảm, Sharpe, chi phí và vòng quay.

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
- Chỉ cân nhắc tiền thật sau thời gian giả lập ổn định.
