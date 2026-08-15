#!/usr/bin/env bash
set -euo pipefail

BRANCH="agent/v80-forward-paper-tactical-actions"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
fail(){ echo "FAILED: $*" >&2; exit 2; }
[[ -n "$ROOT" ]] || fail "hay chay trong repository vn-quant-system"
cd "$ROOT"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "sai branch; can $BRANCH"
git diff --quiet || fail "tracked files da bi sua"
git diff --cached --quiet || fail "staging area co thay doi"

SYSTEM_ROOT="$PWD/vn_quant_local_system"
PY="$SYSTEM_ROOT/.venv/Scripts/python.exe"
STORE="$SYSTEM_ROOT/data/market/dnse_ohlcv.sqlite3"
V77_STATE="$PWD/du_lieu/v77-paper-oos-state"
V78_STATE="$PWD/du_lieu/v78-tactical-state"
V80_STATE="$PWD/du_lieu/v80-tactical-paper-state"
V78_LIVE="$SYSTEM_ROOT/data/v78-c3-tactical"
ART="$PWD/artifacts"
[[ -f "$PY" ]] || fail "khong tim thay canonical workstation Python"
[[ -f "$STORE" ]] || fail "khong tim thay market DB"
[[ -f "$V77_STATE/freeze_manifest.json" ]] || fail "V80 can V77 persistent freeze; KHONG tao lai/reset"
mkdir -p "$V78_STATE" "$V80_STATE" "$V78_LIVE" "$ART"

export PYTHONPATH="$PWD/src:$SYSTEM_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

ensure_dep(){
  local module="$1" spec="$2" expected="$3"
  if "$PY" - "$module" "$expected" <<'PY' >/dev/null 2>&1
import importlib,sys
m=importlib.import_module(sys.argv[1]); v=getattr(m,"__version__","")
raise SystemExit(0 if (not sys.argv[2] or v==sys.argv[2]) else 1)
PY
  then echo "DEPENDENCY_${module}=already_verified"
  else
    echo "DEPENDENCY_${module}=installing_${spec}"
    "$PY" -m pip install --disable-pip-version-check "$spec"
  fi
}
ensure_dep sklearn "scikit-learn==1.9.0" "1.9.0"

RUN_ID="$(date +%Y%m%d-%H%M%S)"
OUT="$ART/v80-tactical-forward-paper-$RUN_ID"
V78_OUT="$OUT/v78-current"
V80_OUT="$OUT/v80"
BUNDLE_DIR="$ART/v80-tactical-forward-paper-bundle-$RUN_ID"
BUNDLE="$ART/UPLOAD_THIS_v80_TACTICAL_FORWARD_PAPER-$RUN_ID.zip"
FAIL_BUNDLE="$ART/UPLOAD_THIS_v80_TACTICAL_FORWARD_PAPER_FAILURE-$RUN_ID.zip"
LOG="$ART/v80-tactical-forward-paper-$RUN_ID.log"
mkdir -p "$V78_OUT" "$V80_OUT" "$BUNDLE_DIR/output" "$BUNDLE_DIR/state_snapshot"

STORE_SHA_BEFORE="$(sha256sum "$STORE" | awk '{print $1}')"
"$PY" -m he_thong_dinh_luong.sqlite_market_fingerprint_v79 --store "$(cygpath -w "$STORE")" > "$OUT/store_logical_before.json"
STORE_LOGICAL_BEFORE="$("$PY" - "$OUT/store_logical_before.json" <<'PY'
import json,sys
print(json.load(open(sys.argv[1],encoding='utf-8'))['bars_sha256'])
PY
)"
V77_DIGEST_BEFORE="$(find "$V77_STATE" -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}')"

