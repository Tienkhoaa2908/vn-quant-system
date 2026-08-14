#!/usr/bin/env bash
set -euo pipefail
BRANCH="agent/v70-deep-backtest-research-standard"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
fail(){ echo "FAILED: $*" >&2; exit 2; }
[[ -n "$ROOT" ]] || fail "hay chay trong repository vn-quant-system"
cd "$ROOT"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "sai branch; can $BRANCH"
git diff --quiet || fail "tracked files da bi sua"
git diff --cached --quiet || fail "staging area co thay doi"

PY="$PWD/vn_quant_local_system/.venv/Scripts/python.exe"
STORE="$PWD/vn_quant_local_system/data/market/dnse_ohlcv.sqlite3"
[[ -f "$PY" ]] || fail "khong tim thay canonical workstation Python"
[[ -f "$STORE" ]] || fail "khong tim thay market DB"
export PYTHONPATH="$PWD/src:$PWD/vn_quant_local_system/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

RUN_ID="$(date +%Y%m%d-%H%M%S)"
ART="$PWD/artifacts"
OUT="$ART/v70-deep-backtest-$RUN_ID"
V68="$OUT/v68"; V69="$OUT/v69"; V70="$OUT/v70"
BUNDLE_DIR="$ART/v70-deep-backtest-bundle-$RUN_ID"
BUNDLE="$ART/UPLOAD_THIS_v70_DEEP_BACKTEST-$RUN_ID.zip"
FAIL_BUNDLE="$ART/UPLOAD_THIS_v70_DEEP_BACKTEST_FAILURE-$RUN_ID.zip"
LOG="$ART/v70-deep-backtest-$RUN_ID.log"
mkdir -p "$V68" "$V69" "$V70" "$BUNDLE_DIR"

