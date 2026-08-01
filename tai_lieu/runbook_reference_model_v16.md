# Runbook vận hành reference model v16

## Mục tiêu

Khóa Model Lab v15 làm reference model, mở rộng bằng chứng lịch sử theo đúng point-in-time contract và chạy paper trading có kill switch. Quy trình này không tự động gửi lệnh thật và không phê duyệt vốn thật.

## Thành phần

- `reference_operations_v16 freeze`: kiểm tra ZIP v15 và tạo policy bất biến.
- `reference_operations_v16 history-audit`: kiểm tra dữ liệu dài hạn trước khi chạy lại nguyên protocol v15.
- `reference_operations_v16 monitor`: tính rolling paper metrics và kill switch.
- `paper_trading_reference_v16`: wrapper paper trading, khóa champion và dùng chi phí DNSE cash mặc định.

## 1. Khóa policy v15

```bash
python -m he_thong_dinh_luong.reference_operations_v16 freeze \
  --model-lab-output /path/to/model_lab_output.zip \
  --output-dir /path/to/reference-policy-v16 \
  --freeze-date 2026-08-01
```

Kết quả bắt buộc:

- `reference_policy.json`
- `source_archive.sha256`
- `manifest.json`

Policy chỉ được tạo khi:

- schema là `vn_quant_model_lab_upgrade_v15`;
- historical status là `HISTORICALLY_VALIDATED_REFERENCE`;
- champion row qua gate;
- model không đổi trong outer blocks;
- turnover cap chỉ chọn từ prior validation;
- live capital vẫn là `false`.

## 2. Chuẩn bị observations cho paper monitor

CSV canonical:

```csv
observation_date,policy_id,rank_ic,net_excess_return,turnover,relative_nav,contract_ok,data_quality_ok,notes
2026-08-31,v15-xxxxxxxxxxxxxxxx,0.041,0.006,0.30,1.006,true,true,
```

Mỗi dòng là một kỳ rebalance đã hoàn tất. Không ghi kỳ chưa có nhãn tương lai hoàn chỉnh.

## 3. Xuất monitor snapshot

```bash
python -m he_thong_dinh_luong.reference_operations_v16 monitor \
  --policy /path/to/reference-policy-v16/reference_policy.json \
  --observations /path/to/paper_observations.csv \
  --output-dir /path/to/paper-monitor-YYYYMMDD
```

Trạng thái:

- `PAPER_WARMUP`: chưa đủ sáu kỳ, chưa kích hoạt predictive kill switch.
- `PAPER_ACTIVE`: đủ dữ liệu và không vi phạm ngưỡng.
- `MODEL_UNDER_REVIEW`: chặn tín hiệu mới.

Kill switch mặc định:

- rolling 6-fold mean IC < 0;
- rolling 6-fold positive IC ratio < 40%;
- rolling 6-fold average net excess < 0;
- relative drawdown <= -12%;
- turnover > 60% trong ba kỳ liên tiếp;
- bất kỳ vi phạm data/contract nào.

## 4. Chạy guarded paper trading

```bash
python -m he_thong_dinh_luong.paper_trading_reference_v16 \
  --daily-output /path/to/daily_quant_output.zip \
  --publication-dir /path/to/latest-publication \
  --state-dir /path/to/paper-state-v16 \
  --policy /path/to/reference-policy-v16/reference_policy.json \
  --monitor /path/to/paper-monitor-YYYYMMDD/paper_model_monitor_v16.json
```

Mặc định chi phí:

- buy fee: 2,7 bps;
- sell fee gồm phí Sở và transfer-equivalent: 3,0 bps;
- sell tax: 10 bps;
- slippage: 5 bps mỗi chiều;
- lot size: 100.

Wrapper từ chối chạy khi:

- kill switch đang bật;
- daily champion khác champion đã khóa;
- policy hoặc monitor sai schema;
- policy/monitor khác `policy_id`;
- bất kỳ file đầu vào nào không hợp lệ.

## 5. Audit dữ liệu lịch sử dài hơn

Input canonical:

- strict OHLCV;
- VNINDEX close-only benchmark;
- universe `pit_membership_v1`;
- metadata PIT/corporate actions khi dùng giá không điều chỉnh.

```bash
python -m he_thong_dinh_luong.reference_operations_v16 history-audit \
  --prices /path/to/ohlcv.csv \
  --benchmark /path/to/vnindex_close.csv \
  --universe /path/to/universe_pit.csv \
  --metadata-pit /path/to/metadata_pit.csv \
  --output-dir /path/to/history-audit-v16 \
  --minimum-train-months 60 \
  --validation-months 6 \
  --target-outer-test-months 48 \
  --minimum-eligible-symbols 80 \
  --minimum-monthly-coverage 0.95 \
  --required-warmup-sessions 251
```

Audit chỉ trả `READY_FOR_EXTENDED_V15` khi có chuỗi tháng research-ready liên tục đủ cho:

```text
60 tháng train + 6 tháng validation + 48 tháng outer test
```

Các blocker chính:

- không phải strict OHLCV;
- price basis chưa xác nhận;
- universe PIT thiếu timestamp hoặc thiếu coverage;
- giá không điều chỉnh nhưng thiếu corporate actions PIT;
- dưới 80 mã eligible;
- warm-up MA250 không đủ;
- chuỗi tháng hợp lệ bị đứt đoạn.

## 6. Quy tắc change control

Không thay đổi v15 khi chỉ mở rộng lịch sử hoặc paper tracking.

Bắt buộc tạo model version mới nếu thay:

- feature;
- learner hoặc ensemble weight;
- Top-K;
- tập turnover cap;
- validation objective;
- research gate.

Bug fix không làm đổi selection/return được phép giữ policy, nhưng phải có regression test và provenance.

## 7. Trạng thái an toàn

- Paper trading: cho phép khi monitor không block.
- Watchlist nghiên cứu: cho phép.
- Auto-submit order: không cho phép.
- Live capital: không được phê duyệt.
