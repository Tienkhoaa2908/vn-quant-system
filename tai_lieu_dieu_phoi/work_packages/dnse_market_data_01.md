# DNSE-MARKET-DATA-01

## Mục tiêu

Thay nguồn EOD primary từ wrapper nguồn mở sang DNSE OpenAPI có credential cá nhân, giữ một nguồn độc lập để cross-check.

## Phạm vi

```text
DNSE Market Data REST /price/ohlc
→ STOCK và INDEX
→ resolution 1D
→ phân trang nextTime
→ chuẩn hóa t/o/h/l/c/v sang EodRow
→ DNSE primary
→ KBS secondary mặc định
→ publication reduced bất biến
→ forward prediction
```

## Hợp đồng nguồn

- SDK tạm thời: `dnse==0.5.0`.
- Credential chỉ đọc từ `DNSE_API_KEY` và `DNSE_API_SECRET`.
- Không ghi credential vào log, raw evidence, ZIP hoặc repository.
- API Key/Secret không đi qua tham số CLI.
- Endpoint: `GET /price/ohlc`.
- `type=STOCK` cho cổ phiếu; `type=INDEX` cho VNINDEX.
- `resolution=1D`.
- Các mảng `t/o/h/l/c/v` phải có cùng độ dài.
- `nextTime` phải tăng đơn điệu; tối đa 100 trang.
- Duplicate symbol/day bị chặn.

## Cross-check

```text
primary: dnse_openapi
secondary: vnstock_kbs
```

Gate hiện hành giữ nguyên:

- open/close lệch tối đa 10 bps;
- volume lệch tối đa 5%;
- coverage tối thiểu 95%;
- không bỏ qua phiên trung gian;
- không sửa lịch sử đã khóa.

## Vận hành

- Thêm smoke HPG + VNINDEX trước lần chạy thật đầu tiên.
- Thêm `.env.dnse` local, thuộc `.gitignore`.
- Runbook không còn `exit $STATUS`; Git Bash dừng ở prompt Enter.
- Raw đổi thành `primary.json` và `secondary.json` để không gắn nhãn sai nguồn.

## Kiểm thử

Offline, không gọi DNSE thật:

1. thiếu credential fail closed;
2. khóa SDK 0.5.0;
3. STOCK/INDEX và resolution 1D;
4. phân trang `nextTime`;
5. chặn mảng lệch độ dài;
6. không lộ secret qua repr/evidence/ZIP;
7. smoke không gọi pipeline;
8. runbook không tự đóng Git Bash;
9. regression EOD hiện hành.

## Giới hạn

```text
technical_validation_only=true
research_eligible=false
```

Package không đóng các blocker price basis, corporate actions hoặc PIT universe. Không đặt lệnh thật và không dùng Trading API.
