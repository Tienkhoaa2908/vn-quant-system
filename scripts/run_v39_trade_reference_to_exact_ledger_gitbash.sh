#!/usr/bin/env bash

set -u
set -o pipefail

BRANCH="agent/model-lab-predictive-value-dnse-sync-v3"
V34_NAME="future-paper-holdout-freeze-v34-1-20260803-094853.zip"
V34_SHA="642a19cddadc271a2cffb16261ad9e0a4fceadab884eea308ab8bce88debbf80"
V33_NAME="turnover-policy-stability-v33-20260803-091649.zip"
V33_SHA="0019679a8108f576b5063e01d493d018148adbd040212cea50fd5fe288f75555"
V32_NAME="portfolio-ablation-v32-1-canonical-11y-20260803-084529.zip"
V32_SHA="c8f95875a5af8762b5a2de2ee923453135e238593ee708eacbe3e8b4bc6f781f"
V22_POSIX="/c/Users/welcome/Documents/vn-quant-data/historical-research-input-v22-20260801-223238/daily_prediction_input.zip"
V22_SHA="66f4dd6699026289501b260949237772f832ac716e700fa686f8b0b8accd38e5"
STORE_POSIX="/c/Users/welcome/Documents/vn-quant-data/market-data/dnse_ohlcv_v20.sqlite3"
STORE_SHA="7b6f2274d43c12a311f83aa71952ef2abcfca04e2f5204c2f0e9a36a6c144549"
REFERENCE_ROOT="/c/Users/welcome/Documents/vn-quant-data/reference"
PAPER_ROOT="/c/Users/welcome/Documents/vn-quant-data/paper"
WORKSPACE_POSIX="$REFERENCE_ROOT/v39-decision-surface"
PAPER_POSIX="$PAPER_ROOT/paper_observations_v37.csv"

keep_open() {
    echo
    echo "Git Bash duoc giu mo."
    exec bash
}

fail() {
    echo "FAILED: $*" >&2
    keep_open
}

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    fail "hay chay trong repository vn-quant-system"
fi
if ! command -v cygpath >/dev/null 2>&1; then
    fail "runner nay can Git Bash tren Windows"
fi

echo "===== MUC TIEU V39 ====="
echo "Mot lenh: V38 surface -> persistent source workspace -> exact ledger -> V37 gate"
echo "Lan dau tao workspace. Lan sau tu validate va chay ledger khi du 510/510/52 + ops 9/9."
echo "Khong tai mang tu dong, khong suy sector, khong gia mao zero-event, khong gui lenh that."

echo
echo "===== DONG BO CODE ====="
if ! git fetch origin \
  || ! git switch "$BRANCH" \
  || ! git pull --ff-only origin "$BRANCH"; then
    fail "khong dong bo duoc branch $BRANCH"
fi
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"

echo
echo "===== KIEM TRA V39 ====="
python -m py_compile \
    src/he_thong_dinh_luong/trade_reference_pack_v39.py \
    src/he_thong_dinh_luong/trade_reference_pack_v39_safe_runner.py \
    src/he_thong_dinh_luong/integrated_data_ledger_v36_v39_adapter.py \
    src/he_thong_dinh_luong/integrated_data_ledger_v36_v39_adapter_safe_runner.py \
    tests/test_trade_reference_pack_v39.py \
    || fail "py_compile V39 that bai"
python -m unittest tests.test_trade_reference_pack_v39 -v \
    || fail "unit test V39 that bai"

MARKER="$(mktemp)"
touch "$MARKER"
echo
echo "===== 1/3 CHAY V38 DE LAY SURFACE MOI NHAT ====="
if ! printf 'exit\n' | bash scripts/run_v38_trade_evidence_accelerator_gitbash.sh; then
    rm -f "$MARKER"
    fail "V38 integrated runner that bai"
fi
V36_POSIX="$(find "$PWD/artifacts" -maxdepth 1 -type f -name 'integrated-data-ledger-v36-*.zip' -newer "$MARKER" -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n 1 | cut -d' ' -f2-)"
V38_POSIX="$(find "$PWD/artifacts" -maxdepth 1 -type f -name 'trade-evidence-accelerator-v38-*.zip' -newer "$MARKER" -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n 1 | cut -d' ' -f2-)"
rm -f "$MARKER"
[[ -f "$V36_POSIX" ]] || fail "khong tim thay V36 artifact moi"
[[ -f "$V38_POSIX" ]] || fail "khong tim thay V38 artifact moi"
V36_SHA="$(sha256sum "$V36_POSIX" | awk '{print $1}')"
V38_SHA="$(sha256sum "$V38_POSIX" | awk '{print $1}')"

