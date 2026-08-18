#!/usr/bin/env bash
set -euo pipefail

BRANCH="agent/v81-frozen-tactical-historical-audit"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
fail(){ echo "FAILED: $*" >&2; exit 2; }
[[ -n "$ROOT" ]] || fail "hay chay trong repository vn-quant-system"
cd "$ROOT"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "sai branch; can $BRANCH"
git diff --quiet || fail "tracked files da bi sua"
git diff --cached --quiet || fail "staging area co thay doi"

PY="$ROOT/vn_quant_local_system/.venv/Scripts/python.exe"
STORE="$ROOT/vn_quant_local_system/data/market/dnse_ohlcv.sqlite3"
V77_STATE="$ROOT/du_lieu/v77-paper-oos-state"
V80_STATE="$ROOT/du_lieu/v80-tactical-paper-state"
[[ -f "$PY" ]] || fail "khong tim thay canonical workstation Python"
[[ -f "$STORE" ]] || fail "khong tim thay market DB"
[[ -f "$V77_STATE/freeze_manifest.json" ]] || fail "khong tim thay V77 persistent state"
[[ -f "$V80_STATE/registry.json" ]] || fail "khong tim thay V80 persistent registry"
export PYTHONPATH="$(cygpath -w "$ROOT/src");$(cygpath -w "$ROOT/vn_quant_local_system/src")"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

RUN_ID="$(date +%Y%m%d-%H%M%S)"
ART="$ROOT/artifacts"
OUT="$ART/v81-frozen-tactical-historical-audit-$RUN_ID"
V68="$OUT/v68"; V70="$OUT/v70"; V81="$OUT/v81"
BUNDLE_DIR="$ART/v81-frozen-tactical-historical-audit-bundle-$RUN_ID"
BUNDLE="$ART/UPLOAD_THIS_v81_FROZEN_TACTICAL_HISTORICAL_AUDIT-$RUN_ID.zip"
FAIL_BUNDLE="$ART/UPLOAD_THIS_v81_FROZEN_TACTICAL_HISTORICAL_AUDIT_FAILURE-$RUN_ID.zip"
LOG="$ART/v81-frozen-tactical-historical-audit-$RUN_ID.log"
mkdir -p "$V68" "$V70" "$V81" "$BUNDLE_DIR"

hash_tree(){
  local dir="$1"
  find "$dir" -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}'
}
STORE_SHA_BEFORE="$(sha256sum "$STORE" | awk '{print $1}')"
STORE_LOGICAL_BEFORE="$("$PY" -m he_thong_dinh_luong.sqlite_market_fingerprint_v79 --store "$(cygpath -w "$STORE")")"
V77_DIGEST_BEFORE="$(hash_tree "$V77_STATE")"
V80_DIGEST_BEFORE="$(hash_tree "$V80_STATE")"
printf '%s\n' "$STORE_LOGICAL_BEFORE" > "$BUNDLE_DIR/store_logical_bars_before.json"
printf '%s\n' "$V77_DIGEST_BEFORE" > "$BUNDLE_DIR/v77_state_digest_before.txt"
printf '%s\n' "$V80_DIGEST_BEFORE" > "$BUNDLE_DIR/v80_state_digest_before.txt"

