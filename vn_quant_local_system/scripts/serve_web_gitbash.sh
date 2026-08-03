#!/usr/bin/env bash
set -euo pipefail

SYSTEM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$SYSTEM_DIR/.." && pwd)"
PY="$SYSTEM_DIR/.venv/Scripts/python.exe"
URL="${VN_QUANT_LOCAL_URL:-http://127.0.0.1:8787}"

fail() {
  echo "FAILED: $*" >&2
  exit 2
}

[[ -f "$PY" ]] || fail "Chưa có môi trường local: $PY"

export PYTHONPATH="$SYSTEM_DIR/src:$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

check_web() {
  "$PY" - "$URL" <<'PY'
import sys
import urllib.request

url = sys.argv[1]
try:
    with urllib.request.urlopen(url, timeout=0.75) as response:
        if 200 <= response.status < 500:
            raise SystemExit(0)
except Exception:
    pass
raise SystemExit(1)
PY
}

open_browser() {
  VN_QUANT_LOCAL_OPEN_URL="$URL" \
    powershell.exe -NoProfile -NonInteractive -Command \
    '$u=$env:VN_QUANT_LOCAL_OPEN_URL; Start-Process $u' \
    >/dev/null 2>&1
}

if check_web >/dev/null 2>&1; then
  echo "WEB_ALREADY_RUNNING=$URL"
  if ! open_browser; then
    echo "Không tự mở được trình duyệt. Mở thủ công: $URL"
  fi
  exit 0
fi

cd "$SYSTEM_DIR"

echo "===== KHỞI ĐỘNG WEB SERVER ====="
"$PY" -m vn_quant_local.webapp &
SERVER_PID=$!

cleanup() {
  if kill -0 "$SERVER_PID" >/dev/null 2>&1; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

READY=0
for _ in $(seq 1 60); do
  if check_web >/dev/null 2>&1; then
    READY=1
    break
  fi
  if ! kill -0 "$SERVER_PID" >/dev/null 2>&1; then
    echo "FAILED: web server kết thúc trước khi sẵn sàng" >&2
    wait "$SERVER_PID" || true
    exit 2
  fi
  sleep 0.25
done

[[ "$READY" -eq 1 ]] || fail "web server không phản hồi tại $URL"

echo "WEB_READY=$URL"
echo "Terminal này giữ web server hoạt động. Dừng bằng Ctrl+C."

if ! open_browser; then
  echo "Không tự mở được trình duyệt. Mở thủ công: $URL"
fi

wait "$SERVER_PID"
