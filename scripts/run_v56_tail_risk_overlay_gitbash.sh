#!/usr/bin/env bash
set -euo pipefail

BRANCH="agent/v56-tail-risk-overlay-study"
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
[[ -f "$PYTHON_EXE" ]] || fail "khong tim thay workstation Python: $PYTHON_EXE"

INPUT_ZIP="$PWD/vn_quant_local_system/data/reference/daily_prediction_input_v22.zip"
STORE="$PWD/vn_quant_local_system/data/market/dnse_ohlcv.sqlite3"
[[ -f "$INPUT_ZIP" ]] || fail "khong tim thay $INPUT_ZIP"
[[ -f "$STORE" ]] || fail "khong tim thay $STORE"

export PYTHONPATH="$PWD/src:$PWD/vn_quant_local_system/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

RUN_ID="$(date +%Y%m%d-%H%M%S)"
OUT_DIR="$PWD/artifacts/tail-risk-v56-$RUN_ID"
OUT_ZIP="$PWD/artifacts/UPLOAD_THIS_v56_TAIL_RISK-$RUN_ID.zip"
LOG="$PWD/artifacts/v56-tail-risk-$RUN_ID.log"
mkdir -p "$PWD/artifacts"

echo "===== V56 TAIL-RISK OVERLAY STUDY ====="
echo "BRANCH=$BRANCH"
echo "HEAD=$(git rev-parse HEAD)"
echo "MODEL=C3_STABLE_3_PAST_IC_SHRUNK"
echo "BASE_POLICY=P1_TOP10_UNDERWEIGHT_BUFFER20"
echo "ANALYSIS_END=2026-07-31"
echo "HOLDOUT_START=2022-01-01"
echo "CURRENT_AUGUST_2026_EPISODE_EXCLUDED_FROM_PARAMETER_SELECTION=true"
echo "OVERLAYS=BASELINE,STOP_08,STOP_10,STOP_12,NAVLOSS_075,NAVLOSS_100,NAVLOSS_125,NAVLOSS_100_MA20,STOP_10_MA20"
echo "CONTRIBUTIONS=200000,250000,300000"
echo "SLIPPAGE_SCENARIOS=BASE,STRESS,SEVERE"
echo "RISK_EXECUTION=SIGNAL_AT_CLOSE_NEXT_SESSION_OPEN"
echo "REBUY_COOLDOWN=UNTIL_NEXT_CANONICAL_MONTH"
echo "BASELINE_PARITY=SAME_FINAL_WEEKLY_TRADING_DAY"
echo "LIVE_MODEL_CHANGE=false"
echo

echo "===== INPUT HASHES ====="
echo "INPUT_ZIP=$INPUT_ZIP"
echo "INPUT_ZIP_SHA256=$(sha256sum "$INPUT_ZIP" | awk '{print $1}')"
echo "STORE=$STORE"
echo "STORE_SHA256=$(sha256sum "$STORE" | awk '{print $1}')"
echo

echo "===== COMPILE + PURE TESTS ====="
"$PYTHON_EXE" -m py_compile \
    src/he_thong_dinh_luong/tail_risk_overlay_v56.py \
    src/he_thong_dinh_luong/tail_risk_overlay_v56_1.py \
    tests/test_tail_risk_overlay_v56.py \
    tests/test_tail_risk_overlay_v56_1.py
"$PYTHON_EXE" -m unittest \
    tests.test_tail_risk_overlay_v56 \
    tests.test_tail_risk_overlay_v56_1 \
    -v

echo
echo "===== RUN 11-YEAR HISTORY / WALK-FORWARD STUDY ====="
set +e
"$PYTHON_EXE" -m he_thong_dinh_luong.tail_risk_overlay_v56_1 \
    --input-zip "$(cygpath -w "$INPUT_ZIP")" \
    --store "$(cygpath -w "$STORE")" \
    --output-dir "$(cygpath -w "$OUT_DIR")" \
    --output-zip "$(cygpath -w "$OUT_ZIP")" \
    --contribution 200000 \
    --contribution 250000 \
    --contribution 300000 \
    --analysis-end 2026-07-31 \
    --holdout-start 2022-01-01 \
    --price-multiplier 1000 \
    2>&1 | tee "$LOG"
RUN_EXIT=${PIPESTATUS[0]}
set -e

if [[ "$RUN_EXIT" -ne 0 ]]; then
    FAILURE_DIR="$PWD/artifacts/v56-tail-risk-failure-$RUN_ID"
    FAILURE_ZIP="$PWD/artifacts/UPLOAD_THIS_v56_TAIL_RISK_FAILURE-$RUN_ID.zip"
    mkdir -p "$FAILURE_DIR"
    cp "$LOG" "$FAILURE_DIR/run.log"
    git branch --show-current > "$FAILURE_DIR/git_branch.txt"
    git rev-parse HEAD > "$FAILURE_DIR/git_head.txt"
    git status --short > "$FAILURE_DIR/git_status.txt"
    sha256sum "$INPUT_ZIP" > "$FAILURE_DIR/input_zip_sha256.txt"
    sha256sum "$STORE" > "$FAILURE_DIR/store_sha256.txt"
    powershell.exe -NoProfile -Command \
        "Compress-Archive -Path '$(cygpath -w "$FAILURE_DIR")\\*' -DestinationPath '$(cygpath -w "$FAILURE_ZIP")' -Force" \
        || true
    echo
    echo "RUN_EXIT=$RUN_EXIT"
    echo "UPLOAD_ZIP=$FAILURE_ZIP"
    echo "UPLOAD_ZIP_WINDOWS=$(cygpath -w "$FAILURE_ZIP")"
    [[ -f "$FAILURE_ZIP" ]] && echo "UPLOAD_ZIP_SHA256=$(sha256sum "$FAILURE_ZIP" | awk '{print $1}')"
    explorer.exe "$(cygpath -w "$PWD/artifacts")" >/dev/null 2>&1 || true
    exit "$RUN_EXIT"
fi

[[ -f "$OUT_ZIP" ]] || fail "khong tao duoc output ZIP"

echo
echo "===== V56 COMPLETE ====="
echo "RUN_EXIT=0"
echo "OUTPUT_DIR=$OUT_DIR"
echo "UPLOAD_ZIP=$OUT_ZIP"
echo "UPLOAD_ZIP_WINDOWS=$(cygpath -w "$OUT_ZIP")"
echo "UPLOAD_ZIP_SHA256=$(sha256sum "$OUT_ZIP" | awk '{print $1}')"
echo "research_only=true"
echo "live_model_change_authorized=false"

explorer.exe "$(cygpath -w "$PWD/artifacts")" >/dev/null 2>&1 || true
