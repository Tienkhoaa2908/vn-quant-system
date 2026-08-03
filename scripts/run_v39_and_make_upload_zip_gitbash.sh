#!/usr/bin/env bash

set -u
set -o pipefail

BRANCH="agent/model-lab-predictive-value-dnse-sync-v3"
WORKSPACE_POSIX="/c/Users/welcome/Documents/vn-quant-data/reference/v39-decision-surface"
DATA_ROOT_POSIX="/c/Users/welcome/Documents/vn-quant-data"
V22_POSIX="/c/Users/welcome/Documents/vn-quant-data/historical-research-input-v22-20260801-223238/daily_prediction_input.zip"
SQLITE_POSIX="/c/Users/welcome/Documents/vn-quant-data/market-data/dnse_ohlcv_v20.sqlite3"
REPO_FULL_NAME="Tienkhoaa2908/vn-quant-system"
GUIDE_POSIX="$WORKSPACE_POSIX/EXACT_DATA_NEEDED_V39.txt"

fail() {
    echo "FAILED: $*" >&2
    exit 2
}

open_workspace() {
    [[ -d "$WORKSPACE_POSIX" ]] || return 0
    local workspace_win guide_win
    workspace_win="$(cygpath -w "$WORKSPACE_POSIX")"
    guide_win="$(cygpath -w "$GUIDE_POSIX")"
    if command -v explorer.exe >/dev/null 2>&1; then
        explorer.exe "$workspace_win" >/dev/null 2>&1 &
    fi
    if [[ -f "$GUIDE_POSIX" ]] && command -v notepad.exe >/dev/null 2>&1; then
        notepad.exe "$guide_win" >/dev/null 2>&1 &
    fi
}

write_git_metadata() {
    local metadata_dir="$1"
    printf '%s\n' "$REPO_FULL_NAME" > "$metadata_dir/repository.txt"
    git branch --show-current > "$metadata_dir/git_branch.txt"
    git rev-parse HEAD > "$metadata_dir/git_head.txt"
    git status --short > "$metadata_dir/git_status_short.txt"
    git log -1 --format='%H%n%cI%n%s' > "$metadata_dir/git_commit.txt"
}

write_canonical_hashes() {
    local destination="$1"
    {
        echo "generated_at=$(date --iso-8601=seconds)"
        if [[ -f "$V22_POSIX" ]]; then
            echo "V22=$(sha256sum "$V22_POSIX" | awk '{print $1}')"
            echo "V22_SIZE_BYTES=$(wc -c < "$V22_POSIX")"
        else
            echo "V22=MISSING"
        fi
        if [[ -f "$SQLITE_POSIX" ]]; then
            echo "SQLITE=$(sha256sum "$SQLITE_POSIX" | awk '{print $1}')"
            echo "SQLITE_SIZE_BYTES=$(wc -c < "$SQLITE_POSIX")"
        else
            echo "SQLITE=MISSING"
        fi
    } > "$destination"
}

build_upload_zip() {
    local staging="$1"
    local upload_zip="$2"
    find "$staging" -type f -printf '%P\n' | sort \
        > "$staging/metadata/staging_file_list.txt"
    python -m he_thong_dinh_luong.upload_handoff_bundle_v39 \
        --staging-dir "$(cygpath -w "$staging")" \
        --output-zip "$(cygpath -w "$upload_zip")" \
        || fail "khong tao duoc upload ZIP; kiem tra canh bao sensitive content"
    [[ -f "$upload_zip" ]] || fail "upload ZIP khong ton tai"
    echo
    echo "===== FILE DUY NHAT CAN UPLOAD ====="
    echo "UPLOAD_THIS_FILE=$upload_zip"
    echo "UPLOAD_THIS_FILE_WINDOWS=$(cygpath -w "$upload_zip")"
    echo "UPLOAD_SHA256=$(sha256sum "$upload_zip" | awk '{print $1}')"
    echo "UPLOAD_SIZE_BYTES=$(wc -c < "$upload_zip")"
}

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    fail "hay chay trong repository vn-quant-system"
fi
if ! command -v cygpath >/dev/null 2>&1; then
    fail "runner nay can Git Bash tren Windows"
