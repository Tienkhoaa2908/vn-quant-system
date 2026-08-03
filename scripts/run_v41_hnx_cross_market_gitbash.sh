#!/usr/bin/env bash

set -u
set -o pipefail

BRANCH="agent/model-lab-predictive-value-dnse-sync-v3"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

fail() {
    echo "FAILED: $*" >&2
    exit 2
}

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    fail "hay chay trong repository vn-quant-system"
fi
if ! command -v cygpath >/dev/null 2>&1; then
    fail "runner nay can Git Bash tren Windows"
fi

echo "===== V41 HNX CROSS-MARKET VALIDATION ====="
echo "Frozen HOSE C3 -> HNX. Khong gui lenh broker. Khong phe duyet von that."

git fetch origin \
    && git switch "$BRANCH" \
    && git pull --ff-only origin "$BRANCH" \
    || fail "khong dong bo duoc branch $BRANCH"

export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"

python -m py_compile \
    src/he_thong_dinh_luong/hnx_cross_market_validation_v41.py \
    src/he_thong_dinh_luong/hnx_cross_market_validation_v41_fallback.py \
    tests/test_hnx_cross_market_validation_v41.py \
    tests/test_hnx_cross_market_validation_v41_fallback.py \
    tests/test_dnse_dpapi_scripts_v41.py \
    || fail "py_compile V41 that bai"
python -m unittest \
    tests.test_hnx_cross_market_validation_v41 \
    tests.test_hnx_cross_market_validation_v41_fallback \
    tests.test_dnse_dpapi_scripts_v41 \
    -v \
    || fail "unit test V41 that bai"

V22_ZIP="$(
    find /c/Users/welcome/Documents/vn-quant-data \
        -maxdepth 4 -type f \
        -path '*/historical-research-input-v22-*/daily_prediction_input.zip' \
        -printf '%T@ %p\n' 2>/dev/null \
    | sort -nr | head -n 1 | cut -d' ' -f2-
)"
[[ -n "$V22_ZIP" && -f "$V22_ZIP" ]] \
    || fail "khong tim thay daily_prediction_input.zip V22"

SOURCE_STORE="/c/Users/welcome/Documents/vn-quant-data/market-data/dnse_ohlcv_v20.sqlite3"
[[ -f "$SOURCE_STORE" ]] || fail "khong tim thay canonical DNSE SQLite: $SOURCE_STORE"

RUN_ID="$(date +%Y%m%d-%H%M%S)"
DATA_ROOT="/c/Users/welcome/Documents/vn-quant-data/hnx-cross-market-v41"
STORE="$DATA_ROOT/hnx_ohlcv_v41.sqlite3"
OUTPUT_DIR="$PWD/artifacts/hnx-cross-market-v41-$RUN_ID"
OUTPUT_ZIP="$PWD/artifacts/UPLOAD_THIS_v41_HNX-$RUN_ID.zip"
LOG="$PWD/artifacts/v41-hnx-$RUN_ID.log"
EXIT_FILE="$PWD/artifacts/v41-hnx-$RUN_ID-exit-code.txt"
MODE_FILE="$PWD/artifacts/v41-hnx-$RUN_ID-source-mode.txt"
CREDENTIAL_MODE_FILE="$PWD/artifacts/v41-hnx-$RUN_ID-credential-source.txt"
mkdir -p "$DATA_ROOT" "$PWD/artifacts"

if [[ -n "${DNSE_API_KEY:-}" && -n "${DNSE_API_SECRET:-}" ]]; then
    SOURCE_MODE="DNSE_OPENAPI"
    MODULE="he_thong_dinh_luong.hnx_cross_market_validation_v41"
    SOURCE_ARGS=(
        --source-store "$(cygpath -w "$SOURCE_STORE")"
        --chunk-days 5000
    )
else
    SOURCE_MODE="VNSTOCK_FREE_FALLBACK"
    MODULE="he_thong_dinh_luong.hnx_cross_market_validation_v41_fallback"
    SOURCE_ARGS=()
fi
printf '%s\n' "$SOURCE_MODE" > "$MODE_FILE"
printf '%s\n' "${VN_QUANT_CREDENTIAL_SOURCE:-NONE}" > "$CREDENTIAL_MODE_FILE"
echo "V41_SOURCE_MODE=$SOURCE_MODE"
echo "V41_CREDENTIAL_SOURCE=${VN_QUANT_CREDENTIAL_SOURCE:-NONE}"

