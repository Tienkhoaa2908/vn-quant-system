# V26 — Nghiên cứu hệ sinh thái quant bên ngoài

## Mục tiêu

Khảo sát các repository có thể bổ sung cho VN Quant System mà không làm mất các
ràng buộc riêng của thị trường Việt Nam:

- dữ liệu point-in-time;
- nhãn 20 phiên và walk-forward theo tháng;
- phí, thuế bán, slippage, odd-lot và tiền mặt;
- giới hạn 15% mỗi mã, 25% mỗi ngành;
- không short, không margin;
- fail closed khi thiếu dữ liệu hoặc bằng chứng;
- không tự động đặt lệnh thật.

Mã nguồn bên thứ ba không được vendor vào repository chính. Clone dùng cho nghiên
cứu phải nằm ngoài repository, không tự cài package, không tự chạy code và được
khóa bằng commit SHA cùng hash file license.

## Nhóm repository được nghiên cứu

### Hạ tầng nghiên cứu và mô hình

- `microsoft/qlib`: workflow, dataset abstraction, model zoo, online rolling.
- `optuna/optuna`: tối ưu siêu tham số chỉ trong nested validation.
- `feast-dev/feast`: point-in-time feature retrieval và offline/online feature
  architecture; chưa cần triển khai feature server ở MVP.
- `mlflow/mlflow`: experiment lineage và model registry khi artifact contract ổn
  định hơn.
- `iterative/dvc`: version hóa dữ liệu/model lớn mà không đưa raw data vào Git.

### Kiểm định factor và hiệu suất

- `stefan-jansen/alphalens-reloaded`: IC, quantile return, turnover, grouped
  analysis.
- `stefan-jansen/pyfolio-reloaded`: risk/performance tear sheets.
- `ranaroussi/quantstats`: rolling metrics, drawdown và Monte Carlo diagnostics.

### Phân bổ vốn và quản trị rủi ro

- `PyPortfolio/PyPortfolioOpt`: minimum volatility, covariance shrinkage,
  Black-Litterman, HRP.
- `skfolio/skfolio`: portfolio models theo giao diện scikit-learn và portfolio CV.
- `dcajasn/Riskfolio-Lib`: CVaR và các risk measures khác.

### Backtest và kiến trúc giao dịch

- `polakowo/vectorbt`: parameter sweeps và cross-check số học nhanh.
- `stefan-jansen/zipline-reloaded`: event-driven simulation và asset lifecycle.
- `vnpy/vnpy`: event engine/gateway patterns, không dùng trực tiếp cho DNSE.
- `mementum/backtrader`: chỉ nghiên cứu kiến trúc; GPL-3.0, không sao chép mã.

Backtest canonical không bị thay thế. Engine hiện tại vẫn chịu trách nhiệm cho
phí DNSE, thuế, lot, cash, corporate actions và chronology Việt Nam.

### Dữ liệu, lịch và feature

- `thinh-vu/vnstock`: nguồn đối chiếu Việt Nam, không thay DNSE canonical store.
- `gerrymanoim/exchange_calendars`: mẫu kiến trúc để xây lịch HOSE/HNX/UPCOM có
  kiểm thử.
- `unionai-oss/pandera`: schema audit độc lập.
- `bukosabino/ta`: tập feature kỹ thuật ứng viên.
- `blue-yonder/tsfresh`: feature discovery offline trong nested research.

Feature mới không được thêm chỉ vì thư viện có sẵn. Mỗi feature phải qua kiểm tra
leakage, redundancy, stability theo regime, rolling IC và leave-best-period-out.

### Repository bị giới hạn license

- `hudson-and-thames/mlfinlab`: repository công khai hiện dùng all-rights-reserved.
  Chỉ nghiên cứu mô tả công khai về purging, backtest overfitting và bet sizing;
  không copy code.
- `mementum/backtrader`: GPL-3.0. Không vendor hoặc liên kết vào core package.

## Tích hợp đã triển khai

### 1. Catalog và clone manager

Module:

```text
he_thong_dinh_luong.external_quant_ecosystem_v26
```

Tính chất:

- catalog hóa repository theo category, tier, license và integration mode;
- clone shallow vào thư mục ngoài repository chính;
- không cài package và không chạy mã clone;
- ghi commit HEAD, branch, remote URL, trạng thái dirty;
- hash file license;
- tạo lock file;
- verify offline rằng clone chưa drift.

Lệnh tạo catalog:

```bash
PYTHONPATH=src uv run --python 3.12 \
  python -m he_thong_dinh_luong.external_quant_ecosystem_v26 catalog \
  --output-json /c/Users/welcome/Documents/vn-quant-research/external-catalog-v26.json
```

Clone nhóm core, mặc định loại repository restricted/review-required:

