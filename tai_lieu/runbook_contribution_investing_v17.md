# Runbook đầu tư góp vốn định kỳ v17

## Nguyên tắc

- Chất lượng model được đánh giá bằng lợi nhuận horizon tháng, không phải T+1.
- T+1 chỉ dùng cho execution: giá mở cửa, phí, slippage, lot và khả năng khớp.
- Model phát target theo tháng.
- Tiền mới có thể xuất hiện hàng tuần, nửa tháng hoặc bất kỳ ngày nào.
- Giữa hai signal tháng, hệ thống dùng target tháng gần nhất; không retrain để đuổi theo từng lần góp tiền.
- Planner mặc định buy-only, không tự bán và không gửi lệnh thật.

## 1. Đánh giá lịch sử dài

Runner v17 khóa protocol:

```text
minimum train              60 tháng
requested OOS              72 tháng
inner validation            6 tháng
outer test block             3 tháng
minimum accepted outer test 48 tháng
Top-K                       10
replacement caps            0,1,2,3,4,5
DNSE base cost              25,7 bps/vòng
DNSE stress cost            35,7 bps/vòng
```

Chạy trong Git Bash:

```bash
cd ~/Documents/vn-quant-system
export PYTHONPATH="$PWD/src"

INPUT_ZIP="/c/Users/welcome/Documents/vn-quant-data/eod-dnse-20260730_214614/daily_prediction_input.zip"
RUN_ID="$(date +%Y%m%d-%H%M%S)"
OUTPUT_ROOT="/c/Users/welcome/Documents/vn-quant-data/extended-history-v17-$RUN_ID"
LOG_FILE="$PWD/extended-history-v17-$RUN_ID.log"

PYTHONPATH=src uv run --python 3.12 \
  --with scikit-learn==1.9.0 \
  --with lightgbm==4.7.0 \
  --with xgboost==3.3.0 \
  --with torch==2.12.1 \
  python -m he_thong_dinh_luong.extended_history_reference_v17 \
  --input-zip "$(cygpath -w "$INPUT_ZIP")" \
  --output-root "$(cygpath -w "$OUTPUT_ROOT")" \
  --evaluation-months 72 \
  --minimum-train-months 60 \
  --minimum-outer-test-periods 48 \
  --contribution-amount-vnd 500000 \
  --contribution-intervals 7,14 \
  --initial-capital-vnd 0 \
  2>&1 | tee "$LOG_FILE"

STATUS=${PIPESTATUS[0]}
echo "EXIT_CODE=$STATUS"
echo "OUTPUT_ROOT=$OUTPUT_ROOT"
echo "LOG_FILE=$LOG_FILE"
```

Runner fail closed nếu chỉ tạo được 18 tháng hoặc dưới 48 tháng outer test.

Output chính:

```text
extended_history_reference_v17.json
model-lab/model_lab_output.zip
contribution-every-7-days/contribution_evaluation_v17.json
contribution-every-14-days/contribution_evaluation_v17.json
```

Báo cáo tách:

- TWR: chất lượng strategy, không bị méo bởi tiền nộp thêm.
- benchmark TWR và relative TWR.
- terminal wealth với cùng lịch góp tiền.
- XIRR/MWR: trải nghiệm tài sản thật theo thời điểm góp tiền.

## 2. Local web góp vốn

Stable web entrypoint hiện route qua v9.

```bash
cd ~/Documents/vn-quant-system
export PYTHONPATH="$PWD/src"

PYTHONPATH=src uv run --python 3.12 \
  --with nicegui==3.14.0 \
  python -m he_thong_dinh_luong.giao_dien_web \
  --repo-root "$PWD" \
  --data-root "C:\\Users\\welcome\\Documents\\vn-quant-data" \
  --host 127.0.0.1 \
  --port 8080 \
  --show-browser
```

Mở nút `GÓP VỐN ĐỊNH KỲ`.

Planner đọc:

- frozen reference signal mới nhất trong `reference-ops-v16`;
- holdings và settled cash đã sync từ DNSE;
- giá mới nhất trong publication;
- số tiền mới người dùng nhập.

Planner sau đó:

- tính tổng danh mục sau contribution;
- không mua thêm mã đang dư tỷ trọng;
- ưu tiên lot làm giảm tracking error nhiều nhất trên mỗi đồng chi phí;
- áp trần 15% mỗi mã;
- áp trần 25% ngành khi có sector PIT đáng tin;
- giữ tiền nếu chưa đủ lot hoặc market regime yêu cầu cash;
- ghi kế hoạch vào SQLite local;
- không gửi lệnh thật.

## 3. Change control

Không sửa model v15 chỉ vì kết quả của một lần góp tiền hoặc một phiên T+1.

Phải tạo model version mới nếu đổi:

- feature;
- learner hoặc ensemble weights;
- Top-K;
- turnover-cap candidates;
- validation objective;
- gate;
- allocation rule dùng để tuyên bố historical performance.

Allocator contribution có thể cải tiến độc lập, nhưng mỗi thay đổi phải được kiểm tra lại trên cùng frozen target và phải tách rõ strategy TWR khỏi investor MWR.
