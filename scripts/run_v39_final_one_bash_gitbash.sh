#!/usr/bin/env bash

set -u
set -o pipefail

BRANCH="agent/model-lab-predictive-value-dnse-sync-v3"
WORKSPACE_POSIX="/c/Users/welcome/Documents/vn-quant-data/reference/v39-decision-surface"
SQLITE_POSIX="/c/Users/welcome/Documents/vn-quant-data/market-data/dnse_ohlcv_v20.sqlite3"
RESEARCH_POSIX="$WORKSPACE_POSIX/research_handoff_v39"
TMP_COMPAT="$(mktemp -d)"

fail() {
    echo "FAILED: $*" >&2
    exit 2
}
cleanup() {
    rm -rf "$TMP_COMPAT"
}
trap cleanup EXIT

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    fail "hay chay trong repository vn-quant-system"
fi
if ! command -v cygpath >/dev/null 2>&1; then
    fail "runner nay can Git Bash tren Windows"
fi

echo "===== V39 FINAL: ONE BASH, ONE UPLOAD ZIP ====="
echo "Tu dong export research-ledger input truoc, sau do thu thap nguon ngoai va dong goi final ZIP."

git fetch origin \
    && git switch "$BRANCH" \
    && git pull --ff-only origin "$BRANCH" \
    || fail "khong dong bo duoc branch $BRANCH"

cat > "$TMP_COMPAT/sitecustomize.py" <<'PY'
try:
    import vnstock
    if not hasattr(vnstock, "Reference"):
        from vnstock_data import Reference
        vnstock.Reference = Reference
except Exception:
    pass
PY

export PYTHONPATH="$TMP_COMPAT:$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
[[ -d "$WORKSPACE_POSIX" ]] || fail "thieu workspace V39: $WORKSPACE_POSIX"
[[ -f "$SQLITE_POSIX" ]] || fail "thieu SQLite canonical: $SQLITE_POSIX"

rm -rf "$RESEARCH_POSIX"
echo
echo "===== EXPORT SELF-CONTAINED RESEARCH LEDGER INPUT ====="
python -m py_compile \
    src/he_thong_dinh_luong/v39_research_ledger_input_export.py \
    tests/test_v39_research_ledger_input_export.py \
    || fail "py_compile research export that bai"
python -m unittest tests.test_v39_research_ledger_input_export -v \
    || fail "unit test research export that bai"
python -m he_thong_dinh_luong.v39_research_ledger_input_export \
    --workspace-dir "$(cygpath -w "$WORKSPACE_POSIX")" \
    --sqlite-store "$(cygpath -w "$SQLITE_POSIX")" \
    --output-dir "$(cygpath -w "$RESEARCH_POSIX")" \
    || fail "khong export duoc research ledger input"

bash scripts/run_v39_one_shot_external_resolution_gitbash.sh
