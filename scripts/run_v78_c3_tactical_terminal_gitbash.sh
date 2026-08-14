#!/usr/bin/env bash
set -euo pipefail

BRANCH="agent/v78-c3-tactical-terminal"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
fail(){ echo "FAILED: $*" >&2; exit 2; }
[[ -n "$ROOT" ]] || fail "hay chay trong repository vn-quant-system"
cd "$ROOT"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "sai branch; can $BRANCH"
git diff --quiet || fail "tracked files da bi sua"
git diff --cached --quiet || fail "staging area co thay doi"

PY="$PWD/vn_quant_local_system/.venv/Scripts/python.exe"
STORE="$PWD/vn_quant_local_system/data/market/dnse_ohlcv.sqlite3"
V77_STATE="$PWD/du_lieu/v77-paper-oos-state"
TACTICAL_STATE="$PWD/du_lieu/v78-tactical-state"
LIVE_ROOT="$PWD/vn_quant_local_system/data/v78-c3-tactical"
ART="$PWD/artifacts"
[[ -f "$PY" ]] || fail "khong tim thay canonical .venv Python"
[[ -f "$STORE" ]] || fail "khong tim thay dnse_ohlcv.sqlite3"
[[ -f "$V77_STATE/freeze_manifest.json" ]] || fail "V78 can V77 freeze state hien huu; KHONG tao lai freeze"
mkdir -p "$TACTICAL_STATE" "$LIVE_ROOT" "$ART"

export PYTHONPATH="$PWD/src:$PWD/vn_quant_local_system/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

ensure_dep(){
  local module="$1" spec="$2" expected="$3"
  if "$PY" - "$module" "$expected" <<'PY' >/dev/null 2>&1
import importlib,sys
m=importlib.import_module(sys.argv[1])
v=getattr(m,"__version__","")
raise SystemExit(0 if (not sys.argv[2] or v==sys.argv[2]) else 1)
PY
  then
    echo "DEPENDENCY_${module}=already_verified"
  else
    echo "DEPENDENCY_${module}=installing_${spec}"
    "$PY" -m pip install --disable-pip-version-check "$spec"
  fi
}
ensure_dep sklearn "scikit-learn==1.9.0" "1.9.0"
ensure_dep nicegui "nicegui==3.14.0" "3.14.0"

RUN_ID="$(date +%Y%m%d-%H%M%S)"
OUT="$ART/v78-c3-tactical-terminal-$RUN_ID"
BUNDLE_DIR="$ART/v78-c3-tactical-terminal-bundle-$RUN_ID"
BUNDLE="$ART/UPLOAD_THIS_v78_C3_TACTICAL_TERMINAL-$RUN_ID.zip"
FAIL_BUNDLE="$ART/UPLOAD_THIS_v78_C3_TACTICAL_TERMINAL_FAILURE-$RUN_ID.zip"
LOG="$ART/v78-c3-tactical-terminal-$RUN_ID.log"
mkdir -p "$OUT" "$BUNDLE_DIR/output" "$BUNDLE_DIR/state_snapshot"

STORE_SHA_BEFORE="$(sha256sum "$STORE" | awk '{print $1}')"
HEAD="$(git rev-parse HEAD)"

