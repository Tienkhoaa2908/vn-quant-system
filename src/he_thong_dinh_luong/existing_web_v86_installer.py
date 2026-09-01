"""Install V86 realtime-health bridge into the approved V84 web.

The user-facing service remains http://127.0.0.1:8787. V86 replaces the meaning
of the legacy ``/api/realtime`` GET route (when present) with read-only sidecar
health. It does NOT start a WebSocket inside the web process and adds no order
mutation endpoint.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil

from . import existing_web_v78_installer as v78
from . import existing_web_v84_installer as v84

HTML_MARK = "V86_DNSE_OPENAPI_REALTIME_HEALTH"
PY_MARK = "V86_DNSE_OPENAPI_REALTIME_BRIDGE"


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise ValueError(f"V86_INSTALL_ANCHOR_{label}_COUNT={count}")
    return text.replace(old, new, 1)


def _replace_route_block(text: str, route: str, replacement: str) -> tuple[str, bool]:
    lines = text.splitlines(keepends=True)
    needle = f'            elif path == "{route}":'
    start = None
    for i, line in enumerate(lines):
        if line.rstrip("\r\n") == needle:
            start = i
            break
    if start is None:
        return text, False
    end = len(lines)
    for j in range(start + 1, len(lines)):
        stripped = lines[j].rstrip("\r\n")
        if stripped.startswith("            elif path ==") or stripped == "            else:":
            end = j
            break
    new_lines = lines[:start] + [replacement] + lines[end:]
    return "".join(new_lines), True


def patch_index(text: str) -> str:
    text = v84.patch_index(text)
    if 'href="/realtime_v86.css"' not in text:
        text = _replace_once(
            text,
            '  <link rel="stylesheet" href="/main_operating_v84.css">',
            '  <link rel="stylesheet" href="/main_operating_v84.css">\n'
            '  <!-- V86_DNSE_OPENAPI_REALTIME_HEALTH -->\n'
            '  <link rel="stylesheet" href="/realtime_v86.css">',
            "INDEX_CSS",
        )
    if 'src="/realtime_v86.js"' not in text:
        text = _replace_once(
            text,
            '  <script src="/main_operating_v84.js"></script>',
            '  <script src="/main_operating_v84.js"></script>\n'
            '  <!-- V86_DNSE_OPENAPI_REALTIME_HEALTH -->\n'
            '  <script src="/realtime_v86.js"></script>',
            "INDEX_JS",
        )
    return text


def patch_webapp(text: str) -> tuple[str, bool]:
    text = v84.patch_webapp(text)
    if f"# {PY_MARK}_IMPORT" not in text:
        anchor = "from he_thong_dinh_luong.local_workstation_v83_bridge import read_v83_dashboard\n"
        text = _replace_once(
            text,
            anchor,
            anchor
            + "\n# V86_DNSE_OPENAPI_REALTIME_BRIDGE_IMPORT\n"
            + "from he_thong_dinh_luong.local_workstation_v86_bridge import read_v86_realtime_status\n",
            "WEBAPP_IMPORT",
        )
    if '"/realtime_v86.js"' not in text:
        text = _replace_once(
            text,
            '                "/main_operating_v84.css",\n',
            '                "/main_operating_v84.css",\n'
            '                "/realtime_v86.js",\n'
            '                "/realtime_v86.css",\n',
            "WEBAPP_STATIC",
        )

    replacement = (
        '            elif path == "/api/realtime":\n'
        '                self._send_json(read_v86_realtime_status(SYSTEM_ROOT))\n'
    )
    text, legacy_replaced = _replace_route_block(text, "/api/realtime", replacement)

    if 'elif path == "/api/realtime-v86":' not in text:
        anchor = (
            '            elif path == "/api/dashboard-v83":\n'
            '                self._send_json(read_v83_dashboard(SYSTEM_ROOT))\n'
        )
        text = _replace_once(
            text,
            anchor,
            anchor
            + '            elif path == "/api/realtime-v86":\n'
            + '                self._send_json(read_v86_realtime_status(SYSTEM_ROOT))\n',
            "WEBAPP_GET",
        )
    return text, legacy_replaced


def install(system_root: Path, assets_root: Path) -> dict[str, object]:
    root = Path(system_root).resolve()
    assets = Path(assets_root).resolve()
    index = root / "web" / "index.html"
    webapp = root / "src" / "vn_quant_local" / "webapp.py"
    if not index.is_file() or not webapp.is_file():
        raise ValueError("V86_EXISTING_WORKSTATION_WEB_NOT_FOUND")

    before = {"index": v78.digest(index), "webapp": v78.digest(webapp)}
    index_text = index.read_text(encoding="utf-8")
    webapp_text = webapp.read_text(encoding="utf-8")
    new_index = patch_index(index_text)
    new_webapp, legacy_replaced = patch_webapp(webapp_text)
    changed = new_index != index_text or new_webapp != webapp_text

    backup: Path | None = None
    if changed:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = root / "validation" / "v86_web_backup" / stamp
        backup.mkdir(parents=True, exist_ok=False)
        shutil.copy2(index, backup / "index.html")
        shutil.copy2(webapp, backup / "webapp.py")
        index.write_text(new_index, encoding="utf-8", newline="\n")
        webapp.write_text(new_webapp, encoding="utf-8", newline="\n")

    inherited = (
        (assets.parent / "v78", ("tactical_v78.js", "tactical_v78.css")),
        (assets.parent / "v82", ("tactical_profit_v82.js", "tactical_profit_v82.css")),
        (assets.parent / "v83", ("capital_discipline_v83.js", "capital_discipline_v83.css")),
        (assets.parent / "v84", ("main_operating_v84.js", "main_operating_v84.css")),
        (assets, ("realtime_v86.js", "realtime_v86.css")),
    )
    for folder, names in inherited:
        for name in names:
            source = folder / name
            if not source.is_file():
                raise ValueError(f"V86_ASSET_MISSING:{name}")
            shutil.copy2(source, root / "web" / name)

    after = {"index": v78.digest(index), "webapp": v78.digest(webapp)}
    report = {
        "status": "SUCCESS",
        "mode": "DNSE_OPENAPI_REALTIME_SIDECAR_BRIDGE",
        "changed": changed,
        "before_sha256": before,
        "after_sha256": after,
        "backup_dir": str(backup) if backup else None,
        "existing_port": 8787,
        "endpoint": "/api/realtime-v86",
        "legacy_realtime_get_route_replaced": legacy_replaced,
        "web_process_owns_websocket": False,
        "isolated_sidecar_required": True,
        "canonical_rest_runtime_replaced": False,
        "research_policy_changed": False,
        "credentials_or_trading_state_touched": False,
        "live_order_endpoint_added": False,
        "trading_token_requested": False,
    }
    output = root / "validation" / "v86_web_integration_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--system-root", type=Path, required=True)
    parser.add_argument("--assets-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = install(args.system_root, args.assets_root)
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "error": f"{type(exc).__name__}:{exc}"}, ensure_ascii=False))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
