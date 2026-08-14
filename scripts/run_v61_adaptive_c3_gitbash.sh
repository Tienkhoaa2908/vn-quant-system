#!/usr/bin/env bash
set -euo pipefail

BRANCH="agent/v61-adaptive-c3-portfolio-policy-study"
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"

fail(){ echo "FAILED: $*" >&2; exit 2; }
[[ -n "$REPO_ROOT" ]] || fail "hay chay trong repository vn-quant-system"
cd "$REPO_ROOT"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "sai branch; can $BRANCH"
git diff --quiet || fail "tracked files da bi sua"
git diff --cached --quiet || fail "staging area co thay doi"

PY="$PWD/vn_quant_local_system/.venv/Scripts/python.exe"
INPUT_ZIP="$PWD/vn_quant_local_system/data/reference/daily_prediction_input_v22.zip"
STORE="$PWD/vn_quant_local_system/data/market/dnse_ohlcv.sqlite3"
[[ -f "$PY" ]] || fail "khong tim thay workstation Python"
[[ -f "$INPUT_ZIP" ]] || fail "khong tim thay frozen V22"
[[ -f "$STORE" ]] || fail "khong tim thay market DB"

export PYTHONPATH="$PWD/src:$PWD/vn_quant_local_system/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

RUN_ID="$(date +%Y%m%d-%H%M%S)"
ART="$PWD/artifacts"
STUDY_ZIP="$ART/v61-adaptive-c3-$RUN_ID.zip"
BUNDLE="$ART/UPLOAD_THIS_v61_ADAPTIVE_C3-$RUN_ID.zip"
FAIL_BUNDLE="$ART/UPLOAD_THIS_v61_ADAPTIVE_C3_FAILURE-$RUN_ID.zip"
LOG="$ART/v61-adaptive-c3-$RUN_ID.log"
BUNDLE_DIR="$ART/v61-bundle-$RUN_ID"
mkdir -p "$ART" "$BUNDLE_DIR"

run_study(){
  echo "===== V61 ADAPTIVE C3 PORTFOLIO POLICY STUDY ====="
  echo "BRANCH=$BRANCH"
  echo "HEAD=$(git rev-parse HEAD)"
  echo "ANALYSIS_END=2026-07-31"
  echo "AUGUST_2026_VPI_SELECTION=false"
  echo "CAUSALITY=PREVIOUS_WEEK_CLOSE_TO_LATER_OPEN"
  echo "FORMER_V60_HOLDOUT_ALREADY_CONSUMED=true"
  echo "VALIDATION_MODE=CROSS_ERA_YEAR_ROBUSTNESS_PLUS_COST_STRESS"
  echo "LIVE_MODEL_CHANGE=false"
  echo
  echo "===== COMPILE + PURE TESTS ====="
  "$PY" -m py_compile \
    src/he_thong_dinh_luong/c3_adaptive_portfolio_v61.py \
    tests/test_c3_adaptive_portfolio_v61.py
  "$PY" -m unittest tests.test_c3_adaptive_portfolio_v61 -v
  echo
  echo "===== RUN LOCAL ARCHIVE PORTFOLIO STUDY ====="
  "$PY" -m he_thong_dinh_luong.c3_adaptive_portfolio_v61 \
    --input-zip "$(cygpath -w "$INPUT_ZIP")" \
    --store "$(cygpath -w "$STORE")" \
    --output-zip "$(cygpath -w "$STUDY_ZIP")" \
    --analysis-end 2026-07-31
}

set +e
run_study 2>&1 | tee "$LOG"
RC=${PIPESTATUS[0]}
set -e

cp "$LOG" "$BUNDLE_DIR/run.log" || true
git branch --show-current > "$BUNDLE_DIR/git_branch.txt"
git rev-parse HEAD > "$BUNDLE_DIR/git_head.txt"
sha256sum "$INPUT_ZIP" > "$BUNDLE_DIR/input_zip_sha256.txt"
sha256sum "$STORE" > "$BUNDLE_DIR/store_sha256.txt"
[[ -f "$STUDY_ZIP" ]] && cp "$STUDY_ZIP" "$BUNDLE_DIR/"

TARGET="$BUNDLE"
[[ "$RC" -eq 0 ]] || TARGET="$FAIL_BUNDLE"
powershell.exe -NoProfile -Command \
  "Compress-Archive -Path '$(cygpath -w "$BUNDLE_DIR")\\*' -DestinationPath '$(cygpath -w "$TARGET")' -Force" || true

if [[ "$RC" -eq 0 ]]; then
  echo
  echo "===== V61 COMPLETE ====="
  echo "RUN_EXIT=0"
  echo "UPLOAD_ZIP=$BUNDLE"
  echo "UPLOAD_ZIP_WINDOWS=$(cygpath -w "$BUNDLE")"
  echo "research_only=true"
  echo "live_model_change_authorized=false"
else
  echo
  echo "===== V61 FAILED ====="
  echo "RUN_EXIT=$RC"
  echo "UPLOAD_ZIP=$FAIL_BUNDLE"
fi

explorer.exe "$(cygpath -w "$ART")" >/dev/null 2>&1 || true
exit "$RC"
