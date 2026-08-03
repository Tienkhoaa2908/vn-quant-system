#!/usr/bin/env bash

set -u
set -o pipefail

BRANCH="agent/model-lab-predictive-value-dnse-sync-v3"
WORKSPACE_POSIX="/c/Users/welcome/Documents/vn-quant-data/reference/v39-decision-surface"
DATA_ROOT_POSIX="/c/Users/welcome/Documents/vn-quant-data"
SQLITE_POSIX="$DATA_ROOT_POSIX/market-data/dnse_ohlcv_v20.sqlite3"
V22_POSIX="$DATA_ROOT_POSIX/historical-research-input-v22-20260801-223238/daily_prediction_input.zip"
CACHE_POSIX="$DATA_ROOT_POSIX/reference/v39-external-cache"
REPO_FULL_NAME="Tienkhoaa2908/vn-quant-system"

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

echo "===== V39 FINAL ONE-SHOT EXTERNAL RESOLUTION ====="
echo "Mot lan chay: dong bo -> tai nguon ngoai -> luu byte/hash -> chuan hoa -> strict decision -> mot ZIP."
echo "Khong quet local lap lai, khong yeu cau tim file bang tay, khong tu phe duyet live."

echo
echo "===== DONG BO CODE ====="
git fetch origin \
    && git switch "$BRANCH" \
    && git pull --ff-only origin "$BRANCH" \
    || fail "khong dong bo duoc branch $BRANCH"
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"

[[ -d "$WORKSPACE_POSIX" ]] || fail "thieu workspace V39: $WORKSPACE_POSIX"
[[ -f "$SQLITE_POSIX" ]] || fail "thieu SQLite canonical: $SQLITE_POSIX"
[[ -f "$V22_POSIX" ]] || fail "thieu V22 canonical: $V22_POSIX"
mkdir -p "$CACHE_POSIX" "$PWD/artifacts"

echo
echo "===== KIEM TRA ONE-SHOT RESOLVER ====="
python -m py_compile \
    src/he_thong_dinh_luong/v39_one_shot_external_resolution.py \
    src/he_thong_dinh_luong/upload_handoff_bundle_v39.py \
    tests/test_v39_one_shot_external_resolution.py \
    tests/test_upload_handoff_bundle_v39.py \
    || fail "py_compile that bai"
python -m unittest \
    tests.test_v39_one_shot_external_resolution \
    tests.test_upload_handoff_bundle_v39 \
    -v || fail "unit test one-shot that bai"

RUN_ID="$(date +%Y%m%d-%H%M%S)"
RESOLUTION_POSIX="$PWD/artifacts/v39-external-resolution-$RUN_ID"
STAGING_POSIX="$PWD/artifacts/upload-handoff-v39-final-$RUN_ID"
UPLOAD_ZIP_POSIX="$PWD/artifacts/UPLOAD_THIS_v39_FINAL-$RUN_ID.zip"
LOG_POSIX="$STAGING_POSIX/metadata/console_one_shot_v39.log"
MARKER="$(mktemp)"
mkdir -p \
    "$STAGING_POSIX/external_resolution" \
    "$STAGING_POSIX/workspace" \
    "$STAGING_POSIX/artifacts" \
    "$STAGING_POSIX/metadata"
touch "$MARKER"

echo
echo "===== THU THAP VA KIEM CHUNG NGUON NGOAI ====="
set +e
uv run --python 3.12 --with vnstock==4.0.4 \
    python -m he_thong_dinh_luong.v39_one_shot_external_resolution \
    --workspace-dir "$(cygpath -w "$WORKSPACE_POSIX")" \
    --sqlite-store "$(cygpath -w "$SQLITE_POSIX")" \
    --output-dir "$(cygpath -w "$RESOLUTION_POSIX")" \
    --cache-dir "$(cygpath -w "$CACHE_POSIX")" \
    --use-vnstock \
    --max-official-symbols 78 \
    2>&1 | tee "$LOG_POSIX"
RESOLUTION_EXIT_CODE=${PIPESTATUS[0]}
set -e
printf '%s\n' "$RESOLUTION_EXIT_CODE" > "$STAGING_POSIX/metadata/resolution_exit_code.txt"

if [[ ! -f "$RESOLUTION_POSIX/one_shot_external_resolution_v39.json" ]]; then
    cat > "$RESOLUTION_POSIX/one_shot_external_resolution_v39.json" <<EOF
{
  "schema_version": "vn_quant_v39_one_shot_external_resolution_v1",
  "status": "RESOLUTION_RUNTIME_FAILED",
  "resolution_exit_code": $RESOLUTION_EXIT_CODE,
  "strict_workspace_mutated": false,
  "exact_cash_ledger_allowed": false,
  "live_capital_approved": false,
  "automatic_live_orders_allowed": false,
  "final_next_action": "REVIEW_PACKAGED_RUNTIME_LOG"
}
EOF
fi

RESOLUTION_STATUS="$(python - "$RESOLUTION_POSIX/one_shot_external_resolution_v39.json" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8-sig") as stream:
    print(json.load(stream).get("status", "UNKNOWN"))
PY
)"
echo "RESOLUTION_STATUS=$RESOLUTION_STATUS"
printf '%s\n' "$RESOLUTION_STATUS" > "$STAGING_POSIX/metadata/resolution_status.txt"

if [[ "$RESOLUTION_STATUS" == "STRICT_READY" ]]; then
    echo
