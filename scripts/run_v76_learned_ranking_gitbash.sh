#!/usr/bin/env bash
set -euo pipefail

BRANCH="agent/v76-learned-ranking-challenger-lab"
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
OUT="$ART/v76-learned-ranking-$RUN_ID"
V76="$OUT/v76"
FRESH_V68="$OUT/v68"
FRESH_V70="$OUT/v70"
V68=""
V70=""
REUSE_SOURCE=""
BUNDLE_DIR="$ART/v76-learned-ranking-bundle-$RUN_ID"
BUNDLE="$ART/UPLOAD_THIS_v76_LEARNED_RANKING-$RUN_ID.zip"
FAIL_BUNDLE="$ART/UPLOAD_THIS_v76_LEARNED_RANKING_FAILURE-$RUN_ID.zip"
LOG="$ART/v76-learned-ranking-$RUN_ID.log"
mkdir -p "$V76" "$BUNDLE_DIR/output/v76" "$BUNDLE_DIR/reference"

CURRENT_STORE_SHA="$(sha256sum "$STORE" | awk '{print $1}')"

find_reusable_reference(){
  shopt -s nullglob
  local dirs=("$ART"/v75-consolidated-selection-bundle-*)
  local i bdir name stamp candidate oldsha
  for ((i=${#dirs[@]}-1; i>=0; i--)); do
    bdir="${dirs[$i]}"
    [[ -d "$bdir" && -f "$bdir/store_sha256.txt" ]] || continue
    name="$(basename "$bdir")"
    stamp="${name#v75-consolidated-selection-bundle-}"
    candidate="$ART/v75-consolidated-selection-$stamp"
    [[ -f "$candidate/v68/v68_consolidated_report.json" ]] || continue
    [[ -f "$candidate/v70/v70_report.json" ]] || continue
    oldsha="$(awk 'NR==1{print $1}' "$bdir/store_sha256.txt")"
    [[ "$oldsha" == "$CURRENT_STORE_SHA" ]] || continue
    if "$PY" - "$candidate/v68/v68_consolidated_report.json" "$candidate/v70/v70_report.json" <<'PY' >/dev/null 2>&1
import json,sys
from pathlib import Path
r68=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
r70=json.loads(Path(sys.argv[2]).read_text(encoding="utf-8-sig"))
assert r68.get("status")=="SUCCESS"
assert r68.get("champion_model")=="C3_STABLE_3_PAST_IC_SHRUNK"
assert r70.get("status")=="SUCCESS"
assert r70.get("champion_model")=="C3_STABLE_3_PAST_IC_SHRUNK"
assert r70.get("deep_backtest_completed") is True
PY
    then
      V68="$candidate/v68"
      V70="$candidate/v70"
      REUSE_SOURCE="$candidate"
      return 0
    fi
  done
  return 1
}

run_all() (
  set -euo pipefail
  echo "===== V76 LEARNED CROSS-SECTIONAL RANKING CHALLENGER LAB ====="
  echo "BRANCH=$BRANCH"
  echo "HEAD=$(git rev-parse HEAD)"
  echo "PYTHON_ENV=vn_quant_local_system/.venv"
  echo "CHAMPION_MODEL=C3_STABLE_3_PAST_IC_SHRUNK"
  echo "CHAMPION_REPLACED=false"
  echo "C3_TRAINING_LABEL=CLOSE_T_TO_CLOSE_T_PLUS_20_BENCHMARK_RELATIVE"
  echo "TRADABLE_EXECUTION=NEXT_SESSION_OPEN"
  echo "MODEL_TRAINABLE_HISTORY_SEPARATE_FROM_PORTFOLIO_ELIGIBILITY=true"
  echo "WALK_FORWARD=EXPANDING_PURGED_COMPLETED_LABELS_WITH_PRIOR_3_MONTH_VALIDATION"
  echo "PRIMARY_SELECTION_END=2025-12-31"
  echo "YEAR_2026_USED_FOR_RESEARCH_SELECTION=false"
  echo "CHALLENGERS=V76_RIDGE_RANK,V76_RIDGE_CONTEXT,V76_HGB_CONTEXT,V76_LOGIT_BOTTOM20_SAFE"
  echo "FEATURES=C3_3_PLUS_REL5_REL10_REL20_ACCEL_BREAKOUT_MA20_MA50_DD20_DD60_VOLUME_STABILITY"
  echo "DEEP_BACKTEST_ENGINE=V70_REUSED"
  echo "ALLOCATORS=EQUAL,INVOL60"
  echo "COST_SCENARIOS=GROSS,BASE_DNSE,STRESS,SEVERE"
  echo "PROFIT_REPORT_REQUIRED=true"
  echo "STORE_MUTATION_ALLOWED=false"
  echo "PROMOTION_AUTHORIZED=false"
  echo

  echo "===== COMPILE + REGRESSION ====="
  "$PY" - <<'PY'
import sklearn,sys
print("SKLEARN_VERSION="+sklearn.__version__)
print("PYTHON="+sys.version.replace("\n"," "))
PY
  "$PY" -m py_compile \
    src/he_thong_dinh_luong/c3_hose_native_driver_v67.py \
    src/he_thong_dinh_luong/c3_hose_consolidated_v68_safe.py \
    src/he_thong_dinh_luong/deep_portfolio_backtest_v70.py \
    src/he_thong_dinh_luong/c3_consolidated_selection_v75.py \
    src/he_thong_dinh_luong/learned_ranking_challenger_v76.py \
    tests/test_learned_ranking_challenger_v76.py
  "$PY" -m unittest tests.test_learned_ranking_challenger_v76 -v
  echo

  if find_reusable_reference; then
    echo "===== REUSE VERIFIED V75 V68/V70 REFERENCE ====="
    echo "REFERENCE_REUSED=true"
    echo "REFERENCE_SOURCE=$REUSE_SOURCE"
    echo "REFERENCE_STORE_SHA=$CURRENT_STORE_SHA"
  else
    echo "===== NO SAFE CACHE: REBUILD V68 + V70 ====="
    echo "REFERENCE_REUSED=false"
    mkdir -p "$FRESH_V68" "$FRESH_V70"
    ARGS=(--store "$(cygpath -w "$STORE")" --output-dir "$(cygpath -w "$FRESH_V68")" --bootstrap-samples 2000 \
          --search-root "$(cygpath -w "$PWD/vn_quant_local_system/data")")
    [[ -d "$PWD/vn_quant_local_system/validation" ]] && ARGS+=(--search-root "$(cygpath -w "$PWD/vn_quant_local_system/validation")")
    [[ -d "$PWD/vn_quant_local_system/outputs" ]] && ARGS+=(--search-root "$(cygpath -w "$PWD/vn_quant_local_system/outputs")")
    "$PY" -m he_thong_dinh_luong.c3_hose_consolidated_v68_safe "${ARGS[@]}"
    "$PY" -m he_thong_dinh_luong.deep_portfolio_backtest_v70 \
      --v68-output "$(cygpath -w "$FRESH_V68")" --store "$(cygpath -w "$STORE")" \
      --output-dir "$(cygpath -w "$FRESH_V70")" --initial-capital 1000000000
    V68="$FRESH_V68"
    V70="$FRESH_V70"
  fi
  echo

  echo "===== V76: LEARNED RANKING + WINNER CAPTURE + DEEP BACKTEST ====="
  "$PY" -m he_thong_dinh_luong.learned_ranking_challenger_v76 \
    --v68-output "$(cygpath -w "$V68")" --v70-output "$(cygpath -w "$V70")" \
    --store "$(cygpath -w "$STORE")" --output-dir "$(cygpath -w "$V76")" \
    --signflip-samples 10000 --bootstrap-samples 5000
  echo

  echo "===== PROFIT FIRST ====="
  "$PY" - "$(cygpath -w "$V76/v76_backtest_summary.csv")" "$(cygpath -w "$V76/v76_candidate_inference.csv")" "$(cygpath -w "$V76/v76_winner_capture_summary.csv")" "$(cygpath -w "$V76/v76_rank_ic_summary.csv")" "$(cygpath -w "$V76/v76_2026_shadow.csv")" "$(cygpath -w "$V76/v76_report.json")" <<'PY'
import csv,json,sys
from pathlib import Path
files=sys.argv[1:6]
for path,label in zip(files,("PNL","INFERENCE","CAPTURE","RANK_IC","Y2026")):
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
        elif label=="RANK_IC":
            print(label,row["variant_id"],row["policy_id"],"pre2026="+row["pre2026_mean_rank_ic"],"positive="+row["pre2026_positive_ic_rate"],"y2026="+str(row.get("y2026_mean_rank_ic")))
        elif label=="Y2026":
            print(label,row["variant_id"],row["allocator"],row["policy_id"],"return="+row["strategy_return"],"benchmark="+row["benchmark_return"],"delta="+row["policy_minus_frozen_2026_return"],"april_delta="+str(row.get("april_2026_policy_minus_frozen")))
report=json.loads(Path(sys.argv[6]).read_text(encoding="utf-8"))
print("WATCHLIST_COUNT="+str(report["diagnostic_watchlist_count"]))
print("ROBUST_PROGRESSION_MODELS="+json.dumps(report["robust_progression_models"]))
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
import sklearn,sys
print(sys.version.replace("\n"," "))
print(sys.executable)
print("scikit-learn",sklearn.__version__)
PY
[[ -d "$V76" ]] && cp -R "$V76"/. "$BUNDLE_DIR/output/v76/" || true
if [[ -n "${V68:-}" && -f "$V68/v68_consolidated_report.json" ]]; then
  cp "$V68/v68_consolidated_report.json" "$BUNDLE_DIR/reference/" || true
  cp "$V68/v68_variant_summary.csv" "$BUNDLE_DIR/reference/" || true
  cp "$V68/v68_basis_audit.json" "$BUNDLE_DIR/reference/" || true
fi
if [[ -n "${V70:-}" && -f "$V70/v70_report.json" ]]; then
  cp "$V70/v70_report.json" "$BUNDLE_DIR/reference/" || true
  cp "$V70/v70_backtest_summary.csv" "$BUNDLE_DIR/reference/" || true
fi
printf '%s\n' "${REUSE_SOURCE:-FRESH_REBUILD}" > "$BUNDLE_DIR/reference_source.txt"

TARGET="$BUNDLE"; [[ "$RC" -eq 0 ]] || TARGET="$FAIL_BUNDLE"
powershell.exe -NoProfile -Command "Compress-Archive -Path '$(cygpath -w "$BUNDLE_DIR")\\*' -DestinationPath '$(cygpath -w "$TARGET")' -Force" || true
if [[ "$RC" -eq 0 ]]; then
  echo "===== V76 COMPLETE ====="
  echo "UPLOAD_ZIP=$BUNDLE"
  echo "UPLOAD_ZIP_WINDOWS=$(cygpath -w "$BUNDLE")"
else
  echo "===== V76 FAILED ====="
  echo "UPLOAD_ZIP=$FAIL_BUNDLE"
fi
explorer.exe "$(cygpath -w "$ART")" >/dev/null 2>&1 || true
exit "$RC"