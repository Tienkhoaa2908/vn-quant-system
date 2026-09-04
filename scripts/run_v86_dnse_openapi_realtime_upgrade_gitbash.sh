#!/usr/bin/env bash
set -euo pipefail

BRANCH="agent/v86-dnse-openapi-realtime-hardening"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
fail(){ echo "FAILED: $*" >&2; exit 2; }
[[ -n "$ROOT" ]] || fail "hay chay trong repository vn-quant-system"
cd "$ROOT"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "sai branch; can $BRANCH"
git diff --cached --quiet || fail "staging area co thay doi"

SYSTEM="$ROOT/vn_quant_local_system"
CANON_PY="$SYSTEM/.venv/Scripts/python.exe"
SIDE_ENV="$SYSTEM/.venv-dnse-openapi-v86"
SIDE_PY="$SIDE_ENV/Scripts/python.exe"
STORE="$SYSTEM/data/market/dnse_ohlcv.sqlite3"
CREDS="$SYSTEM/data/state/dnse_credentials.json"
STATE="$SYSTEM/data/state/dnse_realtime_v86.json"
SYMBOLS="$SYSTEM/data/state/dnse_realtime_v86_symbols.json"
V77="$ROOT/du_lieu/v77-paper-oos-state"
V80="$ROOT/du_lieu/v80-tactical-paper-state"
WEBAPP="vn_quant_local_system/src/vn_quant_local/webapp.py"
INDEX="vn_quant_local_system/web/index.html"

[[ -f "$CANON_PY" ]] || fail "khong tim thay canonical Python"
[[ -f "$STORE" ]] || fail "khong tim thay market store"
[[ -f "$CREDS" ]] || fail "khong tim thay DNSE credentials local"
[[ -f "$V77/freeze_manifest.json" ]] || fail "khong tim thay V77 state"
[[ -f "$V80/registry.json" ]] || fail "khong tim thay V80 state"
command -v cygpath >/dev/null 2>&1 || fail "Git Bash cygpath khong san sang"

mapfile -t DIRTY < <(git diff --name-only --)
for path in "${DIRTY[@]}"; do
  case "$path" in
    "$WEBAPP"|"$INDEX") ;;
    *) fail "tracked change ngoai approved workstation web state: $path" ;;
  esac
done

ROOT_W="$(cygpath -w "$ROOT")"
SYSTEM_W="$(cygpath -w "$SYSTEM")"
STORE_W="$(cygpath -w "$STORE")"
CREDS_W="$(cygpath -w "$CREDS")"
STATE_W="$(cygpath -w "$STATE")"
SYMBOLS_W="$(cygpath -w "$SYMBOLS")"
PY_CANON_PATH="$(cygpath -w "$ROOT/src");$(cygpath -w "$SYSTEM/src")"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

hash_tree(){
  local dir="$1"
  find "$dir" -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}'
}

RUN_ID="$(date +%Y%m%d-%H%M%S)"
ART="$ROOT/artifacts"
BUNDLE_DIR="$ART/v86-dnse-openapi-realtime-bundle-$RUN_ID"
BUNDLE="$ART/UPLOAD_THIS_v86_DNSE_OPENAPI_REALTIME-$RUN_ID.zip"
mkdir -p "$BUNDLE_DIR"

STORE_BEFORE="$(PYTHONPATH="$PY_CANON_PATH" "$CANON_PY" -m he_thong_dinh_luong.sqlite_market_fingerprint_v79 --store "$STORE_W")"
V77_BEFORE="$(hash_tree "$V77")"
V80_BEFORE="$(hash_tree "$V80")"
CANON_DNSE_BEFORE="$("$CANON_PY" -c "from importlib import metadata; print(metadata.version('dnse'))")"
[[ "$CANON_DNSE_BEFORE" == "0.5.0" ]] || fail "canonical dnse drift: $CANON_DNSE_BEFORE"

