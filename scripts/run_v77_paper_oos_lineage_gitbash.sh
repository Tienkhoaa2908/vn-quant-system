#!/usr/bin/env bash
set -euo pipefail

BRANCH="agent/v77-paper-oos-data-lineage"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
fail(){ echo "FAILED: $*" >&2; exit 2; }
[[ -n "$ROOT" ]] || fail "hay chay trong repository vn-quant-system"
cd "$ROOT"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "sai branch; can $BRANCH"
git diff --quiet || fail "tracked files da bi sua"
git diff --cached --quiet || fail "staging area co thay doi"

PY="$PWD/vn_quant_local_system/.venv/Scripts/python.exe"
STORE="$PWD/vn_quant_local_system/data/market/dnse_ohlcv.sqlite3"
STATE="$PWD/du_lieu/v77-paper-oos-state"
[[ -f "$PY" ]] || fail "khong tim thay canonical workstation Python"
[[ -f "$STORE" ]] || fail "khong tim thay market DB"
mkdir -p "$STATE"

export PYTHONPATH="$PWD/src:$PWD/vn_quant_local_system/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

ensure_sklearn(){
  if "$PY" - <<'PY' >/dev/null 2>&1
import sklearn
raise SystemExit(0 if sklearn.__version__ == "1.9.0" else 1)
PY
  then
    echo "SKLEARN_BOOTSTRAP=already_verified"
  else
    echo "SKLEARN_BOOTSTRAP=installing_scikit_learn_1_9_0_into_canonical_venv"
    "$PY" -m pip install --disable-pip-version-check "scikit-learn==1.9.0"
  fi
  "$PY" - <<'PY'
import sklearn
assert sklearn.__version__ == "1.9.0", sklearn.__version__
print("SKLEARN_BOOTSTRAP=verified")
print("SKLEARN_VERSION=" + sklearn.__version__)
PY
}

RUN_ID="$(date +%Y%m%d-%H%M%S)"
ART="$PWD/artifacts"
OUT="$ART/v77-paper-oos-lineage-$RUN_ID"
BUNDLE_DIR="$ART/v77-paper-oos-lineage-bundle-$RUN_ID"
BUNDLE="$ART/UPLOAD_THIS_v77_PAPER_OOS_LINEAGE-$RUN_ID.zip"
FAIL_BUNDLE="$ART/UPLOAD_THIS_v77_PAPER_OOS_LINEAGE_FAILURE-$RUN_ID.zip"
LOG="$ART/v77-paper-oos-lineage-$RUN_ID.log"
mkdir -p "$OUT" "$BUNDLE_DIR/output" "$BUNDLE_DIR/state_snapshot"

STORE_SHA_BEFORE="$(sha256sum "$STORE" | awk '{print $1}')"
HEAD="$(git rev-parse HEAD)"

