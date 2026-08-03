#!/usr/bin/env bash

set -u
set -o pipefail

BRANCH="agent/model-lab-predictive-value-dnse-sync-v3"
WORKSPACE_POSIX="/c/Users/welcome/Documents/vn-quant-data/reference/v39-decision-surface"
V22_POSIX="/c/Users/welcome/Documents/vn-quant-data/historical-research-input-v22-20260801-223238/daily_prediction_input.zip"
SQLITE_POSIX="/c/Users/welcome/Documents/vn-quant-data/market-data/dnse_ohlcv_v20.sqlite3"
REPO_FULL_NAME="Tienkhoaa2908/vn-quant-system"
GUIDE_POSIX="$WORKSPACE_POSIX/BAT_DAU_O_DAY_V39.txt"

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

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    fail "hay chay trong repository vn-quant-system"
fi
if ! command -v cygpath >/dev/null 2>&1; then
    fail "runner nay can Git Bash tren Windows"
fi

echo "===== V39 + ONE UPLOAD ZIP ====="
echo "Neu workspace trong: khong chay lai V36-V39; tu mo dung thu muc va huong dan."
echo "Neu da co input: chay V39, ghi console va tao mot ZIP duy nhat de upload."
echo "Khong dong goi full SQLite/V22; chi ghi SHA-256 cua hai input lon."
echo "Neu phat hien API secret, bearer token hoac private key, bundle se fail closed."

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
    tests/test_upload_handoff_bundle_v39.py \
    tests/test_v39_guided_input.py \
    || fail "py_compile runner that bai"
python -m unittest \
    tests.test_upload_handoff_bundle_v39 \
    tests.test_v39_guided_input \
    -v || fail "unit test runner that bai"

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
    echo
    echo "WORKSPACE DANG TRONG. KHONG CHAY LAI V36-V39."
    echo "Windows Explorer va file BAT_DAU_O_DAY_V39.txt se tu mo."
    echo "Viec duy nhat can lam: dat tai lieu nguon chinh thuc vao source_documents."
    echo "Neu khong biet dien CSV/JSON, upload tai lieu nguon len chat de AI tao file compact."
    echo "Sau khi co input, chay lai CHINH lenh nay."
    echo "HOM NAY KHONG CAN UPLOAD THEM ZIP VI KET QUA KHONG DOI."
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
- workspace V39 va source_documents;
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

printf '%s\n' "$REPO_FULL_NAME" > "$STAGING_POSIX/metadata/repository.txt"
git branch --show-current > "$STAGING_POSIX/metadata/git_branch.txt"
git rev-parse HEAD > "$STAGING_POSIX/metadata/git_head.txt"
git status --short > "$STAGING_POSIX/metadata/git_status_short.txt"
git log -1 --format='%H%n%cI%n%s' > "$STAGING_POSIX/metadata/git_commit.txt"
printf '%s\n' "$PREFLIGHT_JSON" > "$STAGING_POSIX/metadata/input_preflight.json"

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
} > "$STAGING_POSIX/metadata/canonical_input_hashes.txt"

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

if [[ -d "$WORKSPACE_POSIX" ]]; then
    cp -a "$WORKSPACE_POSIX"/. "$STAGING_POSIX/workspace/"
else
    echo "WORKSPACE_MISSING=$WORKSPACE_POSIX" \
        > "$STAGING_POSIX/metadata/workspace_missing.txt"
fi

find "$STAGING_POSIX" -type f -printf '%P\n' | sort \
    > "$STAGING_POSIX/metadata/staging_file_list.txt"

echo
echo "===== TAO MOT ZIP DE UPLOAD ====="
python -m he_thong_dinh_luong.upload_handoff_bundle_v39 \
    --staging-dir "$(cygpath -w "$STAGING_POSIX")" \
    --output-zip "$(cygpath -w "$UPLOAD_ZIP_POSIX")" \
    || fail "khong tao duoc upload ZIP; kiem tra canh bao sensitive content"

[[ -f "$UPLOAD_ZIP_POSIX" ]] || fail "upload ZIP khong ton tai"
UPLOAD_SHA="$(sha256sum "$UPLOAD_ZIP_POSIX" | awk '{print $1}')"
UPLOAD_SIZE="$(wc -c < "$UPLOAD_ZIP_POSIX")"

echo
echo "===== FILE DUY NHAT CAN UPLOAD ====="
echo "UPLOAD_THIS_FILE=$UPLOAD_ZIP_POSIX"
echo "UPLOAD_THIS_FILE_WINDOWS=$(cygpath -w "$UPLOAD_ZIP_POSIX")"
echo "UPLOAD_SHA256=$UPLOAD_SHA"
echo "UPLOAD_SIZE_BYTES=$UPLOAD_SIZE"
echo "V39_EXIT_CODE=$V39_EXIT_CODE"
echo
echo "Chi can upload file UPLOAD_THIS_v39-*.zip nay len chat."

if grep -q "REFERENCE PACK CHUA DU" "$LOG_POSIX"; then
    echo
    echo "V39 VAN THIEU DU LIEU. Thu muc va huong dan se tu mo de bo sung input."
    open_workspace
fi