run_all() (
  set -euo pipefail
  echo "===== V78 C3 TACTICAL OPERATING TERMINAL ====="
  echo "BRANCH=$BRANCH"
  echo "HEAD=$HEAD"
  echo "OPERATIONAL_CHAMPION=C3_STABLE_3_PAST_IC_SHRUNK"
  echo "OPERATIONAL_CHAMPION_FINALIZED=true"
  echo "SECONDARY_MODEL=V76_RIDGE_RANK"
  echo "SECONDARY_ROLE=SHADOW_CONFIRMATION_AND_EMERGENCE_RADAR_ONLY"
  echo "MONTHLY_CORE=C3_TOP10"
  echo "INTRAMONTH_LAYER=V72_TRIGGER_SEMANTICS_ADVISORY"
  echo "LIVE_ORDERS_ALLOWED=false"
  echo "V77_STATE_PRESERVED=$V77_STATE"
  echo "V78_TACTICAL_STATE=$TACTICAL_STATE"
  echo

  echo "===== COMPILE + REGRESSION ====="
  "$PY" -m py_compile \
    src/he_thong_dinh_luong/c3_tactical_terminal_v78.py \
    src/he_thong_dinh_luong/c3_tactical_terminal_v78_driver.py \
    src/he_thong_dinh_luong/web_console_app_v78.py \
    tests/test_c3_tactical_terminal_v78.py \
    tests/test_c3_tactical_terminal_v78_driver.py
  "$PY" -m unittest \
    tests.test_c3_tactical_terminal_v78 \
    tests.test_c3_tactical_terminal_v78_driver -v
  echo

  echo "===== V78 CURRENT TACTICAL + RECENT EVIDENCE ====="
  "$PY" -m he_thong_dinh_luong.c3_tactical_terminal_v78_driver \
    --store "$(cygpath -w "$STORE")" \
    --v77-state-dir "$(cygpath -w "$V77_STATE")" \
    --tactical-state-dir "$(cygpath -w "$TACTICAL_STATE")" \
    --output-dir "$(cygpath -w "$OUT")" \
    --artifact-root "$(cygpath -w "$ART")"
  echo

  echo "===== OPERATIONAL DECISION ====="
  "$PY" - "$(cygpath -w "$OUT/v78_report.json")" <<'PY'
import json,sys
from pathlib import Path
r=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
print("STATUS="+str(r["status"]))
print("OPERATIONAL_CHAMPION="+str(r["operational_champion"]))
print("OPERATIONAL_CHAMPION_FINALIZED="+str(r["operational_champion_finalized"]))
print("CAPTURE_DAY="+str(r["capture_day"]))
print("SOURCE_MONTHLY_SIGNAL_DAY="+str(r["source_monthly_signal_day"]))
print("RISK_ON="+str(r["risk_on"]))
print("MONTHLY_TOP10="+",".join(r["monthly_top10"]))
print("CURRENT_PREVIEW_TOP10="+",".join(r["current_preview_top10"]))
print("INCUMBENT_HEALTH_ALERTS="+str(r["incumbent_health_alert_count"]))
print("EMERGING_RADAR="+str(r["emerging_radar_count"]))
print("L15_SWAP_PAIR="+json.dumps(r["l15_swap_pair"],ensure_ascii=False))
print("PRIOR_WEEK_PREVIEW_AVAILABLE="+str(r["prior_week_preview_available"]))
recent=r["recent_regime_evidence"]
print("RECENT_V72_ROWS="+str(len(recent.get("v72",[]))))
print("RECENT_RIDGE_ROWS="+str(len(recent.get("ridge",[]))))
for row in recent.get("v72",[]):
    print("RECENT_V72",row["window_months"],row["candidate_id"],"base=",row["baseline_return"],"candidate=",row["candidate_return"],"delta=",row["candidate_minus_baseline"],"benchmark=",row["benchmark_return"])
for row in recent.get("ridge",[]):
    print("RECENT_RIDGE",row["window_months"],row["candidate_id"],"base=",row["baseline_return"],"candidate=",row["candidate_return"],"delta=",row["candidate_minus_baseline"],"benchmark=",row["benchmark_return"])
print("LIVE_ORDERS_ALLOWED="+str(r["live_orders_allowed"]))
PY

  echo "===== PUBLISH WEB SNAPSHOT ====="
  cp "$OUT/v78_report.json" "$LIVE_ROOT/LATEST.json"
  cp "$OUT/v78_tactical_rows.csv" "$LIVE_ROOT/v78_tactical_rows.csv"
  cp "$OUT/v78_incumbent_health.csv" "$LIVE_ROOT/v78_incumbent_health.csv"
  cp "$OUT/v78_emerging_radar.csv" "$LIVE_ROOT/v78_emerging_radar.csv"
  cp "$OUT/v78_recent_v72.csv" "$LIVE_ROOT/v78_recent_v72.csv"
  cp "$OUT/v78_recent_ridge.csv" "$LIVE_ROOT/v78_recent_ridge.csv"
  echo "WEB_SNAPSHOT=$LIVE_ROOT/LATEST.json"
)

