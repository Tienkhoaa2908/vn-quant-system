#!/usr/bin/env bash
set -euo pipefail

BRANCH="agent/v80-forward-paper-tactical-actions"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
fail(){ echo "FAILED: $*" >&2; exit 2; }
[[ -n "$ROOT" ]] || fail "hay chay trong repository vn-quant-system"
cd "$ROOT"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "sai branch; can $BRANCH"
git diff --cached --quiet || fail "staging area co thay doi; khong tu dong che thay doi staged"

WEBAPP="vn_quant_local_system/src/vn_quant_local/webapp.py"
INDEX="vn_quant_local_system/web/index.html"
RUNNER="${V80_INNER_RUNNER:-scripts/run_v80_tactical_forward_paper_gitbash.sh}"
[[ -f "$RUNNER" ]] || fail "khong tim thay inner runner: $RUNNER"

mapfile -t DIRTY_TRACKED < <(git diff --name-only --)
if [[ "${#DIRTY_TRACKED[@]}" -eq 0 ]]; then
  echo "V80_WORKTREE_MODE=CLEAN_DIRECT"
  exec bash "$RUNNER"
fi
for path in "${DIRTY_TRACKED[@]}"; do
  case "$path" in
    "$WEBAPP"|"$INDEX") ;;
    *) fail "tracked change ngoai approved V78 web state: $path" ;;
  esac
done
[[ -f "$WEBAPP" && -f "$INDEX" ]] || fail "approved V78 web files missing"
grep -q 'V78_TACTICAL_BRIDGE_IMPORT' "$WEBAPP" || fail "webapp dirty nhung khong co V78 bridge marker"
grep -q 'V78_TACTICAL_EXISTING_WEB' "$INDEX" || fail "index dirty nhung khong co V78 tactical marker"

PATCH="$(mktemp "${TMPDIR:-/tmp}/v80-v78-web-state.XXXXXX.patch")"
git diff --binary -- "$WEBAPP" "$INDEX" > "$PATCH"
[[ -s "$PATCH" ]] || fail "dirty web state nhung patch rong"
PATCH_SHA="$(sha256sum "$PATCH" | awk '{print $1}')"
echo "V80_WORKTREE_MODE=PRESERVE_APPROVED_V78_WEB"
echo "V78_WEB_PATCH_SHA256=$PATCH_SHA"
echo "V78_WEB_PATCH_TEMP=$PATCH"

restore_local_web(){
  local rc=$?
  trap - EXIT
  if [[ -s "$PATCH" ]]; then
    if git apply --whitespace=nowarn "$PATCH"; then
      rm -f "$PATCH"
      echo "V78_LOCAL_WEB_STATE_RESTORED=true"
    else
      echo "FAILED: khong the khoi phuc approved V78 web state" >&2
      echo "RECOVERY_PATCH=$PATCH" >&2
      exit 97
    fi
  fi
  exit "$rc"
}
trap restore_local_web EXIT

git restore --worktree -- "$WEBAPP" "$INDEX"
git diff --quiet || fail "worktree van dirty sau khi tam thoi cat approved web patch"
echo "V78_LOCAL_WEB_STATE_TEMPORARILY_SHELVED=true"
bash "$RUNNER"