echo "===== V86 DNSE OPENAPI REALTIME HARDENING ====="
echo "HEAD=$(git rev-parse HEAD)"
echo "CANONICAL_DNSE_BEFORE=$CANON_DNSE_BEFORE"
echo "SIDE_ENV=$SIDE_ENV"
echo "SDK_NEW_PIN=dnse-sdk-openapi==1.4.6"
echo "REST_API_VERSION_PIN=2026-05-07"
echo "USER_WEB_PORT=8787"
echo "PRIVATE_ORDER_STREAM=false"
echo "PRIVATE_POSITION_STREAM=false"
echo "TRADING_TOKEN_REQUESTED=false"
echo "ORDER_MUTATION=false"
echo "LIVE_ORDER_READY=false"
echo "V77_STATE_DIGEST_BEFORE=$V77_BEFORE"
echo "V80_STATE_DIGEST_BEFORE=$V80_BEFORE"

if [[ ! -f "$SIDE_PY" ]]; then
  echo "===== CREATE ISOLATED SIDECAR ENV ====="
  "$CANON_PY" -m venv "$SYSTEM_W/.venv-dnse-openapi-v86"
fi
[[ -f "$SIDE_PY" ]] || fail "khong tao duoc sidecar env"

echo "===== INSTALL/VERIFY ISOLATED SDK ====="
"$SIDE_PY" -m pip install --disable-pip-version-check --no-input --upgrade pip
"$SIDE_PY" -m pip install --disable-pip-version-check --no-input \
  "dnse-sdk-openapi==1.4.6" \
  "tzdata==2025.2" \
  "websockets>=15,<18" \
  "msgpack>=1,<2" \
  "urllib3>=2,<3" \
  "certifi>=2025.1.31"
"$SIDE_PY" -m pip check
"$SIDE_PY" -m pip freeze | sort > "$BUNDLE_DIR/sidecar_pip_freeze.txt"
"$SIDE_PY" - <<'PY' > "$BUNDLE_DIR/sidecar_runtime.json"
from importlib import metadata, util
import hashlib, json
from pathlib import Path
import dnse
version = metadata.version("dnse-sdk-openapi")
legacy = None
try:
    legacy = metadata.version("dnse")
except metadata.PackageNotFoundError:
    pass
root = Path(dnse.__file__).resolve().parent
h = hashlib.sha256()
for path in sorted(p for p in root.rglob("*") if p.is_file()):
    h.update(str(path.relative_to(root)).encode())
    h.update(path.read_bytes())
print(json.dumps({
    "dnse_sdk_openapi": version,
    "legacy_dnse_distribution": legacy,
    "dnse_module": str(Path(dnse.__file__).resolve()),
    "dnse_module_tree_sha256": h.hexdigest(),
    "trading_client_available": hasattr(dnse, "TradingClient"),
    "dnse_client_available": hasattr(dnse, "DNSEClient"),
}, indent=2, sort_keys=True))
PY
SIDE_VERSION="$("$SIDE_PY" -c "from importlib import metadata; print(metadata.version('dnse-sdk-openapi'))")"
[[ "$SIDE_VERSION" == "1.4.6" ]] || fail "sidecar sdk mismatch $SIDE_VERSION"
if "$SIDE_PY" -c "from importlib import metadata; metadata.version('dnse')" >/dev/null 2>&1; then
  fail "sidecar env bi contaminate boi legacy distribution dnse"
fi

CANON_DNSE_MID="$("$CANON_PY" -c "from importlib import metadata; print(metadata.version('dnse'))")"
[[ "$CANON_DNSE_MID" == "$CANON_DNSE_BEFORE" ]] || fail "canonical .venv bi thay doi"
echo "CANONICAL_ENV_ISOLATION=PASS"
echo "SIDECAR_SDK_VERSION=$SIDE_VERSION"

# Build subscription symbols from the already-approved local portfolio + preview logic.
echo "===== FREEZE SIDECAR SYMBOL SET ====="
PYTHONPATH="$PY_CANON_PATH" "$CANON_PY" - <<PY
import json
from pathlib import Path
from vn_quant_local.v59_market_stream import desired_symbols_v59
symbols = list(desired_symbols_v59())
if not symbols:
    raise SystemExit("V86_DESIRED_SYMBOLS_EMPTY")
