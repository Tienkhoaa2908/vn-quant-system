#!/usr/bin/env bash

set -u
set -o pipefail

BRANCH="agent/model-lab-predictive-value-dnse-sync-v3"
V31_NAME="all-history-protocol-v31-canonical-11y-v2-20260803-000838.zip"
V31_SHA256="6634060e33e21552b60749ad4fd5492e0f771197ead309da927fc34aab444759"
V22_POSIX="/c/Users/welcome/Documents/vn-quant-data/historical-research-input-v22-20260801-223238/daily_prediction_input.zip"
V22_SHA256="66f4dd6699026289501b260949237772f832ac716e700fa686f8b0b8accd38e5"

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
    fail "hay chay script trong repository vn-quant-system"
fi

if ! command -v cygpath >/dev/null 2>&1; then
    fail "khong tim thay cygpath; script nay danh cho Git Bash tren Windows"
fi

echo "===== DONG BO CODE ====="
if ! git fetch origin \
    || ! git switch "$BRANCH" \
    || ! git pull --ff-only origin "$BRANCH"; then
    fail "khong dong bo duoc branch $BRANCH"
fi

export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"

[[ -f "$V22_POSIX" ]] || fail "khong tim thay V22 canonical: $V22_POSIX"

echo
echo "===== TIM V31 ARTIFACT CANONICAL ====="

mapfile -t V31_CANDIDATES < <(
    find \
        "$PWD" \
        "$PWD/artifacts" \
        "$HOME/Downloads" \
        "$HOME/Desktop" \
        "$HOME/Documents" \
        -type f \
        -name "$V31_NAME" \
        -print 2>/dev/null \
    | awk '!seen[$0]++'
)

V31_POSIX=""
for candidate in "${V31_CANDIDATES[@]}"; do
    candidate_sha="$(sha256sum "$candidate" | awk '{print $1}')"
    echo "$candidate_sha  $candidate"
    if [[ "$candidate_sha" == "$V31_SHA256" ]]; then
        V31_POSIX="$candidate"
        break
    fi
done

[[ -n "$V31_POSIX" ]] \
    || fail "khong tim thay V31 artifact dung SHA256=$V31_SHA256"

actual_v22_sha="$(sha256sum "$V22_POSIX" | awk '{print $1}')"
[[ "$actual_v22_sha" == "$V22_SHA256" ]] \
    || fail "V22 SHA256 khong khop: $actual_v22_sha"

echo
echo "V31_ARTIFACT=$V31_POSIX"
echo "V22_INPUT=$V22_POSIX"

echo
echo "===== KIEM TRA CODE V32 ====="

python -m py_compile \
    src/he_thong_dinh_luong/portfolio_ablation_v32.py \
    src/he_thong_dinh_luong/portfolio_ablation_v32_safe_runner.py \
    tests/test_portfolio_ablation_v32.py \
    || fail "py_compile V32 that bai"

python -m unittest tests.test_portfolio_ablation_v32 -v \
    || fail "unit test V32 that bai"

V31_WIN="$(cygpath -w "$V31_POSIX")"
V22_WIN="$(cygpath -w "$V22_POSIX")"
RUN_ID="$(date +%Y%m%d-%H%M%S)"
OUTPUT_POSIX="$PWD/artifacts/portfolio-ablation-v32-canonical-11y-$RUN_ID"
OUTPUT_WIN="$(cygpath -w "$OUTPUT_POSIX")"

echo
echo "===== CHAY V32 PORTFOLIO ABLATION ====="
echo "OUTPUT_DIR=$OUTPUT_POSIX"

python -m he_thong_dinh_luong.portfolio_ablation_v32_safe_runner \
    --v31-artifact-zip "$V31_WIN" \
    --v22-input-zip "$V22_WIN" \
    --output-dir "$OUTPUT_WIN" \
    --expected-v31-sha256 "$V31_SHA256" \
    --expected-input-sha256 "$V22_SHA256" \
    --breadths "10,15,20,30" \
    --replacement-caps "0,1,2,3,4,5" \
    --validation-months 6 \
    --test-months 3 \
    --minimum-outer-test-periods 48 \
    --bootstrap-repetitions 2000 \
    --bootstrap-block-months 3 \
    --seed 20260803 \
    --broker-buy-fee-bps 0 \
    --broker-sell-fee-bps 0 \
    --exchange-buy-fee-bps 2.7 \
    --exchange-sell-fee-bps 2.7 \
    --sell-tax-bps 10 \
    --transfer-fee-vnd-per-share 0.3 \
    --transfer-reference-price-vnd 10000 \
    --slippage-bps 5 \
    --stress-slippage-bps 10

