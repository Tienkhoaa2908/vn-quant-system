#!/usr/bin/env bash

set -u
set -o pipefail

BRANCH="agent/model-lab-predictive-value-dnse-sync-v3"
V33_NAME="turnover-policy-stability-v33-20260803-091649.zip"
V33_SHA256="0019679a8108f576b5063e01d493d018148adbd040212cea50fd5fe288f75555"
FREEZE_TIMESTAMP="2026-08-03T09:22:00+07:00"
EXCLUDE_SIGNAL_THROUGH="2026-07-31"

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
echo "===== TIM V33 ARTIFACT CANONICAL ====="

mapfile -t V33_CANDIDATES < <(
    find \
        "$PWD" \
        "$PWD/artifacts" \
        "$HOME/Downloads" \
        "$HOME/Desktop" \
        "$HOME/Documents" \
        -type f \
        -name "$V33_NAME" \
        -print 2>/dev/null \
    | awk '!seen[$0]++'
)

V33_POSIX=""
for candidate in "${V33_CANDIDATES[@]}"; do
    candidate_sha="$(sha256sum "$candidate" | awk '{print $1}')"
    echo "$candidate_sha  $candidate"
    if [[ "$candidate_sha" == "$V33_SHA256" ]]; then
        V33_POSIX="$candidate"
        break
    fi
done

[[ -n "$V33_POSIX" ]] \
    || fail "khong tim thay V33 artifact dung SHA256=$V33_SHA256"

echo
echo "V33_ARTIFACT=$V33_POSIX"
echo "FREEZE_TIMESTAMP=$FREEZE_TIMESTAMP"
echo "EXCLUDE_SIGNAL_THROUGH=$EXCLUDE_SIGNAL_THROUGH"

echo
echo "===== KIEM TRA CODE V34 ====="

python -m py_compile \
    src/he_thong_dinh_luong/future_paper_holdout_freeze_v34.py \
    src/he_thong_dinh_luong/future_paper_holdout_freeze_v34_safe_runner.py \
    tests/test_future_paper_holdout_freeze_v34.py \
    || fail "py_compile V34 that bai"

python -m unittest tests.test_future_paper_holdout_freeze_v34 -v \
    || fail "unit test V34 that bai"

V33_WIN="$(cygpath -w "$V33_POSIX")"
RUN_ID="$(date +%Y%m%d-%H%M%S)"
OUTPUT_POSIX="$PWD/artifacts/future-paper-holdout-freeze-v34-$RUN_ID"
OUTPUT_WIN="$(cygpath -w "$OUTPUT_POSIX")"

echo
echo "===== TAO FREEZE POLICY V34 ====="
echo "OUTPUT_DIR=$OUTPUT_POSIX"

python -m he_thong_dinh_luong.future_paper_holdout_freeze_v34_safe_runner \
    --v33-artifact-zip "$V33_WIN" \
    --output-dir "$OUTPUT_WIN" \
    --expected-v33-sha256 "$V33_SHA256" \
    --freeze-timestamp "$FREEZE_TIMESTAMP" \
    --exclude-signal-through "$EXCLUDE_SIGNAL_THROUGH"

MODEL_STATUS=$?

echo
echo "===== TOM TAT V34 ====="

python - "$OUTPUT_WIN" <<'PY'
from __future__ import annotations

import json
from pathlib import Path
import sys

output = Path(sys.argv[1]).resolve()
report_path = output / "future_paper_holdout_freeze_v34.json"
policy_path = output / "frozen_policy_v34.json"
failure_path = output / "run_failure_v34.json"

if failure_path.is_file():
    failure = json.loads(failure_path.read_text(encoding="utf-8-sig"))
    print("STATUS=FAILED")
    print("ERROR_TYPE=", failure.get("error_type"))
    print("ERROR=", failure.get("error"))

if report_path.is_file():
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    print("STATUS=", report.get("status"))
    print("POLICY_ID=", report.get("policy_id"))
    print("FROZEN_AT=", report.get("frozen_at"))
    print(
        "PRE_FREEZE_SIGNALS_EXCLUDED_THROUGH=",
        report.get("known_pre_freeze_signals_excluded_through"),
    )
    print(
        "FIRST_COUNTABLE_SIGNAL_RULE=",
        report.get("first_countable_signal_rule"),
    )
    print(
        "MINIMUM_FUTURE_OBSERVATIONS=",
        report.get("minimum_future_observations"),
    )
    print("RECOMMENDATION=", report.get("recommendation"))
    print("PAPER_TRADING_ALLOWED=", report.get("paper_trading_allowed"))
    print(
        "HISTORICAL_PROMOTION_ALLOWED=",
        report.get("historical_promotion_allowed"),
    )
    print("RESEARCH_ELIGIBLE=", report.get("research_eligible"))
    print(
        "LIVE_CAPITAL_APPROVED=",
        report.get("live_capital_approved"),
    )
    print(
        "AUTOMATIC_LIVE_ORDERS_ALLOWED=",
        report.get("automatic_live_orders_allowed"),
    )

if policy_path.is_file():
    policy = json.loads(policy_path.read_text(encoding="utf-8-sig"))
    frozen = policy.get("policy", {})
    holdout = policy.get("holdout_contract", {})
    limits = policy.get("known_limitations", {})
    print()
    print("===== FROZEN POLICY =====")
    print("MODEL=", frozen.get("model"))
    print("BREADTH=", frozen.get("breadth"))
    print(
        "FIXED_VOLUNTARY_REPLACEMENT_CAP=",
        frozen.get("fixed_voluntary_replacement_cap"),
    )
    print(
        "MODEL_RETRAINING_ALLOWED_INSIDE_HOLDOUT=",
        frozen.get("model_retraining_allowed_inside_holdout"),
    )
    print(
        "HISTORICAL_OBSERVATIONS_COUNTED=",
        holdout.get("historical_observations_counted"),
    )
    print(
        "PRE_FREEZE_FORWARD_SNAPSHOTS_COUNTED=",
        holdout.get("pre_freeze_forward_snapshots_counted"),
    )
    print(
        "EXACT_CASH_LEDGER_PNL_COMPUTED=",
        limits.get("exact_cash_ledger_pnl_computed"),
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