run_all() (
  set -euo pipefail
  echo "===== V80 FRESH TACTICAL FORWARD-PAPER REGISTRY ====="
  echo "BRANCH=$BRANCH"
  echo "HEAD=$(git rev-parse HEAD)"
  echo "CHAMPION_MODEL=C3_STABLE_3_PAST_IC_SHRUNK"
  echo "FROZEN_POLICIES=L15_SWAP25_WORST,L15_SWAP50_WORST,L15_CASH_ADD25_SLOT"
  echo "HISTORICAL_THRESHOLD_SEARCH_REOPENED=false"
  echo "INCUMBENT_HEALTH_AUTO_SELL=false"
  echo "EXECUTION_FLOOR=FIRST_MARKET_SESSION_ON_OR_AFTER_CAPTURE_VN_DATE_PLUS_1"
  echo "COUNTERFACTUAL_BASIS=CURRENT_CYCLE_NORMALIZED_1B_C3_EQUAL_BASE_DNSE"
  echo "MONTHLY_REBALANCE_PRECEDENCE=true"
  echo "V77_STATE_PRESERVED=$V77_STATE"
  echo "V78_STATE_REUSED=$V78_STATE"
  echo "V80_PERSISTENT_STATE=$V80_STATE"
  echo "PROMOTION_AUTHORIZED=false"
  echo "LIVE_ORDERS_ALLOWED=false"
  echo "STORE_PHYSICAL_SHA_BEFORE=$STORE_SHA_BEFORE"
  echo "STORE_LOGICAL_BARS_SHA_BEFORE=$STORE_LOGICAL_BEFORE"
  echo

  echo "===== COMPILE + REGRESSION ====="
  "$PY" -m py_compile \
    src/he_thong_dinh_luong/c3_tactical_terminal_v78.py \
    src/he_thong_dinh_luong/c3_tactical_terminal_v78_driver.py \
    src/he_thong_dinh_luong/tactical_capital_policy_v79.py \
    src/he_thong_dinh_luong/sqlite_market_fingerprint_v79.py \
    src/he_thong_dinh_luong/tactical_forward_paper_v80.py \
    src/he_thong_dinh_luong/tactical_forward_paper_v80_driver.py \
    tests/test_c3_tactical_terminal_v78.py \
    tests/test_c3_tactical_terminal_v78_driver.py \
    tests/test_tactical_capital_policy_v79.py \
    tests/test_sqlite_market_fingerprint_v79.py \
    tests/test_tactical_forward_paper_v80.py \
    tests/test_tactical_forward_paper_v80_driver.py
  "$PY" -m unittest \
    tests.test_c3_tactical_terminal_v78 \
    tests.test_c3_tactical_terminal_v78_driver \
    tests.test_tactical_capital_policy_v79 \
    tests.test_sqlite_market_fingerprint_v79 \
    tests.test_tactical_forward_paper_v80 \
    tests.test_tactical_forward_paper_v80_driver -v
  echo

  echo "===== REFRESH CURRENT V78 TACTICAL OBSERVATION WITHOUT WEB MUTATION ====="
  "$PY" -m he_thong_dinh_luong.c3_tactical_terminal_v78_driver \
    --store "$(cygpath -w "$STORE")" \
    --v77-state-dir "$(cygpath -w "$V77_STATE")" \
    --tactical-state-dir "$(cygpath -w "$V78_STATE")" \
    --output-dir "$(cygpath -w "$V78_OUT")" \
    --artifact-root "$(cygpath -w "$ART")"
  cp "$V78_OUT/v78_report.json" "$V78_LIVE/LATEST.json"
  cp "$V78_OUT/v78_report.json" "$V78_LIVE/v78_report.json"
  cp "$V78_OUT/v78_tactical_rows.csv" "$V78_LIVE/v78_tactical_rows.csv"
  cp "$V78_OUT/v78_incumbent_health.csv" "$V78_LIVE/v78_incumbent_health.csv"
  cp "$V78_OUT/v78_emerging_radar.csv" "$V78_LIVE/v78_emerging_radar.csv"
  cp "$V78_OUT/v78_recent_v72.csv" "$V78_LIVE/v78_recent_v72.csv"
  cp "$V78_OUT/v78_recent_ridge.csv" "$V78_LIVE/v78_recent_ridge.csv"
  echo

  echo "===== CAPTURE/ADVANCE V80 IMMUTABLE FORWARD PAPER ====="
  "$PY" -m he_thong_dinh_luong.tactical_forward_paper_v80_driver \
    --store "$(cygpath -w "$STORE")" \
    --v78-report "$(cygpath -w "$V78_OUT/v78_report.json")" \
    --v78-tactical-rows "$(cygpath -w "$V78_OUT/v78_tactical_rows.csv")" \
    --state-dir "$(cygpath -w "$V80_STATE")" \
    --output-dir "$(cygpath -w "$V80_OUT")"
  "$PY" - "$(cygpath -w "$V80_OUT/v80_report.json")" <<'PY'
import json,sys
r=json.load(open(sys.argv[1],encoding='utf-8-sig'))
for key in ('status','current_observation_id','current_capture_market_day','current_capture_wall_time_vn','current_execution_floor_date','current_exact_l15_active','current_leader','current_swap_out','observation_count','action_count','outcome_count','incumbent_health_auto_sell','promotion_authorized','live_orders_allowed'):
    print(key.upper()+'='+str(r[key]))
print('ACTION_STATUS_COUNTS='+json.dumps(r['action_status_counts'],sort_keys=True))
PY

  echo "===== INTEGRITY ====="
  "$PY" -m he_thong_dinh_luong.sqlite_market_fingerprint_v79 --store "$(cygpath -w "$STORE")" > "$OUT/store_logical_after.json"
  STORE_LOGICAL_AFTER="$("$PY" - "$OUT/store_logical_after.json" <<'PY'
import json,sys
print(json.load(open(sys.argv[1],encoding='utf-8'))['bars_sha256'])
PY
)"
  echo "STORE_LOGICAL_BARS_SHA_AFTER=$STORE_LOGICAL_AFTER"
  [[ "$STORE_LOGICAL_AFTER" == "$STORE_LOGICAL_BEFORE" ]] || fail "logical market bars changed during V80"
  V77_DIGEST_AFTER="$(find "$V77_STATE" -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}')"
  echo "V77_STATE_DIGEST_BEFORE=$V77_DIGEST_BEFORE"
  echo "V77_STATE_DIGEST_AFTER=$V77_DIGEST_AFTER"
  [[ "$V77_DIGEST_AFTER" == "$V77_DIGEST_BEFORE" ]] || fail "V77 persistent state changed during V80"
)

