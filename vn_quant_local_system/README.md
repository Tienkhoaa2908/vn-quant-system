# VN Quant Local Workstation

Hệ thống local tách riêng để vận hành và kiểm định chiến lược cổ phiếu Việt Nam:

```text
vn_quant_local_system/
├── .venv/                 môi trường Python riêng trên máy local
├── data/
│   ├── market/            SQLite OHLCV khoảng 11 năm, cập nhật incremental
│   ├── reference/         V22 feature/label history dùng khóa C3
│   ├── derived/           dữ liệu suy dẫn
│   └── state/             holdings, cash, ranking và kế hoạch tuần
├── src/vn_quant_local/    code dữ liệu, C3, portfolio và web
├── web/                   giao diện localhost
├── docs/                  tài liệu tiếng Việt
├── validation/            source snapshot và artifact kiểm định
├── outputs/               output từng lần chạy
├── logs/                  log vận hành
└── scripts/               lệnh Git Bash
```

## Tần suất đúng

Nạp tiền mỗi tuần **không có nghĩa phải huấn luyện hoặc thay ranking mỗi tuần**.

- Dữ liệu: cập nhật khi mở hệ thống hoặc sau phiên giao dịch.
- C3 canonical: chạy một lần mỗi tháng trên phiên cuối tháng đã hoàn tất.
- Latest preview: có thể chạy bất kỳ lúc nào để quan sát, nhưng không thay ranking canonical.
- Kế hoạch mua: chạy mỗi tuần bằng ranking tháng gần nhất, holdings và tiền mặt hiện tại.

Việc này tách đúng ba tầng: dữ liệu, tín hiệu, và giải ngân.

## Lần đầu

Mở Git Bash tại repository:

```bash
cd ~/Documents/vn-quant-system
bash vn_quant_local_system/scripts/setup_and_run_gitbash.sh
```

Script tạo `.venv` riêng, kiểm thử, copy kho dữ liệu 11 năm vào thư mục local, lưu source/artifact kiểm định và mở:

```text
http://127.0.0.1:8787
```

## Những lần sau

```bash
cd ~/Documents/vn-quant-system
bash vn_quant_local_system/scripts/run_web_gitbash.sh
```

## Chạy pipeline headless

Mặc định: bootstrap → sync DNSE incremental → C3 → kế hoạch tuần → ZIP output.

```bash
bash vn_quant_local_system/scripts/run_pipeline_gitbash.sh
```

Nếu chưa có mạng hoặc chưa cấu hình DNSE:

```bash
bash vn_quant_local_system/scripts/run_pipeline_gitbash.sh --skip-sync
```

## Quyền hạn

Hệ thống chỉ phục vụ nghiên cứu:

```text
research_only=true
live_capital_approved=false
automatic_live_orders_allowed=false
```