```bash
PYTHONPATH=src uv run --python 3.12 \
  python -m he_thong_dinh_luong.external_quant_ecosystem_v26 clone \
  --root /c/Users/welcome/Documents/vn-quant-research/external \
  --selection core
```

Clone cả core và extended:

```bash
PYTHONPATH=src uv run --python 3.12 \
  python -m he_thong_dinh_luong.external_quant_ecosystem_v26 clone \
  --root /c/Users/welcome/Documents/vn-quant-research/external \
  --selection extended
```

Không chạy `--include-restricted` trừ khi chỉ cần đọc source/license và chấp nhận
không tích hợp mã.

Verify offline:

```bash
PYTHONPATH=src uv run --python 3.12 \
  python -m he_thong_dinh_luong.external_quant_ecosystem_v26 verify \
  --root /c/Users/welcome/Documents/vn-quant-research/external \
  --lock-file /c/Users/welcome/Documents/vn-quant-research/external/external_quant_repositories_v26.lock.json
```

### 2. Factor diagnostics kiểu Alphalens

Module:

```text
he_thong_dinh_luong.factor_diagnostics_v26
```

Đọc trực tiếp `oos_predictions.csv` đã có, không retrain. Xuất:

- monthly rank IC;
- positive IC ratio;
- first-half/second-half IC;
- rolling 12-month IC minimum/maximum;
- quantile returns;
- top-minus-bottom spread;
- leave-best-period-out spread;
- Top-K turnover;
- trạng thái sector analysis.

Nó không thay historical gate V15 và không phê duyệt model.

Ví dụ:

```bash
RUN_ID="$(date +%Y%m%d-%H%M%S)"

PYTHONPATH=src uv run --python 3.12 \
  python -m he_thong_dinh_luong.factor_diagnostics_v26 \
  --model-output /c/Users/welcome/Documents/vn-quant-data/extended-history-v23-20260801-234520/model-lab \
  --output-dir /c/Users/welcome/Documents/vn-quant-data/factor-diagnostics-v26-$RUN_ID \
  --quantiles 5 \
  --top-k 10 \
  --rolling-months 12
```

### 3. PyPortfolioOpt minimum-volatility benchmark

Module:

```text
he_thong_dinh_luong.portfolio_optimizer_adapter_v26
```

Đây là benchmark độc lập, không thay allocator góp vốn hiện tại. Cấu hình mặc
định:

- Ledoit-Wolf covariance shrinkage;
- long-only;
- tối đa 15% mỗi mã;
- tối đa 25% mỗi ngành;
- lookback 252 phiên;
- so sánh với inverse-volatility reference.

Input price CSV dạng dài:

```text
day,symbol,close
```

Input sector CSV:

```text
symbol,sector
```

Ví dụ:

```bash
RUN_ID="$(date +%Y%m%d-%H%M%S)"

PYTHONPATH=src uv run --python 3.12 \
  --with pandas \
  --with PyPortfolioOpt \
  python -m he_thong_dinh_luong.portfolio_optimizer_adapter_v26 \
  --prices-csv /c/Users/welcome/Documents/vn-quant-data/market-data/ohlcv-close-long.csv \
  --sectors-csv /c/Users/welcome/Documents/vn-quant-data/market-data/symbol-sector.csv \
  --output-dir /c/Users/welcome/Documents/vn-quant-data/portfolio-optimizer-v26-$RUN_ID \
  --lookback-sessions 252 \
  --minimum-observations 120 \
  --max-symbol-weight 0.15 \
  --max-sector-weight 0.25
```

Output chỉ là sensitivity benchmark. Nó không sinh lệnh, không sử dụng buying
power và không tự thay thế contribution allocator.

## Thứ tự tích hợp tiếp theo

1. Chạy V25 trước để xác định rolling train có cải thiện signal hay không.
2. Chạy factor diagnostics V26 trên expanding, rolling-60 và rolling-72.
3. Chỉ khi IC/quantile spread ổn định mới thử Optuna trong nested validation.
4. Dùng PyPortfolioOpt/skfolio/Riskfolio như allocation benchmarks trên cùng model
   score, không dùng để cứu một model có IC yếu.
5. Thêm Pandera audit cho V22 input và output model-lab.
6. Thêm DVC/MLflow sau khi protocol và artifact names ít thay đổi hơn.
7. Nghiên cứu custom HOSE/HNX/UPCOM calendar theo pattern exchange-calendars.
8. Không mở rộng live execution cho đến khi price basis, corporate actions và PIT
   universe được giải quyết.

## Trạng thái an toàn

Mọi sản phẩm V26 phải giữ:

```text
research_eligible=false
live_capital_approved=false
automatic_live_orders_allowed=false
```

Repository bên ngoài là nguồn tham khảo hoặc benchmark, không phải nguồn sự thật
cho kết luận đầu tư.
