#!/usr/bin/env bash
set -euo pipefail

BRANCH="agent/v75-consolidated-selection-optimization"
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
OUT="$ART/v75-consolidated-selection-$RUN_ID"
V68="$OUT/v68"; V70="$OUT/v70"; V75="$OUT/v75"
BUNDLE_DIR="$ART/v75-consolidated-selection-bundle-$RUN_ID"
BUNDLE="$ART/UPLOAD_THIS_v75_CONSOLIDATED_SELECTION-$RUN_ID.zip"
FAIL_BUNDLE="$ART/UPLOAD_THIS_v75_CONSOLIDATED_SELECTION_FAILURE-$RUN_ID.zip"
LOG="$ART/v75-consolidated-selection-$RUN_ID.log"
mkdir -p "$V68" "$V70" "$V75" "$BUNDLE_DIR"

run_all() (
  set -euo pipefail
  echo "===== V75 CONSOLIDATED STOCK-SELECTION OPTIMIZATION ====="
  echo "BRANCH=$BRANCH"
  echo "HEAD=$(git rev-parse HEAD)"
  echo "PYTHON_ENV=vn_quant_local_system/.venv"
  echo "CHAMPION_MODEL=C3_STABLE_3_PAST_IC_SHRUNK"
  echo "CHAMPION_REPLACED=false"
  echo "C3_TRAINING_LABEL=CLOSE_T_TO_CLOSE_T_PLUS_20_BENCHMARK_RELATIVE"
  echo "TRADABLE_EXECUTION=NEXT_SESSION_OPEN"
  echo "PRIMARY_SELECTION_END=2025-12-31"
  echo "YEAR_2026_USED_FOR_SELECTION=false"
  echo "RANKING_POLICIES=C3_BASELINE,C3_FAST_REL20_25,C3_FAST_ACCEL_25,C3_FRESH_BREAKOUT_25,C3_AUX_IC36_35"
  echo "AUX_FEATURES=REL20,REL10,REL5,MOMENTUM_ACCELERATION,BREAKOUT20,DISTANCE_MA20,VOLUME_CONFIRMATION,STABILITY"
  echo "MACRO_LANE=OPTIONAL_NONBLOCKING_NSO_CPI_IIP_PIT"
  echo "DEEP_BACKTEST_ENGINE=V70_REUSED"
  echo "ALLOCATORS=EQUAL,INVOL60"
  echo "COST_SCENARIOS=GROSS,BASE_DNSE,STRESS,SEVERE"
  echo "PROFIT_REPORT_REQUIRED=true"
  echo "STORE_MUTATION_ALLOWED=false"
  echo "PROMOTION_AUTHORIZED=false"
  echo

  echo "===== COMPILE + REGRESSION ====="
  "$PY" -m py_compile \
    src/he_thong_dinh_luong/c3_hose_native_v67.py \
    src/he_thong_dinh_luong/c3_hose_consolidated_v68_safe.py \
    src/he_thong_dinh_luong/deep_portfolio_backtest_v70.py \
    src/he_thong_dinh_luong/macro_pit_ablation_v74.py \
    src/he_thong_dinh_luong/c3_consolidated_selection_v75.py \
    tests/test_c3_consolidated_selection_v75.py
  "$PY" -m unittest tests.test_c3_consolidated_selection_v75 -v
  echo

  echo "===== PHASE 1 V68: FROZEN C3 + DATA SENSITIVITY ====="
  ARGS=(--store "$(cygpath -w "$STORE")" --output-dir "$(cygpath -w "$V68")" --bootstrap-samples 2000 \
        --search-root "$(cygpath -w "$PWD/vn_quant_local_system/data")")
  [[ -d "$PWD/vn_quant_local_system/validation" ]] && ARGS+=(--search-root "$(cygpath -w "$PWD/vn_quant_local_system/validation")")
  [[ -d "$PWD/vn_quant_local_system/outputs" ]] && ARGS+=(--search-root "$(cygpath -w "$PWD/vn_quant_local_system/outputs")")
  "$PY" -m he_thong_dinh_luong.c3_hose_consolidated_v68_safe "${ARGS[@]}"
  echo

  echo "===== PHASE 2 V70: FROZEN DEEP BASELINE ====="
  "$PY" -m he_thong_dinh_luong.deep_portfolio_backtest_v70 \
    --v68-output "$(cygpath -w "$V68")" --store "$(cygpath -w "$STORE")" \
    --output-dir "$(cygpath -w "$V70")" --initial-capital 1000000000
  echo

  echo "===== PHASE 3 V75: MULTI-LANE SELECTION + OPTIONAL MACRO + DEEP BACKTEST ====="
  "$PY" -m he_thong_dinh_luong.c3_consolidated_selection_v75 \
    --v68-output "$(cygpath -w "$V68")" --v70-output "$(cygpath -w "$V70")" \
    --store "$(cygpath -w "$STORE")" --output-dir "$(cygpath -w "$V75")" \
    --signflip-samples 10000 --bootstrap-samples 5000
  echo

  echo "===== PROFIT FIRST ====="
  "$PY" - "$(cygpath -w "$V75/v75_backtest_summary.csv")" "$(cygpath -w "$V75/v75_candidate_inference.csv")" "$(cygpath -w "$V75/v75_winner_capture_summary.csv")" "$(cygpath -w "$V75/v75_2026_shadow.csv")" "$(cygpath -w "$V75/v75_report.json")" <<'PY'
import csv,json,sys
from pathlib import Path
for path,label in ((sys.argv[1],"PNL"),(sys.argv[2],"INFERENCE"),(sys.argv[3],"CAPTURE"),(sys.argv[4],"Y2026")):
    with Path(path).open("r",encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f))
    for row in rows:
        if row.get("variant_id") not in {"BROAD_PROVISIONAL","GAP18_CLEAN"}: continue
        if label=="PNL" and row.get("cost_scenario")=="BASE_DNSE" and row.get("settlement_mode")=="IMMEDIATE" and float(row.get("initial_capital_vnd") or 0)==1_000_000_000.0:
            print(label,row["variant_id"],row["allocator"],row["policy_id"],"return="+row["total_return"],"benchmark="+row["benchmark_total_return"],"cagr="+row["cagr"],"mdd="+row["max_drawdown_daily"])
        elif label=="INFERENCE":
            print(label,row["variant_id"],row["allocator"],row["policy_id"],"delta="+row["mean_monthly_return_delta"],"p="+row["signflip_two_sided_p"],"q="+row.get("bh_fdr_q",""),"ci_low="+row["bootstrap_ci025"],"watch="+row.get("diagnostic_watchlist_gate_passed",""))
        elif label=="CAPTURE":
            print(label,row["variant_id"],row["policy_id"],"winner="+row["mean_winner_top10_capture_rate"],"capture_delta="+row["mean_capture_delta_vs_frozen"],"loser="+row["mean_loser_top10_contamination_rate"],"loser_delta="+row["mean_contamination_delta_vs_frozen"])
        elif label=="Y2026":
            print(label,row["variant_id"],row["allocator"],row["policy_id"],"return="+row["strategy_return"],"benchmark="+row["benchmark_return"],"delta="+row["policy_minus_frozen_2026_return"],"april_delta="+str(row.get("april_2026_policy_minus_frozen")),"used_for_selection="+row["used_for_selection"])
report=json.loads(Path(sys.argv[5]).read_text(encoding="utf-8"))
print("WATCHLIST_COUNT="+str(report["watchlist_candidate_count"]))
print("MACRO_STATUS="+json.dumps(report["macro_status"],sort_keys=True))
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
if [[ "$RC" -eq 0 ]]; then
  echo "===== V75 COMPLETE ====="
  echo "UPLOAD_ZIP=$BUNDLE"
  echo "UPLOAD_ZIP_WINDOWS=$(cygpath -w "$BUNDLE")"
else
  echo "===== V75 FAILED ====="
  echo "UPLOAD_ZIP=$FAIL_BUNDLE"
fi
explorer.exe "$(cygpath -w "$ART")" >/dev/null 2>&1 || true
exit "$RC"
