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
mkdir -p "$ART" "$OUT" "$BUNDLE_DIR"

# Always capture schema before research so a fail-closed HOSE-lineage blocker is diagnosable.
"$PY" - "$(cygpath -w "$STORE")" "$BUNDLE_DIR/store_schema.json" <<'PY'
import json, sqlite3, sys
from pathlib import Path
store = Path(sys.argv[1])
out = Path(sys.argv[2])
with sqlite3.connect(store) as db:
    tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name") if not str(r[0]).startswith('sqlite_')]
    schema = {str(t): [str(r[1]) for r in db.execute('PRAGMA table_info("' + str(t).replace('"','""') + '")')] for t in tables}
out.write_text(json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

run_all(){
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
    tests/test_c3_hose_native_v67.py
  "$PY" -m unittest tests.test_c3_hose_native_v67 -v
  echo

  echo "===== REBUILD C3 ON POINT-IN-TIME HOSE HISTORY ====="
  "$PY" -m he_thong_dinh_luong.c3_hose_native_driver_v67 \
    --store "$(cygpath -w "$STORE")" \
    --output-dir "$(cygpath -w "$OUT")" \
    --historical-end 2026-07-31 \
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
  echo "===== V67 FAILED ====="
  echo "RUN_EXIT=$RC"
  echo "UPLOAD_ZIP=$FAIL_BUNDLE"
  echo "NOTE=gui failure bundle; neu exchange lineage thieu thi fail-closed, khong duoc dung static HOSE mapping"
fi

explorer.exe "$(cygpath -w "$ART")" >/dev/null 2>&1 || true
exit "$RC"
