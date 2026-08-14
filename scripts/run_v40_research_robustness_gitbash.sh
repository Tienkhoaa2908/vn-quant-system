#!/usr/bin/env bash

set -u
set -o pipefail

BRANCH="agent/model-lab-predictive-value-dnse-sync-v3"
INPUT_POSIX="${1:-}"

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

echo "===== V40 RESEARCH ROBUSTNESS ====="
echo "Chi danh gia research ledger va dong bang protocol shadow paper."
echo "Khong gui lenh broker, khong phe duyet live capital."

git fetch origin \
    && git switch "$BRANCH" \
    && git pull --ff-only origin "$BRANCH" \
    || fail "khong dong bo duoc branch $BRANCH"
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"

if [[ -z "$INPUT_POSIX" ]]; then
    INPUT_POSIX="$(
        find \
            "$PWD/artifacts" \
            /c/Users/welcome/Downloads \
            /c/Users/welcome/Documents/vn-quant-data \
            -maxdepth 3 -type f -name 'V39_RESEARCH_LEDGER_ANALYSIS-*.zip' \
            -printf '%T@ %p\n' 2>/dev/null \
        | sort -nr | head -n 1 | cut -d' ' -f2-
    )"
fi
[[ -n "$INPUT_POSIX" && -f "$INPUT_POSIX" ]] \
    || fail "khong tim thay V39_RESEARCH_LEDGER_ANALYSIS-*.zip; truyen path lam tham so thu nhat"

python -m py_compile \
    src/he_thong_dinh_luong/v40_research_robustness.py \
    tests/test_v40_research_robustness.py \
    || fail "py_compile V40 that bai"
python -m unittest tests.test_v40_research_robustness -v \
    || fail "unit test V40 that bai"

RUN_ID="$(date +%Y%m%d-%H%M%S)"
OUTPUT_POSIX="$PWD/artifacts/v40-research-robustness-$RUN_ID"
ZIP_POSIX="$PWD/artifacts/V40_RESEARCH_ROBUSTNESS-$RUN_ID.zip"

python -m he_thong_dinh_luong.v40_research_robustness \
    --v39-analysis-zip "$(cygpath -w "$INPUT_POSIX")" \
    --output-dir "$(cygpath -w "$OUTPUT_POSIX")" \
    --bootstrap-draws 20000 \
    --bootstrap-seed 2908 \
    || fail "V40 research robustness that bai"

python - "$OUTPUT_POSIX" "$ZIP_POSIX" <<'PY'
from pathlib import Path
import sys
from zipfile import ZIP_DEFLATED, ZipFile
source = Path(sys.argv[1])
target = Path(sys.argv[2])
with ZipFile(target, "w", ZIP_DEFLATED) as archive:
    for path in sorted(source.iterdir()):
        if path.is_file():
            archive.write(path, path.name)
with ZipFile(target) as archive:
    bad = archive.testzip()
    if bad is not None:
        raise SystemExit(f"ZIP_CRC_FAILED:{bad}")
PY

echo
echo "===== V40 HOAN TAT ====="
cat "$OUTPUT_POSIX/V40_CONCLUSION.txt"
echo "V40_OUTPUT_ZIP=$ZIP_POSIX"
echo "V40_OUTPUT_ZIP_WINDOWS=$(cygpath -w "$ZIP_POSIX")"
echo "V40_OUTPUT_SHA256=$(sha256sum "$ZIP_POSIX" | awk '{print $1}')"
echo "Khong co lenh broker nao duoc tao hoac gui."