run_all() (
  set -euo pipefail
  echo "===== V70 ONE-SHOT C3 RESEARCH + DEEP BACKTEST ====="
  echo "BRANCH=$BRANCH"
  echo "HEAD=$(git rev-parse HEAD)"
  echo "PYTHON_ENV=vn_quant_local_system/.venv"
  echo "CHAMPION_MODEL=C3_STABLE_3_PAST_IC_SHRUNK"
  echo "CHAMPION_REPLACED=false"
  echo "C3_TRAINING_LABEL=CLOSE_T_TO_CLOSE_T_PLUS_20_BENCHMARK_RELATIVE"
  echo "TRADABLE_EXECUTION=NEXT_SESSION_OPEN"
  echo "DEEP_BACKTEST_REQUIRED=true"
  echo "LOT_SIZE=100"
  echo "SINGLE_NAME_CAP=0.15"
  echo "COST_SCENARIOS=GROSS,BASE_DNSE,STRESS,SEVERE"
  echo "SETTLEMENT_SENSITIVITY=T2_NO_ADVANCE_WITH_CATCHUP"
  echo "EXPOSURE_MATCHED_BENCHMARK=true"
  echo "YEAR_2026=OBSERVED_STRESS_NOT_TUNING"
  echo "MACRO_INCLUDED=false"
  echo "PROMOTION_AUTHORIZED=false"
  echo

  echo "===== COMPILE + REGRESSION ====="
  "$PY" -m py_compile \
    src/he_thong_dinh_luong/c3_hose_native_v67.py \
    src/he_thong_dinh_luong/c3_hose_consolidated_v68_safe.py \
    src/he_thong_dinh_luong/c3_matched_control_v69.py \
    src/he_thong_dinh_luong/c3_portfolio_profit_v69.py \
    src/he_thong_dinh_luong/deep_portfolio_backtest_v70.py \
    tests/test_c3_hose_native_v67.py \
    tests/test_c3_hose_consolidated_v68.py \
    tests/test_c3_matched_control_v69.py \
    tests/test_c3_matched_control_v69_integration.py \
    tests/test_deep_portfolio_backtest_v70.py
  "$PY" -m unittest \
    tests.test_c3_hose_native_v67 \
    tests.test_c3_hose_consolidated_v68 \
    tests.test_c3_matched_control_v69 \
    tests.test_c3_matched_control_v69_integration \
    tests.test_deep_portfolio_backtest_v70 -v
  echo

  echo "===== PHASE 1 V68: DATA + C3 + COHORTS ====="
  ARGS=(--store "$(cygpath -w "$STORE")" --output-dir "$(cygpath -w "$V68")" --bootstrap-samples 2000
        --search-root "$(cygpath -w "$PWD/vn_quant_local_system/data")")
  [[ -d "$PWD/vn_quant_local_system/validation" ]] && ARGS+=(--search-root "$(cygpath -w "$PWD/vn_quant_local_system/validation")")
  [[ -d "$PWD/vn_quant_local_system/outputs" ]] && ARGS+=(--search-root "$(cygpath -w "$PWD/vn_quant_local_system/outputs")")
  "$PY" -m he_thong_dinh_luong.c3_hose_consolidated_v68_safe "${ARGS[@]}"
  echo

  echo "===== PHASE 2 V69: MATCHED CONTROL + BLOCK INFERENCE ====="
  "$PY" -m he_thong_dinh_luong.c3_matched_control_v69 \
    --v68-output "$(cygpath -w "$V68")" --store "$(cygpath -w "$STORE")" \
    --output-dir "$(cygpath -w "$V69")" --signflip-samples 10000 --bootstrap-samples 5000
  echo

  echo "===== PHASE 3 V69: GROSS PROFIT REFERENCE ====="
  "$PY" -m he_thong_dinh_luong.c3_portfolio_profit_v69 \
    --v68-output "$(cygpath -w "$V68")" --store "$(cygpath -w "$STORE")" \
    --output-dir "$(cygpath -w "$V69")"
  echo

  echo "===== PHASE 4 V70: DEEP EXECUTION BACKTEST ====="
  "$PY" -m he_thong_dinh_luong.deep_portfolio_backtest_v70 \
    --v68-output "$(cygpath -w "$V68")" --store "$(cygpath -w "$STORE")" \
    --output-dir "$(cygpath -w "$V70")" --initial-capital 1000000000
  echo

  echo "===== PROFIT + 2026 SCORECARD ====="
  "$PY" - "$(cygpath -w "$V70/v70_backtest_summary.csv")" "$(cygpath -w "$V70/v70_bear_market_scorecard.csv")" <<'PY'
import csv,sys
from pathlib import Path
def rows(path):
    with Path(path).open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
s=rows(sys.argv[1]); y=rows(sys.argv[2])
for r in s:
    if r["strategy_id"]=="C3_EQ_ALWAYS" and r["cost_scenario"]=="BASE_DNSE":
        print("BASE",r["variant_id"],"total_return="+str(r["total_return"]),"benchmark="+str(r["benchmark_total_return"]),"alpha="+str(r["total_alpha_arithmetic"]),"cagr="+str(r["cagr"]),"mdd="+str(r["max_drawdown_daily"]),"down_alpha="+str(r["down_market_mean_alpha"]))
for r in y:
    if r["strategy_id"]=="C3_EQ_ALWAYS":
        print("Y2026",r["variant_id"],"return="+str(r["strategy_return"]),"benchmark="+str(r["benchmark_return"]),"alpha="+str(r["alpha_arithmetic"]))
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
TARGET="$BUNDLE"; [[ "$RC" -eq 0 ]] || TARGET="$FAIL_BUNDLE"
powershell.exe -NoProfile -Command "Compress-Archive -Path '$(cygpath -w "$BUNDLE_DIR")\\*' -DestinationPath '$(cygpath -w "$TARGET")' -Force" || true
echo
if [[ "$RC" -eq 0 ]]; then
  echo "===== V70 COMPLETE ====="; echo "UPLOAD_ZIP=$BUNDLE"; echo "UPLOAD_ZIP_WINDOWS=$(cygpath -w "$BUNDLE")"
else
  echo "===== V70 FAILED ====="; echo "UPLOAD_ZIP=$FAIL_BUNDLE"
fi
explorer.exe "$(cygpath -w "$ART")" >/dev/null 2>&1 || true
exit "$RC"
