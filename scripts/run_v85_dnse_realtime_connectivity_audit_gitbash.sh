#!/usr/bin/env bash
set -euo pipefail

BRANCH="agent/v85-dnse-realtime-connectivity-audit"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
fail(){ echo "FAILED: $*" >&2; exit 2; }
[[ -n "$ROOT" ]] || fail "hay chay trong repository vn-quant-system"
cd "$ROOT"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "sai branch; can $BRANCH"
git diff --cached --quiet || fail "staging area co thay doi"

# Preserve the approved local web state. V85 is forensic/read-only and does not
# rewrite these files, but it intentionally scans them because /api/realtime may
# live only in the local approved patch.
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
"$PY" -c "import he_thong_dinh_luong.dnse_realtime_connectivity_audit_v85; print('V85_PYTHONPATH_PREFLIGHT=PASS')"

hash_tree(){
  local dir="$1"
  find "$dir" -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}'
}

RUN_ID="$(date +%Y%m%d-%H%M%S)"
ART="$ROOT/artifacts"
BUNDLE_DIR="$ART/v85-dnse-realtime-connectivity-audit-$RUN_ID"
BUNDLE="$ART/UPLOAD_THIS_v85_DNSE_REALTIME_CONNECTIVITY_AUDIT-$RUN_ID.zip"
REPORT="$BUNDLE_DIR/v85_realtime_connectivity_audit.json"
mkdir -p "$BUNDLE_DIR"

STORE_BEFORE="$("$PY" -m he_thong_dinh_luong.sqlite_market_fingerprint_v79 --store "$(cygpath -w "$STORE")")"
V77_BEFORE="$(hash_tree "$V77")"
V80_BEFORE="$(hash_tree "$V80")"

echo "===== V85 DNSE REALTIME CONNECTIVITY AUDIT ====="
echo "HEAD=$(git rev-parse HEAD)"
echo "WEB_URL=http://127.0.0.1:8787"
echo "AUDIT_ONLY=true"
echo "PACKAGE_INSTALL_OR_UPGRADE=false"
echo "WEB_PATCH=false"
echo "ORDERS_SENT=false"
echo "LIVE_ORDER_READY=false"
echo "V77_STATE_DIGEST_BEFORE=$V77_BEFORE"
echo "V80_STATE_DIGEST_BEFORE=$V80_BEFORE"

echo "===== COMPILE + TEST ====="
"$PY" -m py_compile \
  src/he_thong_dinh_luong/dnse_realtime_connectivity_audit_v85.py \
  tests/test_dnse_realtime_connectivity_audit_v85.py
"$PY" -m unittest tests.test_dnse_realtime_connectivity_audit_v85 -v

echo "===== FORENSIC AUDIT ====="
"$PY" -m he_thong_dinh_luong.dnse_realtime_connectivity_audit_v85 \
  --repo-root "$(cygpath -w "$ROOT")" \
  --system-root "$(cygpath -w "$SYSTEM")" \
  --output "$(cygpath -w "$REPORT")" \
  --realtime-url "http://127.0.0.1:8787/api/realtime" \
  --endpoint-samples 8 \
  --probe-rest | tee "$BUNDLE_DIR/conclusion.txt"

echo "===== SAFE SUMMARY ====="
"$PY" -c "import json,pathlib; p=json.loads(pathlib.Path(r'$(cygpath -w "$REPORT")').read_text(encoding='utf-8')); r=p['runtime']; c=p['conclusion']; print('DNSE_DISTRIBUTION_VERSION='+str(r.get('dnse_distribution_version'))); print('DNSE_SDK_OPENAPI_VERSION='+str(r.get('dnse_sdk_openapi_distribution_version'))); print('WEBSOCKETS_VERSION='+str(r.get('websockets_version'))); print('LEGACY_SDK_RECONNECT_BUG_SIGNATURE='+str(c.get('legacy_sdk_reconnect_bug_signature'))); print('LOCAL_REALTIME_DIRTY_OR_UNTRACKED='+str(c.get('local_realtime_implementation_untracked_or_dirty'))); print('LOCALHOST_REALTIME_HTTP_ALIVE='+str(c.get('localhost_realtime_http_alive'))); print('REST_CONNECTIVITY_OK='+str(c.get('rest_connectivity_ok'))); print('REST_OK_WS_UNSTABLE='+str(c.get('rest_ok_ws_unstable'))); print('MIGRATION_RECOMMENDED='+str(c.get('migration_recommended'))); print('LIVE_ORDER_READY='+str(c.get('live_order_ready')))"

echo "===== INTEGRITY ====="
STORE_AFTER="$("$PY" -m he_thong_dinh_luong.sqlite_market_fingerprint_v79 --store "$(cygpath -w "$STORE")")"
V77_AFTER="$(hash_tree "$V77")"
V80_AFTER="$(hash_tree "$V80")"
echo "STORE_LOGICAL_AFTER=$STORE_AFTER"
echo "V77_STATE_DIGEST_AFTER=$V77_AFTER"
echo "V80_STATE_DIGEST_AFTER=$V80_AFTER"
[[ "$STORE_AFTER" == "$STORE_BEFORE" ]] || fail "logical market bars changed during V85"
[[ "$V77_AFTER" == "$V77_BEFORE" ]] || fail "V77 changed during V85"
[[ "$V80_AFTER" == "$V80_BEFORE" ]] || fail "V80 changed during V85"

printf '%s\n' "$STORE_BEFORE" > "$BUNDLE_DIR/store_logical_before.json"
printf '%s\n' "$STORE_AFTER" > "$BUNDLE_DIR/store_logical_after.json"
printf '%s\n' "$V77_BEFORE" > "$BUNDLE_DIR/v77_before.txt"
printf '%s\n' "$V77_AFTER" > "$BUNDLE_DIR/v77_after.txt"
printf '%s\n' "$V80_BEFORE" > "$BUNDLE_DIR/v80_before.txt"
printf '%s\n' "$V80_AFTER" > "$BUNDLE_DIR/v80_after.txt"
git rev-parse HEAD > "$BUNDLE_DIR/git_head.txt"
git branch --show-current > "$BUNDLE_DIR/git_branch.txt"

# The bundle contains only hashes, booleans, sanitized endpoint fields and REST
# status. It never copies dnse_credentials.json or source files.
powershell.exe -NoProfile -Command "Compress-Archive -Path '$(cygpath -w "$BUNDLE_DIR")\\*' -DestinationPath '$(cygpath -w "$BUNDLE")' -Force"

echo
echo "===== V85 AUDIT COMPLETE ====="
echo "UPLOAD_ZIP=$BUNDLE"
echo "UPLOAD_ZIP_SHA256=$(sha256sum "$BUNDLE" | awk '{print $1}')"
echo "Do NOT install/upgrade DNSE packages in the canonical .venv yet."