set +e
run_all 2>&1 | tee "$LOG"
RC=${PIPESTATUS[0]}
set -e

STORE_SHA_AFTER="$(sha256sum "$STORE" | awk '{print $1}')"
if [[ "$STORE_SHA_AFTER" != "$STORE_SHA_BEFORE" ]]; then
  echo "FATAL: market store SHA changed during V78" | tee -a "$LOG"
  RC=9
fi

cp "$LOG" "$BUNDLE_DIR/run.log" || true
git branch --show-current > "$BUNDLE_DIR/git_branch.txt"
git rev-parse HEAD > "$BUNDLE_DIR/git_head.txt"
printf '%s\n' "$STORE_SHA_BEFORE" > "$BUNDLE_DIR/store_sha256_before.txt"
printf '%s\n' "$STORE_SHA_AFTER" > "$BUNDLE_DIR/store_sha256_after.txt"
"$PY" - <<'PY' > "$BUNDLE_DIR/python_version.txt" 2>&1 || true
import sklearn,sys
try:
 import nicegui
 nv=getattr(nicegui,"__version__","")
except Exception as exc:
 nv=f"ERROR:{exc}"
print(sys.version.replace("\n"," "))
print(sys.executable)
print("scikit-learn",sklearn.__version__)
print("nicegui",nv)
PY
[[ -d "$OUT" ]] && cp -R "$OUT"/. "$BUNDLE_DIR/output/" || true
[[ -d "$TACTICAL_STATE/previews" ]] && cp -R "$TACTICAL_STATE/previews" "$BUNDLE_DIR/state_snapshot/" || true
[[ -f "$V77_STATE/freeze_manifest.json" ]] && cp "$V77_STATE/freeze_manifest.json" "$BUNDLE_DIR/state_snapshot/v77_freeze_manifest.json" || true

TARGET="$BUNDLE"; [[ "$RC" -eq 0 ]] || TARGET="$FAIL_BUNDLE"
powershell.exe -NoProfile -Command "Compress-Archive -Path '$(cygpath -w "$BUNDLE_DIR")\\*' -DestinationPath '$(cygpath -w "$TARGET")' -Force" || true

if [[ "$RC" -eq 0 ]]; then
  echo "===== V78 COMPLETE ====="
  echo "UPLOAD_ZIP=$BUNDLE"
  echo "UPLOAD_ZIP_WINDOWS=$(cygpath -w "$BUNDLE")"
  if [[ "${V78_LAUNCH_WEB:-1}" == "1" ]]; then
    WEB_PORT="${V78_WEB_PORT:-8089}"
    PY_WIN="$(cygpath -w "$PY")"
    ROOT_WIN="$(cygpath -w "$PWD")"
    DATA_WIN="$(cygpath -w "$PWD/vn_quant_local_system/data")"
    echo "WEB_URL=http://127.0.0.1:$WEB_PORT/"
    powershell.exe -NoProfile -Command "Start-Process -FilePath '$PY_WIN' -WorkingDirectory '$ROOT_WIN' -ArgumentList '-m','he_thong_dinh_luong.web_console_app_v78','--repo-root','$ROOT_WIN','--data-root','$DATA_WIN','--host','127.0.0.1','--port','$WEB_PORT','--no-show-browser'" || true
    powershell.exe -NoProfile -Command "Start-Process 'http://127.0.0.1:$WEB_PORT/'" || true
  fi
else
  echo "===== V78 FAILED ====="
  echo "UPLOAD_ZIP=$FAIL_BUNDLE"
fi
explorer.exe "$(cygpath -w "$ART")" >/dev/null 2>&1 || true
exit "$RC"
