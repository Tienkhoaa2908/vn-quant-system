#!/usr/bin/env bash
set -euo pipefail

BRANCH="agent/v79-c3-tactical-capital-policy"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
fail(){ echo "FAILED: $*" >&2; exit 2; }
[[ -n "$ROOT" ]] || fail "hay chay trong repository vn-quant-system"
cd "$ROOT"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "sai branch; can $BRANCH"

git diff --cached --quiet || fail "staging area co thay doi; khong tu dong che thay doi staged"

WEBAPP="vn_quant_local_system/src/vn_quant_local/webapp.py"
INDEX="vn_quant_local_system/web/index.html"
RUNNER="scripts/run_v79_tactical_capital_policy_gitbash.sh"

mapfile -t DIRTY_TRACKED < <(git diff --name-only --)
if [[ "${#DIRTY_TRACKED[@]}" -eq 0 ]]; then
  echo "V79_WORKTREE_MODE=CLEAN_DIRECT"
  exec bash "$RUNNER"
fi

for path in "${DIRTY_TRACKED[@]}"; do
  case "$path" in
    "$WEBAPP"|"$INDEX") ;;
    *) fail "tracked change ngoai approved V78 web state: $path" ;;
  esac
done

[[ -f "$WEBAPP" ]] || fail "khong tim thay $WEBAPP"
[[ -f "$INDEX" ]] || fail "khong tim thay $INDEX"
grep -q 'V78_TACTICAL_BRIDGE_IMPORT' "$WEBAPP" || fail "webapp dirty nhung khong co V78 bridge marker"
grep -q 'V78_TACTICAL_EXISTING_WEB' "$INDEX" || fail "index dirty nhung khong co V78 tactical marker"

PATCH="$(mktemp "${TMPDIR:-/tmp}/v79-v78-web-state.XXXXXX.patch")"
git diff --binary -- "$WEBAPP" "$INDEX" > "$PATCH"
[[ -s "$PATCH" ]] || fail "dirty web state nhung patch rong"
PATCH_SHA="$(sha256sum "$PATCH" | awk '{print $1}')"

echo "V79_WORKTREE_MODE=PRESERVE_APPROVED_V78_WEB"
echo "PRESERVED_TRACKED_PATHS=${DIRTY_TRACKED[*]}"
echo "V78_WEB_PATCH_SHA256=$PATCH_SHA"
echo "V78_WEB_PATCH_TEMP=$PATCH"

restore_local_web() {
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
