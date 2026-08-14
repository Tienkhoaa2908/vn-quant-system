#!/usr/bin/env bash
set -euo pipefail

BRANCH="agent/v64-multisignal-weekly-gate-research"
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
OUT="$ART/v64-multisignal-cohorts-$RUN_ID"
STUDY_ZIP="$ART/v64-multisignal-cohorts-$RUN_ID.zip"
BUNDLE_DIR="$ART/v64-multisignal-bundle-$RUN_ID"
BUNDLE="$ART/UPLOAD_THIS_v64_MULTISIGNAL_COHORTS-$RUN_ID.zip"
FAIL_BUNDLE="$ART/UPLOAD_THIS_v64_MULTISIGNAL_COHORTS_FAILURE-$RUN_ID.zip"
LOG="$ART/v64-multisignal-cohorts-$RUN_ID.log"
mkdir -p "$ART" "$BUNDLE_DIR"

run_all(){
  echo "===== V64 MULTI-SIGNAL WEEKLY COHORT RESEARCH ====="
  echo "BRANCH=$BRANCH"
  echo "HEAD=$(git rev-parse HEAD)"
  echo "SELECTION_END=2026-07-31"
  echo "ANALYSIS_END=2026-08-13"
  echo "AUGUST_2026_SELECTION=false"
  echo "SHADOW_USED_FOR_POLICY_SELECTION=false"
  echo "CAUSALITY=COMPLETED_WEEKLY_CLOSE_TO_NEXT_SESSION_OPEN"
  echo "COHORT_MATRIX=18_RISK+18_LEADER"
  echo "COST_ROLE=DEFERRED_TO_PORTFOLIO_STAGE"
  echo "TURNOVER_IS_VETO=false"
  echo "LIVE_MODEL_CHANGE=false"
  echo
  echo "===== COMPILE + PURE TESTS ====="
  "$PY" -m py_compile src/he_thong_dinh_luong/_v64_cohort_contract.py src/he_thong_dinh_luong/c3_cohort_matrix_v64.py tests/test_c3_multisignal_gates_v64.py
  "$PY" -m unittest tests.test_c3_multisignal_gates_v64 -v
  echo
  echo "===== RUN V64 WORKSTATION STUDY ====="
  "$PY" -m he_thong_dinh_luong.c3_cohort_matrix_v64 \
    --input-zip "$(cygpath -w "$INPUT_ZIP")" \
    --store "$(cygpath -w "$STORE")" \
    --output-dir "$(cygpath -w "$OUT")" \
    --output-zip "$(cygpath -w "$STUDY_ZIP")" \
    --selection-end 2026-07-31 \
    --analysis-end 2026-08-13 \
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
[[ -f "$STUDY_ZIP" ]] && cp "$STUDY_ZIP" "$BUNDLE_DIR/"
[[ -f "$OUT/v64_report.json" ]] && cp "$OUT/v64_report.json" "$BUNDLE_DIR/"
[[ -f "$OUT/v64_shortlist.csv" ]] && cp "$OUT/v64_shortlist.csv" "$BUNDLE_DIR/"
[[ -f "$OUT/v64_shadow_focus_vpi_tlg_baf.csv" ]] && cp "$OUT/v64_shadow_focus_vpi_tlg_baf.csv" "$BUNDLE_DIR/"

TARGET="$BUNDLE"
[[ "$RC" -eq 0 ]] || TARGET="$FAIL_BUNDLE"
powershell.exe -NoProfile -Command \
  "Compress-Archive -Path '$(cygpath -w "$BUNDLE_DIR")\\*' -DestinationPath '$(cygpath -w "$TARGET")' -Force" || true

if [[ "$RC" -eq 0 ]]; then
  echo
  echo "===== V64 COMPLETE ====="
  echo "RUN_EXIT=0"
  echo "UPLOAD_ZIP=$BUNDLE"
  echo "UPLOAD_ZIP_WINDOWS=$(cygpath -w "$BUNDLE")"
  echo "research_only=true"
  echo "live_model_change_authorized=false"
else
  echo
  echo "===== V64 FAILED ====="
  echo "RUN_EXIT=$RC"
  echo "UPLOAD_ZIP=$FAIL_BUNDLE"
fi

explorer.exe "$(cygpath -w "$ART")" >/dev/null 2>&1 || true
exit "$RC"
