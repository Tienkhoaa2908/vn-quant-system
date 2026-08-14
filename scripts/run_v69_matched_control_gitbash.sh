#!/usr/bin/env bash
set -euo pipefail

BRANCH="agent/v69-matched-control-block-robustness"
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
fail(){ echo "FAILED: $*" >&2; exit 2; }
[[ -n "$REPO_ROOT" ]] || fail "hay chay trong repository vn-quant-system"
cd "$REPO_ROOT"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "sai branch; can $BRANCH"
git diff --quiet || fail "tracked files da bi sua"
git diff --cached --quiet || fail "staging area co thay doi"

PY="$PWD/vn_quant_local_system/.venv/Scripts/python.exe"
STORE="$PWD/vn_quant_local_system/data/market/dnse_ohlcv.sqlite3"
DATA_ROOT="$PWD/vn_quant_local_system/data"
VALIDATION_ROOT="$PWD/vn_quant_local_system/validation"
OUTPUTS_ROOT="$PWD/vn_quant_local_system/outputs"
[[ -f "$PY" ]] || fail "khong tim thay canonical workstation Python"
[[ -f "$STORE" ]] || fail "khong tim thay market DB"

export PYTHONPATH="$PWD/src:$PWD/vn_quant_local_system/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

RUN_ID="$(date +%Y%m%d-%H%M%S)"
ART="$PWD/artifacts"
OUT="$ART/v69-matched-control-$RUN_ID"
V68_OUT="$OUT/v68"
V69_OUT="$OUT/v69"
BUNDLE_DIR="$ART/v69-matched-control-bundle-$RUN_ID"
BUNDLE="$ART/UPLOAD_THIS_v69_MATCHED_CONTROL-$RUN_ID.zip"
FAIL_BUNDLE="$ART/UPLOAD_THIS_v69_MATCHED_CONTROL_FAILURE-$RUN_ID.zip"
LOG="$ART/v69-matched-control-$RUN_ID.log"
mkdir -p "$ART" "$V68_OUT" "$V69_OUT" "$BUNDLE_DIR"

