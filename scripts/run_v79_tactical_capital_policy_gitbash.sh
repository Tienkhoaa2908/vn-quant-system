#!/usr/bin/env bash
set -euo pipefail

BRANCH="agent/v79-c3-tactical-capital-policy"
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
OUT="$ART/v79-tactical-capital-policy-$RUN_ID"
V68="$OUT/v68"; V70="$OUT/v70"; V79="$OUT/v79"
BUNDLE_DIR="$ART/v79-tactical-capital-policy-bundle-$RUN_ID"
BUNDLE="$ART/UPLOAD_THIS_v79_TACTICAL_CAPITAL_POLICY-$RUN_ID.zip"
FAIL_BUNDLE="$ART/UPLOAD_THIS_v79_TACTICAL_CAPITAL_POLICY_FAILURE-$RUN_ID.zip"
LOG="$ART/v79-tactical-capital-policy-$RUN_ID.log"
mkdir -p "$V68" "$V70" "$V79" "$BUNDLE_DIR"
STORE_SHA_BEFORE="$(sha256sum "$STORE" | awk '{print $1}')"
STORE_LOGICAL_BEFORE="$("$PY" -m he_thong_dinh_luong.sqlite_market_fingerprint_v79 --store "$(cygpath -w "$STORE")")"
printf '%s\n' "$STORE_LOGICAL_BEFORE" > "$BUNDLE_DIR/store_logical_bars_before.json"