MODEL_STATUS=$?

echo
echo "===== TOM TAT V32 ====="

python - "$OUTPUT_WIN" <<'PY'
from __future__ import annotations

import csv
import json
from pathlib import Path
import sys

output = Path(sys.argv[1]).resolve()
report_path = output / "portfolio_ablation_v32.json"
failure_path = output / "run_failure_v32.json"
summary_path = output / "portfolio_comparison_v32.csv"
decision_path = output / "decision_gates_v32.csv"

if failure_path.is_file():
    failure = json.loads(failure_path.read_text(encoding="utf-8-sig"))
    print("STATUS=FAILED")
    print("ERROR_TYPE=", failure.get("error_type"))
    print("ERROR=", failure.get("error"))

if report_path.is_file():
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    audit = report.get("policy_input_audit", {})
    print("STATUS=", report.get("status"))
    print(
        "OOS_FIRST_LAST=",
        audit.get("eligible_first_test_date"),
        audit.get("eligible_last_test_date"),
    )
    print("OOS_MONTHS=", audit.get("eligible_test_month_count"))
    print(
        "ELIGIBLE_KEYS_PER_MODEL=",
        audit.get("eligible_prediction_key_count_per_model"),
    )
    print(
        "EXCLUDED_NONELIGIBLE_KEYS_PER_MODEL=",
        audit.get("excluded_noneligible_prediction_key_count_per_model"),
    )
    print(
        "MIN_MAX_ELIGIBLE_SYMBOLS=",
        audit.get("minimum_eligible_symbol_count_per_month"),
        audit.get("maximum_eligible_symbol_count_per_month"),
    )
    print(
        "DIAGNOSTIC_PASSING_POLICIES=",
        json.dumps(
            report.get("diagnostic_passing_policies", []),
            ensure_ascii=True,
            sort_keys=True,
        ),
    )
    print(
        "HISTORICAL_PROMOTION_PASSING_POLICIES=",
        json.dumps(
            report.get("historical_promotion_passing_policies", []),
            ensure_ascii=True,
            sort_keys=True,
        ),
    )
    print("RECOMMENDATION=", report.get("recommendation"))
    print("PORTFOLIO_PNL_AFTER_COSTS_COMPUTED=true")
    print("EXACT_CASH_LEDGER_PNL_COMPUTED=false")
    print("LOT_SIZE_100_APPLIED=false")
    print("EXACT_T1_OPEN_EXECUTION_PRICE_APPLIED=false")

if summary_path.is_file():
    with summary_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as stream:
        rows = list(csv.DictReader(stream))
    print()
    print("MODEL,BREADTH,PERIODS,BASE_NET,VNINDEX,BASE_REL,STRESS_NET,STRESS_REL,DRAWDOWN,TURNOVER,GATE")
    for row in sorted(
        rows,
        key=lambda item: (
            str(item.get("model") or ""),
            int(float(item.get("breadth") or 0)),
        ),
    ):
        print(
            ",".join(
                [
                    str(row.get("model") or ""),
                    str(row.get("breadth") or ""),
                    str(row.get("base_period_count") or ""),
                    str(row.get("base_net_total_return") or ""),
                    str(row.get("base_benchmark_total_return") or ""),
                    str(row.get("base_relative_total_return") or ""),
                    str(row.get("stress_net_total_return") or ""),
                    str(row.get("stress_relative_total_return") or ""),
                    str(row.get("base_max_drawdown") or ""),
                    str(row.get("base_mean_turnover") or ""),
                    str(row.get("gate_passed") or ""),
                ]
            )
        )

if decision_path.is_file():
    with decision_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as stream:
        decisions = list(csv.DictReader(stream))
    print()
    print("===== DECISION GATES =====")
    for row in decisions:
        if str(row.get("role") or "") == "BASELINE":
            continue
        print(
            "MODEL=",
            row.get("model"),
            "BREADTH=",
            row.get("breadth"),
            "DIAGNOSTIC_PASS=",
            row.get("portfolio_diagnostic_gate_passed"),
            "PROMOTION_PASS=",
            row.get("v32_historical_promotion_gate_passed"),
            "FAILED=",
            row.get("failed_v32_gates"),
        )
PY

ZIP_POSIX="${OUTPUT_POSIX}.zip"

echo
echo "MODEL_EXIT_CODE=$MODEL_STATUS"
if [[ -f "$ZIP_POSIX" ]]; then
    echo "ARTIFACT_ZIP=$ZIP_POSIX"
    sha256sum "$ZIP_POSIX"
else
    echo "WARNING: khong tim thay artifact ZIP tai $ZIP_POSIX"
fi

keep_open
