#!/usr/bin/env bash

set -u
set -o pipefail

BRANCH="agent/model-lab-predictive-value-dnse-sync-v3"
V34_NAME="future-paper-holdout-freeze-v34-1-20260803-094853.zip"
V34_SHA256="642a19cddadc271a2cffb16261ad9e0a4fceadab884eea308ab8bce88debbf80"
STORE_POSIX="/c/Users/welcome/Documents/vn-quant-data/market-data/dnse_ohlcv_v20.sqlite3"
STORE_SHA256="7b6f2274d43c12a311f83aa71952ef2abcfca04e2f5204c2f0e9a36a6c144549"
SECTOR_MASTER_POSIX="/c/Users/welcome/Documents/vn-quant-data/reference/sector_master_point_in_time.csv"
CORPORATE_ACTIONS_POSIX="/c/Users/welcome/Documents/vn-quant-data/reference/corporate_actions.csv"

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
echo "===== TIM V34.1 ARTIFACT CANONICAL ====="
mapfile -t CANDIDATES < <(
    find "$PWD" "$PWD/artifacts" "$HOME/Downloads" "$HOME/Desktop" "$HOME/Documents" \
        -type f -name "$V34_NAME" -print 2>/dev/null | awk '!seen[$0]++'
)
V34_POSIX=""
for candidate in "${CANDIDATES[@]}"; do
    candidate_sha="$(sha256sum "$candidate" | awk '{print $1}')"
    echo "$candidate_sha  $candidate"
    if [[ "$candidate_sha" == "$V34_SHA256" ]]; then
        V34_POSIX="$candidate"
        break
    fi
done
[[ -n "$V34_POSIX" ]] || fail "khong tim thay V34.1 dung SHA256=$V34_SHA256"

[[ -f "$STORE_POSIX" ]] || fail "khong tim thay SQLite canonical: $STORE_POSIX"
actual_store_sha="$(sha256sum "$STORE_POSIX" | awk '{print $1}')"
echo "$actual_store_sha  $STORE_POSIX"
[[ "$actual_store_sha" == "$STORE_SHA256" ]] \
    || fail "SQLite hash da thay doi: $actual_store_sha"

echo
echo "===== KIEM TRA CODE V35 ====="
python -m py_compile \
    src/he_thong_dinh_luong/exact_cash_ledger_readiness_v35.py \
    src/he_thong_dinh_luong/exact_cash_ledger_readiness_v35_safe_runner.py \
    tests/test_exact_cash_ledger_readiness_v35.py \
    || fail "py_compile V35 that bai"
python -m unittest tests.test_exact_cash_ledger_readiness_v35 -v \
    || fail "unit test V35 that bai"

RUN_ID="$(date +%Y%m%d-%H%M%S)"
OUTPUT_POSIX="$PWD/artifacts/exact-cash-ledger-readiness-v35-$RUN_ID"
OUTPUT_WIN="$(cygpath -w "$OUTPUT_POSIX")"
V34_WIN="$(cygpath -w "$V34_POSIX")"
STORE_WIN="$(cygpath -w "$STORE_POSIX")"

ARGS=(
    --v34-artifact-zip "$V34_WIN"
    --sqlite-store "$STORE_WIN"
    --output-dir "$OUTPUT_WIN"
    --expected-v34-sha256 "$V34_SHA256"
    --expected-sqlite-sha256 "$STORE_SHA256"
    --initial-capital-vnd 1000000000
)

if [[ -f "$SECTOR_MASTER_POSIX" ]]; then
    echo "SECTOR_MASTER_FOUND=$SECTOR_MASTER_POSIX"
    ARGS+=(--sector-master "$(cygpath -w "$SECTOR_MASTER_POSIX")")
else
    echo "SECTOR_MASTER_MISSING=$SECTOR_MASTER_POSIX"
fi

if [[ -f "$CORPORATE_ACTIONS_POSIX" ]]; then
    echo "CORPORATE_ACTIONS_FOUND=$CORPORATE_ACTIONS_POSIX"
    ARGS+=(--corporate-actions "$(cygpath -w "$CORPORATE_ACTIONS_POSIX")")
else
    echo "CORPORATE_ACTIONS_MISSING=$CORPORATE_ACTIONS_POSIX"
fi

echo
echo "===== CHAY V35 EXACT-LEDGER READINESS AUDIT ====="
echo "V34_ARTIFACT=$V34_POSIX"
echo "SQLITE_STORE=$STORE_POSIX"
echo "OUTPUT_DIR=$OUTPUT_POSIX"
echo "PRICE_BASIS_CONFIRMED=false"

python -m he_thong_dinh_luong.exact_cash_ledger_readiness_v35_safe_runner "${ARGS[@]}"
STATUS=$?

echo
echo "===== TOM TAT V35 ====="
python - "$OUTPUT_WIN" <<'PY'
import json
from pathlib import Path
import sys

out = Path(sys.argv[1])
failure = out / "run_failure_v35.json"
report_path = out / "exact_cash_ledger_readiness_v35.json"

if failure.is_file():
    value = json.loads(failure.read_text(encoding="utf-8-sig"))
    print("STATUS=FAILED")
    print("ERROR=", value.get("error"))

if report_path.is_file():
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    sqlite = report.get("sqlite", {})
    print("STATUS=", report.get("status"))
    print("AUDIT_OUTCOME=", report.get("audit_outcome"))
    print("RECOMMENDATION=", report.get("recommendation"))
    print("POLICY_ID=", report.get("policy_id"))
    print("SQLITE_ROWS=", sqlite.get("row_count"))
    print("SQLITE_FIRST_LAST=", sqlite.get("first_day"), sqlite.get("last_day"))
    print("SQLITE_SYMBOLS_DAYS=", sqlite.get("distinct_symbols"), sqlite.get("distinct_days"))
    print("DUPLICATE_KEYS=", sqlite.get("duplicate_key_count"))
    print("INVALID_OHLCV_ROWS=", sqlite.get("invalid_ohlcv_row_count"))
    print("T1_OPEN_COVERAGE_RATIO=", sqlite.get("t1_open_coverage_ratio"))
    print("BLOCKERS=", json.dumps(report.get("blockers", []), ensure_ascii=True))
    print("EXACT_CASH_LEDGER_PNL_COMPUTED=false")
    print("LIVE_CAPITAL_APPROVED=false")
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