RUN_ID="$(date +%Y%m%d-%H%M%S)"
V39_OUT_POSIX="$PWD/artifacts/trade-reference-pack-v39-$RUN_ID"
V39_OUT_WIN="$(cygpath -w "$V39_OUT_POSIX")"
WORKSPACE_WIN="$(cygpath -w "$WORKSPACE_POSIX")"

echo
echo "===== 2/3 TAO HOAC VALIDATE REFERENCE WORKSPACE ====="
python -m he_thong_dinh_luong.trade_reference_pack_v39_safe_runner \
    --v36-artifact-zip "$(cygpath -w "$V36_POSIX")" \
    --v38-artifact-zip "$(cygpath -w "$V38_POSIX")" \
    --expected-v36-sha256 "$V36_SHA" \
    --expected-v38-sha256 "$V38_SHA" \
    --workspace-dir "$WORKSPACE_WIN" \
    --output-dir "$V39_OUT_WIN"
V39_STATUS=$?
[[ $V39_STATUS -eq 0 ]] || fail "V39 reference runner that bai"

READY="$(python - "$V39_OUT_WIN" <<'PY'
import json
from pathlib import Path
import sys
report = json.loads((Path(sys.argv[1]) / "trade_reference_pack_v39.json").read_text(encoding="utf-8-sig"))
print("true" if report.get("reference_pack_ready") is True else "false")
PY
)"

echo
echo "===== TOM TAT REFERENCE PACK ====="
python - "$V39_OUT_WIN" <<'PY'
import json
from pathlib import Path
import sys
report = json.loads((Path(sys.argv[1]) / "trade_reference_pack_v39.json").read_text(encoding="utf-8-sig"))
metrics = report.get("metrics", {})
print("DECISION=", report.get("decision"))
print("WORKSPACE=", report.get("workspace_dir"))
print("WORKSPACE_FILES_CREATED=", "|".join(report.get("workspace_files_created_this_run", [])))
print("SECTOR=", metrics.get("sector_verified"), "/", metrics.get("sector_required"))
print("CORPORATE_ACTION_WINDOWS=", metrics.get("windows_verified"), "/", metrics.get("windows_required"))
print("CORPORATE_ACTION_EVENTS=", metrics.get("events_verified"), "/", metrics.get("event_rows"))
print("PRICE_DATES=", metrics.get("price_dates_verified"), "/", metrics.get("price_dates_required"))
print("EXECUTION_CONTRACT=", metrics.get("execution_contract_verified"))
print("OPS=", metrics.get("operational_controls_verified"), "/", metrics.get("operational_controls_required"))
print("GAP_COUNT=", report.get("gap_count"))
for key, value in report.get("gaps_by_workstream", {}).items():
    print("GAP", key, value)
print("NEXT_ACTION=", report.get("next_action"))
PY

echo "V39_ARTIFACT=${V39_OUT_POSIX}.zip"
sha256sum "${V39_OUT_POSIX}.zip"

if [[ "$READY" != "true" ]]; then
    echo
    echo "REFERENCE PACK CHUA DU. KHONG CHAY EXACT LEDGER."
    echo "Hay hoan thien cac file trong: $WORKSPACE_POSIX"
    echo "Raw source documents dat trong: $WORKSPACE_POSIX/source_documents"
    echo "Sau do chay lai CHINH lenh V39 nay; khong can version moi."
    keep_open
fi

find_artifact() {
    local name="$1"
    local expected="$2"
    local candidate actual
    while IFS= read -r candidate; do
        [[ -f "$candidate" ]] || continue
        actual="$(sha256sum "$candidate" | awk '{print $1}')"
        if [[ "$actual" == "$expected" ]]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done < <(find "$PWD" "$PWD/artifacts" "$HOME/Downloads" "$HOME/Desktop" "$HOME/Documents" -type f -name "$name" -print 2>/dev/null | awk '!seen[$0]++')
    return 1
}

V34_POSIX="$(find_artifact "$V34_NAME" "$V34_SHA")" || fail "thieu V34 canonical"
V33_POSIX="$(find_artifact "$V33_NAME" "$V33_SHA")" || fail "thieu V33 canonical"
V32_POSIX="$(find_artifact "$V32_NAME" "$V32_SHA")" || fail "thieu V32 canonical"
for required in "$V22_POSIX" "$STORE_POSIX"; do
    [[ -f "$required" ]] || fail "thieu file canonical: $required"
done
[[ "$(sha256sum "$V22_POSIX" | awk '{print $1}')" == "$V22_SHA" ]] || fail "V22 hash thay doi"
[[ "$(sha256sum "$STORE_POSIX" | awk '{print $1}')" == "$STORE_SHA" ]] || fail "SQLite hash thay doi"

