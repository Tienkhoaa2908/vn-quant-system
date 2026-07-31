# Work package: Local Web Console 01

Ngày: 2026-07-30

## Mục tiêu

Xây giao diện web chạy hoàn toàn trên máy người dùng để vận hành hệ thống định lượng mà không cần gõ Git Bash hằng ngày.

Luồng chính một nút:

```text
Kiểm tra môi trường và credential
→ phát hiện phiên EOD còn thiếu
→ tải DNSE primary
→ cross-check nguồn phụ advisory
→ cập nhật publication bất biến
→ tính feature
→ chạy champion–challenger
→ chia vốn
→ cập nhật paper-trading OOS sống
→ xuất báo cáo và snapshot
```

Không gửi lệnh thật. Không dùng Trading API trong gói này.

## Quyết định công nghệ

### UI

Dùng Streamlit multipage cho MVP local Windows.

Lý do:

- cùng hệ Python 3.12 với quant engine;
- không cần Node.js hoặc build frontend;
- có navigation, form, table, chart và download;
- thời gian triển khai thấp;
- phù hợp single-user localhost.

UI không được gọi trực tiếp các hàm nội bộ rời rạc. Mọi thao tác đi qua application service có hợp đồng rõ ràng.

### Application service

Thêm lớp điều phối độc lập UI:

```text
src/he_thong_dinh_luong/ung_dung_local/
```

Trách nhiệm:

- preflight;
- lập kế hoạch phiên cần tải;
- chạy EOD/model/paper theo pipeline hiện hữu;
- khóa một run duy nhất;
- ghi trạng thái và progress;
- đọc lịch sử run;
- không phụ thuộc Streamlit.

### State store

MVP dùng file JSON/CSV/ZIP bất biến trong data root; không dùng Session State làm nguồn sự thật.

```text
vn-quant-data/local-console/
  app_config.json
  run.lock
  runs/<run_id>/
    request.json
    status.json
    events.jsonl
    result.json
    logs.txt
  index.json
```

Session State chỉ giữ trạng thái hiển thị tạm thời. Reload trình duyệt phải khôi phục được run từ disk.

DuckDB chưa bắt buộc trong MVP. Chỉ thêm ở phase sau khi số snapshot đủ lớn và truy vấn lịch sử bằng CSV trở nên chậm.

## Màn hình bắt buộc

### 1. Tổng quan

- phiên local mới nhất;
- phiên DNSE mới nhất;
- trạng thái dữ liệu FINAL/NOT_FINAL;
- market regime;
- champion model;
- Top 10;
- vốn paper, NAV, tiền mặt, drawdown;
- cảnh báo research gate.

### 2. Chạy hằng ngày

Một nút chính: `Cập nhật dữ liệu và chạy toàn hệ thống`.

Tùy chọn nâng cao được thu gọn:

- target date;
- secondary source;
- advisory/strict;
- coverage threshold;
- validation months;
- top_k;
- paper capital;
- phí, thuế, slippage, lot size.

Trước khi chạy phải hiển thị execution plan:

```text
latest_local
latest_primary
missing_sessions
symbol_count
estimated_steps
```

Yêu cầu xác nhận trước khi bắt đầu. Không cho chạy trùng khi run.lock còn hợp lệ.

### 3. Tiến trình và log

- progress theo stage;
- elapsed time;
- stage hiện tại;
- log tail;
- lỗi chuẩn hóa thành mã lỗi và hướng xử lý;
- nút mở thư mục output;
- nút tải ZIP kết quả.

Stage tối thiểu:

```text
PREFLIGHT
DISCOVER_SESSIONS
FETCH_PRIMARY
CROSSCHECK_SECONDARY
PUBLISH_EOD
BUILD_FEATURES
RUN_MODELS
ALLOCATE_PORTFOLIO
UPDATE_PAPER
FINALIZE
```

### 4. Dữ liệu

- bảng OHLCV theo mã/ngày;
- lọc symbol và date range;
- candlestick;
- volume;
- MA20/60/120/250;
- provenance source/version;
- coverage và lỗi theo mã;
- benchmark VNINDEX;
- xem raw primary/secondary chỉ từ file local, không đóng gói credential.

### 5. Model và ranking

- champion/challenger;
- Rank IC, Precision@10, Top-10 relative return, turnover;
- validation window;
- model gate và lý do reject;
- Top 10 hiện tại;
- feature values từng mã;
- cảnh báo rõ momentum score không phải xác suất.

### 6. Chia vốn

MVP hiển thị và cho thử nghiệm:

