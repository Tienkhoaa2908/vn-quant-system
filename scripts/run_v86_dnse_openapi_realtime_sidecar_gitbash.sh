#!/usr/bin/env bash
set -euo pipefail

BRANCH="agent/v86-dnse-openapi-realtime-hardening"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
fail(){ echo "FAILED: $*" >&2; exit 2; }
[[ -n "$ROOT" ]] || fail "hay chay trong repository vn-quant-system"
cd "$ROOT"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "sai branch; can $BRANCH"

SYSTEM="$ROOT/vn_quant_local_system"
CANON_PY="$SYSTEM/.venv/Scripts/python.exe"
SIDE_PY="$SYSTEM/.venv-dnse-openapi-v86/Scripts/python.exe"
CREDS="$SYSTEM/data/state/dnse_credentials.json"
STATE="$SYSTEM/data/state/dnse_realtime_v86.json"
SYMBOLS="$SYSTEM/data/state/dnse_realtime_v86_symbols.json"
[[ -f "$CANON_PY" ]] || fail "khong tim thay canonical Python"
[[ -f "$SIDE_PY" ]] || fail "chua co V86 sidecar env; chay one-shot upgrade truoc"
[[ -f "$CREDS" ]] || fail "khong tim thay DNSE credentials"
command -v cygpath >/dev/null 2>&1 || fail "Git Bash cygpath khong san sang"

export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
PY_CANON_PATH="$(cygpath -w "$ROOT/src");$(cygpath -w "$SYSTEM/src")"
PY_SIDE_PATH="$(cygpath -w "$ROOT/src")"

CANON_VERSION="$("$CANON_PY" -c "from importlib import metadata; print(metadata.version('dnse'))")"
SIDE_VERSION="$("$SIDE_PY" -c "from importlib import metadata; print(metadata.version('dnse-sdk-openapi'))")"
[[ "$CANON_VERSION" == "0.5.0" ]] || fail "canonical dnse drift $CANON_VERSION"
[[ "$SIDE_VERSION" == "1.4.6" ]] || fail "sidecar SDK drift $SIDE_VERSION"
if "$SIDE_PY" -c "from importlib import metadata; metadata.version('dnse')" >/dev/null 2>&1; then
  fail "sidecar env chua legacy dnse; khong dat isolation contract"
fi

PYTHONPATH="$PY_CANON_PATH" "$CANON_PY" - <<PY
import json
from pathlib import Path
from vn_quant_local.v59_market_stream import desired_symbols_v59
symbols=list(desired_symbols_v59())
if not symbols:
    raise SystemExit("V86_DESIRED_SYMBOLS_EMPTY")
p=Path(r"$(cygpath -w "$SYMBOLS")")
p.parent.mkdir(parents=True, exist_ok=True)
t=p.with_suffix(p.suffix+".tmp")
t.write_text(json.dumps({"version":"V86","symbols":symbols},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
t.replace(p)
print("V86_SYMBOL_COUNT="+str(len(symbols)))
print("V86_SYMBOLS="+",".join(symbols))
PY

echo "===== V86 LONG-LIVED DNSE OPENAPI SIDECAR ====="
echo "CANONICAL_DNSE=$CANON_VERSION"
echo "SIDECAR_DNSE_OPENAPI=$SIDE_VERSION"
echo "REST_API_VERSION_PIN=2026-05-07"
echo "ENCODING=msgpack"
echo "WEB remains http://127.0.0.1:8787"
echo "PRIVATE_ORDER_STREAM=false"
echo "PRIVATE_POSITION_STREAM=false"
echo "TRADING_TOKEN_REQUESTED=false"
echo "ORDER_MUTATION=false"
echo "LIVE_ORDER_READY=false"
echo "State: $STATE"
echo "Keep this terminal open. Ctrl+C stops only the realtime sidecar."

PYTHONPATH="$PY_SIDE_PATH" exec "$SIDE_PY" -m he_thong_dinh_luong.dnse_openapi_sidecar_v86 \
  --credentials "$(cygpath -w "$CREDS")" \
  --symbols-file "$(cygpath -w "$SYMBOLS")" \
  --state "$(cygpath -w "$STATE")" \
  --encoding msgpack \
  --rest-smoke
