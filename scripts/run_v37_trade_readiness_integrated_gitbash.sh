#!/usr/bin/env bash

set -u
set -o pipefail

BRANCH="agent/model-lab-predictive-value-dnse-sync-v3"
V34_NAME="future-paper-holdout-freeze-v34-1-20260803-094853.zip"
V34_SHA="642a19cddadc271a2cffb16261ad9e0a4fceadab884eea308ab8bce88debbf80"
V33_NAME="turnover-policy-stability-v33-20260803-091649.zip"
V33_SHA="0019679a8108f576b5063e01d493d018148adbd040212cea50fd5fe288f75555"
V32_NAME="portfolio-ablation-v32-1-canonical-11y-20260803-084529.zip"
V32_SHA="c8f95875a5af8762b5a2de2ee923453135e238593ee708eacbe3e8b4bc6f781f"
V22_POSIX="/c/Users/welcome/Documents/vn-quant-data/historical-research-input-v22-20260801-223238/daily_prediction_input.zip"
V22_SHA="66f4dd6699026289501b260949237772f832ac716e700fa686f8b0b8accd38e5"
STORE_POSIX="/c/Users/welcome/Documents/vn-quant-data/market-data/dnse_ohlcv_v20.sqlite3"
STORE_SHA="7b6f2274d43c12a311f83aa71952ef2abcfca04e2f5204c2f0e9a36a6c144549"
REFERENCE_ROOT="/c/Users/welcome/Documents/vn-quant-data/reference"
PAPER_ROOT="/c/Users/welcome/Documents/vn-quant-data/paper"
SECTOR_POSIX="$REFERENCE_ROOT/sector_master_point_in_time.csv"
ACTIONS_POSIX="$REFERENCE_ROOT/corporate_actions.csv"
ASSURANCE_POSIX="$REFERENCE_ROOT/exact_ledger_data_assurance_v2.json"
BENCHMARK_POSIX="$REFERENCE_ROOT/vnindex_ohlcv.csv"
PAPER_POSIX="$PAPER_ROOT/paper_observations_v37.csv"
OPS_POSIX="$REFERENCE_ROOT/operational_checklist_v37.json"

keep_open() {
    echo
    echo "Git Bash duoc giu mo."
    exec bash
}

fail() {
    echo "FAILED: $*" >&2
    keep_open
}

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    fail "hay chay trong repository vn-quant-system"
fi
if ! command -v cygpath >/dev/null 2>&1; then
    fail "runner nay can Git Bash tren Windows"
fi

echo "===== MUC TIEU DUY NHAT ====="
echo "MODEL -> EXACT LEDGER -> 12 FUTURE HOLDOUT -> OPS -> CAPITAL REVIEW"
echo "Khong retrain model, khong tune cap, khong tu dong gui lenh that."

echo
echo "===== DONG BO CODE ====="
if ! git fetch origin \
  || ! git switch "$BRANCH" \
  || ! git pull --ff-only origin "$BRANCH"; then
    fail "khong dong bo duoc branch $BRANCH"
fi
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"

find_artifact() {
    local name="$1"
    local expected="$2"
    local candidate actual
    while IFS= read -r candidate; do
        [[ -f "$candidate" ]] || continue
        actual="$(sha256sum "$candidate" | awk '{print $1}')"
        if [[ "$actual" == "$expected" ]]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done < <(
        find "$PWD" "$PWD/artifacts" "$HOME/Downloads" "$HOME/Desktop" "$HOME/Documents" \
            -type f -name "$name" -print 2>/dev/null | awk '!seen[$0]++'
    )
    return 1
}

V34_POSIX="$(find_artifact "$V34_NAME" "$V34_SHA")" || fail "thieu V34 canonical"
V33_POSIX="$(find_artifact "$V33_NAME" "$V33_SHA")" || fail "thieu V33 canonical"
V32_POSIX="$(find_artifact "$V32_NAME" "$V32_SHA")" || fail "thieu V32 canonical"
for required in "$V22_POSIX" "$STORE_POSIX"; do
    [[ -f "$required" ]] || fail "thieu file canonical: $required"
done
[[ "$(sha256sum "$V22_POSIX" | awk '{print $1}')" == "$V22_SHA" ]] || fail "V22 hash thay doi"
[[ "$(sha256sum "$STORE_POSIX" | awk '{print $1}')" == "$STORE_SHA" ]] || fail "SQLite hash thay doi"

echo
echo "===== KIEM TRA TICH HOP V36 + V37 ====="
python -m py_compile \
    src/he_thong_dinh_luong/integrated_data_ledger_v36.py \
    src/he_thong_dinh_luong/integrated_data_ledger_v36_strict.py \
    src/he_thong_dinh_luong/integrated_data_ledger_v36_auto.py \
    src/he_thong_dinh_luong/integrated_data_ledger_v36_safe_runner.py \
    src/he_thong_dinh_luong/trade_readiness_v37.py \
    src/he_thong_dinh_luong/trade_readiness_v37_safe_runner.py \
    tests/test_integrated_data_ledger_v36.py \
    tests/test_integrated_data_ledger_v36_strict.py \
    tests/test_integrated_data_ledger_v36_auto.py \
    tests/test_trade_readiness_v37.py \
    || fail "py_compile that bai"
