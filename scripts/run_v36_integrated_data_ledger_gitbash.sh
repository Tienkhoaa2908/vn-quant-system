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
SECTOR_POSIX="$REFERENCE_ROOT/sector_master_point_in_time.csv"
ACTIONS_POSIX="$REFERENCE_ROOT/corporate_actions.csv"
ASSURANCE_POSIX="$REFERENCE_ROOT/exact_ledger_data_assurance_v2.json"

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
        echo "$actual  $candidate" >&2
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

echo
echo "===== TIM ARTIFACT CANONICAL ====="
V34_POSIX="$(find_artifact "$V34_NAME" "$V34_SHA")" \
    || fail "khong tim thay V34 canonical"
V33_POSIX="$(find_artifact "$V33_NAME" "$V33_SHA")" \
    || fail "khong tim thay V33 canonical"
V32_POSIX="$(find_artifact "$V32_NAME" "$V32_SHA")" \
    || fail "khong tim thay V32.1 canonical"

for required in "$V22_POSIX" "$STORE_POSIX"; do
    [[ -f "$required" ]] || fail "thieu file canonical: $required"
done
[[ "$(sha256sum "$V22_POSIX" | awk '{print $1}')" == "$V22_SHA" ]] \
    || fail "V22 hash thay doi"
[[ "$(sha256sum "$STORE_POSIX" | awk '{print $1}')" == "$STORE_SHA" ]] \
    || fail "SQLite hash thay doi"

echo "V34=$V34_POSIX"
echo "V33=$V33_POSIX"
echo "V32=$V32_POSIX"
echo "V22=$V22_POSIX"
echo "SQLITE=$STORE_POSIX"

echo
echo "===== KIEM TRA CODE V36 ====="
python -m py_compile \
    src/he_thong_dinh_luong/integrated_data_ledger_v36.py \
    src/he_thong_dinh_luong/integrated_data_ledger_v36_safe_runner.py \
    tests/test_integrated_data_ledger_v36.py \
    || fail "py_compile V36 that bai"
python -m unittest tests.test_integrated_data_ledger_v36 -v \
    || fail "unit test V36 that bai"

RUN_ID="$(date +%Y%m%d-%H%M%S)"
OUTPUT_POSIX="$PWD/artifacts/integrated-data-ledger-v36-$RUN_ID"
OUTPUT_WIN="$(cygpath -w "$OUTPUT_POSIX")"

ARGS=(
    --v34-artifact-zip "$(cygpath -w "$V34_POSIX")"
    --v33-artifact-zip "$(cygpath -w "$V33_POSIX")"
    --v32-artifact-zip "$(cygpath -w "$V32_POSIX")"
    --v22-input-zip "$(cygpath -w "$V22_POSIX")"
    --sqlite-store "$(cygpath -w "$STORE_POSIX")"
    --output-dir "$OUTPUT_WIN"
    --expected-v34-sha256 "$V34_SHA"
    --expected-v33-sha256 "$V33_SHA"
    --expected-v32-sha256 "$V32_SHA"
    --expected-v22-sha256 "$V22_SHA"
    --expected-sqlite-sha256 "$STORE_SHA"
    --initial-capital-vnd 1000000000
)

[[ -f "$SECTOR_POSIX" ]] \
    && ARGS+=(--sector-master "$(cygpath -w "$SECTOR_POSIX")")
[[ -f "$ACTIONS_POSIX" ]] \
    && ARGS+=(--corporate-actions "$(cygpath -w "$ACTIONS_POSIX")")
[[ -f "$ASSURANCE_POSIX" ]] \
    && ARGS+=(--data-assurance-report "$(cygpath -w "$ASSURANCE_POSIX")")

echo
echo "===== CHAY V36 DATA INTEGRITY + EXACT LEDGER ====="
echo "OUTPUT_DIR=$OUTPUT_POSIX"
[[ -f "$SECTOR_POSIX" ]] || echo "INFO: sector master chua co; audit se BLOCKED"
[[ -f "$ACTIONS_POSIX" ]] || echo "INFO: corporate actions chua co; audit se BLOCKED"
[[ -f "$ASSURANCE_POSIX" ]] || echo "INFO: assurance v2 chua co; audit se BLOCKED"

