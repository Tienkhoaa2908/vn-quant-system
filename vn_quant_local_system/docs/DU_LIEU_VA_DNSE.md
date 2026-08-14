# Nguồn dữ liệu, DNSE credentials và nhập CSV thủ công

## 1. Nguyên tắc lưu credentials

Workstation không yêu cầu đặt `DNSE_API_KEY` và `DNSE_API_SECRET` trong Git Bash.
Có thể nhập trực tiếp tại tab **Dữ liệu** của web local.

Credentials được lưu tại:

```text
data/state/dnse_credentials.json
```

Thư mục `data/state` bị Git bỏ qua. API Secret không được gửi trở lại trình
duyệt sau khi lưu, không ghi vào log, output ZIP hoặc state database.

Đây vẫn là file local trên máy. Không chia sẻ thư mục workstation hoặc file này.

## 2. Quy trình DNSE

1. Mở tab **Dữ liệu**.
2. Nếu SDK chưa sẵn sàng, bấm **Cài DNSE SDK 0.5.0**.
3. Nhập API Key và API Secret.
4. Bấm **Lưu credentials local**.
5. Bấm **Kiểm tra kết nối**.
6. Khi kiểm tra thành công, bấm **Đồng bộ ngay**.

Đồng bộ chỉ bổ sung dữ liệu vào:

```text
data/market/dnse_ohlcv.sqlite3
```

Nó không ghi ngược vào kho canonical cũ bên ngoài workstation.

## 3. Nhập CSV khi chưa có API

CSV có thể dùng một trong hai bộ cột:

```text
asset_type,symbol,day,open,high,low,close,volume
```

hoặc:

```text
ma,ngay,gia_mo_cua,gia_cao_nhat,gia_thap_nhat,gia_dong_cua,khoi_luong
```

`asset_type` có thể là `STOCK` hoặc `INDEX`. Nếu bỏ cột này, `VNINDEX` được nhận
là `INDEX`, các mã khác là `STOCK`.

Kho hiện tại lưu giá cổ phiếu theo **nghìn đồng**. Khi CSV dùng giá VND đầy đủ,
chọn `Đồng — hệ thống tự chia 1.000` trước khi import. Giá VNINDEX luôn giữ theo
điểm chỉ số.

Mỗi import:

- kiểm tra kiểu dữ liệu và quan hệ OHLC;
- từ chối khóa trùng trong chính file;
- đối chiếu với dữ liệu đã có;
- ghi conflict và dừng nếu lịch sử khác nhau;
- chỉ chèn những dòng mới;
- lưu bản CSV gốc tại `data/market/manual_imports/`;
- ghi SHA-256 và báo cáo import để audit.

## 4. Bảo vệ dữ liệu

Không dùng CSV không rõ nguồn. Không sửa dữ liệu lịch sử để làm đẹp kết quả.
Nếu import gặp `HISTORICAL_CONFLICT`, cần xác minh nguồn giá trước khi quyết định
sửa kho.
