#!/usr/bin/env bash
set -euo pipefail

BRANCH="agent/v83-capital-discipline-main-web"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
fail(){ echo "FAILED: $*" >&2; exit 2; }
[[ -n "$ROOT" ]] || fail "hay chay trong repository vn-quant-system"
cd "$ROOT"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "sai branch; can $BRANCH"
git diff --cached --quiet || fail "staging area co thay doi"

WEBAPP="vn_quant_local_system/src/vn_quant_local/webapp.py"
INDEX="vn_quant_local_system/web/index.html"
mapfile -t DIRTY < <(git diff --name-only --)
for path in "${DIRTY[@]}"; do
  case "$path" in
    "$WEBAPP"|"$INDEX") ;;
    *) fail "tracked change ngoai approved workstation web state: $path" ;;
  esac
done

SYSTEM="$ROOT/vn_quant_local_system"
PY="$SYSTEM/.venv/Scripts/python.exe"
STORE="$SYSTEM/data/market/dnse_ohlcv.sqlite3"
V77="$ROOT/du_lieu/v77-paper-oos-state"
V80="$ROOT/du_lieu/v80-tactical-paper-state"
[[ -f "$PY" ]] || fail "khong tim thay canonical workstation Python"
[[ -f "$STORE" ]] || fail "khong tim thay market DB"
[[ -f "$V77/freeze_manifest.json" ]] || fail "khong tim thay V77 state"
[[ -f "$V80/registry.json" ]] || fail "khong tim thay V80 state"
command -v cygpath >/dev/null 2>&1 || fail "Git Bash cygpath khong san sang"

if ! "$PY" - <<'PY' >/dev/null 2>&1
from zoneinfo import ZoneInfo
ZoneInfo("Asia/Ho_Chi_Minh")
PY
then
  echo "DEPENDENCY_tzdata=installing_tzdata==2025.2"
  "$PY" -m pip install --disable-pip-version-check "tzdata==2025.2"
else
  echo "DEPENDENCY_tzdata=already_verified"
fi
export PYTHONPATH="$(cygpath -w "$ROOT/src");$(cygpath -w "$SYSTEM/src")"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
"$PY" -c "import he_thong_dinh_luong.capital_discipline_audit_v83, he_thong_dinh_luong.capital_discipline_selection_v83, he_thong_dinh_luong.local_workstation_v83_bridge; print('V83_PYTHONPATH_PREFLIGHT=PASS')"

hash_tree(){
  local dir="$1"
  find "$dir" -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}'
}
RUN_ID="$(date +%Y%m%d-%H%M%S)"
ART="$ROOT/artifacts"
OUT="$ART/v83-capital-discipline-$RUN_ID"
V83="$OUT/v83"
BUNDLE_DIR="$ART/v83-capital-discipline-bundle-$RUN_ID"
BUNDLE="$ART/UPLOAD_THIS_v83_CAPITAL_DISCIPLINE_MAIN_WEB-$RUN_ID.zip"
LOG="$ART/v83-capital-discipline-$RUN_ID.log"
mkdir -p "$V83" "$BUNDLE_DIR" "$SYSTEM/data/v83-capital-discipline"

STORE_BEFORE="$("$PY" -m he_thong_dinh_luong.sqlite_market_fingerprint_v79 --store "$(cygpath -w "$STORE")")"
V77_BEFORE="$(hash_tree "$V77")"
V80_BEFORE="$(hash_tree "$V80")"
printf '%s\n' "$STORE_BEFORE" > "$BUNDLE_DIR/store_logical_before.json"
printf '%s\n' "$V77_BEFORE" > "$BUNDLE_DIR/v77_before.txt"
printf '%s\n' "$V80_BEFORE" > "$BUNDLE_DIR/v80_before.txt"