run_all() (
  set -euo pipefail
  echo "===== V79 ONE-SHOT C3 TACTICAL CAPITAL POLICY RESEARCH ====="
  echo "BRANCH=$BRANCH"
  echo "HEAD=$(git rev-parse HEAD)"
  echo "PYTHON_ENV=vn_quant_local_system/.venv"
  echo "CHAMPION_MODEL=C3_STABLE_3_PAST_IC_SHRUNK"
  echo "CHAMPION_REPLACED=false"
  echo "HISTORICAL_MODEL_SEARCH_REOPENED=false"
  echo "POLICY_MATRIX=BASELINE,V72_ANCHORS,INCUMBENT_TRIM25,INCUMBENT_TRIM50,SEVERE_EXIT100,L15_SWAP25,L15_CASH_ADD25_SLOT,ROTATE25,ROTATE50,COMBINED50"
  echo "INCUMBENT_DRAG=NEXT_SESSION_OPEN_AFTER_MONTHLY_SIGNAL_TO_WEEKLY_EVALUATION_CLOSE_GROSS"
  echo "INCUMBENT_PERSISTENCE_REQUIRED=true"
  echo "EXACT_L15_REUSED=true"
  echo "WEEKLY_SIGNAL_EXECUTION=AFTER_CLOSE_TO_NEXT_MARKET_OPEN"
  echo "MONTHLY_REBALANCE_PRECEDENCE=true"
  echo "PRIMARY_SELECTION_END=2025-12-31"
  echo "YEAR_2026_USED_FOR_SELECTION=false"
  echo "DEEP_BACKTEST_ENGINE=V70_EXECUTION_PRIMITIVES"
  echo "ALLOCATORS=EQUAL,INVOL60"
  echo "COST_SCENARIOS=GROSS,BASE_DNSE,STRESS,SEVERE"
  echo "SETTLEMENT_SENSITIVITY=T2_NO_ADVANCE_WITH_CATCHUP"
  echo "CAPITAL_SENSITIVITY=100M,1B,10B_VND"
  echo "LOT_SIZE=100"
  echo "SINGLE_NAME_CAP=0.15"
  echo "CASH_ADD_USES_ONLY_AVAILABLE_SIMULATED_CASH=true"
  echo "PROFIT_REPORT_REQUIRED=true"
  echo "PROMOTION_AUTHORIZED=false"
  echo "AUTOMATIC_LIVE_ORDERS_ALLOWED=false"
  echo "STORE_PHYSICAL_SHA_BEFORE=$STORE_SHA_BEFORE"
  echo "STORE_LOGICAL_BARS_BEFORE=$STORE_LOGICAL_BEFORE"
  echo

  echo "===== COMPILE + REGRESSION ====="
  "$PY" -m py_compile \
    src/he_thong_dinh_luong/c3_hose_native_v67.py \
    src/he_thong_dinh_luong/c3_hose_consolidated_v68_safe.py \
    src/he_thong_dinh_luong/deep_portfolio_backtest_v70.py \
    src/he_thong_dinh_luong/weekly_overlay_backtest_v72.py \
    src/he_thong_dinh_luong/tactical_capital_policy_v79.py \
    src/he_thong_dinh_luong/sqlite_market_fingerprint_v79.py \
    tests/test_weekly_overlay_backtest_v72.py \
    tests/test_tactical_capital_policy_v79.py \
    tests/test_sqlite_market_fingerprint_v79.py
  "$PY" -m unittest \
    tests.test_weekly_overlay_backtest_v72 \
    tests.test_tactical_capital_policy_v79 \
    tests.test_sqlite_market_fingerprint_v79 -v
  echo

  echo "===== PHASE 1: REBUILD V68 CAUSAL WEEKLY SIGNAL STATES ====="
  ARGS=(--store "$(cygpath -w "$STORE")" --output-dir "$(cygpath -w "$V68")" --bootstrap-samples 2000 \
        --search-root "$(cygpath -w "$PWD/vn_quant_local_system/data")")
  [[ -d "$PWD/vn_quant_local_system/validation" ]] && ARGS+=(--search-root "$(cygpath -w "$PWD/vn_quant_local_system/validation")")
  [[ -d "$PWD/vn_quant_local_system/outputs" ]] && ARGS+=(--search-root "$(cygpath -w "$PWD/vn_quant_local_system/outputs")")
  "$PY" -m he_thong_dinh_luong.c3_hose_consolidated_v68_safe "${ARGS[@]}"
  echo

  echo "===== PHASE 2: RECONSTRUCT V70 FROZEN-C3 BASELINE ====="
  "$PY" -m he_thong_dinh_luong.deep_portfolio_backtest_v70 \
    --v68-output "$(cygpath -w "$V68")" --store "$(cygpath -w "$STORE")" \
    --output-dir "$(cygpath -w "$V70")" --initial-capital 1000000000
  echo

  echo "===== PHASE 3: RUN ALL V79 CAPITAL-ACTION DIRECTIONS ====="
  "$PY" -m he_thong_dinh_luong.tactical_capital_policy_v79 \
    --v68-output "$(cygpath -w "$V68")" --v70-output "$(cygpath -w "$V70")" \
    --store "$(cygpath -w "$STORE")" --output-dir "$(cygpath -w "$V79")" \
    --initial-capital 1000000000 --signflip-samples 10000 --bootstrap-samples 5000
  echo

  echo "===== PROFIT + ABLATION + INFERENCE FIRST ====="
  "$PY" - "$(cygpath -w "$V79/v79_report.json")" "$(cygpath -w "$V79/v79_policy_inference.csv")" \
    "$(cygpath -w "$V79/v79_family_ablation.csv")" "$(cygpath -w "$V79/v79_2026_shadow.csv")" <<'PY'
import csv,json,sys
from pathlib import Path
report=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
for row in sorted(report["profit_reporting"]["base_cost_profit_table"],key=lambda x:x["policy_id"]):
    if row["variant_id"]=="GAP18_CLEAN" and row["allocator"]=="EQUAL":
        print("PNL",row["policy_id"],"family="+str(row.get("policy_family")),
              "return="+str(row["total_return"]),"benchmark="+str(row["benchmark_total_return"]),
              "alpha="+str(row["total_alpha_arithmetic"]),"cagr="+str(row["cagr"]),
              "mdd="+str(row["max_drawdown_daily"]),"actions="+str(row["overlay_action_count"]),
              "cost_vnd="+str(row["modeled_cost_and_slippage_vnd"]))
with Path(sys.argv[2]).open("r",encoding="utf-8-sig",newline="") as f:
    rows=list(csv.DictReader(f))
for row in rows:
    if row["variant_id"]=="GAP18_CLEAN" and row["allocator"]=="EQUAL":
        print("INFERENCE",row["policy_id"],"family="+row["policy_family"],
              "mean_delta="+row["mean_monthly_return_delta"],"p="+row["signflip_two_sided_p"],
              "q="+row["bh_fdr_q"],"ci_low="+row["bootstrap_ci025"],
              "cagr_delta="+row["pre2026_cagr_delta"],"mdd_improve="+row["pre2026_mdd_improvement"],
              "watch="+row["diagnostic_watchlist_gate_passed"])
with Path(sys.argv[3]).open("r",encoding="utf-8-sig",newline="") as f:
    family=list(csv.DictReader(f))
for row in family:
    if row["variant_id"]=="GAP18_CLEAN" and row["allocator"]=="EQUAL":
        print("FAMILY",row["policy_family"],"best="+row["best_policy_id"],
              "mean_delta="+row["best_mean_monthly_return_delta"],
              "cagr_delta="+row["best_pre2026_cagr_delta"],
              "mdd_improve="+row["best_pre2026_mdd_improvement"],
              "watch="+row["any_watchlist_gate_passed"])
with Path(sys.argv[4]).open("r",encoding="utf-8-sig",newline="") as f:
    shadow=list(csv.DictReader(f))
for row in shadow:
    if row["variant_id"]=="GAP18_CLEAN" and row["allocator"]=="EQUAL":
        print("Y2026",row["policy_id"],"return="+row["strategy_return"],
              "benchmark="+row["benchmark_return"],"delta_vs_base="+row["policy_minus_base_2026_return"],
              "used_for_selection="+row["used_for_selection"])
print("POLICY_COUNT="+str(report["policy_count"]))
print("WATCHLIST_COUNT="+str(report["diagnostic_watchlist_count"]))
print("BASELINE_RECONSTRUCTION="+json.dumps(report["baseline_reconstruction_audit"],sort_keys=True))
print("YEAR_2026_USED_FOR_SELECTION="+str(report["year_2026_used_for_candidate_selection"]))
print("HISTORICAL_MODEL_SEARCH_REOPENED="+str(report["historical_model_search_reopened"]))
print("PROMOTION_AUTHORIZED="+str(report["promotion_authorized"]))
print("AUTOMATIC_LIVE_ORDERS_ALLOWED="+str(report["automatic_live_orders_allowed"]))
PY

  STORE_SHA_AFTER="$(sha256sum "$STORE" | awk '{print $1}')"
  STORE_LOGICAL_AFTER="$("$PY" -m he_thong_dinh_luong.sqlite_market_fingerprint_v79 --store "$(cygpath -w "$STORE")")"
  printf '%s\n' "$STORE_LOGICAL_AFTER" > "$BUNDLE_DIR/store_logical_bars_after.json"
  echo "STORE_PHYSICAL_SHA_AFTER=$STORE_SHA_AFTER"
  echo "STORE_LOGICAL_BARS_AFTER=$STORE_LOGICAL_AFTER"
  [[ "$STORE_LOGICAL_AFTER" == "$STORE_LOGICAL_BEFORE" ]] || fail "logical market bars changed during research run"
  if [[ "$STORE_SHA_AFTER" != "$STORE_SHA_BEFORE" ]]; then
    echo "STORE_PHYSICAL_SHA_CHANGED_LOGICAL_BARS_STABLE=true"
    echo "STORE_PHYSICAL_CHANGE_INTERPRETATION=SQLITE_WAL_CHECKPOINT_OR_PAGE_LAYOUT_CHANGE_NOT_LOGICAL_BARS_MUTATION"
  else
    echo "STORE_PHYSICAL_SHA_CHANGED_LOGICAL_BARS_STABLE=false"
  fi
)