python -m unittest \
    tests.test_integrated_data_ledger_v36 \
    tests.test_integrated_data_ledger_v36_strict \
    tests.test_integrated_data_ledger_v36_auto \
    tests.test_trade_readiness_v37 \
    -v || fail "unit test that bai"

RUN_ID="$(date +%Y%m%d-%H%M%S)"
V36_OUT_POSIX="$PWD/artifacts/integrated-data-ledger-v36-$RUN_ID"
V37_OUT_POSIX="$PWD/artifacts/trade-readiness-v37-$RUN_ID"
V36_OUT_WIN="$(cygpath -w "$V36_OUT_POSIX")"
V37_OUT_WIN="$(cygpath -w "$V37_OUT_POSIX")"

V36_ARGS=(
    --v34-artifact-zip "$(cygpath -w "$V34_POSIX")"
    --v33-artifact-zip "$(cygpath -w "$V33_POSIX")"
    --v32-artifact-zip "$(cygpath -w "$V32_POSIX")"
    --v22-input-zip "$(cygpath -w "$V22_POSIX")"
    --sqlite-store "$(cygpath -w "$STORE_POSIX")"
    --output-dir "$V36_OUT_WIN"
    --expected-v34-sha256 "$V34_SHA"
    --expected-v33-sha256 "$V33_SHA"
    --expected-v32-sha256 "$V32_SHA"
    --expected-v22-sha256 "$V22_SHA"
    --expected-sqlite-sha256 "$STORE_SHA"
    --initial-capital-vnd 1000000000
)
[[ -f "$SECTOR_POSIX" ]] && V36_ARGS+=(--sector-master "$(cygpath -w "$SECTOR_POSIX")")
[[ -f "$ACTIONS_POSIX" ]] && V36_ARGS+=(--corporate-actions "$(cygpath -w "$ACTIONS_POSIX")")
[[ -f "$ASSURANCE_POSIX" ]] && V36_ARGS+=(--data-assurance-report "$(cygpath -w "$ASSURANCE_POSIX")")
[[ -f "$BENCHMARK_POSIX" ]] && V36_ARGS+=(--benchmark-ohlcv "$(cygpath -w "$BENCHMARK_POSIX")")

echo
echo "===== 1/2 CHAY DATA + EXACT LEDGER V36 ====="
python -m he_thong_dinh_luong.integrated_data_ledger_v36_safe_runner "${V36_ARGS[@]}"
V36_STATUS=$?
[[ $V36_STATUS -eq 0 ]] || fail "V36 runtime that bai"
V36_ZIP_POSIX="${V36_OUT_POSIX}.zip"
[[ -f "$V36_ZIP_POSIX" ]] || fail "V36 khong tao ZIP"
V36_ZIP_SHA="$(sha256sum "$V36_ZIP_POSIX" | awk '{print $1}')"

V37_ARGS=(
    --v36-artifact-zip "$(cygpath -w "$V36_ZIP_POSIX")"
    --expected-v36-sha256 "$V36_ZIP_SHA"
    --output-dir "$V37_OUT_WIN"
)
[[ -f "$PAPER_POSIX" ]] && V37_ARGS+=(--paper-observations "$(cygpath -w "$PAPER_POSIX")")
[[ -f "$OPS_POSIX" ]] && V37_ARGS+=(--operational-checklist "$(cygpath -w "$OPS_POSIX")")

echo
echo "===== 2/2 CHAY TRADE READINESS V37 ====="
python -m he_thong_dinh_luong.trade_readiness_v37_safe_runner "${V37_ARGS[@]}"
V37_STATUS=$?
[[ $V37_STATUS -eq 0 ]] || fail "V37 runtime that bai"

echo
echo "===== KET LUAN DUY NHAT ====="
python - "$V37_OUT_WIN" <<'PY'
import json
from pathlib import Path
import sys
out = Path(sys.argv[1])
report = json.loads((out / "trade_readiness_v37.json").read_text(encoding="utf-8-sig"))
print("OBJECTIVE=", report.get("objective"))
print("CAPITAL_STAGE=", report.get("capital_stage"))
print("READINESS_SCORE_PERCENT=", report.get("readiness_score_percent"))
print("NEXT_ACTION=", report.get("next_action"))
print("PAPER_OBSERVATIONS=", report.get("paper_holdout", {}).get("completed_observation_count"), "/ 12")
print("MANUAL_MICRO_LIVE_REVIEW_ELIGIBLE=", report.get("manual_micro_live_review_eligible"))
print("LIVE_CAPITAL_APPROVED=", report.get("live_capital_approved"))
print("AUTOMATIC_LIVE_ORDERS_ALLOWED=", report.get("automatic_live_orders_allowed"))
print("BLOCKERS=")
for blocker in report.get("blockers", []):
    print(" -", blocker)
print("WORKPLAN=")
for row in report.get("workplan", []):
    print(" ", row.get("priority"), row.get("workstream"), row.get("status"))
PY

echo
echo "V36_ARTIFACT=$V36_ZIP_POSIX"
sha256sum "$V36_ZIP_POSIX"
echo "V37_ARTIFACT=${V37_OUT_POSIX}.zip"
sha256sum "${V37_OUT_POSIX}.zip"
keep_open
