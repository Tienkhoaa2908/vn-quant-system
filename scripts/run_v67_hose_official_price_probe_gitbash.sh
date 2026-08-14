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
OUT="$ART/v67-hose-official-price-probe-$RUN_ID"
BUNDLE_DIR="$ART/v67-hose-official-price-probe-bundle-$RUN_ID"
BUNDLE="$ART/UPLOAD_THIS_v67_HOSE_OFFICIAL_PRICE_PROBE-$RUN_ID.zip"
LOG="$ART/v67-hose-official-price-probe-$RUN_ID.log"
mkdir -p "$ART" "$OUT" "$BUNDLE_DIR"

run_all() (
  set -euo pipefail

  echo "===== V67 HOSE OFFICIAL + PRICE-BASIS PROBE ====="
  echo "BRANCH=$BRANCH"
  echo "HEAD=$(git rev-parse HEAD)"
  echo "PYTHON_ENV=vn_quant_local_system/.venv"
  echo "STORE=$STORE"
  echo "MODEL_TRAINING_RUN=false"
  echo "C3_CHAMPION_CHANGED=false"
  echo "STORE_MUTATION_ALLOWED=false"
  echo "NETWORK_SCOPE=HOSE_OFFICIAL_PUBLIC_METADATA_ONLY"
  echo "TRAINING_AUTHORIZED=false"
  echo

  echo "===== COMPILE + PROBE TESTS ====="
  "$PY" -m py_compile \
    src/he_thong_dinh_luong/hose_lineage_price_probe_v67.py \
    tests/test_hose_lineage_price_probe_v67.py
  "$PY" -m unittest tests.test_hose_lineage_price_probe_v67 -v
  echo

  echo "===== OFFICIAL HOSE LINEAGE + LOCAL GAP AUDIT ====="
  "$PY" -m he_thong_dinh_luong.hose_lineage_price_probe_v67 \
    --store "$(cygpath -w "$STORE")" \
    --output-dir "$(cygpath -w "$OUT")" \
    --timeout 35
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

powershell.exe -NoProfile -Command \
  "Compress-Archive -Path '$(cygpath -w "$BUNDLE_DIR")\*' -DestinationPath '$(cygpath -w "$BUNDLE")' -Force" || true

echo
if [[ "$RC" -eq 0 ]]; then
  echo "===== V67 PROBE COMPLETE ====="
  echo "RUN_EXIT=0"
else
  echo "===== V67 PROBE FAILED ====="
  echo "RUN_EXIT=$RC"
  echo "NOTE=van gui bundle; network/parse/test evidence nam trong run.log va output neu co"
fi
echo "UPLOAD_ZIP=$BUNDLE"
echo "UPLOAD_ZIP_WINDOWS=$(cygpath -w "$BUNDLE")"
echo "NEXT=upload bundle; do not run C3 until HOSE PIT and price-basis gates are closed"

explorer.exe "$(cygpath -w "$ART")" >/dev/null 2>&1 || true
exit "$RC"