run_all() (
  set -euo pipefail
  echo "===== V81 FROZEN TACTICAL HISTORICAL AUDIT ====="
  echo "BRANCH=$BRANCH"
  echo "HEAD=$(git rev-parse HEAD)"
  echo "CHAMPION_MODEL=C3_STABLE_3_PAST_IC_SHRUNK"
  echo "FROZEN_POLICIES=NO_OVERLAY,L15_SWAP25_WORST,L15_SWAP50_WORST,L15_CASH_ADD25_SLOT"
  echo "EXACT_L15_REUSED_FROM_V72_V79=true"
  echo "HISTORICAL_THRESHOLD_SEARCH_REOPENED=false"
  echo "HISTORICAL_MODEL_SEARCH_REOPENED=false"
  echo "POST_SELECTION_DESCRIPTIVE_AUDIT=true"
  echo "SELECTION_AUTHORIZED_FROM_V81=false"
  echo "YEAR_2026_USED_TO_TUNE=false"
  echo "ALLOCATORS=EQUAL,INVOL60"
  echo "COST_SCENARIOS=GROSS,BASE_DNSE,STRESS,SEVERE"
  echo "SETTLEMENT_SENSITIVITY=T2_NO_ADVANCE"
  echo "CAPITAL_SENSITIVITY=100M,1B,10B_VND"
  echo "EVENT_ANALYSIS=FREQUENCY,REGRET,H5,H10,H20,MONTHLY_BOUNDARY,REGIME,CONCENTRATION"
  echo "FORWARD_STATE_MUTATION_ALLOWED=false"
  echo "PROMOTION_AUTHORIZED=false"
  echo "LIVE_ORDERS_ALLOWED=false"
  echo "STORE_PHYSICAL_SHA_BEFORE=$STORE_SHA_BEFORE"
  echo "STORE_LOGICAL_BARS_BEFORE=$STORE_LOGICAL_BEFORE"
  echo "V77_STATE_DIGEST_BEFORE=$V77_DIGEST_BEFORE"
  echo "V80_STATE_DIGEST_BEFORE=$V80_DIGEST_BEFORE"
  echo

  echo "===== COMPILE + REGRESSION ====="
  "$PY" -m py_compile \
    src/he_thong_dinh_luong/c3_hose_native_v67.py \
    src/he_thong_dinh_luong/c3_hose_consolidated_v68_safe.py \
    src/he_thong_dinh_luong/deep_portfolio_backtest_v70.py \
    src/he_thong_dinh_luong/weekly_overlay_backtest_v72.py \
    src/he_thong_dinh_luong/tactical_capital_policy_v79.py \
    src/he_thong_dinh_luong/frozen_tactical_historical_audit_v81.py \
    src/he_thong_dinh_luong/sqlite_market_fingerprint_v79.py \
    tests/test_weekly_overlay_backtest_v72.py \
    tests/test_tactical_capital_policy_v79.py \
    tests/test_frozen_tactical_historical_audit_v81.py \
    tests/test_sqlite_market_fingerprint_v79.py
  "$PY" -m unittest \
    tests.test_weekly_overlay_backtest_v72 \
    tests.test_tactical_capital_policy_v79 \
    tests.test_frozen_tactical_historical_audit_v81 \
    tests.test_sqlite_market_fingerprint_v79 -v
  echo

  echo "===== PHASE 1: REBUILD V68 CAUSAL SIGNAL STATES ====="
  ARGS=(--store "$(cygpath -w "$STORE")" --output-dir "$(cygpath -w "$V68")" --bootstrap-samples 2000 \
        --search-root "$(cygpath -w "$ROOT/vn_quant_local_system/data")")
  [[ -d "$ROOT/vn_quant_local_system/validation" ]] && ARGS+=(--search-root "$(cygpath -w "$ROOT/vn_quant_local_system/validation")")
  [[ -d "$ROOT/vn_quant_local_system/outputs" ]] && ARGS+=(--search-root "$(cygpath -w "$ROOT/vn_quant_local_system/outputs")")
  "$PY" -m he_thong_dinh_luong.c3_hose_consolidated_v68_safe "${ARGS[@]}"
  echo

  echo "===== PHASE 2: RECONSTRUCT V70 FROZEN C3 ====="
  "$PY" -m he_thong_dinh_luong.deep_portfolio_backtest_v70 \
    --v68-output "$(cygpath -w "$V68")" --store "$(cygpath -w "$STORE")" \
    --output-dir "$(cygpath -w "$V70")" --initial-capital 1000000000
  echo

  echo "===== PHASE 3: V81 FROZEN POLICY HISTORICAL REPLAY ====="
  "$PY" -m he_thong_dinh_luong.frozen_tactical_historical_audit_v81 \
    --v68-output "$(cygpath -w "$V68")" --v70-output "$(cygpath -w "$V70")" \
    --store "$(cygpath -w "$STORE")" --output-dir "$(cygpath -w "$V81")" --initial-capital 1000000000
  echo

  echo "===== PRIMARY AUDIT TABLES ====="
  "$PY" - "$(cygpath -w "$V81/v81_report.json")" \
    "$(cygpath -w "$V81/v81_signal_frequency.csv")" \
    "$(cygpath -w "$V81/v81_horizon_summary.csv")" \
    "$(cygpath -w "$V81/v81_portfolio_delta_diagnostics.csv")" \
    "$(cygpath -w "$V81/v81_cost_robustness.csv")" \
    "$(cygpath -w "$V81/v81_capital_robustness.csv")" <<'PY'
import csv,json,sys
from pathlib import Path
r=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
print('STATUS='+str(r['status']))
print('FROZEN_POLICIES='+','.join(r['frozen_policy_ids']))
print('SIGNAL_EVENT_COUNT='+str(r['signal_event_count']))
print('EXECUTED_ACTION_COUNT='+str(r['executed_action_count']))
print('BASELINE_AUDIT='+json.dumps(r['baseline_reconstruction_audit'],sort_keys=True))
print('THRESHOLD_SEARCH_REOPENED='+str(r['historical_threshold_search_reopened']))
print('SELECTION_AUTHORIZED_FROM_V81='+str(r['selection_authorized_from_v81']))

def rows(path):
    with Path(path).open('r',encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
for row in rows(sys.argv[2]):
    if row['variant_id']=='GAP18_CLEAN' and row['scope'] in {'ALL','PRE2026','Y2026'}:
        print('FREQ',row)
for row in rows(sys.argv[3]):
    if row['variant_id']=='GAP18_CLEAN' and row['allocator']=='EQUAL' and row['horizon'] in {'H5','H10','H20','MONTHLY_REBALANCE'}:
        print('HORIZON',row)
for row in rows(sys.argv[4]):
    if row['variant_id']=='GAP18_CLEAN' and row['allocator']=='EQUAL':
        print('DELTA',row)
for row in rows(sys.argv[5]):
    if row['variant_id']=='GAP18_CLEAN' and row['allocator']=='EQUAL':
        print('COST',row)
for row in rows(sys.argv[6]):
    if row['variant_id']=='GAP18_CLEAN' and row['allocator']=='EQUAL':
        print('CAPACITY',row)
PY

  echo "===== INTEGRITY ====="
  STORE_SHA_AFTER="$(sha256sum "$STORE" | awk '{print $1}')"
  STORE_LOGICAL_AFTER="$("$PY" -m he_thong_dinh_luong.sqlite_market_fingerprint_v79 --store "$(cygpath -w "$STORE")")"
  V77_DIGEST_AFTER="$(hash_tree "$V77_STATE")"
  V80_DIGEST_AFTER="$(hash_tree "$V80_STATE")"
  echo "STORE_PHYSICAL_SHA_AFTER=$STORE_SHA_AFTER"
  echo "STORE_LOGICAL_BARS_AFTER=$STORE_LOGICAL_AFTER"
  echo "V77_STATE_DIGEST_AFTER=$V77_DIGEST_AFTER"
  echo "V80_STATE_DIGEST_AFTER=$V80_DIGEST_AFTER"
  [[ "$STORE_LOGICAL_AFTER" == "$STORE_LOGICAL_BEFORE" ]] || fail "logical market bars changed during V81"
  [[ "$V77_DIGEST_AFTER" == "$V77_DIGEST_BEFORE" ]] || fail "V77 persistent state changed during V81"
  [[ "$V80_DIGEST_AFTER" == "$V80_DIGEST_BEFORE" ]] || fail "V80 persistent state changed during V81"
)

set +e
run_all 2>&1 | tee "$LOG"
RC=${PIPESTATUS[0]}
set -e

STORE_SHA_AFTER="$(sha256sum "$STORE" | awk '{print $1}')"
STORE_LOGICAL_AFTER="$("$PY" -m he_thong_dinh_luong.sqlite_market_fingerprint_v79 --store "$(cygpath -w "$STORE")" 2>/dev/null || true)"
V77_DIGEST_AFTER="$(hash_tree "$V77_STATE" 2>/dev/null || true)"
V80_DIGEST_AFTER="$(hash_tree "$V80_STATE" 2>/dev/null || true)"
cp "$LOG" "$BUNDLE_DIR/run.log" || true
git branch --show-current > "$BUNDLE_DIR/git_branch.txt"
git rev-parse HEAD > "$BUNDLE_DIR/git_head.txt"
printf '%s\n' "$STORE_SHA_BEFORE" > "$BUNDLE_DIR/store_physical_sha256_before.txt"
printf '%s\n' "$STORE_SHA_AFTER" > "$BUNDLE_DIR/store_physical_sha256_after.txt"
printf '%s\n' "$STORE_LOGICAL_BEFORE" > "$BUNDLE_DIR/store_logical_bars_before.json"
printf '%s\n' "$STORE_LOGICAL_AFTER" > "$BUNDLE_DIR/store_logical_bars_after.json"
printf '%s\n' "$V77_DIGEST_BEFORE" > "$BUNDLE_DIR/v77_state_digest_before.txt"
printf '%s\n' "$V77_DIGEST_AFTER" > "$BUNDLE_DIR/v77_state_digest_after.txt"
printf '%s\n' "$V80_DIGEST_BEFORE" > "$BUNDLE_DIR/v80_state_digest_before.txt"
printf '%s\n' "$V80_DIGEST_AFTER" > "$BUNDLE_DIR/v80_state_digest_after.txt"
"$PY" - <<'PY' > "$BUNDLE_DIR/python_version.txt" 2>&1 || true
import sklearn,sys
print(sys.version.replace('\n',' ')); print(sys.executable); print('sklearn='+sklearn.__version__)
PY
[[ -d "$OUT" ]] && cp -R "$OUT" "$BUNDLE_DIR/output" || true
TARGET="$BUNDLE"; [[ "$RC" -eq 0 ]] || TARGET="$FAIL_BUNDLE"
powershell.exe -NoProfile -Command "Compress-Archive -Path '$(cygpath -w "$BUNDLE_DIR")\\*' -DestinationPath '$(cygpath -w "$TARGET")' -Force" || true

echo
if [[ "$RC" -eq 0 ]]; then
  echo "===== V81 COMPLETE ====="
  echo "UPLOAD_ZIP=$BUNDLE"
  echo "UPLOAD_ZIP_WINDOWS=$(cygpath -w "$BUNDLE")"
  echo "UPLOAD_ZIP_SHA256=$(sha256sum "$BUNDLE" | awk '{print $1}')"
else
  echo "===== V81 FAILED ====="
  echo "UPLOAD_ZIP=$FAIL_BUNDLE"
fi
explorer.exe "$(cygpath -w "$ART")" >/dev/null 2>&1 || true
exit "$RC"