echo "===== STRICT READY: CHAY V39 -> EXACT V36 -> V37 ====="
    set +e
    printf 'exit\n' \
        | bash scripts/run_v39_trade_reference_to_exact_ledger_gitbash.sh 2>&1 \
        | tee -a "$LOG_POSIX"
    PIPELINE_EXIT_CODE=${PIPESTATUS[1]}
    set -e
else
    echo
echo "===== STRICT GATE VAN BLOCKED ====="
    echo "Khong chay lai model/V36-V39. ZIP cuoi se chot blocker va dataset/contract can co."
    PIPELINE_EXIT_CODE=0
fi
printf '%s\n' "$PIPELINE_EXIT_CODE" > "$STAGING_POSIX/metadata/exact_pipeline_exit_code.txt"

cp -a "$RESOLUTION_POSIX"/. "$STAGING_POSIX/external_resolution/"
cp -a "$WORKSPACE_POSIX"/. "$STAGING_POSIX/workspace/"

# Gom artifact moi neu strict pipeline da chay.
while IFS= read -r artifact; do
    [[ -f "$artifact" ]] || continue
    cp -f "$artifact" "$STAGING_POSIX/artifacts/"
done < <(
    find "$PWD/artifacts" -maxdepth 1 -type f -newer "$MARKER" \
        \( \
            -name 'integrated-data-ledger-v36-*.zip' -o \
            -name 'trade-readiness-v37-*.zip' -o \
            -name 'trade-evidence-accelerator-v38-*.zip' -o \
            -name 'trade-reference-pack-v39-*.zip' \
        \) -print 2>/dev/null | sort
)
rm -f "$MARKER"

# Neu khong co artifact moi, gom ban moi nhat cua tung loai de reviewer co du lineage.
for pattern in \
    'integrated-data-ledger-v36-*.zip' \
    'trade-readiness-v37-*.zip' \
    'trade-evidence-accelerator-v38-*.zip' \
    'trade-reference-pack-v39-*.zip'; do
    latest="$(find "$PWD/artifacts" -maxdepth 1 -type f -name "$pattern" -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n 1 | cut -d' ' -f2-)"
    if [[ -n "$latest" && -f "$latest" ]]; then
        cp -n "$latest" "$STAGING_POSIX/artifacts/" || true
    fi
done

printf '%s\n' "$REPO_FULL_NAME" > "$STAGING_POSIX/metadata/repository.txt"
git branch --show-current > "$STAGING_POSIX/metadata/git_branch.txt"
git rev-parse HEAD > "$STAGING_POSIX/metadata/git_head.txt"
git status --short > "$STAGING_POSIX/metadata/git_status_short.txt"
git log -1 --format='%H%n%cI%n%s' > "$STAGING_POSIX/metadata/git_commit.txt"
{
    echo "generated_at=$(date --iso-8601=seconds)"
    echo "V22=$(sha256sum "$V22_POSIX" | awk '{print $1}')"
    echo "V22_SIZE_BYTES=$(wc -c < "$V22_POSIX")"
    echo "SQLITE=$(sha256sum "$SQLITE_POSIX" | awk '{print $1}')"
    echo "SQLITE_SIZE_BYTES=$(wc -c < "$SQLITE_POSIX")"
} > "$STAGING_POSIX/metadata/canonical_input_hashes.txt"

cat > "$STAGING_POSIX/README_FIRST.txt" <<EOF
V39 FINAL ONE-SHOT HANDOFF

Day la bundle cuoi cua luong resolution, tao boi mot lenh Git Bash.
No chua:
- source pages da tai, byte/hash manifest va network log;
- research-only static sector va corporate-action candidates;
- empirical price-basis diagnostic;
- strict blocker decision;
- workspace V39 hien tai, Git metadata va canonical hashes;
- exact V36/V37 artifact neu strict gate thuc su da du.

Vnstock chi dung lam candidate locator, khong phai authoritative assurance.
Static sector khong duoc danh dong voi point-in-time sector history.
Empirical price jumps khong duoc danh dong voi vendor price-basis contract.
Neu status STRICT_BLOCKED_EXTERNAL_DATA, khong can chay lai local scan/bash nua:
quyet dinh tiep theo la mua/nhan licensed PIT reference data hoac sua strict research contract.
Live capital va automatic orders luon bi khoa.
EOF

find "$STAGING_POSIX" -type f -printf '%P\n' | sort \
    > "$STAGING_POSIX/metadata/staging_file_list.txt"

echo
echo "===== TAO MOT ZIP CUOI DE UPLOAD ====="
python -m he_thong_dinh_luong.upload_handoff_bundle_v39 \
    --staging-dir "$(cygpath -w "$STAGING_POSIX")" \
    --output-zip "$(cygpath -w "$UPLOAD_ZIP_POSIX")" \
    || fail "khong tao duoc final ZIP; kiem tra sensitive-content report"

[[ -f "$UPLOAD_ZIP_POSIX" ]] || fail "final upload ZIP khong ton tai"
echo
echo "===== FILE DUY NHAT CAN UPLOAD ====="
echo "UPLOAD_THIS_FILE=$UPLOAD_ZIP_POSIX"
echo "UPLOAD_THIS_FILE_WINDOWS=$(cygpath -w "$UPLOAD_ZIP_POSIX")"
echo "UPLOAD_SHA256=$(sha256sum "$UPLOAD_ZIP_POSIX" | awk '{print $1}')"
echo "UPLOAD_SIZE_BYTES=$(wc -c < "$UPLOAD_ZIP_POSIX")"
echo "RESOLUTION_STATUS=$RESOLUTION_STATUS"
echo "Chi upload file UPLOAD_THIS_v39_FINAL-*.zip nay len chat. Khong chay them bash nao khac."
