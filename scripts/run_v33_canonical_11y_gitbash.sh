#!/usr/bin/env bash

set -u
set -o pipefail

BRANCH="agent/model-lab-predictive-value-dnse-sync-v3"
V32_NAME="portfolio-ablation-v32-1-canonical-11y-20260803-084529.zip"
V32_SHA256="c8f95875a5af8762b5a2de2ee923453135e238593ee708eacbe3e8b4bc6f781f"

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
    fail "khong tim thay cygpath; runner nay danh cho Git Bash tren Windows"
fi

echo "===== DONG BO CODE ====="
if ! git fetch origin \
    || ! git switch "$BRANCH" \
    || ! git pull --ff-only origin "$BRANCH"; then
    fail "khong dong bo duoc branch $BRANCH"
fi

export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"

echo
echo "===== TIM V32.1 ARTIFACT CANONICAL ====="

mapfile -t CANDIDATES < <(
    find \
        "$PWD" \
        "$PWD/artifacts" \
        "$HOME/Downloads" \
        "$HOME/Desktop" \
        "$HOME/Documents" \
        -type f \
        -name "$V32_NAME" \
        -print 2>/dev/null \
    | awk '!seen[$0]++'
)

V32_POSIX=""
for candidate in "${CANDIDATES[@]}"; do
    candidate_sha="$(sha256sum "$candidate" | awk '{print $1}')"
    echo "$candidate_sha  $candidate"
    if [[ "$candidate_sha" == "$V32_SHA256" ]]; then
        V32_POSIX="$candidate"
        break
    fi
done

[[ -n "$V32_POSIX" ]] \
    || fail "khong tim thay V32.1 artifact dung SHA256=$V32_SHA256"

echo
echo "V32_1_ARTIFACT=$V32_POSIX"

echo
echo "===== KIEM TRA CODE V33 ====="

python -m py_compile \
    src/he_thong_dinh_luong/turnover_policy_stability_v33.py \
    src/he_thong_dinh_luong/turnover_policy_stability_v33_safe_runner.py \
    tests/test_turnover_policy_stability_v33.py \
    || fail "py_compile V33 that bai"

python -m unittest tests.test_turnover_policy_stability_v33 -v \
    || fail "unit test V33 that bai"

V32_WIN="$(cygpath -w "$V32_POSIX")"
RUN_ID="$(date +%Y%m%d-%H%M%S)"
OUTPUT_POSIX="$PWD/artifacts/turnover-policy-stability-v33-$RUN_ID"
OUTPUT_WIN="$(cygpath -w "$OUTPUT_POSIX")"

echo
echo "===== CHAY V33 FIXED CAP STABILITY ====="
echo "OUTPUT_DIR=$OUTPUT_POSIX"

python -m he_thong_dinh_luong.turnover_policy_stability_v33_safe_runner \
    --v32-artifact-zip "$V32_WIN" \
    --output-dir "$OUTPUT_WIN" \
    --expected-v32-sha256 "$V32_SHA256" \
    --caps "0,1,2,3,4,5,6,7,8,9,10" \
    --bootstrap-repetitions 2000 \
    --bootstrap-block-months 3 \
    --seed 20260803

MODEL_STATUS=$?

echo
echo "===== TOM TAT V33 ====="

python - "$OUTPUT_WIN" <<'PY'
from __future__ import annotations

import csv
import json
from pathlib import Path
import sys

output = Path(sys.argv[1]).resolve()
report_path = output / "turnover_policy_stability_v33.json"
failure_path = output / "run_failure_v33.json"
summary_path = output / "fixed_cap_summary_v33.csv"
paired_path = output / "paired_vs_nested_v33.csv"
decision_path = output / "decision_gates_v33.csv"

if failure_path.is_file():
    failure = json.loads(failure_path.read_text(encoding="utf-8-sig"))
    print("STATUS=FAILED")
    print("ERROR_TYPE=", failure.get("error_type"))
    print("ERROR=", failure.get("error"))

if report_path.is_file():
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    print("STATUS=", report.get("status"))
    print(
        "OUTER_FIRST_LAST=",
        report.get("source_v32_1_outer_test_first_date"),
        report.get("source_v32_1_outer_test_last_date"),
    )
    print(
        "OUTER_PERIODS=",
        report.get("source_v32_1_outer_test_period_count"),
    )
    print("MODEL=", report.get("model"))
    print("BREADTH=", report.get("breadth"))
    print("PRE_REGISTERED_CAP=", report.get("pre_registered_cap"))
    print("RECOMMENDATION=", report.get("recommendation"))
    print("HISTORICAL_PROMOTION_ALLOWED=false")
    print("LIVE_CAPITAL_APPROVED=false")

if summary_path.is_file() and paired_path.is_file() and decision_path.is_file():
    with summary_path.open("r", encoding="utf-8-sig", newline="") as stream:
        summaries = {
            int(row["fixed_replacement_cap"]): row
            for row in csv.DictReader(stream)
        }
    with paired_path.open("r", encoding="utf-8-sig", newline="") as stream:
        paired = {
            int(row["fixed_replacement_cap"]): row
            for row in csv.DictReader(stream)
        }
    with decision_path.open("r", encoding="utf-8-sig", newline="") as stream:
        decisions = {
            int(row["fixed_replacement_cap"]): row
            for row in csv.DictReader(stream)
        }

    print()
    print(
        "CAP,BASE_NET,VNINDEX,BASE_REL,STRESS_NET,STRESS_REL,"
        "DRAWDOWN,TURNOVER,DELTA_VS_NESTED,BOOT_PROB,LEAVE3_DELTA,"
        "SENSITIVITY_PASS,FUTURE_FREEZE"
    )
    for cap in sorted(summaries):
        row = summaries[cap]
        pair = paired[cap]
        decision = decisions[cap]
        print(
            ",".join(
                [
                    str(cap),
                    str(row.get("base_net_total_return") or ""),
                    str(row.get("base_benchmark_total_return") or ""),
                    str(row.get("base_relative_total_return") or ""),
                    str(row.get("stress_net_total_return") or ""),
                    str(row.get("stress_relative_total_return") or ""),
                    str(row.get("base_max_drawdown") or ""),
                    str(row.get("base_mean_turnover") or ""),
                    str(pair.get("mean_net_excess_delta") or ""),
                    str(pair.get("bootstrap_probability_delta_positive") or ""),
                    str(pair.get("leave_best_3_mean_net_excess_delta") or ""),
                    str(decision.get("sensitivity_gate_passed") or ""),
                    str(decision.get("future_holdout_freeze_candidate") or ""),
                ]
            )
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