set +e
run_all 2>&1 | tee "$LOG"
RC=${PIPESTATUS[0]}
set -e

STORE_SHA_AFTER="$(sha256sum "$STORE" | awk '{print $1}')"
cp "$LOG" "$BUNDLE_DIR/run.log" || true
git branch --show-current > "$BUNDLE_DIR/git_branch.txt"
git rev-parse HEAD > "$BUNDLE_DIR/git_head.txt"
printf '%s\n' "$STORE_SHA_BEFORE" > "$BUNDLE_DIR/store_physical_sha256_before.txt"
printf '%s\n' "$STORE_SHA_AFTER" > "$BUNDLE_DIR/store_physical_sha256_after.txt"
cp "$OUT/store_logical_before.json" "$BUNDLE_DIR/store_logical_before.json" 2>/dev/null || true
cp "$OUT/store_logical_after.json" "$BUNDLE_DIR/store_logical_after.json" 2>/dev/null || true
[[ -d "$OUT" ]] && cp -R "$OUT"/. "$BUNDLE_DIR/output/" || true
[[ -f "$V80_STATE/registry.json" ]] && cp "$V80_STATE/registry.json" "$BUNDLE_DIR/state_snapshot/" || true
[[ -d "$V80_STATE/observations" ]] && cp -R "$V80_STATE/observations" "$BUNDLE_DIR/state_snapshot/" || true
[[ -f "$V77_STATE/freeze_manifest.json" ]] && cp "$V77_STATE/freeze_manifest.json" "$BUNDLE_DIR/state_snapshot/v77_freeze_manifest.json" || true
"$PY" - <<'PY' > "$BUNDLE_DIR/python_version.txt" 2>&1 || true
import sklearn,sys
print(sys.version.replace('\n',' ')); print(sys.executable); print('sklearn='+sklearn.__version__)
PY

TARGET="$BUNDLE"; [[ "$RC" -eq 0 ]] || TARGET="$FAIL_BUNDLE"
powershell.exe -NoProfile -Command "Compress-Archive -Path '$(cygpath -w "$BUNDLE_DIR")\\*' -DestinationPath '$(cygpath -w "$TARGET")' -Force" || true

echo
if [[ "$RC" -eq 0 ]]; then
  echo "===== V80 COMPLETE ====="
  echo "UPLOAD_ZIP=$BUNDLE"
  echo "UPLOAD_ZIP_WINDOWS=$(cygpath -w "$BUNDLE")"
  echo "UPLOAD_ZIP_SHA256=$(sha256sum "$BUNDLE" | awk '{print $1}')"
else
  echo "===== V80 FAILED ====="
  echo "UPLOAD_ZIP=$FAIL_BUNDLE"
fi
explorer.exe "$(cygpath -w "$ART")" >/dev/null 2>&1 || true
exit "$RC"
