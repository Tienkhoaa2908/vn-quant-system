#!/usr/bin/env bash
set -euo pipefail

BRANCH="agent/v73-c3-factor-health-regime"
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
export PYTHONHASHSEED=0

RUN_ID="$(date +%Y%m%d-%H%M%S)"
ART="$PWD/artifacts"
OUT="$ART/v73-c3-factor-health-$RUN_ID"
V68="$OUT/v68"; V70="$OUT/v70"; V73="$OUT/v73"
BUNDLE_DIR="$ART/v73-c3-factor-health-bundle-$RUN_ID"
BUNDLE="$ART/UPLOAD_THIS_v73_C3_FACTOR_HEALTH-$RUN_ID.zip"
FAIL_BUNDLE="$ART/UPLOAD_THIS_v73_C3_FACTOR_HEALTH_FAILURE-$RUN_ID.zip"
LOG="$ART/v73-c3-factor-health-$RUN_ID.log"
mkdir -p "$V68" "$V70" "$V73" "$BUNDLE_DIR"

run_all() (
  set -euo pipefail
  echo "===== V73 ONE-SHOT C3 FACTOR-HEALTH REGIME ABLATION ====="
  echo "BRANCH=$BRANCH"
  echo "HEAD=$(git rev-parse HEAD)"
  echo "PYTHON_ENV=vn_quant_local_system/.venv"
  echo "PYTHONHASHSEED=0"
  echo "CHAMPION_MODEL=C3_STABLE_3_PAST_IC_SHRUNK"
  echo "CHAMPION_REPLACED=false"
  echo "RANKING_CHANGED=false"
  echo "COMPONENTS_CHANGED=false"
  echo "GATES=FH_RS3_SOFT50,FH_MOM3_AVG_SOFT50,FH_MOM6_AVG_SOFT50"
  echo "GATE_SOURCE=COMPLETED_C3_COMPONENT_IC_ONLY"
  echo "GATE_THRESHOLD=ZERO_SIGN_ONLY"
  echo "GATE_EXPOSURE=0.50"
  echo "PRIMARY_SELECTION_END=2025-12-31"
  echo "YEAR_2026_USED_FOR_SELECTION=false"
  echo "YEAR_2026=OBSERVED_STRESS_NOT_SELECTION_SET"
  echo "POST_SELECTED_MECHANISM_AUDIT=true"
  echo "WEEKLY_OVERLAY_COMBINED=false"
  echo "ADAPTIVE_WEIGHT_COMBINED=false"
  echo "MACRO_INCLUDED=false"
  echo "DEEP_BACKTEST_ENGINE=V70_REUSED"
  echo "COST_SCENARIOS=GROSS,BASE_DNSE,STRESS,SEVERE"
  echo "ALLOCATORS=EQUAL,INVOL60"
  echo "CAPITAL_SENSITIVITY=100M,1B,10B_VND"
  echo "SETTLEMENT_SENSITIVITY=T2_NO_ADVANCE_WITH_CATCHUP"
  echo "PROFIT_REPORT_REQUIRED=true"
  echo "PROMOTION_AUTHORIZED=false"
  echo

  echo "===== COMPILE + REGRESSION ====="
  "$PY" -m py_compile \
    src/he_thong_dinh_luong/c3_hose_native_v67.py \
    src/he_thong_dinh_luong/c3_hose_consolidated_v68_safe.py \
    src/he_thong_dinh_luong/deep_portfolio_backtest_v70.py \
    src/he_thong_dinh_luong/c3_adaptive_weight_v71.py \
    src/he_thong_dinh_luong/c3_factor_health_regime_v73.py \
    tests/test_c3_factor_health_regime_v73.py
  "$PY" -m unittest tests.test_c3_factor_health_regime_v73 -v
  echo

  echo "===== PHASE 1 V68: DATA + FROZEN C3 + SENSITIVITY UNIVERSES ====="
  ARGS=(--store "$(cygpath -w "$STORE")" --output-dir "$(cygpath -w "$V68")" --bootstrap-samples 500 \
        --search-root "$(cygpath -w "$PWD/vn_quant_local_system/data")")
  [[ -d "$PWD/vn_quant_local_system/validation" ]] && ARGS+=(--search-root "$(cygpath -w "$PWD/vn_quant_local_system/validation")")
  [[ -d "$PWD/vn_quant_local_system/outputs" ]] && ARGS+=(--search-root "$(cygpath -w "$PWD/vn_quant_local_system/outputs")")
  "$PY" -m he_thong_dinh_luong.c3_hose_consolidated_v68_safe "${ARGS[@]}"
  echo

  echo "===== PHASE 2 V70: FROZEN-C3 DEEP BACKTEST REFERENCE ====="
  "$PY" -m he_thong_dinh_luong.deep_portfolio_backtest_v70 \
    --v68-output "$(cygpath -w "$V68")" --store "$(cygpath -w "$STORE")" \
    --output-dir "$(cygpath -w "$V70")" --initial-capital 1000000000
  echo

  echo "===== PHASE 3 V73: CAUSAL FACTOR-HEALTH EXPOSURE GATES ====="
  "$PY" -m he_thong_dinh_luong.c3_factor_health_regime_v73 \
    --v68-output "$(cygpath -w "$V68")" --v70-output "$(cygpath -w "$V70")" \
    --store "$(cygpath -w "$STORE")" --output-dir "$(cygpath -w "$V73")" \
    --signflip-samples 10000 --bootstrap-samples 5000
  echo

  echo "===== PROFIT FIRST ====="
  "$PY" - "$(cygpath -w "$V73/v73_report.json")" "$(cygpath -w "$V73/v73_candidate_inference.csv")" "$(cygpath -w "$V73/v73_2026_shadow.csv")" <<'PY'
import csv,json,sys
from pathlib import Path
report=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for row in sorted(report["profit_reporting"]["profit_table"],key=lambda x:(x["variant_id"],x["allocator"],x["policy_id"])):
    if row["variant_id"] in {"BROAD_PROVISIONAL","GAP18_CLEAN"}:
        print("PNL",row["variant_id"],row["allocator"],row["policy_id"],
              "return="+str(row["total_return"]),"benchmark="+str(row["benchmark_total_return"]),
              "alpha="+str(row["total_alpha_arithmetic"]),"cagr="+str(row["cagr"]),
              "mdd="+str(row["max_drawdown_daily"]))
with Path(sys.argv[2]).open("r",encoding="utf-8-sig",newline="") as f:
    for row in csv.DictReader(f):
        print("INFERENCE",row["variant_id"],row["allocator"],row["policy_id"],
              "mean_delta="+row["mean_monthly_return_delta"],"p="+row["signflip_two_sided_p"],
              "q="+row["bh_fdr_q"],"ci_low="+row["bootstrap_ci025"],
              "watch="+row["diagnostic_watchlist_gate_passed"])
with Path(sys.argv[3]).open("r",encoding="utf-8-sig",newline="") as f:
    for row in csv.DictReader(f):
        if row["variant_id"] in {"BROAD_PROVISIONAL","GAP18_CLEAN"}:
            print("Y2026",row["variant_id"],row["allocator"],row["policy_id"],
                  "return="+row["strategy_return"],"benchmark="+row["benchmark_return"],
                  "delta_vs_base="+row["policy_minus_base_2026_return"],
                  "april_delta="+row["april_2026_policy_minus_base"],"used_for_selection="+row["used_for_selection"])
print("WATCHLIST_COUNT="+str(report["diagnostic_watchlist_count"]))
print("BASELINE_RECONSTRUCTION="+json.dumps(report["baseline_reconstruction_audit"],sort_keys=True))
print("PROMOTION_AUTHORIZED="+str(report["promotion_authorized"]))
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
  echo "===== V73 COMPLETE ====="
  echo "UPLOAD_ZIP=$BUNDLE"
  echo "UPLOAD_ZIP_WINDOWS=$(cygpath -w "$BUNDLE")"
else
  echo "===== V73 FAILED ====="
  echo "UPLOAD_ZIP=$FAIL_BUNDLE"
fi
explorer.exe "$(cygpath -w "$ART")" >/dev/null 2>&1 || true
exit "$RC"
