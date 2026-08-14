#!/usr/bin/env bash
set -euo pipefail

BRANCH="agent/v66-hose-master-panel-walkforward-ml"
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
fail(){ echo "FAILED: $*" >&2; exit 2; }
[[ -n "$REPO_ROOT" ]] || fail "hay chay trong repository vn-quant-system"
cd "$REPO_ROOT"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "sai branch; can $BRANCH"
git diff --quiet || fail "tracked files da bi sua"
git diff --cached --quiet || fail "staging area co thay doi"

PY="$PWD/vn_quant_local_system/.venv/Scripts/python.exe"
STORE="$PWD/vn_quant_local_system/data/market/dnse_ohlcv.sqlite3"
[[ -f "$PY" ]] || fail "khong tim thay workstation Python"
[[ -f "$STORE" ]] || fail "khong tim thay market DB"

export PYTHONPATH="$PWD/src:$PWD/vn_quant_local_system/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

RUN_ID="$(date +%Y%m%d-%H%M%S)"
ART="$PWD/artifacts"
OUT="$ART/v66-hose-master-ml-$RUN_ID"
PANEL_OUT="$OUT/panel"
ML_OUT="$OUT/ml"
BUNDLE_DIR="$ART/v66-hose-master-ml-bundle-$RUN_ID"
BUNDLE="$ART/UPLOAD_THIS_v66_HOSE_MASTER_ML-$RUN_ID.zip"
FAIL_BUNDLE="$ART/UPLOAD_THIS_v66_HOSE_MASTER_ML_FAILURE-$RUN_ID.zip"
LOG="$ART/v66-hose-master-ml-$RUN_ID.log"
mkdir -p "$ART" "$OUT" "$PANEL_OUT" "$ML_OUT" "$BUNDLE_DIR"

run_all(){
  echo "===== V66 HOSE MASTER PANEL + WALK-FORWARD ML ====="
  echo "BRANCH=$BRANCH"
  echo "HEAD=$(git rev-parse HEAD)"
  echo "STORE=$STORE"
  echo "TRAINING_SOURCE=LOCAL_11Y_HOSE_MASTER_PANEL"
  echo "V22_USED_AS_TRAINING_INPUT=false"
  echo "POINT_IN_TIME_EXCHANGE_REQUIRED=true"
  echo "RANDOM_CV=false"
  echo "MODELS=LOGISTIC|HIST_GRADIENT_BOOSTING|HEURISTIC_BASELINE"
  echo "LIVE_MODEL_CHANGE=false"
  echo

  echo "===== ENVIRONMENT ====="
  "$PY" - <<'PY'
import sklearn, numpy
print("sklearn=" + sklearn.__version__)
print("numpy=" + numpy.__version__)
PY
  echo

  echo "===== COMPILE + PURE TESTS ====="
  "$PY" -m py_compile \
    src/he_thong_dinh_luong/hose_master_panel_v66.py \
    src/he_thong_dinh_luong/hose_walkforward_ml_v66.py \
    tests/test_hose_master_ml_v66.py
  "$PY" -m unittest tests.test_hose_master_ml_v66 -v
  echo

  echo "===== BUILD HOSE MASTER PANEL FROM LOCAL STORE ====="
  "$PY" -m he_thong_dinh_luong.hose_master_panel_v66 \
    --store "$(cygpath -w "$STORE")" \
    --output-dir "$(cygpath -w "$PANEL_OUT")" \
    --price-multiplier 1000
  echo

  echo "===== PURGED WALK-FORWARD ML ====="
  "$PY" -m he_thong_dinh_luong.hose_walkforward_ml_v66 \
    --panel "$(cygpath -w "$PANEL_OUT/v66_hose_master_panel.csv.gz")" \
    --output-dir "$(cygpath -w "$ML_OUT")"
}

set +e
run_all 2>&1 | tee "$LOG"
RC=${PIPESTATUS[0]}
set -e

cp "$LOG" "$BUNDLE_DIR/run.log" || true
git branch --show-current > "$BUNDLE_DIR/git_branch.txt"
git rev-parse HEAD > "$BUNDLE_DIR/git_head.txt"
sha256sum "$STORE" > "$BUNDLE_DIR/store_sha256.txt"
"$PY" - <<'PY' > "$BUNDLE_DIR/python_ml_versions.txt" 2>&1 || true
import sys, sklearn, numpy
print("python=" + sys.version.replace("\n"," "))
print("sklearn=" + sklearn.__version__)
print("numpy=" + numpy.__version__)
PY
[[ -d "$PANEL_OUT" ]] && cp -R "$PANEL_OUT" "$BUNDLE_DIR/panel" || true
[[ -d "$ML_OUT" ]] && cp -R "$ML_OUT" "$BUNDLE_DIR/ml" || true

TARGET="$BUNDLE"
[[ "$RC" -eq 0 ]] || TARGET="$FAIL_BUNDLE"
powershell.exe -NoProfile -Command \
  "Compress-Archive -Path '$(cygpath -w "$BUNDLE_DIR")\\*' -DestinationPath '$(cygpath -w "$TARGET")' -Force" || true

if [[ "$RC" -eq 0 ]]; then
  echo
  echo "===== V66 COMPLETE ====="
  echo "RUN_EXIT=0"
  echo "UPLOAD_ZIP=$BUNDLE"
  echo "UPLOAD_ZIP_WINDOWS=$(cygpath -w "$BUNDLE")"
  echo "research_only=true"
  echo "live_model_change_authorized=false"
else
  echo
  echo "===== V66 FAILED ====="
  echo "RUN_EXIT=$RC"
  echo "UPLOAD_ZIP=$FAIL_BUNDLE"
  echo "NOTE=neu fail do exchange metadata, gui failure bundle; khong dung static HOSE mapping de train"
fi

explorer.exe "$(cygpath -w "$ART")" >/dev/null 2>&1 || true
exit "$RC"