set +e
uv run --python 3.12 \
    --with vnstock==4.0.4 \
    --with dnse==0.5.0 \
    python -m "$MODULE" \
    --v22-input-zip "$(cygpath -w "$V22_ZIP")" \
    --store "$(cygpath -w "$STORE")" \
    --output-dir "$(cygpath -w "$OUTPUT_DIR")" \
    --output-zip "$(cygpath -w "$OUTPUT_ZIP")" \
    --start 2015-06-29 \
    --end "$(date +%F)" \
    --universe-size 70 \
    --top-k 10 \
    --price-multiplier 1000 \
    --initial-capital 1000000000 \
    --max-adv-share 0.05 \
    "${SOURCE_ARGS[@]}" \
    2>&1 | tee "$LOG"
V41_EXIT=${PIPESTATUS[0]}
set -e
printf '%s\n' "$V41_EXIT" > "$EXIT_FILE"

# Repackage with execution evidence even when the Python run failed.
STAGING="$PWD/artifacts/.v41-upload-$RUN_ID"
rm -rf "$STAGING"
mkdir -p "$STAGING"
[[ -d "$OUTPUT_DIR" ]] && cp -R "$OUTPUT_DIR" "$STAGING/output"
find "$PWD/artifacts" -maxdepth 1 -type f \
    \( -name "hnx-cross-market-v41-$RUN_ID-failure.json" \
       -o -name "hnx-cross-market-v41-$RUN_ID-fallback-failure.json" \) \
    -exec cp {} "$STAGING/" \;
cp "$LOG" "$EXIT_FILE" "$MODE_FILE" "$CREDENTIAL_MODE_FILE" "$STAGING/"
python - "$STAGING/v41_uncompressed_source.py" <<'PY'
from pathlib import Path
import sys
from he_thong_dinh_luong import hnx_cross_market_validation_v41 as v41
Path(sys.argv[1]).write_bytes(v41._SOURCE)
PY
cp \
    src/he_thong_dinh_luong/hnx_cross_market_validation_v41_fallback.py \
    "$STAGING/v41_vnstock_fallback_source.py"
printf '%s\n' "$BRANCH" > "$STAGING/git_branch.txt"
git rev-parse HEAD > "$STAGING/git_head.txt"
printf '%s\n' "$V22_ZIP" > "$STAGING/v22_input_path.txt"
sha256sum "$V22_ZIP" > "$STAGING/v22_input_sha256.txt"
printf '%s\n' "$SOURCE_STORE" > "$STAGING/source_store_path.txt"
sha256sum "$SOURCE_STORE" > "$STAGING/source_store_sha256.txt"
printf '%s\n' "$STORE" > "$STAGING/hnx_store_path.txt"
[[ -f "$STORE" ]] && sha256sum "$STORE" > "$STAGING/hnx_store_sha256.txt"

python - "$STAGING" "$OUTPUT_ZIP" <<'PY'
from pathlib import Path
import sys
from zipfile import ZIP_DEFLATED, ZipFile
source = Path(sys.argv[1])
target = Path(sys.argv[2])
with ZipFile(target, "w", ZIP_DEFLATED) as archive:
    for path in sorted(source.rglob("*")):
        if path.is_file():
            archive.write(path, path.relative_to(source).as_posix())
with ZipFile(target) as archive:
    bad = archive.testzip()
    if bad is not None:
        raise SystemExit(f"ZIP_CRC_FAILED:{bad}")
PY
rm -rf "$STAGING"

echo
echo "===== V41 DA HOAN TAT ONE-SHOT ====="
echo "V41_SOURCE_MODE=$SOURCE_MODE"
echo "V41_CREDENTIAL_SOURCE=${VN_QUANT_CREDENTIAL_SOURCE:-NONE}"
echo "V41_EXIT_CODE=$V41_EXIT"
echo "UPLOAD_ZIP=$OUTPUT_ZIP"
echo "UPLOAD_ZIP_WINDOWS=$(cygpath -w "$OUTPUT_ZIP")"
echo "UPLOAD_ZIP_SHA256=$(sha256sum "$OUTPUT_ZIP" | awk '{print $1}')"
echo "Chi can upload file UPLOAD_THIS_v41_HNX-*.zip. Khong can chay Bash them."
echo "Khong co lenh broker nao duoc tao hoac gui."
exit 0
