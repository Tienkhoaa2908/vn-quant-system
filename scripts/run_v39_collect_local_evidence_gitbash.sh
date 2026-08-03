#!/usr/bin/env bash

set -u
set -o pipefail

BRANCH="agent/model-lab-predictive-value-dnse-sync-v3"
WORKSPACE_POSIX="/c/Users/welcome/Documents/vn-quant-data/reference/v39-decision-surface"
DATA_ROOT_POSIX="/c/Users/welcome/Documents/vn-quant-data"
V22_POSIX="/c/Users/welcome/Documents/vn-quant-data/historical-research-input-v22-20260801-223238/daily_prediction_input.zip"
SQLITE_POSIX="/c/Users/welcome/Documents/vn-quant-data/market-data/dnse_ohlcv_v20.sqlite3"
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

echo "===== V39 COLLECT ACTUAL LOCAL EVIDENCE ====="
echo "Khong chay model, V36, V37, V38 hay exact ledger."
echo "Tu quet lai va copy noi dung file corporate-action/price-basis/operations co gia tri cao."
echo "Khong copy full V22, SQLite, credential, .env, private key hay arbitrary user files."

echo
echo "===== DONG BO CODE ====="
git fetch origin \
    && git switch "$BRANCH" \
    && git pull --ff-only origin "$BRANCH" \
    || fail "khong dong bo duoc branch $BRANCH"
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"

echo
echo "===== KIEM TRA COLLECTOR ====="
python -m py_compile \
    src/he_thong_dinh_luong/v39_local_evidence_discovery.py \
    src/he_thong_dinh_luong/v39_local_evidence_collector.py \
    src/he_thong_dinh_luong/upload_handoff_bundle_v39.py \
    tests/test_v39_local_evidence_discovery.py \
    tests/test_v39_local_evidence_collector.py \
    tests/test_upload_handoff_bundle_v39.py \
    || fail "py_compile that bai"
python -m unittest \
    tests.test_v39_local_evidence_discovery \
    tests.test_v39_local_evidence_collector \
    tests.test_upload_handoff_bundle_v39 \
    -v || fail "unit test collector that bai"

[[ -f "$V22_POSIX" ]] || fail "thieu V22 canonical: $V22_POSIX"
[[ -f "$SQLITE_POSIX" ]] || fail "thieu SQLite canonical: $SQLITE_POSIX"
[[ -d "$WORKSPACE_POSIX" ]] || fail "workspace V39 chua ton tai: $WORKSPACE_POSIX"

echo
echo "===== QUET LAI FILE LOCAL ====="
DISCOVERY_JSON="$(
    python -m he_thong_dinh_luong.v39_local_evidence_discovery \
        --workspace-dir "$(cygpath -w "$WORKSPACE_POSIX")" \
        --repo-root "$(cygpath -w "$PWD")" \
        --data-root "$(cygpath -w "$DATA_ROOT_POSIX")" \
        --v22-zip "$(cygpath -w "$V22_POSIX")" \
        --sqlite-store "$(cygpath -w "$SQLITE_POSIX")"
)" || fail "local discovery that bai"
echo "$DISCOVERY_JSON"

CANDIDATES_POSIX="$WORKSPACE_POSIX/local_evidence_candidates_v39.csv"
[[ -f "$CANDIDATES_POSIX" ]] || fail "thieu candidate CSV sau discovery"

RUN_ID="$(date +%Y%m%d-%H%M%S)"
STAGING_POSIX="$PWD/artifacts/upload-handoff-v39-local-evidence-$RUN_ID"
UPLOAD_ZIP_POSIX="$PWD/artifacts/UPLOAD_THIS_v39_LOCAL_EVIDENCE-$RUN_ID.zip"
COLLECTED_POSIX="$STAGING_POSIX/local_evidence"
mkdir -p "$STAGING_POSIX/workspace" "$STAGING_POSIX/metadata"

echo
echo "===== COPY NOI DUNG CANDIDATE CO GIA TRI CAO ====="
COLLECTION_JSON="$(
    python -m he_thong_dinh_luong.v39_local_evidence_collector \
        --candidates-csv "$(cygpath -w "$CANDIDATES_POSIX")" \
        --output-dir "$(cygpath -w "$COLLECTED_POSIX")"
)" || fail "local evidence collector that bai"
echo "$COLLECTION_JSON"

cp -a "$WORKSPACE_POSIX"/. "$STAGING_POSIX/workspace/"
printf '%s\n' "$DISCOVERY_JSON" > "$STAGING_POSIX/metadata/local_discovery_stdout.json"
printf '%s\n' "$COLLECTION_JSON" > "$STAGING_POSIX/metadata/local_collection_stdout.json"
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
V39 LOCAL EVIDENCE HANDOFF

Bundle nay khong chay lai model/ledger. No chua noi dung thuc te cua:
- corporate-action inventory/audit da tim thay trong m4_tier_a;
- price-basis audit va provenance lien quan;
- DNSE read-only portfolio snapshot moi nhat;
- discovery report, workspace, Git metadata va canonical hashes.

Sector master point-in-time khong duoc tim thay trong local data.
File duoc copy chi la evidence de review; khong tu dong duoc coi la authoritative.
Live capital va automatic orders van bi khoa.
EOF

find "$STAGING_POSIX" -type f -printf '%P\n' | sort \
    > "$STAGING_POSIX/metadata/staging_file_list.txt"

echo
echo "===== TAO MOT ZIP DE UPLOAD ====="
python -m he_thong_dinh_luong.upload_handoff_bundle_v39 \
    --staging-dir "$(cygpath -w "$STAGING_POSIX")" \
    --output-zip "$(cygpath -w "$UPLOAD_ZIP_POSIX")" \
    || fail "khong tao duoc upload ZIP; collector da fail closed neu co sensitive content"

[[ -f "$UPLOAD_ZIP_POSIX" ]] || fail "upload ZIP khong ton tai"
echo
echo "===== FILE DUY NHAT CAN UPLOAD ====="
echo "UPLOAD_THIS_FILE=$UPLOAD_ZIP_POSIX"
echo "UPLOAD_THIS_FILE_WINDOWS=$(cygpath -w "$UPLOAD_ZIP_POSIX")"
echo "UPLOAD_SHA256=$(sha256sum "$UPLOAD_ZIP_POSIX" | awk '{print $1}')"
echo "UPLOAD_SIZE_BYTES=$(wc -c < "$UPLOAD_ZIP_POSIX")"
echo "Chi upload file UPLOAD_THIS_v39_LOCAL_EVIDENCE-*.zip nay len chat."
