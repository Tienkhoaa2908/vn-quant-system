#!/usr/bin/env bash
set -euo pipefail

BRANCH="agent/v68-consolidated-c3-hose-research"
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
fail(){ echo "FAILED: $*" >&2; exit 2; }
[[ -n "$REPO_ROOT" ]] || fail "hay chay trong repository vn-quant-system"
cd "$REPO_ROOT"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "sai branch; can $BRANCH"
git diff --quiet || fail "tracked files da bi sua"
git diff --cached --quiet || fail "staging area co thay doi"

PY="$PWD/vn_quant_local_system/.venv/Scripts/python.exe"
STORE="$PWD/vn_quant_local_system/data/market/dnse_ohlcv.sqlite3"
DATA_ROOT="$PWD/vn_quant_local_system/data"
VALIDATION_ROOT="$PWD/vn_quant_local_system/validation"
OUTPUTS_ROOT="$PWD/vn_quant_local_system/outputs"
[[ -f "$PY" ]] || fail "khong tim thay canonical workstation Python: vn_quant_local_system/.venv"
[[ -f "$STORE" ]] || fail "khong tim thay market DB"

export PYTHONPATH="$PWD/src:$PWD/vn_quant_local_system/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

RUN_ID="$(date +%Y%m%d-%H%M%S)"
ART="$PWD/artifacts"
OUT="$ART/v68-consolidated-c3-hose-$RUN_ID"
BUNDLE_DIR="$ART/v68-consolidated-c3-hose-bundle-$RUN_ID"
BUNDLE="$ART/UPLOAD_THIS_v68_CONSOLIDATED_C3_HOSE-$RUN_ID.zip"
FAIL_BUNDLE="$ART/UPLOAD_THIS_v68_CONSOLIDATED_C3_HOSE_FAILURE-$RUN_ID.zip"
LOG="$ART/v68-consolidated-c3-hose-$RUN_ID.log"
mkdir -p "$ART" "$OUT" "$BUNDLE_DIR"

