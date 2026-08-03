#!/usr/bin/env bash

set -u
set -o pipefail

TMP_COMPAT="$(mktemp -d)"
cleanup() {
    rm -rf "$TMP_COMPAT"
}
trap cleanup EXIT

cat > "$TMP_COMPAT/sitecustomize.py" <<'PY'
try:
    import vnstock
    if not hasattr(vnstock, "Reference"):
        from vnstock_data import Reference
        vnstock.Reference = Reference
except Exception:
    pass
PY

export PYTHONPATH="$TMP_COMPAT${PYTHONPATH:+:$PYTHONPATH}"
exec bash scripts/run_v39_one_shot_external_resolution_gitbash.sh
