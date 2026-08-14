#!/usr/bin/env bash

set -u
set -o pipefail

BRANCH="agent/model-lab-predictive-value-dnse-sync-v3"

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

echo "===== MUC TIEU V38 ====="
echo "Mot lenh: V36 data/ledger -> V37 capital gate -> V38 decision-surface + ops dry-run"
echo "Khong retrain model. Khong suy sector. Khong tu dong xac nhan corporate actions."

echo
echo "===== DONG BO CODE ====="
if ! git fetch origin \
  || ! git switch "$BRANCH" \
  || ! git pull --ff-only origin "$BRANCH"; then
    fail "khong dong bo duoc branch $BRANCH"
fi
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"

echo
echo "===== KIEM TRA V38 ====="
python -m py_compile \
    src/he_thong_dinh_luong/trade_evidence_accelerator_v38.py \
    src/he_thong_dinh_luong/trade_evidence_accelerator_v38_io.py \
    src/he_thong_dinh_luong/trade_evidence_accelerator_v38_surface.py \
    src/he_thong_dinh_luong/trade_evidence_accelerator_v38_ops.py \
    src/he_thong_dinh_luong/trade_evidence_accelerator_v38_safe_runner.py \
    tests/test_trade_evidence_accelerator_v38.py \
    || fail "py_compile V38 that bai"
python -m unittest tests.test_trade_evidence_accelerator_v38 -v \
    || fail "unit test V38 that bai"

MARKER="$(mktemp)"
touch "$MARKER"

echo
echo "===== 1/2 CHAY FULL V36 + V37 ====="
if ! printf 'exit\n' | bash scripts/run_v37_trade_readiness_integrated_gitbash.sh; then
    rm -f "$MARKER"
    fail "V37 integrated runner that bai"
fi

V36_POSIX="$(
    find "$PWD/artifacts" -maxdepth 1 -type f \
        -name 'integrated-data-ledger-v36-*.zip' -newer "$MARKER" \
        -printf '%T@ %p\n' 2>/dev/null \
      | sort -nr | head -n 1 | cut -d' ' -f2-
)"
V37_POSIX="$(
    find "$PWD/artifacts" -maxdepth 1 -type f \
        -name 'trade-readiness-v37-*.zip' -newer "$MARKER" \
        -printf '%T@ %p\n' 2>/dev/null \
      | sort -nr | head -n 1 | cut -d' ' -f2-
)"
rm -f "$MARKER"

[[ -f "$V36_POSIX" ]] || fail "khong tim thay V36 artifact moi"
[[ -f "$V37_POSIX" ]] || fail "khong tim thay V37 artifact moi"

V36_SHA="$(sha256sum "$V36_POSIX" | awk '{print $1}')"
V37_SHA="$(sha256sum "$V37_POSIX" | awk '{print $1}')"

RUN_ID="$(date +%Y%m%d-%H%M%S)"
OUTPUT_POSIX="$PWD/artifacts/trade-evidence-accelerator-v38-$RUN_ID"
OUTPUT_WIN="$(cygpath -w "$OUTPUT_POSIX")"

echo
echo "===== 2/2 TAO DECISION-SURFACE PACK + OPS DRY-RUN ====="
python -m he_thong_dinh_luong.trade_evidence_accelerator_v38_safe_runner \
    --v36-artifact-zip "$(cygpath -w "$V36_POSIX")" \
    --v37-artifact-zip "$(cygpath -w "$V37_POSIX")" \
    --expected-v36-sha256 "$V36_SHA" \
    --expected-v37-sha256 "$V37_SHA" \
    --output-dir "$OUTPUT_WIN"
STATUS=$?

echo
echo "===== KET LUAN V38 ====="
python - "$OUTPUT_WIN" <<'PY'
import json
from pathlib import Path
import sys

out = Path(sys.argv[1])
report_path = out / "trade_evidence_accelerator_v38.json"
failure_path = out / "run_failure_v38.json"
if failure_path.is_file():
    failure = json.loads(failure_path.read_text(encoding="utf-8-sig"))
    print("STATUS=FAILED")
    print("ERROR=", failure.get("error"))
elif report_path.is_file():
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    surface = report.get("decision_surface", {})
    ops = report.get("operational_dry_run", {})
    print("STATUS=", report.get("status"))
    print("OBJECTIVE=", report.get("objective"))
    print("POLICY_ID=", report.get("policy_id"))
    print("PERIODS=", surface.get("period_count"))
    print("POSITION_TIME_KEYS=", surface.get("position_time_key_count"))
    print("HOLDING_WINDOWS=", surface.get("holding_window_count"))
    print("UNIQUE_SELECTED_SYMBOLS=", surface.get("unique_symbol_count"))
    print("EXECUTION_DATES=", surface.get("execution_date_count"))
    print(
        "EXECUTION_FIRST_LAST=",
        surface.get("first_execution_day"),
        surface.get("last_execution_day"),
    )
    print(
        "OPERATIONAL_DRY_RUN=",
        ops.get("passed_count"),
        "/",
        ops.get("total_count"),
    )
    print(
        "REMAINING_WORKSTATION_CONTROLS=",
        "|".join(ops.get("remaining_workstation_controls", [])),
    )
    print("NEXT_ACTION=", report.get("next_action"))
    print("LIVE_CAPITAL_APPROVED=", report.get("live_capital_approved"))
PY

ZIP_POSIX="${OUTPUT_POSIX}.zip"
echo
echo "MODEL_EXIT_CODE=$STATUS"
echo "V36_ARTIFACT=$V36_POSIX"
echo "$V36_SHA *$V36_POSIX"
echo "V37_ARTIFACT=$V37_POSIX"
echo "$V37_SHA *$V37_POSIX"
if [[ -f "$ZIP_POSIX" ]]; then
    echo "V38_ARTIFACT=$ZIP_POSIX"
    sha256sum "$ZIP_POSIX"
else
    echo "WARNING: khong tim thay V38 ZIP"
fi
keep_open
