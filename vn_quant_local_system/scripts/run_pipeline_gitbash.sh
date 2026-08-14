#!/usr/bin/env bash
set -euo pipefail
SYSTEM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$SYSTEM_DIR/.." && pwd)"
PY="$SYSTEM_DIR/.venv/Scripts/python.exe"
[[ -f "$PY" ]] || { echo "Chưa setup. Chạy scripts/setup_and_run_gitbash.sh trước." >&2; exit 2; }
export PYTHONPATH="$SYSTEM_DIR/src:$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
cd "$SYSTEM_DIR"

SKIP_SYNC=0
[[ "${1:-}" == "--skip-sync" ]] && SKIP_SYNC=1
RUN_ID="$(date +%Y%m%d-%H%M%S)"
RUN_DIR="$SYSTEM_DIR/outputs/workstation-run-$RUN_ID"
ZIP="$SYSTEM_DIR/outputs/UPLOAD_THIS_v44_LOCAL_WORKSTATION-$RUN_ID.zip"
mkdir -p "$RUN_DIR"

"$PY" -m vn_quant_local.pipeline bootstrap > "$RUN_DIR/bootstrap.json"
if [[ "$SKIP_SYNC" -eq 0 ]]; then
  "$PY" -m vn_quant_local.pipeline sync > "$RUN_DIR/sync.json"
fi
"$PY" -m vn_quant_local.pipeline model > "$RUN_DIR/model.json"
"$PY" -m vn_quant_local.pipeline plan > "$RUN_DIR/plan.json"
"$PY" -m vn_quant_local.pipeline status > "$RUN_DIR/status.json"

powershell.exe -NoProfile -Command \
  "Compress-Archive -Path '$(cygpath -w "$RUN_DIR")\*' -DestinationPath '$(cygpath -w "$ZIP")' -Force"

echo "RUN_EXIT=0"
echo "OUTPUT_DIR=$RUN_DIR"
echo "UPLOAD_ZIP=$ZIP"
echo "UPLOAD_ZIP_WINDOWS=$(cygpath -w "$ZIP")"
echo "UPLOAD_ZIP_SHA256=$(sha256sum "$ZIP" | awk '{print $1}')"
explorer.exe "$(cygpath -w "$SYSTEM_DIR/outputs")"
