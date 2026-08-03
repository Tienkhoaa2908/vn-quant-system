#!/usr/bin/env bash

set -euo pipefail

BRANCH="agent/model-lab-predictive-value-dnse-sync-v3"

fail() {
    echo "FAILED: $*" >&2
    exit 2
}

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    fail "hay chay trong repository vn-quant-system"
fi
if ! command -v cygpath >/dev/null 2>&1; then
    fail "runner nay can Git Bash tren Windows"
fi
if ! command -v powershell.exe >/dev/null 2>&1; then
    fail "khong tim thay Windows PowerShell"
fi

echo "===== SECURE DNSE SETUP + V41 ====="
echo "API key va secret se duoc nhap trong prompt an ky tu."
echo "Khong dan credential vao chat, command line, .env hoac Git."

git fetch origin \
    && git switch "$BRANCH" \
    && git pull --ff-only origin "$BRANCH" \
    || fail "khong dong bo duoc branch $BRANCH"

SETUP_PS="$(cygpath -w "$PWD/scripts/setup_dnse_credentials_windows.ps1")"
RUN_PS="$(cygpath -w "$PWD/scripts/run_v41_with_dnse_credentials_windows.ps1")"
REPO_WINDOWS="$(cygpath -w "$PWD")"

powershell.exe \
    -NoLogo \
    -NoProfile \
    -NonInteractive:$false \
    -ExecutionPolicy Bypass \
    -File "$SETUP_PS" \
    || fail "khong luu duoc DNSE credentials bang Windows DPAPI"

powershell.exe \
    -NoLogo \
    -NoProfile \
    -ExecutionPolicy Bypass \
    -File "$RUN_PS" \
    -RepositoryRoot "$REPO_WINDOWS" \
    || fail "V41 secure runner that bai"

echo "===== SECURE DNSE V41 HOAN TAT ====="
echo "Credential van duoc ma hoa cuc bo va khong duoc dua vao artifact."
