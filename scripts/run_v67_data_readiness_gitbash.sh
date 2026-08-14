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
BUNDLE_DIR="$ART/v67-data-readiness-bundle-$RUN_ID"
BUNDLE="$ART/UPLOAD_THIS_v67_DATA_READINESS-$RUN_ID.zip"
LOG="$BUNDLE_DIR/run.log"
READINESS="$BUNDLE_DIR/data_readiness.json"
mkdir -p "$BUNDLE_DIR"

{
  echo "===== V67 DATA READINESS ONLY ====="
  echo "BRANCH=$BRANCH"
  echo "HEAD=$(git rev-parse HEAD)"
  echo "PYTHON_ENV=vn_quant_local_system/.venv"
  echo "STORE=$STORE"
  echo "MODEL_TRAINING_RUN=false"
  echo "C3_CHAMPION_CHANGED=false"
  echo "NETWORK_USED=false"
  echo "STORE_MUTATION_ALLOWED=false"
  echo

  CENSUS_ARGS=(
    --store "$(cygpath -w "$STORE")"
    --search-root "$(cygpath -w "$DATA_ROOT")"
    --output "$(cygpath -w "$READINESS")"
  )
  [[ -d "$VALIDATION_ROOT" ]] && CENSUS_ARGS+=(--search-root "$(cygpath -w "$VALIDATION_ROOT")")
  [[ -d "$OUTPUTS_ROOT" ]] && CENSUS_ARGS+=(--search-root "$(cygpath -w "$OUTPUTS_ROOT")")

  "$PY" -m he_thong_dinh_luong.hose_data_readiness_v67 "${CENSUS_ARGS[@]}"
  echo
  echo "===== READINESS SUMMARY ====="
  "$PY" - "$(cygpath -w "$READINESS")" <<'PY'
import json, sys
from pathlib import Path
report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
store = report.get("store", {})
scan = report.get("local_lineage_scan", {})
gates = report.get("gates", {})
print("bars_first_day=" + str(store.get("bars_first_day")))
print("bars_last_day=" + str(store.get("bars_last_day")))
print("bars_row_count=" + str(store.get("bars_row_count")))
print("bars_unique_symbol_count=" + str(store.get("bars_unique_symbol_count")))
print("bars_by_asset_type=" + json.dumps(store.get("bars_by_asset_type", []), ensure_ascii=False))
print("price_basis=" + json.dumps(store.get("bars_price_basis_distribution", []), ensure_ascii=False))
print("source=" + json.dumps(store.get("bars_source_distribution", []), ensure_ascii=False))
print("source_version=" + json.dumps(store.get("bars_source_version_distribution", []), ensure_ascii=False))
print("exchange_lineage_in_store=" + str(gates.get("exchange_lineage_in_store")))
print("strict_local_lineage_shape_candidates=" + str(scan.get("strict_shape_candidate_count", 0)))
for item in scan.get("strict_shape_candidates", []):
    print("LINEAGE_CANDIDATE=" + json.dumps(item, ensure_ascii=False, sort_keys=True))
PY
} 2>&1 | tee "$LOG"

git branch --show-current > "$BUNDLE_DIR/git_branch.txt"
git rev-parse HEAD > "$BUNDLE_DIR/git_head.txt"
sha256sum "$STORE" > "$BUNDLE_DIR/store_sha256.txt"
"$PY" - <<'PY' > "$BUNDLE_DIR/python_version.txt"
import sys
print(sys.version.replace("\n", " "))
print(sys.executable)
PY

powershell.exe -NoProfile -Command \
  "Compress-Archive -Path '$(cygpath -w "$BUNDLE_DIR")\\*' -DestinationPath '$(cygpath -w "$BUNDLE")' -Force"

echo
echo "===== V67 DATA READINESS COMPLETE ====="
echo "UPLOAD_ZIP=$BUNDLE"
echo "UPLOAD_ZIP_WINDOWS=$(cygpath -w "$BUNDLE")"
echo "NEXT=upload this bundle; do not run C3 training until HOSE lineage and price basis are audited"
explorer.exe "$(cygpath -w "$ART")" >/dev/null 2>&1 || true