run_all() (
  set -euo pipefail

  echo "===== V68 CONSOLIDATED C3 / HOSE RESEARCH ====="
  echo "BRANCH=$BRANCH"
  echo "HEAD=$(git rev-parse HEAD)"
  echo "PYTHON_ENV=vn_quant_local_system/.venv"
  echo "CHAMPION_MODEL=C3_STABLE_3_PAST_IC_SHRUNK"
  echo "CHAMPION_REPLACED=false"
  echo "CHALLENGER_ML_RUN=false"
  echo "SOURCE_STORE_MUTATION_ALLOWED=false"
  echo "PROVISIONAL_DIAGNOSTIC_C3_ALLOWED=true"
  echo "CANONICAL_PROMOTION_REQUIRES_PIT_HOSE_AND_PRICE_BASIS=true"
  echo "C3_TRAINING_LABEL=CLOSE_T_TO_CLOSE_T_PLUS_20_BENCHMARK_RELATIVE"
  echo "TRADABLE_OUTCOME=NEXT_SESSION_OPEN_TO_FUTURE_OPEN"
  echo "HISTORICAL_END=2026-07-31"
  echo "ANALYSIS_END=2026-08-13"
  echo "AUGUST_2026_SHADOW_ONLY=true"
  echo "BOOTSTRAP_CLUSTER_UNIT=WEEK"
  echo "BOOTSTRAP_SAMPLES=2000"
  echo "NETWORK_SCOPE=BEST_EFFORT_HOSE_PUBLIC_METADATA_ONLY"
  echo "SQLITE_RESOURCE_ENTRYPOINT=c3_hose_consolidated_v68_safe"
  echo "LIVE_MODEL_CHANGE=false"
  echo

  echo "===== CANONICAL WORKSTATION ENVIRONMENT ====="
  "$PY" - <<'PY'
import sys
print("python=" + sys.version.replace("\n", " "))
print("executable=" + sys.executable)
PY
  echo

  echo "===== COMPILE + REGRESSION TESTS ====="
  "$PY" -m py_compile \
    src/he_thong_dinh_luong/c3_hose_native_v67.py \
    src/he_thong_dinh_luong/c3_hose_native_driver_v67.py \
    src/he_thong_dinh_luong/hose_data_readiness_v67.py \
    src/he_thong_dinh_luong/hose_lineage_price_probe_v67.py \
    src/he_thong_dinh_luong/market_store_basis_audit_v67.py \
    src/he_thong_dinh_luong/c3_hose_consolidated_v68.py \
    src/he_thong_dinh_luong/c3_hose_consolidated_v68_safe.py \
    tests/test_c3_hose_native_v67.py \
    tests/test_hose_data_readiness_v67.py \
    tests/test_hose_lineage_price_probe_v67.py \
    tests/test_market_store_basis_audit_v67.py \
    tests/test_c3_hose_consolidated_v68.py
  "$PY" -m unittest \
    tests.test_c3_hose_native_v67 \
    tests.test_hose_data_readiness_v67 \
    tests.test_hose_lineage_price_probe_v67 \
    tests.test_market_store_basis_audit_v67 \
    tests.test_c3_hose_consolidated_v68 -v
  echo

  echo "===== ONE-SHOT DATA AUDIT + C3 + COHORT ROBUSTNESS ====="
  ARGS=(
    --store "$(cygpath -w "$STORE")"
    --output-dir "$(cygpath -w "$OUT")"
    --search-root "$(cygpath -w "$DATA_ROOT")"
    --bootstrap-samples 2000
  )
  [[ -d "$VALIDATION_ROOT" ]] && ARGS+=(--search-root "$(cygpath -w "$VALIDATION_ROOT")")
  [[ -d "$OUTPUTS_ROOT" ]] && ARGS+=(--search-root "$(cygpath -w "$OUTPUTS_ROOT")")
  "$PY" -m he_thong_dinh_luong.c3_hose_consolidated_v68_safe "${ARGS[@]}"
  echo

  echo "===== REPORT GATE SUMMARY ====="
  "$PY" - "$(cygpath -w "$OUT/v68_consolidated_report.json")" <<'PY'
import json, sys
from pathlib import Path
r=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print("status=" + str(r.get("status")))
print("local_stock_symbol_count=" + str(r.get("local_stock_symbol_count")))
print("variant_count=" + str(r.get("variant_count")))
print("gap18_symbol_count=" + str(r.get("gap18_symbol_count")))
print("mixed_basis_seam_symbol_count=" + str(r.get("mixed_basis_seam_symbol_count")))
print("price_basis_gate_closed=" + str(r.get("data_gates",{}).get("price_basis_gate_closed")))
print("hose_point_in_time_gate_closed=" + str(r.get("data_gates",{}).get("hose_point_in_time_gate_closed")))
print("canonical_research_claim_authorized=" + str(r.get("data_gates",{}).get("canonical_research_claim_authorized")))
print("diagnostic_c3_allowed=" + str(r.get("data_gates",{}).get("diagnostic_c3_allowed")))
print("promotion_authorized=" + str(r.get("data_gates",{}).get("promotion_authorized")))
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
import sys
print(sys.version.replace("\n", " "))
print(sys.executable)
PY
[[ -d "$OUT" ]] && cp -R "$OUT" "$BUNDLE_DIR/output" || true

TARGET="$BUNDLE"
[[ "$RC" -eq 0 ]] || TARGET="$FAIL_BUNDLE"
powershell.exe -NoProfile -Command \
  "Compress-Archive -Path '$(cygpath -w "$BUNDLE_DIR")\\*' -DestinationPath '$(cygpath -w "$TARGET")' -Force" || true

if [[ "$RC" -eq 0 ]]; then
  echo
  echo "===== V68 COMPLETE ====="
  echo "RUN_EXIT=0"
  echo "UPLOAD_ZIP=$BUNDLE"
  echo "UPLOAD_ZIP_WINDOWS=$(cygpath -w "$BUNDLE")"
  echo "NEXT=upload one consolidated bundle for deep analysis"
else
  echo
  echo "===== V68 FAILED ====="
  echo "RUN_EXIT=$RC"
  echo "UPLOAD_ZIP=$FAIL_BUNDLE"
fi

explorer.exe "$(cygpath -w "$ART")" >/dev/null 2>&1 || true
exit "$RC"
