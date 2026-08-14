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
mapfile -t CANDIDATES < <(
    find "$PWD" "$PWD/artifacts" "$HOME/Downloads" "$HOME/Desktop" "$HOME/Documents" \
        -type f -name "$V33_NAME" -print 2>/dev/null | awk '!seen[$0]++'
)
V33_POSIX=""
for candidate in "${CANDIDATES[@]}"; do
    candidate_sha="$(sha256sum "$candidate" | awk '{print $1}')"
    echo "$candidate_sha  $candidate"
    if [[ "$candidate_sha" == "$V33_SHA256" ]]; then
        V33_POSIX="$candidate"
        break
    fi
done
[[ -n "$V33_POSIX" ]] || fail "khong tim thay V33 dung SHA256=$V33_SHA256"

echo
echo "===== KIEM TRA CODE V34.1 ====="
python -m py_compile \
    src/he_thong_dinh_luong/future_paper_holdout_freeze_v34.py \
    src/he_thong_dinh_luong/future_paper_holdout_freeze_v34_safe_runner.py \
    src/he_thong_dinh_luong/future_paper_holdout_freeze_v34_1.py \
    src/he_thong_dinh_luong/future_paper_holdout_freeze_v34_1_safe_runner.py \
    tests/test_future_paper_holdout_freeze_v34.py \
    tests/test_future_paper_holdout_freeze_v34_1.py \
    || fail "py_compile V34.1 that bai"
python -m unittest \
    tests.test_future_paper_holdout_freeze_v34 \
    tests.test_future_paper_holdout_freeze_v34_1 \
    -v || fail "unit test V34.1 that bai"

RUN_ID="$(date +%Y%m%d-%H%M%S)"
OUTPUT_POSIX="$PWD/artifacts/future-paper-holdout-freeze-v34-1-$RUN_ID"
OUTPUT_WIN="$(cygpath -w "$OUTPUT_POSIX")"
V33_WIN="$(cygpath -w "$V33_POSIX")"

echo
echo "===== TAO FREEZE POLICY V34.1 ====="
echo "V33_ARTIFACT=$V33_POSIX"
echo "OUTPUT_DIR=$OUTPUT_POSIX"
echo "FREEZE_TIMESTAMP=$FREEZE_TIMESTAMP"
echo "EXCLUDE_SIGNAL_THROUGH=$EXCLUDE_SIGNAL_THROUGH"

python -m he_thong_dinh_luong.future_paper_holdout_freeze_v34_1_safe_runner \
    --v33-artifact-zip "$V33_WIN" \
    --output-dir "$OUTPUT_WIN" \
    --expected-v33-sha256 "$V33_SHA256" \
    --freeze-timestamp "$FREEZE_TIMESTAMP" \
    --exclude-signal-through "$EXCLUDE_SIGNAL_THROUGH"
STATUS=$?

echo
echo "===== TOM TAT V34.1 ====="
python - "$OUTPUT_WIN" <<'PY'
import json
from pathlib import Path
import sys
out = Path(sys.argv[1])
failure = out / "run_failure_v34.json"
report_path = out / "future_paper_holdout_freeze_v34.json"
policy_path = out / "frozen_policy_v34.json"
if failure.is_file():
    value = json.loads(failure.read_text(encoding="utf-8-sig"))
    print("STATUS=FAILED")
    print("ERROR=", value.get("error"))
if report_path.is_file():
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    print("STATUS=", report.get("status"))
    print("POLICY_ID=", report.get("policy_id"))
    print("FROZEN_AT=", report.get("frozen_at"))
    print("POLICY_ID_PATH_INDEPENDENT=", report.get("policy_id_path_independent"))
    print("PRE_FREEZE_SIGNALS_EXCLUDED_THROUGH=", report.get("known_pre_freeze_signals_excluded_through"))
    print("MINIMUM_FUTURE_OBSERVATIONS=", report.get("minimum_future_observations"))
    print("RECOMMENDATION=", report.get("recommendation"))
if policy_path.is_file():
    policy = json.loads(policy_path.read_text(encoding="utf-8-sig"))
    frozen = policy.get("policy", {})
    permissions = policy.get("permissions", {})
    print("MODEL=", frozen.get("model"))
    print("BREADTH=", frozen.get("breadth"))
    print("FIXED_CAP=", frozen.get("fixed_voluntary_replacement_cap"))
    print("PAPER_TRADING_ALLOWED=", permissions.get("paper_trading_allowed"))
    print("LIVE_CAPITAL_APPROVED=", permissions.get("live_capital_approved"))
PY

ZIP_POSIX="${OUTPUT_POSIX}.zip"
echo
echo "MODEL_EXIT_CODE=$STATUS"
if [[ -f "$ZIP_POSIX" ]]; then
    echo "ARTIFACT_ZIP=$ZIP_POSIX"
    sha256sum "$ZIP_POSIX"
else
    echo "WARNING: khong tim thay artifact ZIP tai $ZIP_POSIX"
fi
keep_open