set +e
run_all 2>&1 | tee "$LOG"
RC=${PIPESTATUS[0]}
set -e

STORE_SHA_AFTER="$(sha256sum "$STORE" | awk '{print $1}')"
STORE_LOGICAL_AFTER="$("$PY" -m he_thong_dinh_luong.sqlite_market_fingerprint_v79 --store "$(cygpath -w "$STORE")" 2>/dev/null || true)"
cp "$LOG" "$BUNDLE_DIR/run.log" || true
git branch --show-current > "$BUNDLE_DIR/git_branch.txt"
git rev-parse HEAD > "$BUNDLE_DIR/git_head.txt"
printf '%s\n' "$STORE_SHA_BEFORE" > "$BUNDLE_DIR/store_sha256_before.txt"
printf '%s\n' "$STORE_SHA_AFTER" > "$BUNDLE_DIR/store_sha256_after.txt"
printf '%s\n' "$STORE_LOGICAL_BEFORE" > "$BUNDLE_DIR/store_logical_bars_before.json"
printf '%s\n' "$STORE_LOGICAL_AFTER" > "$BUNDLE_DIR/store_logical_bars_after.json"
"$PY" - <<'PY' > "$BUNDLE_DIR/python_version.txt" 2>&1 || true
import sys
print(sys.version.replace("\n"," "))
print(sys.executable)
try:
 import sklearn
 print("sklearn="+sklearn.__version__)
except Exception as exc:
 print("sklearn_unavailable="+repr(exc))
PY
[[ -d "$OUT" ]] && cp -R "$OUT" "$BUNDLE_DIR/output" || true
TARGET="$BUNDLE"; [[ "$RC" -eq 0 ]] || TARGET="$FAIL_BUNDLE"
powershell.exe -NoProfile -Command "Compress-Archive -Path '$(cygpath -w "$BUNDLE_DIR")\\*' -DestinationPath '$(cygpath -w "$TARGET")' -Force" || true

echo
if [[ "$RC" -eq 0 ]]; then
  echo "===== V79 COMPLETE ====="
  echo "UPLOAD_ZIP=$BUNDLE"
  echo "UPLOAD_ZIP_WINDOWS=$(cygpath -w "$BUNDLE")"
  echo "UPLOAD_ZIP_SHA256=$(sha256sum "$BUNDLE" | awk '{print $1}')"
else
  echo "===== V79 FAILED ====="
  echo "UPLOAD_ZIP=$FAIL_BUNDLE"
fi
explorer.exe "$(cygpath -w "$ART")" >/dev/null 2>&1 || true
exit "$RC"
