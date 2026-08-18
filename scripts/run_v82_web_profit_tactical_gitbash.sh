#!/usr/bin/env bash
set -euo pipefail

BRANCH="agent/v82-web-profit-tactical-dashboard"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
fail(){ echo "FAILED: $*" >&2; exit 2; }
[[ -n "$ROOT" ]] || fail "hay chay trong repository vn-quant-system"
cd "$ROOT"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "sai branch; can $BRANCH"
git diff --cached --quiet || fail "staging area co thay doi"

WEBAPP="vn_quant_local_system/src/vn_quant_local/webapp.py"
INDEX="vn_quant_local_system/web/index.html"
mapfile -t DIRTY < <(git diff --name-only --)
for path in "${DIRTY[@]}"; do
  case "$path" in
    "$WEBAPP"|"$INDEX") ;;
    *) fail "tracked change ngoai approved web state: $path" ;;
  esac
done

PY="$ROOT/vn_quant_local_system/.venv/Scripts/python.exe"
[[ -f "$PY" ]] || fail "khong tim thay canonical workstation Python"
command -v cygpath >/dev/null 2>&1 || fail "Git Bash cygpath khong san sang"
if ! "$PY" - <<'PY' >/dev/null 2>&1
from zoneinfo import ZoneInfo
ZoneInfo("Asia/Ho_Chi_Minh")
PY
then
  echo "DEPENDENCY_tzdata=installing_tzdata==2025.2"
  "$PY" -m pip install --disable-pip-version-check "tzdata==2025.2"
else
  echo "DEPENDENCY_tzdata=already_verified"
fi
PYTHONPATH_WIN="$(cygpath -w "$ROOT/src");$(cygpath -w "$ROOT/vn_quant_local_system/src")"
export PYTHONPATH="$PYTHONPATH_WIN"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
"$PY" -c "import he_thong_dinh_luong.local_workstation_v82_bridge, vn_quant_local.webapp; print('V82_PYTHONPATH_PREFLIGHT=PASS')"

state_digest(){
  local dir="$1"
  if [[ ! -d "$dir" ]]; then printf 'MISSING\n'; return; fi
  find "$dir" -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}'
}
V77="$ROOT/du_lieu/v77-paper-oos-state"
V80="$ROOT/du_lieu/v80-tactical-paper-state"
V77_BEFORE="$(state_digest "$V77")"
V80_BEFORE="$(state_digest "$V80")"

echo "===== V82 ADDITIVE APPROVED WEB PROFIT + PAPER ====="
echo "HEAD=$(git rev-parse HEAD)"
echo "EXISTING_WEB_PORT=8787"
echo "V77_STATE_DIGEST_BEFORE=$V77_BEFORE"
echo "V80_STATE_DIGEST_BEFORE=$V80_BEFORE"

echo "===== COMPILE + TEST ====="
"$PY" -m py_compile \
  src/he_thong_dinh_luong/local_workstation_v78_bridge.py \
  src/he_thong_dinh_luong/local_workstation_v82_bridge.py \
  src/he_thong_dinh_luong/existing_web_v78_installer.py \
  src/he_thong_dinh_luong/existing_web_v82_installer.py \
  tests/test_local_workstation_v82_bridge.py \
  tests/test_existing_web_v82_installer.py
"$PY" -m unittest tests.test_local_workstation_v82_bridge tests.test_existing_web_v82_installer -v

echo "===== INSTALL ADDITIVE V82 ====="
"$PY" -m he_thong_dinh_luong.existing_web_v82_installer \
  --system-root "$(cygpath -w "$ROOT/vn_quant_local_system")" \
  --assets-root "$(cygpath -w "$ROOT/web_extensions/v82")"

grep -q 'V78_TACTICAL_BRIDGE_IMPORT' "$WEBAPP" || fail "V78 bridge marker missing after install"
grep -q 'V82_PROFIT_PAPER_BRIDGE_IMPORT' "$WEBAPP" || fail "V82 bridge marker missing after install"
grep -q 'V78_TACTICAL_EXISTING_WEB' "$INDEX" || fail "V78 index marker missing after install"
grep -q 'V82_PROFIT_PAPER_EXISTING_WEB' "$INDEX" || fail "V82 index marker missing after install"
[[ -f "$ROOT/vn_quant_local_system/web/tactical_profit_v82.js" ]] || fail "V82 JS asset missing"
[[ -f "$ROOT/vn_quant_local_system/web/tactical_profit_v82.css" ]] || fail "V82 CSS asset missing"

V77_AFTER="$(state_digest "$V77")"
V80_AFTER="$(state_digest "$V80")"
echo "V77_STATE_DIGEST_AFTER=$V77_AFTER"
echo "V80_STATE_DIGEST_AFTER=$V80_AFTER"
[[ "$V77_AFTER" == "$V77_BEFORE" ]] || fail "V77 state changed during web install"
[[ "$V80_AFTER" == "$V80_BEFORE" ]] || fail "V80 state changed during web install"

echo "===== V82 WEB INSTALL COMPLETE ====="
echo "WEB_URL=http://127.0.0.1:8787"
echo "If the web server was already running, stop it with Ctrl+C and rerun the existing vn_quant_local_system/scripts/run_web_gitbash.sh so the new Python endpoint is loaded."
