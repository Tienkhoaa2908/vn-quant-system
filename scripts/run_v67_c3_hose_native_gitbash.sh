#!/usr/bin/env bash
set -euo pipefail

BRANCH="agent/v67-c3-hose-native-research"
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
OUT="$ART/v67-c3-hose-native-$RUN_ID"
BUNDLE_DIR="$ART/v67-c3-hose-native-bundle-$RUN_ID"
BUNDLE="$ART/UPLOAD_THIS_v67_C3_HOSE_NATIVE-$RUN_ID.zip"
FAIL_BUNDLE="$ART/UPLOAD_THIS_v67_C3_HOSE_NATIVE_FAILURE-$RUN_ID.zip"
LOG="$ART/v67-c3-hose-native-$RUN_ID.log"
READINESS="$BUNDLE_DIR/data_readiness.json"
mkdir -p "$ART" "$OUT" "$BUNDLE_DIR"

# Minimal schema is captured outside the research pipeline so even an early
# Python/test failure leaves enough evidence for diagnosis.
"$PY" - "$(cygpath -w "$STORE")" "$(cygpath -w "$BUNDLE_DIR/store_schema.json")" <<'PY'
import json, sqlite3, sys
from pathlib import Path
store = Path(sys.argv[1])
out = Path(sys.argv[2])
db = sqlite3.connect(store)
try:
    tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name") if not str(r[0]).startswith('sqlite_')]
    schema = {str(t): [str(r[1]) for r in db.execute('PRAGMA table_info("' + str(t).replace('"','""') + '")')] for t in tables}
finally:
    db.close()
out.write_text(json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

# Run in a subshell with errexit enabled.  The outer shell temporarily disables
# errexit only so PIPESTATUS can be captured through tee.  This prevents a later
# successful command from masking an earlier failed test.
run_all() (
  set -euo pipefail

  echo "===== V67 C3-NATIVE HOSE RESEARCH ====="
  echo "BRANCH=$BRANCH"
  echo "HEAD=$(git rev-parse HEAD)"
  echo "STORE=$STORE"
  echo "PYTHON_ENV=vn_quant_local_system/.venv"
  echo "CHAMPION_MODEL=C3_STABLE_3_PAST_IC_SHRUNK"
  echo "CHAMPION_REPLACED=false"
  echo "TRAINING_SOURCE=LOCAL_POINT_IN_TIME_HOSE_MARKET_STORE"
  echo "V22_USED_AS_TRAINING_INPUT=false"
  echo "CHALLENGER_ML_RUN=false"
  echo "C3_TRAINING_LABEL=CLOSE_T_TO_CLOSE_T_PLUS_20"
  echo "TRADABLE_OUTCOME=NEXT_SESSION_OPEN_TO_FUTURE_OPEN"
  echo "HISTORICAL_END=2026-07-31"
  echo "ANALYSIS_END=2026-08-13"
  echo "AUGUST_2026_SHADOW_ONLY=true"
  echo "CAUSALITY=COMPLETED_SIGNAL_CLOSE_TO_NEXT_SESSION_OPEN"
  echo "LIVE_MODEL_CHANGE=false"
  echo

  echo "===== CANONICAL WORKSTATION ENVIRONMENT ====="
  "$PY" - <<'PY'
import sys
print("python=" + sys.version.replace("\n", " "))
print("executable=" + sys.executable)
PY
  echo

  echo "===== COMPILE + PURE TESTS ====="
  "$PY" -m py_compile \
    src/he_thong_dinh_luong/c3_hose_native_v67.py \
    src/he_thong_dinh_luong/c3_hose_native_driver_v67.py \
    src/he_thong_dinh_luong/hose_data_readiness_v67.py \
    tests/test_c3_hose_native_v67.py \
    tests/test_hose_data_readiness_v67.py
  "$PY" -m unittest \
    tests.test_c3_hose_native_v67 \
    tests.test_hose_data_readiness_v67 -v
  echo

  echo "===== LOCAL DATA READINESS CENSUS ====="
  CENSUS_ARGS=(
    --store "$(cygpath -w "$STORE")"
    --search-root "$(cygpath -w "$DATA_ROOT")"
    --output "$(cygpath -w "$READINESS")"
  )
  [[ -d "$VALIDATION_ROOT" ]] && CENSUS_ARGS+=(--search-root "$(cygpath -w "$VALIDATION_ROOT")")
  [[ -d "$OUTPUTS_ROOT" ]] && CENSUS_ARGS+=(--search-root "$(cygpath -w "$OUTPUTS_ROOT")")
  "$PY" -m he_thong_dinh_luong.hose_data_readiness_v67 "${CENSUS_ARGS[@]}"
  echo

  echo "===== DATA GATE CHECK ====="
  "$PY" - "$(cygpath -w "$READINESS")" <<'PY'
import json, sys
from pathlib import Path
report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
store = report.get("store", {})
scan = report.get("local_lineage_scan", {})
print("bars_first_day=" + str(store.get("bars_first_day")))
print("bars_last_day=" + str(store.get("bars_last_day")))
print("bars_unique_symbol_count=" + str(store.get("bars_unique_symbol_count")))
print("price_basis=" + json.dumps(store.get("bars_price_basis_distribution", []), ensure_ascii=False))
print("strict_local_lineage_shape_candidates=" + str(scan.get("strict_shape_candidate_count", 0)))
# The current V67 research engine can consume PIT venue metadata from the market
# DB itself.  If it is absent, stop here rather than silently using a current
# mapping; the readiness artifact tells the next repair whether a local sidecar
# source can be integrated.
tables = store.get("tables", {}) if isinstance(store.get("tables"), dict) else {}
venue_names = {"exchange","market","floor","venue","board","trading_place","stock_exchange","exchange_code","market_code","san","so_giao_dich"}
has_venue = any(any(str(col).lower() in venue_names for col in cols) for cols in tables.values())
if not has_venue:
    raise SystemExit("V67_DATA_GATE_BLOCKED:NO_POINT_IN_TIME_HOSE_VENUE_IN_MARKET_DB; inspect data_readiness.json for local sidecar candidates")
PY
  echo

  echo "===== REBUILD C3 ON POINT-IN-TIME HOSE HISTORY ====="
  "$PY" -m he_thong_dinh_luong.c3_hose_native_driver_v67 \
    --store "$(cygpath -w "$STORE")" \
    --output-dir "$(cygpath -w "$OUT")" \
    --historical-end 2026-07-31 \
    --analysis-end 2026-08-13 \
    --price-multiplier 1000
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
  echo "===== V67 COMPLETE ====="
  echo "RUN_EXIT=0"
  echo "UPLOAD_ZIP=$BUNDLE"
  echo "UPLOAD_ZIP_WINDOWS=$(cygpath -w "$BUNDLE")"
  echo "NEXT=upload bundle for deep analysis before any challenger model"
else
  echo
  echo "===== V67 FAILED / DATA GATE BLOCKED ====="
  echo "RUN_EXIT=$RC"
  echo "UPLOAD_ZIP=$FAIL_BUNDLE"
  echo "NOTE=gui failure bundle; data_readiness.json contains 11y coverage, price basis, metadata and local lineage candidates"
fi

explorer.exe "$(cygpath -w "$ART")" >/dev/null 2>&1 || true
exit "$RC"