run_all() (
  set -euo pipefail
  echo "===== V77 FRESH PAPER OOS + DATA LINEAGE ====="
  echo "BRANCH=$BRANCH"
  echo "HEAD=$HEAD"
  echo "PYTHON_ENV=vn_quant_local_system/.venv"
  echo "CHAMPION_MODEL=C3_STABLE_3_PAST_IC_SHRUNK"
  echo "SHADOW_MODEL=V76_RIDGE_RANK"
  echo "CHAMPION_REPLACED=false"
  echo "PRIMARY_VARIANT=GAP18_CLEAN_FROZEN_AT_FIRST_RUN"
  echo "PRIMARY_ALLOCATOR=EQUAL"
  echo "PAPER_CAPITAL_AUTHORIZED=false"
  echo "LIVE_ORDERS_ALLOWED=false"
  echo "HISTORICAL_MODEL_FISHING_ALLOWED=false"
  echo "PERSISTENT_STATE=$STATE"
  echo

  echo "===== DEPENDENCY CONTRACT ====="
  ensure_sklearn
  echo

  echo "===== COMPILE + REGRESSION ====="
  "$PY" -m py_compile \
    src/he_thong_dinh_luong/paper_oos_data_lineage_v77.py \
    src/he_thong_dinh_luong/paper_oos_data_lineage_v77_driver.py \
    tests/test_paper_oos_data_lineage_v77.py \
    tests/test_paper_oos_data_lineage_v77_driver.py
  "$PY" -m unittest \
    tests.test_paper_oos_data_lineage_v77 \
    tests.test_paper_oos_data_lineage_v77_driver -v
  echo

  ARGS=(
    --store "$(cygpath -w "$STORE")"
    --state-dir "$(cygpath -w "$STATE")"
    --output-dir "$(cygpath -w "$OUT")"
    --git-head "$HEAD"
    --search-root "$(cygpath -w "$PWD/vn_quant_local_system/data")"
  )
  [[ -d "$PWD/vn_quant_local_system/validation" ]] && ARGS+=(--search-root "$(cygpath -w "$PWD/vn_quant_local_system/validation")")
  [[ -d "$PWD/vn_quant_local_system/outputs" ]] && ARGS+=(--search-root "$(cygpath -w "$PWD/vn_quant_local_system/outputs")")
  [[ -d "$PWD/du_lieu" ]] && ARGS+=(--search-root "$(cygpath -w "$PWD/du_lieu")")
  if [[ "${V77_MONTH_CLOSE_CONFIRMED:-0}" == "1" ]]; then
    echo "MONTH_CLOSE_OVERRIDE=true"
    ARGS+=(--month-close-confirmed)
  else
    echo "MONTH_CLOSE_OVERRIDE=false"
  fi

  echo "===== V77 RUN ====="
  "$PY" -m he_thong_dinh_luong.paper_oos_data_lineage_v77_driver "${ARGS[@]}"
  echo

  echo "===== PAPER PNL FIRST ====="
  "$PY" - "$(cygpath -w "$OUT/v77_report.json")" <<'PY'
import json,sys
from pathlib import Path
r=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
print("STATUS="+str(r["status"]))
print("FREEZE_MARKET_DAY="+str(r["freeze"]["freeze_market_day"]))
print("CAPTURE_MARKET_DAY="+str(r["capture_market_day"]))
print("SOURCE_SIGNAL_DAY="+str(r["source_signal_day"]))
print("CAPTURE_WALL_DATE_VN="+str(r.get("capture_wall_date_vn")))
for model,p in r["paper_results"].items():
    print("PAPER",model,
          "status="+str(p.get("status")),
          "signals="+str(p.get("signal_date_count",0)),
          "fresh_sessions="+str(p.get("fresh_oos_session_count",0)),
          "fills="+str(p.get("fill_count",0)),
          "return="+str(p.get("total_return")),
          "mdd="+str(p.get("max_drawdown")),
          "nav_vnd="+str(p.get("latest_nav_vnd")))
print("SHADOW_MINUS_CHAMPION="+str(r["paper_comparison"].get("shadow_minus_champion_total_return")))
print("DATA_GATE_BLOCKERS="+json.dumps(r["data_lineage"]["blockers"],ensure_ascii=False))
print("CANONICAL_DATA_GATES_PASSED="+str(r["canonical_data_gates_passed"]))
print("PROMOTION_AUTHORIZED="+str(r["promotion_authorized"]))
print("LIVE_ORDERS_ALLOWED="+str(r["live_orders_allowed"]))
PY
)

set +e
run_all 2>&1 | tee "$LOG"
RC=${PIPESTATUS[0]}
set -e

STORE_SHA_AFTER="$(sha256sum "$STORE" | awk '{print $1}')"
if [[ "$STORE_SHA_AFTER" != "$STORE_SHA_BEFORE" ]]; then
  echo "FATAL: market store SHA changed during V77" | tee -a "$LOG"
  RC=9
fi

cp "$LOG" "$BUNDLE_DIR/run.log" || true
git branch --show-current > "$BUNDLE_DIR/git_branch.txt"
git rev-parse HEAD > "$BUNDLE_DIR/git_head.txt"
printf '%s\n' "$STORE_SHA_BEFORE" > "$BUNDLE_DIR/store_sha256_before.txt"
printf '%s\n' "$STORE_SHA_AFTER" > "$BUNDLE_DIR/store_sha256_after.txt"
"$PY" - <<'PY' > "$BUNDLE_DIR/python_version.txt" 2>&1 || true
import sklearn,sys
print(sys.version.replace("\n"," "))
print(sys.executable)
print("scikit-learn",sklearn.__version__)
PY
[[ -d "$OUT" ]] && cp -R "$OUT"/. "$BUNDLE_DIR/output/" || true
[[ -f "$STATE/freeze_manifest.json" ]] && cp "$STATE/freeze_manifest.json" "$BUNDLE_DIR/state_snapshot/" || true
if [[ -d "$STATE/signals" ]]; then
  mkdir -p "$BUNDLE_DIR/state_snapshot/signals"
  cp -R "$STATE/signals"/. "$BUNDLE_DIR/state_snapshot/signals/" || true
fi

TARGET="$BUNDLE"; [[ "$RC" -eq 0 ]] || TARGET="$FAIL_BUNDLE"
powershell.exe -NoProfile -Command "Compress-Archive -Path '$(cygpath -w "$BUNDLE_DIR")\\*' -DestinationPath '$(cygpath -w "$TARGET")' -Force" || true
if [[ "$RC" -eq 0 ]]; then
  echo "===== V77 COMPLETE ====="
  echo "UPLOAD_ZIP=$BUNDLE"
  echo "UPLOAD_ZIP_WINDOWS=$(cygpath -w "$BUNDLE")"
else
  echo "===== V77 FAILED ====="
  echo "UPLOAD_ZIP=$FAIL_BUNDLE"
fi
explorer.exe "$(cygpath -w "$ART")" >/dev/null 2>&1 || true
exit "$RC"