run_all() (
  set -euo pipefail
  echo "===== V69 MATCHED-CONTROL C3 ROBUSTNESS ====="
  echo "BRANCH=$BRANCH"
  echo "HEAD=$(git rev-parse HEAD)"
  echo "PYTHON_ENV=vn_quant_local_system/.venv"
  echo "CHAMPION_MODEL=C3_STABLE_3_PAST_IC_SHRUNK"
  echo "CHAMPION_REPLACED=false"
  echo "COHORT_THRESHOLDS_CHANGED=false"
  echo "C3_TRAINING_LABEL=CLOSE_T_TO_CLOSE_T_PLUS_20_BENCHMARK_RELATIVE"
  echo "TRADABLE_OUTCOME=NEXT_SESSION_OPEN_TO_FUTURE_OPEN"
  echo "AUGUST_2026_SHADOW_ONLY=true"
  echo "LEADER_MATCHED_CONTROL=true"
  echo "RISK_MATCHED_CONTROL=true"
  echo "DEPENDENCE_BLOCK=CONTIGUOUS_TWO_CALENDAR_MONTHS"
  echo "SIGNFLIP_SAMPLES=10000"
  echo "BOOTSTRAP_SAMPLES_CI_ONLY=5000"
  echo "P_VALUES_NEVER_ZERO=true"
  echo "PROFIT_REPORT_REQUIRED=true"
  echo "PROFIT_PORTFOLIO_CONTRACT=MONTHLY_C3_TOP10_EQUAL_WEIGHT_NEXT_OPEN_TO_NEXT_REBALANCE_OPEN"
  echo "PROFIT_REPORT_GROSS_ONLY=true"
  echo "SOURCE_STORE_MUTATION_ALLOWED=false"
  echo "PROMOTION_AUTHORIZED=false"
  echo

  echo "===== COMPILE + REGRESSION TESTS ====="
  "$PY" -m py_compile \
    src/he_thong_dinh_luong/c3_hose_native_v67.py \
    src/he_thong_dinh_luong/c3_hose_native_driver_v67.py \
    src/he_thong_dinh_luong/c3_hose_consolidated_v68.py \
    src/he_thong_dinh_luong/c3_hose_consolidated_v68_safe.py \
    src/he_thong_dinh_luong/c3_matched_control_v69.py \
    src/he_thong_dinh_luong/c3_portfolio_profit_v69.py \
    tests/test_c3_hose_native_v67.py \
    tests/test_c3_hose_consolidated_v68.py \
    tests/test_c3_matched_control_v69.py \
    tests/test_c3_matched_control_v69_integration.py
  "$PY" -m unittest \
    tests.test_c3_hose_native_v67 \
    tests.test_c3_hose_consolidated_v68 \
    tests.test_c3_matched_control_v69 \
    tests.test_c3_matched_control_v69_integration -v
  echo

  echo "===== PHASE 1: V68 C3 + DATA SENSITIVITY ====="
  ARGS=(
    --store "$(cygpath -w "$STORE")"
    --output-dir "$(cygpath -w "$V68_OUT")"
    --search-root "$(cygpath -w "$DATA_ROOT")"
    --bootstrap-samples 2000
  )
  [[ -d "$VALIDATION_ROOT" ]] && ARGS+=(--search-root "$(cygpath -w "$VALIDATION_ROOT")")
  [[ -d "$OUTPUTS_ROOT" ]] && ARGS+=(--search-root "$(cygpath -w "$OUTPUTS_ROOT")")
  "$PY" -m he_thong_dinh_luong.c3_hose_consolidated_v68_safe "${ARGS[@]}"
  echo

  echo "===== PHASE 2: V69 MATCHED CONTROLS + BLOCK INFERENCE ====="
  "$PY" -m he_thong_dinh_luong.c3_matched_control_v69 \
    --v68-output "$(cygpath -w "$V68_OUT")" \
    --store "$(cygpath -w "$STORE")" \
    --output-dir "$(cygpath -w "$V69_OUT")" \
    --signflip-samples 10000 \
    --bootstrap-samples 5000
  echo

  echo "===== PHASE 3: MANDATORY PORTFOLIO PROFIT REPORT ====="
  "$PY" -m he_thong_dinh_luong.c3_portfolio_profit_v69 \
    --v68-output "$(cygpath -w "$V68_OUT")" \
    --store "$(cygpath -w "$STORE")" \
    --output-dir "$(cygpath -w "$V69_OUT")"
  echo

  echo "===== V69 REPORT SUMMARY ====="
  "$PY" - "$(cygpath -w "$V69_OUT/v69_report.json")" "$(cygpath -w "$V69_OUT/v69_profit_report.json")" <<'PY'
import json, sys
from pathlib import Path
r=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
p=json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
print("status="+str(r.get("status")))
print("leader_watch_count="+str(len(r.get("leader_diagnostic_watchlist",[]))))
print("risk_watch_count="+str(len(r.get("risk_diagnostic_watchlist",[]))))
print("canonical_research_claim_authorized="+str(r.get("canonical_research_claim_authorized")))
print("promotion_authorized="+str(r.get("promotion_authorized")))
print("profit_report_status="+str(p.get("status")))
print("profit_summary_rows="+str(len(p.get("summary",[]))))
print("profit_gross_only="+str(p.get("gross_only")))
print("profit_missing_price_period_count="+str(p.get("missing_price_period_count")))
PY
)

set +e
run_all 2>&1 | tee "$LOG"
RC=${PIPESTATUS[0]}
set -e

cp "$LOG" "$BUNDLE_DIR/run.log" || true
git branch --show-current > "$BUNDLE_DIR/git_branch.txt"
git rev-parse HEAD > "$BUNDLE_DIR/git_head.txt"
sha256sum "$STORE" > "$BUNDLE_DIR/store_sha256.txt"
"$PY" - <<'PY' > "$BUNDLE_DIR/python_version.txt" 2>&1 || true
import sys
print(sys.version.replace("\n"," "))
print(sys.executable)
PY
[[ -d "$OUT" ]] && cp -R "$OUT" "$BUNDLE_DIR/output" || true

TARGET="$BUNDLE"
[[ "$RC" -eq 0 ]] || TARGET="$FAIL_BUNDLE"
powershell.exe -NoProfile -Command \
  "Compress-Archive -Path '$(cygpath -w "$BUNDLE_DIR")\\*' -DestinationPath '$(cygpath -w "$TARGET")' -Force" || true

if [[ "$RC" -eq 0 ]]; then
  echo
  echo "===== V69 COMPLETE ====="
  echo "RUN_EXIT=0"
  echo "UPLOAD_ZIP=$BUNDLE"
  echo "UPLOAD_ZIP_WINDOWS=$(cygpath -w "$BUNDLE")"
else
  echo
  echo "===== V69 FAILED ====="
  echo "RUN_EXIT=$RC"
  echo "UPLOAD_ZIP=$FAIL_BUNDLE"
fi
explorer.exe "$(cygpath -w "$ART")" >/dev/null 2>&1 || true
exit "$RC"
