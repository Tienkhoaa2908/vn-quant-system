#!/usr/bin/env bash
set -euo pipefail

SYSTEM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVE_SCRIPT="$SYSTEM_DIR/scripts/serve_web_gitbash.sh"

[[ -f "$SERVE_SCRIPT" ]] || {
  echo "Không tìm thấy web runner: $SERVE_SCRIPT" >&2
  exit 2
}

bash -n "$SERVE_SCRIPT"
bash "$SERVE_SCRIPT"