fi

echo "===== V39 LOCAL DISCOVERY + ONE UPLOAD ZIP ====="
echo "Tu kiem V22, SQLite, repo va vn-quant-data truoc khi yeu cau con nguoi tim file."
echo "Neu input van thieu: khong chay lai V36-V39; tao mot ZIP discovery de upload."
echo "Neu da co input: chay V39 va tao mot ZIP ket qua duy nhat."
echo "Khong dong goi full SQLite/V22; chi ghi schema, ket luan va SHA-256."

echo
echo "===== DONG BO CODE ====="
git fetch origin \
    && git switch "$BRANCH" \
    && git pull --ff-only origin "$BRANCH" \
    || fail "khong dong bo duoc branch $BRANCH"
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"

echo
echo "===== KIEM TRA RUNNER ====="
python -m py_compile \
    src/he_thong_dinh_luong/upload_handoff_bundle_v39.py \
    src/he_thong_dinh_luong/v39_guided_input.py \
    src/he_thong_dinh_luong/v39_local_evidence_discovery.py \
    tests/test_upload_handoff_bundle_v39.py \
    tests/test_v39_guided_input.py \
    tests/test_v39_local_evidence_discovery.py \
    || fail "py_compile runner that bai"
python -m unittest \
    tests.test_upload_handoff_bundle_v39 \
    tests.test_v39_guided_input \
    tests.test_v39_local_evidence_discovery \
    -v || fail "unit test runner that bai"

[[ -f "$V22_POSIX" ]] || fail "thieu V22 canonical: $V22_POSIX"
[[ -f "$SQLITE_POSIX" ]] || fail "thieu SQLite canonical: $SQLITE_POSIX"
[[ -d "$WORKSPACE_POSIX" ]] || fail "workspace V39 chua duoc seed: $WORKSPACE_POSIX"

echo
echo "===== TU QUET TOAN BO DU LIEU LOCAL ====="
DISCOVERY_JSON="$(
    python -m he_thong_dinh_luong.v39_local_evidence_discovery \
        --workspace-dir "$(cygpath -w "$WORKSPACE_POSIX")" \
        --repo-root "$(cygpath -w "$PWD")" \
        --data-root "$(cygpath -w "$DATA_ROOT_POSIX")" \
        --v22-zip "$(cygpath -w "$V22_POSIX")" \
        --sqlite-store "$(cygpath -w "$SQLITE_POSIX")"
)" || fail "local evidence discovery that bai"
echo "$DISCOVERY_JSON"

PREFLIGHT_JSON="$(
    python -m he_thong_dinh_luong.v39_guided_input \
        --workspace-dir "$(cygpath -w "$WORKSPACE_POSIX")"
)"
PREFLIGHT_STATUS="$(python - "$PREFLIGHT_JSON" <<'PY'
import json
import sys
print(json.loads(sys.argv[1]).get("status", "UNKNOWN"))
PY
)"

echo
echo "===== KIEM TRA INPUT TRUOC KHI CHAY NANG ====="
echo "INPUT_STATUS=$PREFLIGHT_STATUS"

if [[ "$PREFLIGHT_STATUS" == "INPUT_EMPTY" ]]; then
    RUN_ID="$(date +%Y%m%d-%H%M%S)"
    STAGING_POSIX="$PWD/artifacts/upload-handoff-v39-discovery-$RUN_ID"
    UPLOAD_ZIP_POSIX="$PWD/artifacts/UPLOAD_THIS_v39_DISCOVERY-$RUN_ID.zip"
    mkdir -p "$STAGING_POSIX/artifacts" "$STAGING_POSIX/workspace" "$STAGING_POSIX/metadata"

    cp -a "$WORKSPACE_POSIX"/. "$STAGING_POSIX/workspace/"
    printf '%s\n' "$DISCOVERY_JSON" > "$STAGING_POSIX/metadata/local_discovery_stdout.json"
    printf '%s\n' "$PREFLIGHT_JSON" > "$STAGING_POSIX/metadata/input_preflight.json"
    write_git_metadata "$STAGING_POSIX/metadata"
    write_canonical_hashes "$STAGING_POSIX/metadata/canonical_input_hashes.txt"

    cat > "$STAGING_POSIX/README_FIRST.txt" <<EOF
