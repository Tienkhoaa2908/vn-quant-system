# External AI review handoff v1

## Mục tiêu

Tạo một gói bàn giao độc lập để một AI hoặc reviewer khác có thể đánh giá toàn bộ VN Quant System mà không cần truy cập máy local, credential DNSE hoặc tài khoản môi giới.

Gói gồm:

- snapshot toàn bộ tracked source tại đúng Git commit;
- metadata branch, commit, Git log và diff stat so với `origin/main`;
- V22 research input và data-lineage report;
- Model Lab summary;
- V24 metadata repair report nếu có;
- V27 component/breadth diagnostics;
- V28 frozen-candidate verification nếu đã chạy;
- SQLite schema, row counts, SHA-256 và mẫu deterministic nếu truyền `--store`;
- prompt kiểm toán độc lập;
- open questions;
- reproduction instructions;
- artifact manifest và SHA-256 cho mọi file.

## Không bao gồm

- credential, API key, bearer token hoặc password;
- broker account export hoặc holdings cá nhân;
- toàn bộ SQLite store;
- quyền gửi lệnh thật;
- khẳng định live-capital approval.

Research input ZIP có thể được bao gồm vì nó cần để tái tạo feature/label experiments. Full SQLite chỉ được mô tả bằng schema, counts, hashes và samples.

## Entrypoint

```bash
PYTHONPATH=src uv run --python 3.12 \
  python -m he_thong_dinh_luong.ai_review_bundle_v1 \
  --repo-root . \
  --historical-input-dir <V22_OUTPUT_DIR> \
  --model-output <V23_MODEL_LAB_DIR> \
  --v24-report <V24_REPORT> \
  --v27-output-dir <V27_OUTPUT_DIR> \
  --v28-output-dir <V28_OUTPUT_DIR_IF_AVAILABLE> \
  --store <DNSE_SQLITE_STORE> \
  --output-dir <NEW_REVIEW_BUNDLE_DIR>
```

Không truyền `--v28-output-dir` nếu V28 chưa chạy. Mặc định tool fail nếu working tree dirty để bundle luôn truy về đúng commit.

## File gửi cho reviewer

Tool tạo một ZIP cạnh output directory:

```text
<NEW_REVIEW_BUNDLE_DIR>.zip
```

Upload đúng ZIP đó, sau đó bảo reviewer mở theo thứ tự:

1. `README_FIRST.md`
2. `PROMPT_FOR_EXTERNAL_AI.md`
3. `artifact_manifest.json`
4. `evidence/`
5. `source/source_snapshot.zip`
6. `research_input/daily_prediction_input.zip`

## Diễn giải bắt buộc

V27 và V28 là post-selection sensitivity/reproducibility evidence. Chúng không phải genuinely future holdout. Reviewer phải giữ riêng ba mức:

- historical technical evidence;
- post-selection candidate evidence;
- future paper holdout evidence.

T+1 chỉ được dùng cho execution accounting, không dùng để đánh giá predictive quality.
