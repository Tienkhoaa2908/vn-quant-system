#!/usr/bin/env bash
set -euo pipefail

BRANCH="agent/v84-main-web-operating-dashboard"
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
    *) fail "tracked change ngoai approved workstation web state: $path" ;;
  esac
done

SYSTEM="$ROOT/vn_quant_local_system"
PY="$SYSTEM/.venv/Scripts/python.exe"
STORE="$SYSTEM/data/market/dnse_ohlcv.sqlite3"
V77="$ROOT/du_lieu/v77-paper-oos-state"
V80="$ROOT/du_lieu/v80-tactical-paper-state"
[[ -f "$PY" ]] || fail "khong tim thay canonical workstation Python"
[[ -f "$STORE" ]] || fail "khong tim thay market DB"
[[ -f "$V77/freeze_manifest.json" ]] || fail "khong tim thay V77 state"
[[ -f "$V80/registry.json" ]] || fail "khong tim thay V80 state"
command -v cygpath >/dev/null 2>&1 || fail "Git Bash cygpath khong san sang"

export PYTHONPATH="$(cygpath -w "$ROOT/src");$(cygpath -w "$SYSTEM/src")"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
"$PY" -c "import he_thong_dinh_luong.existing_web_v84_installer; print('V84_PYTHONPATH_PREFLIGHT=PASS')"

hash_tree(){
  local dir="$1"
  find "$dir" -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}'
}
RUN_ID="$(date +%Y%m%d-%H%M%S)"
ART="$ROOT/artifacts"
BUNDLE_DIR="$ART/v84-main-operating-web-bundle-$RUN_ID"
BUNDLE="$ART/UPLOAD_THIS_v84_MAIN_OPERATING_WEB-$RUN_ID.zip"
mkdir -p "$BUNDLE_DIR"

STORE_BEFORE="$("$PY" -m he_thong_dinh_luong.sqlite_market_fingerprint_v79 --store "$(cygpath -w "$STORE")")"
V77_BEFORE="$(hash_tree "$V77")"
V80_BEFORE="$(hash_tree "$V80")"
echo "===== V84 MAIN DAILY OPERATING WEB ====="
echo "HEAD=$(git rev-parse HEAD)"
echo "EXISTING_WEB_PORT=8787"
echo "RESEARCH_REOPENED=false"
echo "NEW_API_ENDPOINT_ADDED=false"
echo "LIVE_ORDERS_ALLOWED=false"
echo "V77_STATE_DIGEST_BEFORE=$V77_BEFORE"
echo "V80_STATE_DIGEST_BEFORE=$V80_BEFORE"

echo "===== COMPILE + CONTRACT ====="
"$PY" -m py_compile src/he_thong_dinh_luong/existing_web_v84_installer.py tests/test_existing_web_v84_installer.py
"$PY" -m unittest tests.test_existing_web_v84_installer -v

echo "===== INSTALL V84 MAIN WEB ====="
"$PY" -m he_thong_dinh_luong.existing_web_v84_installer \
  --system-root "$(cygpath -w "$SYSTEM")" \
  --assets-root "$(cygpath -w "$ROOT/web_extensions/v84")" | tee "$BUNDLE_DIR/install_report.txt"
cp "$SYSTEM/validation/v84_web_integration_report.json" "$BUNDLE_DIR/" || true

echo "===== INTEGRITY ====="
STORE_AFTER="$("$PY" -m he_thong_dinh_luong.sqlite_market_fingerprint_v79 --store "$(cygpath -w "$STORE")")"
V77_AFTER="$(hash_tree "$V77")"
V80_AFTER="$(hash_tree "$V80")"
echo "STORE_LOGICAL_AFTER=$STORE_AFTER"
echo "V77_STATE_DIGEST_AFTER=$V77_AFTER"
echo "V80_STATE_DIGEST_AFTER=$V80_AFTER"
[[ "$STORE_AFTER" == "$STORE_BEFORE" ]] || fail "logical market bars changed during V84"
[[ "$V77_AFTER" == "$V77_BEFORE" ]] || fail "V77 changed during V84"
[[ "$V80_AFTER" == "$V80_BEFORE" ]] || fail "V80 changed during V84"

printf '%s\n' "$STORE_BEFORE" > "$BUNDLE_DIR/store_logical_before.json"
printf '%s\n' "$STORE_AFTER" > "$BUNDLE_DIR/store_logical_after.json"
printf '%s\n' "$V77_BEFORE" > "$BUNDLE_DIR/v77_before.txt"
printf '%s\n' "$V77_AFTER" > "$BUNDLE_DIR/v77_after.txt"
printf '%s\n' "$V80_BEFORE" > "$BUNDLE_DIR/v80_before.txt"
printf '%s\n' "$V80_AFTER" > "$BUNDLE_DIR/v80_after.txt"
git rev-parse HEAD > "$BUNDLE_DIR/git_head.txt"
git branch --show-current > "$BUNDLE_DIR/git_branch.txt"
powershell.exe -NoProfile -Command "Compress-Archive -Path '$(cygpath -w "$BUNDLE_DIR")\\*' -DestinationPath '$(cygpath -w "$BUNDLE")' -Force"

echo
echo "===== V84 WEB COMPLETE ====="
echo "WEB_URL=http://127.0.0.1:8787"
echo "UPLOAD_ZIP=$BUNDLE"
echo "UPLOAD_ZIP_SHA256=$(sha256sum "$BUNDLE" | awk '{print $1}')"
echo "Restart existing web server so the V84 static assets are loaded."
