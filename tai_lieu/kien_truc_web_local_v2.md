# Kiến trúc VN Quant Local Console v2

## Mục tiêu

Giao diện local là lớp vận hành và quan sát, không chứa logic model cốt lõi. Một lỗi UI không được làm thay đổi artifact, model gate, backtest hoặc paper ledger.

## Phân lớp

```text
Browser / NiceGUI page
        ↓
Application services
- job orchestration
- artifact repository
- portfolio planner
- paper scenario
        ↓
Domain contracts
- EOD publication
- prediction/model comparison
- target allocation
- portfolio holdings
- execution assumptions
        ↓
Existing engines
- DNSE EOD
- feature/model runner
- Mốc 3 simulator
```

### UI

`web_console_app.py` chỉ dựng component, gọi service và trình bày lỗi theo từng khối. Trang `/` là explicit page. Không dùng NiceGUI auto-index khi khởi động bằng `python -m`.

### Job orchestration

`web_local_core.py` chịu trách nhiệm tạo command, khóa một job active, ghi SQLite job ledger và log. Credential DNSE chỉ truyền qua environment của process.

### Portfolio planner

`portfolio_planner.py` lưu danh mục thực tế trong SQLite local và tạo kế hoạch cho tiền mới:

- đọc close mới nhất từ publication;
- đổi đơn vị nghìn đồng sang VND;
- so sánh giá trị hiện tại với target weight;
- chỉ phân bổ vào khoảng thiếu;
- làm tròn theo lot;
- tính phí mua và slippage;
- chặn mua thêm mã đã vượt target;
- giữ phần tiền không phù hợp với target/regime;
- không tự động phát lệnh bán.

Trần 15% mỗi mã được hỗ trợ trong planner. Trần ngành 25% chưa được tuyên bố là đã kiểm soát cho đến khi có sector master point-in-time đáng tin cậy.

## Hợp đồng model và allocator

Registry hiển thị các model/allocator đang có. Khi thêm model mới, implementation phải tạo cùng bộ artifact:

```text
latest_prediction.csv
model_comparison.json
paper_portfolio.csv
manifest.json
```

UI không đọc object model trực tiếp. Nó chỉ đọc artifact contract. Vì vậy có thể thay LightGBM bằng CatBoost/XGBoost/ranker khác mà không sửa bảng và chart, miễn adapter xuất đúng contract.

Allocator mới phải nhận:

```text
holdings
latest prices
target allocation
market regime
capital constraints
execution assumptions
```

và trả:

```text
allocation plan rows
cash summary
constraints/limitations
manifest metadata
```

## Health và smoke test

Server có endpoint:

```text
GET /healthz
```

CI Windows và Ubuntu phải:

1. cài đúng NiceGUI transient version;
2. khởi động server trên port ngẫu nhiên;
3. gọi `/healthz` và yêu cầu HTTP 200;
4. gọi `/` và yêu cầu HTTP 200 cùng title marker;
5. từ chối body `Internal Server Error`.

Unit test import không được dùng thay cho startup smoke test.

## Bảo mật

- Bind duy nhất `127.0.0.1` hoặc `localhost`.
- API Key/Secret không nằm trong form, URL, SQLite, command hoặc log.
- Không kết nối Trading API và không gửi lệnh thật.
- Artifact và portfolio state nằm dưới `vn-quant-data`, không commit vào repository.

## Hạn chế nghiên cứu

```text
technical_validation_only=true
research_eligible=false
```

Planner là công cụ phân bổ kỹ thuật dựa trên signal hiện có, không phải khuyến nghị đầu tư. Price basis, corporate actions, universe point-in-time và sector master vẫn phải được đóng trước khi nâng cấp research gate.