run_all() (
  set -euo pipefail
  echo "===== V83 CAPITAL DISCIPLINE + MAIN WEB ====="
  echo "HEAD=$(git rev-parse HEAD)"
  echo "CHAMPION_MODEL=C3_STABLE_3_PAST_IC_SHRUNK"
  echo "PRIMARY_PRODUCT_FOCUS=CAPITAL_DISCIPLINE"
  echo "NEW_LEADER_RESEARCH_REOPENED=false"
  echo "FIXED_POLICIES=C3_BASE,NO_ADD_UNDERWATER,PERSIST2_SEVERE_TRIM50,NO_ADD_PLUS_PERSIST2_TRIM50"
  echo "ENTRY_AUDIT=T1_OPEN_VS_T2_OPEN_VS_STAGED_50_50"
  echo "SELECTION_SAMPLE_END=2025-12-31"
  echo "YEAR_2026_USED_TO_SELECT=false"
  echo "LIVE_ORDERS_ALLOWED=false"
  echo "V77_STATE_DIGEST_BEFORE=$V77_BEFORE"
  echo "V80_STATE_DIGEST_BEFORE=$V80_BEFORE"

  echo "===== COMPILE + REGRESSION ====="
  "$PY" -m py_compile \
    src/he_thong_dinh_luong/capital_discipline_audit_v83.py \
    src/he_thong_dinh_luong/capital_discipline_selection_v83.py \
    src/he_thong_dinh_luong/local_workstation_v83_bridge.py \
    src/he_thong_dinh_luong/existing_web_v83_installer.py \
    tests/test_capital_discipline_audit_v83.py \
    tests/test_local_workstation_v83_bridge.py \
    tests/test_existing_web_v83_installer.py
  "$PY" -m unittest \
    tests.test_capital_discipline_audit_v83 \
    tests.test_local_workstation_v83_bridge \
    tests.test_existing_web_v83_installer -v

  echo "===== LOCATE AUDITED CAUSAL INPUTS ====="
  V81_DIR="$(find "$ART" -maxdepth 1 -type d -name 'v81-frozen-tactical-historical-audit-*' -print | sort | tail -n 1 || true)"
  if [[ -n "$V81_DIR" && -f "$V81_DIR/v68/v68_report.json" && -f "$V81_DIR/v70/v70_report.json" ]]; then
    V68="$V81_DIR/v68"; V70="$V81_DIR/v70"
    echo "V83_REUSE_V81_CAUSAL_OUTPUTS=true"
    echo "V83_REUSE_DIR=$V81_DIR"
  else
    echo "V83_REUSE_V81_CAUSAL_OUTPUTS=false"
    V68="$OUT/v68"; V70="$OUT/v70"; mkdir -p "$V68" "$V70"
    echo "===== REBUILD V68 CAUSAL STATES ====="
    ARGS=(--store "$(cygpath -w "$STORE")" --output-dir "$(cygpath -w "$V68")" --bootstrap-samples 1000 --search-root "$(cygpath -w "$SYSTEM/data")")
    [[ -d "$SYSTEM/validation" ]] && ARGS+=(--search-root "$(cygpath -w "$SYSTEM/validation")")
    [[ -d "$SYSTEM/outputs" ]] && ARGS+=(--search-root "$(cygpath -w "$SYSTEM/outputs")")
    "$PY" -m he_thong_dinh_luong.c3_hose_consolidated_v68_safe "${ARGS[@]}"
    echo "===== REBUILD V70 FROZEN C3 ====="
    "$PY" -m he_thong_dinh_luong.deep_portfolio_backtest_v70 --v68-output "$(cygpath -w "$V68")" --store "$(cygpath -w "$STORE")" --output-dir "$(cygpath -w "$V70")" --initial-capital 1000000000
  fi

  echo "===== V83 ALL-SAMPLE DIAGNOSTIC ====="
  "$PY" -m he_thong_dinh_luong.capital_discipline_audit_v83 \
    --v68-output "$(cygpath -w "$V68")" --v70-output "$(cygpath -w "$V70")" \
    --store "$(cygpath -w "$STORE")" --output-dir "$(cygpath -w "$V83")" --initial-capital 1000000000

  echo "===== V83 PRE-2026 SELECTION EVIDENCE ====="
  "$PY" -m he_thong_dinh_luong.capital_discipline_selection_v83 \
    --v68-output "$(cygpath -w "$V68")" --v70-output "$(cygpath -w "$V70")" \
    --store "$(cygpath -w "$STORE")" --output-dir "$(cygpath -w "$V83")" --initial-capital 1000000000

  "$PY" - "$V83/v83_report.json" "$V83/v83_selection_report.json" "$SYSTEM/data/v83-capital-discipline/LATEST.json" <<'PY'
import json,sys
from pathlib import Path
allr=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
sel=json.loads(Path(sys.argv[2]).read_text(encoding='utf-8-sig'))
allr['primary_base_dnse_all_sample']=allr.get('primary_base_dnse',[])
allr['primary_base_dnse']=sel.get('primary_base_dnse_pre2026',[])
allr['selection_sample']='PRE2026_SELECTION'
allr['selection_end']=sel.get('selection_end')
allr['entry_timing_primary_pre2026']=sel.get('entry_timing_pre2026',{})
allr['year_2026_used_to_select']=False
Path(sys.argv[3]).write_text(json.dumps(allr,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
PY

  echo "===== PROFIT + ENTRY SUMMARY: PRE-2026 SELECTION ====="
  "$PY" - "$SYSTEM/data/v83-capital-discipline/LATEST.json" <<'PY'
import json,sys
from pathlib import Path
r=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
print('STATUS='+str(r['status']))
print('PRIMARY_VARIANT='+str(r['primary_variant']))
print('SELECTION_SAMPLE='+str(r.get('selection_sample')))
print('SELECTION_END='+str(r.get('selection_end')))
for p in r.get('primary_base_dnse',[]):
    print('POLICY',p['policy_id'],'ENDING_NAV_VND',round(float(p['ending_nav_vnd']),2),'NET_PROFIT_VND',round(float(p['net_profit_vnd']),2),'TOTAL_RETURN',p['total_return'],'CAGR',p.get('cagr'),'MDD',p.get('max_drawdown'),'DELTA_NAV_VND',p.get('incremental_nav_vs_c3_vnd'))
print('ENTRY_PRE2026='+json.dumps(r.get('entry_timing_primary_pre2026',{}),sort_keys=True))
print('ENTRY_2026_SHADOW='+json.dumps(r.get('entry_timing_primary_2026_shadow',{}),sort_keys=True))
PY

  echo "===== INSTALL V83 MAIN WEB ====="
  "$PY" -m he_thong_dinh_luong.existing_web_v83_installer --system-root "$(cygpath -w "$SYSTEM")" --assets-root "$(cygpath -w "$ROOT/web_extensions/v83")"

  echo "===== INTEGRITY ====="
  STORE_AFTER="$("$PY" -m he_thong_dinh_luong.sqlite_market_fingerprint_v79 --store "$(cygpath -w "$STORE")")"
  V77_AFTER="$(hash_tree "$V77")"; V80_AFTER="$(hash_tree "$V80")"
  echo "STORE_LOGICAL_AFTER=$STORE_AFTER"
  echo "V77_STATE_DIGEST_AFTER=$V77_AFTER"
  echo "V80_STATE_DIGEST_AFTER=$V80_AFTER"
  [[ "$STORE_AFTER" == "$STORE_BEFORE" ]] || fail "logical market bars changed during V83"
  [[ "$V77_AFTER" == "$V77_BEFORE" ]] || fail "V77 changed during V83"
  [[ "$V80_AFTER" == "$V80_BEFORE" ]] || fail "V80 changed during V83"
)

set +e
run_all 2>&1 | tee "$LOG"
RC=${PIPESTATUS[0]}
set -e
cp "$LOG" "$BUNDLE_DIR/run.log" || true
git branch --show-current > "$BUNDLE_DIR/git_branch.txt"
git rev-parse HEAD > "$BUNDLE_DIR/git_head.txt"
[[ -d "$V83" ]] && cp -R "$V83" "$BUNDLE_DIR/v83" || true
[[ -f "$SYSTEM/data/v83-capital-discipline/LATEST.json" ]] && cp "$SYSTEM/data/v83-capital-discipline/LATEST.json" "$BUNDLE_DIR/LATEST.json" || true
[[ -f "$SYSTEM/validation/v83_web_integration_report.json" ]] && cp "$SYSTEM/validation/v83_web_integration_report.json" "$BUNDLE_DIR/" || true
printf '%s\n' "$(hash_tree "$V77")" > "$BUNDLE_DIR/v77_after.txt" || true
printf '%s\n' "$(hash_tree "$V80")" > "$BUNDLE_DIR/v80_after.txt" || true
powershell.exe -NoProfile -Command "Compress-Archive -Path '$(cygpath -w "$BUNDLE_DIR")\\*' -DestinationPath '$(cygpath -w "$BUNDLE")' -Force" || true

echo
if [[ "$RC" -eq 0 ]]; then
  echo "===== V83 COMPLETE ====="
  echo "WEB_URL=http://127.0.0.1:8787"
  echo "UPLOAD_ZIP=$BUNDLE"
  echo "UPLOAD_ZIP_SHA256=$(sha256sum "$BUNDLE" | awk '{print $1}')"
  echo "Restart existing web server so /api/dashboard-v83 is loaded."
else
  echo "===== V83 FAILED ====="
fi
exit "$RC"