- equal weight;
- inverse volatility;
- max 15% mỗi mã;
- max 25% mỗi ngành khi metadata ngành khả dụng;
- cash budget theo regime;
- lot-size rounding;
- phí/slippage dự kiến;
- tỷ trọng mục tiêu và số lượng cổ phiếu giả định.

Không cho phép ghi đè paper state chỉ bằng preview. Chỉ pipeline đã xác nhận mới được commit signal.

### 7. Paper trading sống

- signals;
- pending orders;
- fills;
- positions;
- cash;
- NAV curve;
- drawdown;
- turnover;
- realized/unrealized P&L;
- phí và thuế;
- lịch sử snapshot;
- reset phải yêu cầu gõ cụm xác nhận và tạo backup trước.

### 8. Backtest lịch sử

Cho chọn:

- date range;
- strategy/model;
- top_k;
- rebalance frequency;
- capital allocation;
- fee/tax/slippage/lot;
- MA250 eligibility;
- cash regime;
- universe policy.

Output:

- CAGR;
- Sharpe;
- max drawdown;
- turnover;
- hit rate;
- benchmark-relative return;
- NAV chart;
- drawdown chart;
- trade ledger;
- downloadable ZIP.

Backtest phải dùng engine Mốc 3 và không viết vào state paper sống.

### 9. Cấu hình và chẩn đoán

- data root;
- trạng thái `.env.dnse` chỉ báo LOADED/MISSING;
- không hiển thị key/secret;
- SDK versions;
- repo commit;
- dependency check;
- write permission;
- disk free space;
- open folder;
- smoke DNSE;
- test source secondary;
- export diagnostic log đã redact.

## Bảo mật

- chỉ bind `127.0.0.1` mặc định;
- không bind `0.0.0.0`;
- credential chỉ đọc từ environment hoặc `.env.dnse` local;
- không ghi credential vào app config, logs, traceback, snapshot hoặc download;
- tất cả lỗi phải qua redaction;
- không dùng pickle cho dữ liệu do người dùng tải lên;
- không thực thi đường dẫn hoặc shell string do UI ghép trực tiếp.

## Tính nhất quán và fail closed

- một run tại một thời điểm;
- run_id duy nhất;
- output directory không ghi đè;
- restart app vẫn đọc được trạng thái run;
- stale lock được nhận diện bằng PID + timestamp;
- cùng signal date nhưng payload khác phải chặn;
- không cập nhật paper khi EOD/model thất bại;
- không coi secondary advisory thấp là primary failure;
- không chạy phiên hôm nay trước 18:00 giờ Việt Nam;
- mọi artifact có SHA-256 và manifest.

## Lệnh khởi động mục tiêu

```bash
PYTHONPATH=src uv run --python 3.12 \
  --with streamlit \
  --with plotly \
  --with dnse==0.5.0 \
  --with vnstock==4.0.4 \
  --with lightgbm==4.6.0 \
  streamlit run src/he_thong_dinh_luong/giao_dien_local/app.py \
  --server.address 127.0.0.1
```

Sau MVP sẽ thêm `start_local_console.cmd` để người dùng double-click.

## Phân kỳ triển khai

### Phase A — Operational MVP

- application service;
- run state, locking, progress events;
- Dashboard;
- one-click daily pipeline;
- data/model/portfolio/paper pages;
- Windows launcher;
- test offline và CI.

### Phase B — Historical research

- backtest form;
- scenario comparison;
- saved experiments;
- chart/report export;
- DuckDB index nếu cần.

### Phase C — Hardening

- recovery after crash;
- stale lock handling;
- redaction audit;
- large-file pagination;
- performance profiling;
- packaged desktop launcher.

## Tiêu chí nghiệm thu Phase A

1. Double-click launcher mở trình duyệt localhost.
2. Dashboard đọc được output EOD hiện có mà không chạy pipeline.
3. Một nút chạy được toàn bộ EOD → model → allocation → paper.
4. Reload trình duyệt không làm mất tiến trình hoặc lịch sử run.
5. Không chạy trùng.
6. Credential không xuất hiện trong UI/log/download.
7. Lỗi DNSE, coverage, feature hoặc model hiển thị đúng mã lỗi.
8. Output bằng CLI và UI có cùng hash khi cùng input/config.
9. Windows và Ubuntu CI xanh.
10. Không gửi lệnh thật và không gọi Trading API.

## Ngoài phạm vi Phase A

- multi-user;
- cloud deployment;
- mobile app;
- broker order routing;
- real-time intraday trading;
- websocket market feed;
- portfolio optimization nâng cao;
- authentication qua internet.
