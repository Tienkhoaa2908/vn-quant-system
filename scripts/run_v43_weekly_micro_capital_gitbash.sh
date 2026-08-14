#!/usr/bin/env bash

set -euo pipefail

BRANCH="agent/v43-weekly-micro-capital-accumulation"
EXPECTED_V22_SHA256="66f4dd6699026289501b260949237772f832ac716e700fa686f8b0b8accd38e5"
EXPECTED_STORE_SHA256="7b6f2274d43c12a311f83aa71952ef2abcfca04e2f5204c2f0e9a36a6c144549"

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

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

[[ "$(git branch --show-current)" == "$BRANCH" ]] \
    || fail "sai branch; can $BRANCH"

git diff --quiet || fail "tracked files da bi sua"
git diff --cached --quiet || fail "staging area co thay doi"

PYTHON_EXE="$PWD/.venv/Scripts/python.exe"
[[ -f "$PYTHON_EXE" ]] || fail "khong tim thay .venv Python: $PYTHON_EXE"

export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

echo "===== V43 WEEKLY MICRO-CAPITAL ====="
echo "BRANCH=$BRANCH"
echo "HEAD=$(git rev-parse HEAD)"
echo "NETWORK_MODE=OFFLINE_AFTER_BRANCH_SYNC"
echo "MODEL=C3_STABLE_3_PAST_IC_SHRUNK"
echo "CONTRIBUTIONS=200000,250000,300000 VND/WEEK"
echo "NO_BROKER_ORDERS=true"

echo
echo "===== 1. KIEM THU V43 ====="
"$PYTHON_EXE" -m py_compile \
    src/he_thong_dinh_luong/weekly_micro_capital_v43.py \
    tests/test_weekly_micro_capital_v43.py
"$PYTHON_EXE" -m unittest tests.test_weekly_micro_capital_v43 -v

echo
echo "===== 2. KHOA INPUT ====="
V22_ZIP="$(
    find /c/Users/welcome/Documents/vn-quant-data \
        -maxdepth 4 -type f \
        -path '*/historical-research-input-v22-*/daily_prediction_input.zip' \
        -printf '%T@ %p\n' 2>/dev/null \
    | sort -nr | head -n 1 | cut -d' ' -f2-
)"
STORE="/c/Users/welcome/Documents/vn-quant-data/market-data/dnse_ohlcv_v20.sqlite3"

[[ -n "$V22_ZIP" && -f "$V22_ZIP" ]] || fail "khong tim thay V22 daily_prediction_input.zip"
[[ -f "$STORE" ]] || fail "khong tim thay canonical DNSE SQLite"

V22_SHA256="$(sha256sum "$V22_ZIP" | awk '{print $1}')"
STORE_SHA256="$(sha256sum "$STORE" | awk '{print $1}')"

[[ "$V22_SHA256" == "$EXPECTED_V22_SHA256" ]] || fail "V22 SHA256 khong khop: $V22_SHA256"
[[ "$STORE_SHA256" == "$EXPECTED_STORE_SHA256" ]] || fail "STORE SHA256 khong khop: $STORE_SHA256"

echo "V22_ZIP=$V22_ZIP"
echo "V22_SHA256=$V22_SHA256"
echo "STORE=$STORE"
echo "STORE_SHA256=$STORE_SHA256"

echo
echo "===== 3. CHAY 6 POLICY x 3 MUC TIEN x 3 KICH BAN CHI PHI ====="
RUN_ID="$(date +%Y%m%d-%H%M%S)"
OUTPUT_DIR="$PWD/artifacts/weekly-micro-capital-v43-$RUN_ID"
OUTPUT_ZIP="$PWD/artifacts/UPLOAD_THIS_v43_WEEKLY_MICRO_CAPITAL-$RUN_ID.zip"
LOG="$PWD/artifacts/v43-weekly-micro-capital-$RUN_ID.log"
mkdir -p "$PWD/artifacts"

set +e
"$PYTHON_EXE" -m he_thong_dinh_luong.weekly_micro_capital_v43 \
    --input-zip "$(cygpath -w "$V22_ZIP")" \
    --store "$(cygpath -w "$STORE")" \
    --output-dir "$(cygpath -w "$OUTPUT_DIR")" \
    --output-zip "$(cygpath -w "$OUTPUT_ZIP")" \
    --contribution 200000 \
    --contribution 250000 \
    --contribution 300000 \
    --price-multiplier 1000 \
    2>&1 | tee "$LOG"
RUN_EXIT=${PIPESTATUS[0]}
set -e

if [[ "$RUN_EXIT" -ne 0 ]]; then
    FAILURE_DIR="$PWD/artifacts/v43-weekly-micro-capital-failure-$RUN_ID"
    FAILURE_ZIP="$PWD/artifacts/UPLOAD_THIS_v43_WEEKLY_MICRO_CAPITAL_FAILURE-$RUN_ID.zip"
    mkdir -p "$FAILURE_DIR"
    cp "$LOG" "$FAILURE_DIR/run.log"
    printf '%s\n' "$RUN_EXIT" > "$FAILURE_DIR/exit_code.txt"
    git branch --show-current > "$FAILURE_DIR/git_branch.txt"
    git rev-parse HEAD > "$FAILURE_DIR/git_head.txt"
    git status --short > "$FAILURE_DIR/git_status.txt"
    sha256sum "$V22_ZIP" > "$FAILURE_DIR/v22_sha256.txt"
    sha256sum "$STORE" > "$FAILURE_DIR/store_sha256.txt"
    powershell.exe -NoProfile -Command \
        "Compress-Archive -Path '$(cygpath -w "$FAILURE_DIR")\*' -DestinationPath '$(cygpath -w "$FAILURE_ZIP")' -Force"
    echo "RUN_EXIT=$RUN_EXIT"
    echo "UPLOAD_ZIP=$FAILURE_ZIP"
    echo "UPLOAD_ZIP_WINDOWS=$(cygpath -w "$FAILURE_ZIP")"
    echo "UPLOAD_ZIP_SHA256=$(sha256sum "$FAILURE_ZIP" | awk '{print $1}')"
    explorer.exe "$(cygpath -w "$PWD/artifacts")"
    exit "$RUN_EXIT"
fi

[[ -f "$OUTPUT_ZIP" ]] || fail "khong tao duoc ZIP ket qua"

echo
echo "===== V43 HOAN TAT ====="
echo "RUN_EXIT=0"
echo "OUTPUT_DIR=$OUTPUT_DIR"
echo "UPLOAD_ZIP=$OUTPUT_ZIP"
echo "UPLOAD_ZIP_WINDOWS=$(cygpath -w "$OUTPUT_ZIP")"
echo "UPLOAD_ZIP_SHA256=$(sha256sum "$OUTPUT_ZIP" | awk '{print $1}')"
echo "Chi upload file UPLOAD_THIS_v43_WEEKLY_MICRO_CAPITAL-*.zip."
echo "research_only=true"
echo "live_capital_approved=false"
echo "automatic_live_orders_allowed=false"

explorer.exe "$(cygpath -w "$PWD/artifacts")"