EXACT_V36_OUT_POSIX="$PWD/artifacts/integrated-data-ledger-v36-v39-$RUN_ID"
EXACT_V37_OUT_POSIX="$PWD/artifacts/trade-readiness-v37-v39-$RUN_ID"
EXACT_V36_OUT_WIN="$(cygpath -w "$EXACT_V36_OUT_POSIX")"
EXACT_V37_OUT_WIN="$(cygpath -w "$EXACT_V37_OUT_POSIX")"

echo
echo "===== 3/3 CHAY EXACT LEDGER + CAPITAL GATE ====="
python -m he_thong_dinh_luong.integrated_data_ledger_v36_v39_adapter_safe_runner \
    --v39-output-dir "$V39_OUT_WIN" \
    --v34-artifact-zip "$(cygpath -w "$V34_POSIX")" \
    --v33-artifact-zip "$(cygpath -w "$V33_POSIX")" \
    --v32-artifact-zip "$(cygpath -w "$V32_POSIX")" \
    --v22-input-zip "$(cygpath -w "$V22_POSIX")" \
    --sqlite-store "$(cygpath -w "$STORE_POSIX")" \
    --output-dir "$EXACT_V36_OUT_WIN" \
    --expected-v34-sha256 "$V34_SHA" \
    --expected-v33-sha256 "$V33_SHA" \
    --expected-v32-sha256 "$V32_SHA" \
    --expected-v22-sha256 "$V22_SHA" \
    --expected-sqlite-sha256 "$STORE_SHA" \
    --initial-capital-vnd 1000000000
ADAPTER_STATUS=$?
[[ $ADAPTER_STATUS -eq 0 ]] || fail "exact V36/V39 adapter that bai"
EXACT_V36_ZIP="${EXACT_V36_OUT_POSIX}.zip"
[[ -f "$EXACT_V36_ZIP" ]] || fail "exact V36 khong tao ZIP"
EXACT_V36_SHA="$(sha256sum "$EXACT_V36_ZIP" | awk '{print $1}')"

V37_ARGS=(
    --v36-artifact-zip "$(cygpath -w "$EXACT_V36_ZIP")"
    --expected-v36-sha256 "$EXACT_V36_SHA"
    --operational-checklist "$(cygpath -w "$V39_OUT_POSIX/operational_checklist_v37.json")"
    --output-dir "$EXACT_V37_OUT_WIN"
)
[[ -f "$PAPER_POSIX" ]] && V37_ARGS+=(--paper-observations "$(cygpath -w "$PAPER_POSIX")")
python -m he_thong_dinh_luong.trade_readiness_v37_safe_runner "${V37_ARGS[@]}"
V37_STATUS=$?
[[ $V37_STATUS -eq 0 ]] || fail "V37 sau exact ledger that bai"

echo
echo "===== KET QUA CUOI ====="
python - "$EXACT_V36_OUT_WIN" "$EXACT_V37_OUT_WIN" <<'PY'
import json
from pathlib import Path
import sys
v36 = json.loads((Path(sys.argv[1]) / "integrated_data_ledger_v36.json").read_text(encoding="utf-8-sig"))
v37 = json.loads((Path(sys.argv[2]) / "trade_readiness_v37.json").read_text(encoding="utf-8-sig"))
print("LEDGER_STATUS=", v36.get("ledger_status"))
print("EXACT_CASH_LEDGER_PNL_COMPUTED=", v36.get("exact_cash_ledger_pnl_computed"))
print("EXACT_VNINDEX_COMPARISON_COMPUTED=", v36.get("exact_vnindex_comparison_computed"))
for row in v36.get("ledger_summaries", []):
    print("LEDGER", row.get("strategy"), row.get("scenario"), "NET_RETURN=", row.get("net_total_return"), "VNINDEX=", row.get("benchmark_total_return"), "RELATIVE=", row.get("relative_total_return"), "DRAWDOWN=", row.get("max_drawdown"), "PROFIT_VND=", row.get("net_profit_vnd"))
print("CAPITAL_STAGE=", v37.get("capital_stage"))
print("READINESS_SCORE_PERCENT=", v37.get("readiness_score_percent"))
print("PAPER_OBSERVATIONS=", v37.get("paper_holdout", {}).get("completed_observation_count"), "/ 12")
print("NEXT_ACTION=", v37.get("next_action"))
print("LIVE_CAPITAL_APPROVED=", v37.get("live_capital_approved"))
PY

echo "EXACT_V36_ARTIFACT=$EXACT_V36_ZIP"
sha256sum "$EXACT_V36_ZIP"
echo "EXACT_V37_ARTIFACT=${EXACT_V37_OUT_POSIX}.zip"
sha256sum "${EXACT_V37_OUT_POSIX}.zip"
keep_open
