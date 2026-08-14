#!/usr/bin/env bash
set -euo pipefail

BRANCH="agent/v63-weekly-protection-opportunity-gates"
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
HIST_OUT="$ART/v63-weekly-gates-historical-$RUN_ID"
SHADOW_OUT="$ART/v63-weekly-gates-shadow-$RUN_ID"
HIST_ZIP="$ART/v63-weekly-gates-historical-$RUN_ID.zip"
SHADOW_ZIP="$ART/v63-weekly-gates-shadow-$RUN_ID.zip"
BUNDLE_DIR="$ART/v63-weekly-gates-bundle-$RUN_ID"
BUNDLE="$ART/UPLOAD_THIS_v63_WEEKLY_GATES-$RUN_ID.zip"
FAIL_BUNDLE="$ART/UPLOAD_THIS_v63_WEEKLY_GATES_FAILURE-$RUN_ID.zip"
LOG="$ART/v63-weekly-gates-$RUN_ID.log"
mkdir -p "$ART" "$BUNDLE_DIR"

run_all(){
  echo "===== V63 WEEKLY GATE DIAGNOSTICS ====="
  echo "BRANCH=$BRANCH"
  echo "HEAD=$(git rev-parse HEAD)"
  echo "HISTORICAL_END=2026-07-31"
  echo "SHADOW_END=2026-08-13"
  echo "HISTORICAL_SELECTION_USES_AUGUST=false"
  echo "SHADOW_USED_FOR_POLICY_SELECTION=false"
  echo "CAUSALITY=WEEK_LAST_CLOSE_TO_NEXT_SESSION_OPEN"
  echo "ENGINE=he_thong_dinh_luong.c3_short_horizon_v60"
  echo "COHORTS=CANONICAL_TOP10_DROPPED20|NEW_PREVIEW_TOP5|NEW_PREVIEW_TOP10"
  echo "LIVE_MODEL_CHANGE=false"
  echo
  echo "===== COMPILE + PURE TESTS ====="
  "$PY" -m py_compile src/he_thong_dinh_luong/c3_short_horizon_v60.py tests/test_c3_short_horizon_v60.py
  "$PY" -m unittest tests.test_c3_short_horizon_v60 -v
  echo
  echo "===== HISTORICAL PASS ====="
  "$PY" -m he_thong_dinh_luong.c3_short_horizon_v60 \
    --input-zip "$(cygpath -w "$INPUT_ZIP")" \
    --store "$(cygpath -w "$STORE")" \
    --output-dir "$(cygpath -w "$HIST_OUT")" \
    --output-zip "$(cygpath -w "$HIST_ZIP")" \
    --analysis-end 2026-07-31 \
    --holdout-start 2022-01-01 \
    --price-multiplier 1000
  echo
  echo "===== AUGUST SHADOW PASS ====="
  "$PY" -m he_thong_dinh_luong.c3_short_horizon_v60 \
    --input-zip "$(cygpath -w "$INPUT_ZIP")" \
    --store "$(cygpath -w "$STORE")" \
    --output-dir "$(cygpath -w "$SHADOW_OUT")" \
    --output-zip "$(cygpath -w "$SHADOW_ZIP")" \
    --analysis-end 2026-08-13 \
    --holdout-start 2022-01-01 \
    --price-multiplier 1000
}

set +e
run_all 2>&1 | tee "$LOG"
RC=${PIPESTATUS[0]}
set -e

cp "$LOG" "$BUNDLE_DIR/run.log" || true
git branch --show-current > "$BUNDLE_DIR/git_branch.txt"
git rev-parse HEAD > "$BUNDLE_DIR/git_head.txt"
sha256sum "$INPUT_ZIP" > "$BUNDLE_DIR/input_zip_sha256.txt"
sha256sum "$STORE" > "$BUNDLE_DIR/store_sha256.txt"
[[ -f "$HIST_ZIP" ]] && cp "$HIST_ZIP" "$BUNDLE_DIR/"
[[ -f "$SHADOW_ZIP" ]] && cp "$SHADOW_ZIP" "$BUNDLE_DIR/"
[[ -f "$HIST_OUT/report.json" ]] && cp "$HIST_OUT/report.json" "$BUNDLE_DIR/historical_report.json"
[[ -f "$SHADOW_OUT/report.json" ]] && cp "$SHADOW_OUT/report.json" "$BUNDLE_DIR/shadow_report.json"

TARGET="$BUNDLE"
[[ "$RC" -eq 0 ]] || TARGET="$FAIL_BUNDLE"
powershell.exe -NoProfile -Command \
  "Compress-Archive -Path '$(cygpath -w "$BUNDLE_DIR")\\*' -DestinationPath '$(cygpath -w "$TARGET")' -Force" || true

if [[ "$RC" -eq 0 ]]; then
  echo
  echo "===== V63 COMPLETE ====="
  echo "RUN_EXIT=0"
  echo "UPLOAD_ZIP=$BUNDLE"
  echo "UPLOAD_ZIP_WINDOWS=$(cygpath -w "$BUNDLE")"
  echo "research_only=true"
  echo "shadow_used_for_policy_selection=false"
  echo "live_model_change_authorized=false"
else
  echo
  echo "===== V63 FAILED ====="
  echo "RUN_EXIT=$RC"
  echo "UPLOAD_ZIP=$FAIL_BUNDLE"
fi

explorer.exe "$(cygpath -w "$ART")" >/dev/null 2>&1 || true
exit "$RC"
