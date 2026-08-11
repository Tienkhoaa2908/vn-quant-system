#!/usr/bin/env bash
set -euo pipefail

BRANCH="agent/v57-staged-deployment-noadd-study"
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"

fail() {
    echo "FAILED: $*" >&2
    exit 2
}

[[ -n "$REPO_ROOT" ]] || fail "hay chay trong repository vn-quant-system"
cd "$REPO_ROOT"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "sai branch; can $BRANCH"
git diff --quiet || fail "tracked files da bi sua"
git diff --cached --quiet || fail "staging area co thay doi"

PYTHON_EXE="$PWD/vn_quant_local_system/.venv/Scripts/python.exe"
INPUT_ZIP="$PWD/vn_quant_local_system/data/reference/daily_prediction_input_v22.zip"
STORE="$PWD/vn_quant_local_system/data/market/dnse_ohlcv.sqlite3"
[[ -f "$PYTHON_EXE" ]] || fail "khong tim thay workstation Python"
[[ -f "$INPUT_ZIP" ]] || fail "khong tim thay frozen reference ZIP"
[[ -f "$STORE" ]] || fail "khong tim thay market DB"

export PYTHONPATH="$PWD/src:$PWD/vn_quant_local_system/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

RUN_ID="$(date +%Y%m%d-%H%M%S)"
ART="$PWD/artifacts"
DEP_DIR="$ART/v57-deployment-$RUN_ID"
DEP_ZIP="$ART/v57-deployment-$RUN_ID.zip"
NOADD_DIR="$ART/v57-noadd-$RUN_ID"
NOADD_ZIP="$ART/v57-noadd-$RUN_ID.zip"
BUNDLE_DIR="$ART/v57-bundle-$RUN_ID"
BUNDLE_ZIP="$ART/UPLOAD_THIS_v57_STAGED_NOADD-$RUN_ID.zip"
LOG="$ART/v57-staged-noadd-$RUN_ID.log"
mkdir -p "$ART" "$BUNDLE_DIR"

{
    echo "===== V57 STAGED DEPLOYMENT + NO-ADD STUDY ====="
    echo "BRANCH=$BRANCH"
    echo "HEAD=$(git rev-parse HEAD)"
    echo "INPUT_ZIP_SHA256=$(sha256sum "$INPUT_ZIP" | awk '{print $1}')"
    echo "STORE_SHA256=$(sha256sum "$STORE" | awk '{print $1}')"
    echo "ANALYSIS_END=2026-07-31"
    echo "HOLDOUT_START=2022-01-01"
    echo "LIVE_MODEL_CHANGE=false"
    echo

    echo "===== COMPILE + PURE TESTS ====="
    "$PYTHON_EXE" -m py_compile \
        src/he_thong_dinh_luong/capital_deployment_v57.py \
        src/he_thong_dinh_luong/tail_noadd_v57.py \
        tests/test_capital_deployment_v57.py \
        tests/test_tail_noadd_v57.py
    "$PYTHON_EXE" -m unittest \
        tests.test_capital_deployment_v57 \
        tests.test_tail_noadd_v57 \
        -v

    echo
    echo "===== STUDY A: CAPITAL DEPLOYMENT ====="
    "$PYTHON_EXE" -m he_thong_dinh_luong.capital_deployment_v57 \
        --input-zip "$(cygpath -w "$INPUT_ZIP")" \
        --store "$(cygpath -w "$STORE")" \
        --output-dir "$(cygpath -w "$DEP_DIR")" \
        --output-zip "$(cygpath -w "$DEP_ZIP")" \
        --contribution 200000 \
        --contribution 250000 \
        --contribution 300000 \
        --analysis-end 2026-07-31 \
        --holdout-start 2022-01-01 \
        --price-multiplier 1000

    echo
    echo "===== STUDY B: NO-ADD + CAP ====="
    "$PYTHON_EXE" -m he_thong_dinh_luong.tail_noadd_v57 \
        --input-zip "$(cygpath -w "$INPUT_ZIP")" \
        --store "$(cygpath -w "$STORE")" \
        --output-dir "$(cygpath -w "$NOADD_DIR")" \
        --output-zip "$(cygpath -w "$NOADD_ZIP")" \
        --contribution 200000 \
        --contribution 250000 \
        --contribution 300000 \
        --analysis-end 2026-07-31 \
        --holdout-start 2022-01-01 \
        --price-multiplier 1000
} 2>&1 | tee "$LOG"

cp "$DEP_ZIP" "$BUNDLE_DIR/"
cp "$NOADD_ZIP" "$BUNDLE_DIR/"
cp "$LOG" "$BUNDLE_DIR/run.log"
git branch --show-current > "$BUNDLE_DIR/git_branch.txt"
git rev-parse HEAD > "$BUNDLE_DIR/git_head.txt"
sha256sum "$INPUT_ZIP" > "$BUNDLE_DIR/input_zip_sha256.txt"
sha256sum "$STORE" > "$BUNDLE_DIR/store_sha256.txt"

powershell.exe -NoProfile -Command \
    "Compress-Archive -Path '$(cygpath -w "$BUNDLE_DIR")\\*' -DestinationPath '$(cygpath -w "$BUNDLE_ZIP")' -Force"

[[ -f "$BUNDLE_ZIP" ]] || fail "khong tao duoc V57 bundle"

echo
echo "===== V57 COMPLETE ====="
echo "RUN_EXIT=0"
echo "UPLOAD_ZIP=$BUNDLE_ZIP"
echo "UPLOAD_ZIP_WINDOWS=$(cygpath -w "$BUNDLE_ZIP")"
echo "UPLOAD_ZIP_SHA256=$(sha256sum "$BUNDLE_ZIP" | awk '{print $1}')"
echo "research_only=true"
echo "live_model_change_authorized=false"

explorer.exe "$(cygpath -w "$ART")" >/dev/null 2>&1 || true