V39 DISCOVERY HANDOFF

Workspace van chua co authoritative input, nen runner khong chay lai V36-V39.
Bundle nay chua:
- schema va ket luan cua V22 canonical;
- schema va price_basis cua SQLite canonical;
- danh sach file local co kha nang chua sector/corporate-action/price/account data;
- danh sach chinh xac 78 ma va 4 nhom du lieu con thieu;
- SHA-256 canonical inputs va Git metadata.

Upload duy nhat ZIP nay len chat. AI se doc candidate report va chi ra file local nao co the dung.
EOF

    build_upload_zip "$STAGING_POSIX" "$UPLOAD_ZIP_POSIX"
    echo "V36_V39_RERUN=SKIPPED_INPUT_EMPTY"
    echo "Chi can upload file UPLOAD_THIS_v39_DISCOVERY-*.zip nay len chat."
    open_workspace
    exit 0
fi

RUN_ID="$(date +%Y%m%d-%H%M%S)"
STAGING_POSIX="$PWD/artifacts/upload-handoff-v39-$RUN_ID"
UPLOAD_ZIP_POSIX="$PWD/artifacts/UPLOAD_THIS_v39-$RUN_ID.zip"
LOG_POSIX="$STAGING_POSIX/metadata/console_v39.log"
MARKER="$(mktemp)"

mkdir -p \
    "$STAGING_POSIX/artifacts" \
    "$STAGING_POSIX/workspace" \
    "$STAGING_POSIX/metadata"
touch "$MARKER"

cat > "$STAGING_POSIX/README_FIRST.txt" <<EOF
UPLOAD HANDOFF V39

Upload duy nhat file:
$(cygpath -w "$UPLOAD_ZIP_POSIX")

Bundle gom:
- console log cua lan chay V39;
- tat ca V36/V37/V38/V39 ZIP sinh trong lan chay;
- workspace V39, local discovery va source_documents;
- repo HEAD/status;
- SHA-256 canonical V22/SQLite, khong gom hai file lon;
- handoff summary va SHA-256 manifest.

An toan:
- khong dat API key/secret, password, bearer token hoac private key trong workspace;
- account evidence phai mask account ID va khong chua credential;
- live capital va automatic orders van bi khoa.
EOF

echo
echo "===== CHAY V39 VA GHI LOG ====="
set +e
printf 'exit\n' \
    | bash scripts/run_v39_trade_reference_to_exact_ledger_gitbash.sh 2>&1 \
    | tee "$LOG_POSIX"
V39_EXIT_CODE=${PIPESTATUS[1]}
set -e
printf '%s\n' "$V39_EXIT_CODE" > "$STAGING_POSIX/metadata/v39_exit_code.txt"
printf '%s\n' "$DISCOVERY_JSON" > "$STAGING_POSIX/metadata/local_discovery_stdout.json"
printf '%s\n' "$PREFLIGHT_JSON" > "$STAGING_POSIX/metadata/input_preflight.json"
write_git_metadata "$STAGING_POSIX/metadata"
write_canonical_hashes "$STAGING_POSIX/metadata/canonical_input_hashes.txt"

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
        \) \
        -print 2>/dev/null | sort
)
rm -f "$MARKER"
cp -a "$WORKSPACE_POSIX"/. "$STAGING_POSIX/workspace/"

echo
echo "===== TAO MOT ZIP DE UPLOAD ====="
build_upload_zip "$STAGING_POSIX" "$UPLOAD_ZIP_POSIX"
echo "V39_EXIT_CODE=$V39_EXIT_CODE"
echo "Chi can upload file UPLOAD_THIS_v39-*.zip nay len chat."

if grep -q "REFERENCE PACK CHUA DU" "$LOG_POSIX"; then
    echo
    echo "V39 VAN THIEU DU LIEU. Candidate report va EXACT_DATA_NEEDED_V39.txt da duoc dong goi."
    open_workspace
fi
