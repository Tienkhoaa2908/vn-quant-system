#!/usr/bin/env bash
set -euo pipefail
BRANCH="agent/v65-multisignal-robustness-audit"
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
V64_OUT="$ART/v65-rebuild-v64-$RUN_ID"
V64_ZIP="$ART/v65-rebuild-v64-$RUN_ID.zip"
V65_OUT="$ART/v65-multisignal-robustness-$RUN_ID"
V65_ZIP="$ART/v65-multisignal-robustness-$RUN_ID.zip"
BUNDLE_DIR="$ART/v65-bundle-$RUN_ID"
BUNDLE="$ART/UPLOAD_THIS_v65_MULTISIGNAL_ROBUSTNESS-$RUN_ID.zip"
FAIL_BUNDLE="$ART/UPLOAD_THIS_v65_MULTISIGNAL_ROBUSTNESS_FAILURE-$RUN_ID.zip"
LOG="$ART/v65-multisignal-robustness-$RUN_ID.log"
mkdir -p "$ART" "$BUNDLE_DIR"
run_all(){
  echo "===== V65 MULTI-SIGNAL ROBUSTNESS AUDIT ====="
  echo "BRANCH=$BRANCH"
  echo "HEAD=$(git rev-parse HEAD)"
  echo "V64_MATRIX=18_RISK+18_LEADER_FROZEN"
  echo "SELECTION_END=2026-07-31"
  echo "ANALYSIS_END=2026-08-13"
  echo "BOOTSTRAP_REPS=10000"
  echo "DEPENDENCE=BLOCK_BY_WEEK+BLOCK_BY_SYMBOL"
  echo "MULTIPLE_TESTING=BH_FDR_WITHIN_KIND"
  echo "SHADOW_SIGNAL_STATE_REQUIRES_FUTURE_OUTCOME=false"
  echo "LIVE_MODEL_CHANGE=false"
  "$PY" -m py_compile src/he_thong_dinh_luong/c3_multisignal_robustness_v65.py tests/test_c3_multisignal_robustness_v65.py
  "$PY" -m unittest tests.test_c3_multisignal_robustness_v65 -v
  "$PY" -m he_thong_dinh_luong.c3_cohort_matrix_v64 \
    --input-zip "$(cygpath -w "$INPUT_ZIP")" \
    --store "$(cygpath -w "$STORE")" \
    --output-dir "$(cygpath -w "$V64_OUT")" \
    --output-zip "$(cygpath -w "$V64_ZIP")" \
    --selection-end 2026-07-31 --analysis-end 2026-08-13 --price-multiplier 1000
  "$PY" -m he_thong_dinh_luong.c3_multisignal_robustness_v65 \
    --v64-dir "$(cygpath -w "$V64_OUT")" \
    --output-dir "$(cygpath -w "$V65_OUT")" \
    --output-zip "$(cygpath -w "$V65_ZIP")" \
    --bootstrap-reps 10000
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
[[ -f "$V64_OUT/v64_report.json" ]] && cp "$V64_OUT/v64_report.json" "$BUNDLE_DIR/"
[[ -f "$V64_OUT/v64_shortlist.csv" ]] && cp "$V64_OUT/v64_shortlist.csv" "$BUNDLE_DIR/"
[[ -f "$V65_OUT/v65_report.json" ]] && cp "$V65_OUT/v65_report.json" "$BUNDLE_DIR/"
[[ -f "$V65_OUT/v65_robustness_h10.csv" ]] && cp "$V65_OUT/v65_robustness_h10.csv" "$BUNDLE_DIR/"
[[ -f "$V65_OUT/v65_shadow_focus_vpi_tlg_baf_state.csv" ]] && cp "$V65_OUT/v65_shadow_focus_vpi_tlg_baf_state.csv" "$BUNDLE_DIR/"
[[ -f "$V65_ZIP" ]] && cp "$V65_ZIP" "$BUNDLE_DIR/"
TARGET="$BUNDLE"; [[ "$RC" -eq 0 ]] || TARGET="$FAIL_BUNDLE"
powershell.exe -NoProfile -Command "Compress-Archive -Path '$(cygpath -w "$BUNDLE_DIR")\\*' -DestinationPath '$(cygpath -w "$TARGET")' -Force" || true
if [[ "$RC" -eq 0 ]]; then
  echo "===== V65 COMPLETE ====="
  echo "RUN_EXIT=0"
  echo "UPLOAD_ZIP=$BUNDLE"
  echo "UPLOAD_ZIP_WINDOWS=$(cygpath -w "$BUNDLE")"
  echo "research_only=true"
  echo "live_model_change_authorized=false"
else
  echo "===== V65 FAILED ====="
  echo "RUN_EXIT=$RC"
  echo "UPLOAD_ZIP=$FAIL_BUNDLE"
fi
explorer.exe "$(cygpath -w "$ART")" >/dev/null 2>&1 || true
exit "$RC"