python -m he_thong_dinh_luong.integrated_data_ledger_v36_safe_runner \
    "${ARGS[@]}"
STATUS=$?

echo
echo "===== TOM TAT V36 ====="
python - "$OUTPUT_WIN" <<'PY'
import csv
import json
from pathlib import Path
import sys

out = Path(sys.argv[1])
failure = out / "run_failure_v36.json"
report_path = out / "integrated_data_ledger_v36.json"
if failure.is_file():
    value = json.loads(failure.read_text(encoding="utf-8-sig"))
    print("STATUS=FAILED")
    print("ERROR=", value.get("error"))
if report_path.is_file():
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    integrity = report.get("data_integrity", {})
    selection = report.get("selection_lineage", {})
    coverage = report.get("coverage", {})
    print("STATUS=", report.get("status"))
    print("DECISION=", report.get("decision"))
    print("RECOMMENDATION=", report.get("recommendation"))
    print("POLICY_ID=", report.get("policy_id"))
    print(
        "HISTORICAL_FIRST_LAST=",
        coverage.get("first_signal_date"),
        coverage.get("last_signal_date"),
    )
    print("HISTORICAL_PERIODS=", coverage.get("historical_period_count"))
    print("SELECTION_LINEAGE_EXACT=", selection.get("exact_match"))
    print("SQLITE_ROWS=", integrity.get("sqlite_row_count"))
    print("INVALID_OHLCV_ROWS=", integrity.get("invalid_ohlcv_row_count"))
    print("INVALID_OHLCV_RATIO=", integrity.get("invalid_ohlcv_ratio"))
    print(
        "INVALID_OHLCV_EXECUTION_CRITICAL=",
        integrity.get("invalid_ohlcv_execution_critical_count"),
    )
    print("INVALID_EXPORT_SHA256=", integrity.get("invalid_ohlcv_export_sha256"))
    print("LEDGER_STATUS=", report.get("ledger_status"))
    print(
        "EXACT_CASH_LEDGER_PNL_COMPUTED=",
        report.get("exact_cash_ledger_pnl_computed"),
    )
    print("BLOCKERS=", "|".join(report.get("blockers", [])))
    print("LIVE_CAPITAL_APPROVED=", report.get("live_capital_approved"))
    for row in report.get("ledger_summaries", []):
        print(
            "LEDGER",
            row.get("strategy"),
            row.get("scenario"),
            "PERIODS=",
            row.get("period_count"),
            "FIRST_LAST=",
            row.get("first_signal_date"),
            row.get("last_signal_date"),
            "PROFIT_VND=",
            row.get("net_profit_vnd"),
            "NET_RETURN=",
            row.get("net_total_return"),
            "VNINDEX=",
            row.get("benchmark_total_return"),
            "RELATIVE=",
            row.get("relative_total_return"),
            "DRAWDOWN=",
            row.get("max_drawdown"),
        )
summary_path = out / "invalid_ohlcv_summary_v36.csv"
if summary_path.is_file():
    with summary_path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = [
            row
            for row in csv.DictReader(stream)
            if row.get("dimension") == "CATEGORY"
        ]
    print("INVALID_CATEGORIES:")
    for row in sorted(rows, key=lambda item: -int(item["row_count"])):
        print(" ", row["value"], row["row_count"])
PY

ZIP_POSIX="${OUTPUT_POSIX}.zip"
echo
echo "MODEL_EXIT_CODE=$STATUS"
if [[ -f "$ZIP_POSIX" ]]; then
    echo "ARTIFACT_ZIP=$ZIP_POSIX"
    sha256sum "$ZIP_POSIX"
else
    echo "WARNING: khong tim thay ZIP tai $ZIP_POSIX"
fi
keep_open
