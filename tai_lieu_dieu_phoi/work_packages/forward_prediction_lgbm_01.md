# FORWARD-PREDICTION-LGBM-01

## Outcome

Tạo forward inference thực sự trên sản phẩm Mốc 4 hiện có:

```text
prediction_input.zip
→ kiểm manifest/hash
→ feature cross-sectional
→ target relevance 5 mức
→ temporal train/validation có purge theo label end
→ LightGBM LambdaRank grid nhỏ
→ champion–challenger với momentum
→ fit toàn bộ lịch sử hợp lệ
→ dự đoán ngày mới nhất chưa có nhãn
→ latest_prediction.csv
```

## Phạm vi

- Không sửa parser PDF.
- Không mở Mốc 5.
- Không thay đổi engine backtest.
- Không thêm dependency thường trực.
- LightGBM được gọi tạm bằng `uv run --with lightgbm==4.6.0`.
- Logistic giữ làm legacy benchmark trong báo cáo.
- Momentum giữ champion nếu LightGBM không vượt toàn bộ cửa.

## Cửa champion

LightGBM chỉ thắng khi:

```text
mean_rank_ic > 0
mean_rank_ic > momentum
top_k_relative_return > momentum
precision_at_k >= momentum
turnover <= 1.5 × momentum turnover
```

## Safety

- Không random split.
- Train loại mọi nhãn kết thúc chạm hoặc vượt validation start.
- Forward row không yêu cầu open T+1 vì đây là prediction, không phải execution eligibility.
- ZIP đầu vào được kiểm SHA-256 và byte size theo manifest.
- Output ZIP chỉ chứa sản phẩm dự đoán.
- Không canonical promotion.
- `research_eligible=false`.

## Acceptance

- 5 synthetic tests đạt.
- Chạy được trên `prediction_input.zip` thực.
- Xuất `latest_prediction.csv`, `model_comparison.json`, `prediction_summary.txt`, `manifest.json`.
- Không sửa `pyproject.toml`, `uv.lock` hoặc workflow.