path = Path(r"$SYMBOLS_W")
path.parent.mkdir(parents=True, exist_ok=True)
tmp = path.with_suffix(path.suffix + ".tmp")
tmp.write_text(json.dumps({"version":"V86","symbols":symbols}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
tmp.replace(path)
print("V86_SYMBOL_COUNT=" + str(len(symbols)))
print("V86_SYMBOLS=" + ",".join(symbols))
PY
cp "$SYMBOLS" "$BUNDLE_DIR/symbols.json"

# Compile/contracts in canonical env; no SDK import is required by unit tests.
echo "===== COMPILE + CONTRACT ====="
PYTHONPATH="$PY_CANON_PATH" "$CANON_PY" -m py_compile \
  src/he_thong_dinh_luong/dnse_openapi_sidecar_v86.py \
  src/he_thong_dinh_luong/local_workstation_v86_bridge.py \
  src/he_thong_dinh_luong/existing_web_v86_installer.py \
  tests/test_dnse_openapi_sidecar_v86.py \
  tests/test_local_workstation_v86_bridge.py \
  tests/test_existing_web_v86_installer.py
PYTHONPATH="$PY_CANON_PATH" "$CANON_PY" -m unittest \
  tests.test_dnse_openapi_sidecar_v86 \
  tests.test_local_workstation_v86_bridge \
  tests.test_existing_web_v86_installer -v

# Real read-only smoke. The process runs long enough for connect/auth/subscribe and state capture.
echo "===== REAL OPENAPI REST + WS SMOKE (READ ONLY) ====="
SIDE_PY_W="$(cygpath -w "$SIDE_PY")"
PY_SIDE_PATH="$(cygpath -w "$ROOT/src")"
rm -f "$STATE"
PYTHONPATH="$PY_SIDE_PATH" "$SIDE_PY" -m he_thong_dinh_luong.dnse_openapi_sidecar_v86 \
  --credentials "$CREDS_W" \
  --symbols-file "$SYMBOLS_W" \
  --state "$STATE_W" \
  --duration 20 \
  --encoding msgpack \
  --rest-smoke &
SMOKE_PID=$!
ACTIVE_CAPTURED=false
for _ in $(seq 1 18); do
  sleep 1
  if [[ -f "$STATE" ]] && "$CANON_PY" - <<PY >/dev/null 2>&1
import json
from pathlib import Path
p=Path(r"$STATE_W")
d=json.loads(p.read_text(encoding="utf-8"))
assert d.get("process_alive") is True
assert d.get("transport_connected") is True
assert d.get("authenticated") is True
assert d.get("subscriptions_active") is True
assert d.get("heartbeat_healthy") is True
assert d.get("rest_smoke",{}).get("status") == "SUCCESS"
assert d.get("live_order_ready") is False
PY
  then
    cp "$STATE" "$BUNDLE_DIR/active_sidecar_state.json"
    ACTIVE_CAPTURED=true
    break
  fi
done
wait "$SMOKE_PID" || fail "V86 sidecar live smoke failed"
[[ "$ACTIVE_CAPTURED" == "true" ]] || fail "sidecar khong dat active health trong smoke window"
cp "$STATE" "$BUNDLE_DIR/final_sidecar_state.json"
"$CANON_PY" - <<PY
import json
from pathlib import Path
d=json.loads(Path(r"$BUNDLE_DIR/active_sidecar_state.json").read_text(encoding="utf-8"))
print("V86_SMOKE_STATUS=" + str(d.get("status")))
print("V86_TRANSPORT_CONNECTED=" + str(d.get("transport_connected")))
print("V86_AUTHENTICATED=" + str(d.get("authenticated")))
print("V86_SUBSCRIPTIONS_ACTIVE=" + str(d.get("subscriptions_active")))
print("V86_HEARTBEAT_HEALTHY=" + str(d.get("heartbeat_healthy")))
print("V86_EVENT_COUNT=" + str(d.get("event_count")))
print("V86_RECONNECT_COUNT=" + str(d.get("reconnect_count")))
print("V86_REST_SMOKE=" + str(d.get("rest_smoke",{}).get("status")))
print("V86_LIVE_ORDER_READY=" + str(d.get("live_order_ready")))
PY

# Patch only the approved local web. A restart is required after the installer.
echo "===== INSTALL V86 REALTIME HEALTH INTO WEB 8787 ====="
PYTHONPATH="$PY_CANON_PATH" "$CANON_PY" -m he_thong_dinh_luong.existing_web_v86_installer \
  --system-root "$SYSTEM_W" \
  --assets-root "$(cygpath -w "$ROOT/web_extensions/v86")" | tee "$BUNDLE_DIR/install_report.txt"
cp "$SYSTEM/validation/v86_web_integration_report.json" "$BUNDLE_DIR/" || true

# Integrity: research/paper/market and canonical package must remain unchanged.
echo "===== INTEGRITY ====="
STORE_AFTER="$(PYTHONPATH="$PY_CANON_PATH" "$CANON_PY" -m he_thong_dinh_luong.sqlite_market_fingerprint_v79 --store "$STORE_W")"
V77_AFTER="$(hash_tree "$V77")"
V80_AFTER="$(hash_tree "$V80")"
CANON_DNSE_AFTER="$("$CANON_PY" -c "from importlib import metadata; print(metadata.version('dnse'))")"
[[ "$STORE_AFTER" == "$STORE_BEFORE" ]] || fail "logical market bars changed during V86"
[[ "$V77_AFTER" == "$V77_BEFORE" ]] || fail "V77 changed during V86"
[[ "$V80_AFTER" == "$V80_BEFORE" ]] || fail "V80 changed during V86"
[[ "$CANON_DNSE_AFTER" == "$CANON_DNSE_BEFORE" ]] || fail "canonical dnse changed during V86"
echo "CANONICAL_DNSE_AFTER=$CANON_DNSE_AFTER"
echo "V77_STATE_DIGEST_AFTER=$V77_AFTER"
echo "V80_STATE_DIGEST_AFTER=$V80_AFTER"

printf '%s\n' "$STORE_BEFORE" > "$BUNDLE_DIR/store_logical_before.json"
printf '%s\n' "$STORE_AFTER" > "$BUNDLE_DIR/store_logical_after.json"
printf '%s\n' "$V77_BEFORE" > "$BUNDLE_DIR/v77_before.txt"
printf '%s\n' "$V77_AFTER" > "$BUNDLE_DIR/v77_after.txt"
printf '%s\n' "$V80_BEFORE" > "$BUNDLE_DIR/v80_before.txt"
printf '%s\n' "$V80_AFTER" > "$BUNDLE_DIR/v80_after.txt"
printf '%s\n' "$CANON_DNSE_BEFORE" > "$BUNDLE_DIR/canonical_dnse_before.txt"
printf '%s\n' "$CANON_DNSE_AFTER" > "$BUNDLE_DIR/canonical_dnse_after.txt"
git rev-parse HEAD > "$BUNDLE_DIR/git_head.txt"
git branch --show-current > "$BUNDLE_DIR/git_branch.txt"
powershell.exe -NoProfile -Command "Compress-Archive -Path '$(cygpath -w "$BUNDLE_DIR")\\*' -DestinationPath '$(cygpath -w "$BUNDLE")' -Force"

echo
echo "===== V86 COMPLETE ====="
echo "WEB_URL=http://127.0.0.1:8787"
echo "SIDECAR_ENV=$SIDE_ENV"
echo "SIDECAR_STATE=$STATE"
echo "UPLOAD_ZIP=$BUNDLE"
echo "UPLOAD_ZIP_SHA256=$(sha256sum "$BUNDLE" | awk '{print $1}')"
echo "NEXT: restart web, then run scripts/run_v86_dnse_openapi_realtime_sidecar_gitbash.sh in a separate Git Bash terminal."
