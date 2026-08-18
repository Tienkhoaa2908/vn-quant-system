"""Install V82 profit/paper panels into the already-approved local web.

V82 first ensures the additive V78 tactical bridge is present, then adds one
read-only dashboard endpoint plus scoped JS/CSS assets. Existing layout, port,
credentials, market data and persistent paper states are not replaced or reset.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil

from . import existing_web_v78_installer as v78

HTML_MARK = "V82_PROFIT_PAPER_EXISTING_WEB"
PY_MARK = "V82_PROFIT_PAPER_BRIDGE"


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise ValueError(f"V82_INSTALL_ANCHOR_{label}_COUNT={count}")
    return text.replace(old, new, 1)


def patch_index(text: str) -> str:
    text = v78.patch_index(text)
    if 'href="/tactical_profit_v82.css"' not in text:
        text = _replace_once(
            text,
            '  <link rel="stylesheet" href="/tactical_v78.css">',
            '  <link rel="stylesheet" href="/tactical_v78.css">\n'
            '  <!-- V82_PROFIT_PAPER_EXISTING_WEB -->\n'
            '  <link rel="stylesheet" href="/tactical_profit_v82.css">',
            "INDEX_CSS",
        )
    if 'src="/tactical_profit_v82.js"' not in text:
        text = _replace_once(
            text,
            '  <script src="/tactical_v78.js"></script>',
            '  <script src="/tactical_v78.js"></script>\n'
            '  <!-- V82_PROFIT_PAPER_EXISTING_WEB -->\n'
            '  <script src="/tactical_profit_v82.js"></script>',
            "INDEX_JS",
        )
    return text


def patch_webapp(text: str) -> str:
    text = v78.patch_webapp(text)
    if f"# {PY_MARK}_IMPORT" not in text:
        anchor = (
            "from he_thong_dinh_luong.local_workstation_v78_bridge import (\n"
            "    read_v78_tactical_snapshot,\n"
            "    refresh_v78_tactical_snapshot,\n"
            ")\n"
        )
        insert = anchor + (
            "\n# V82_PROFIT_PAPER_BRIDGE_IMPORT\n"
            "from he_thong_dinh_luong.local_workstation_v82_bridge import read_v82_dashboard\n"
        )
        text = _replace_once(text, anchor, insert, "WEBAPP_IMPORT")
    if '"/tactical_profit_v82.js"' not in text:
        text = _replace_once(
            text,
            '                "/tactical_v78.css",\n',
            '                "/tactical_v78.css",\n'
            '                "/tactical_profit_v82.js",\n'
            '                "/tactical_profit_v82.css",\n',
            "WEBAPP_STATIC",
        )
    if 'elif path == "/api/dashboard-v82":' not in text:
        text = _replace_once(
            text,
            '            elif path == "/api/tactical-v78":\n'
            '                self._send_json(read_v78_tactical_snapshot(SYSTEM_ROOT))\n',
            '            elif path == "/api/tactical-v78":\n'
            '                self._send_json(read_v78_tactical_snapshot(SYSTEM_ROOT))\n'
            '            elif path == "/api/dashboard-v82":\n'
            '                self._send_json(read_v82_dashboard(SYSTEM_ROOT))\n',
            "WEBAPP_GET",
        )
    return text


def install(system_root: Path, assets_root: Path) -> dict[str, object]:
    root = Path(system_root).resolve()
    assets = Path(assets_root).resolve()
    index = root / "web" / "index.html"
    webapp = root / "src" / "vn_quant_local" / "webapp.py"
    if not index.is_file() or not webapp.is_file():
        raise ValueError("V82_EXISTING_WORKSTATION_WEB_NOT_FOUND")

    before = {"index": v78.digest(index), "webapp": v78.digest(webapp)}
    index_text = index.read_text(encoding="utf-8")
    webapp_text = webapp.read_text(encoding="utf-8")
    new_index = patch_index(index_text)
    new_webapp = patch_webapp(webapp_text)
    changed = new_index != index_text or new_webapp != webapp_text
    backup: Path | None = None

    if changed:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = root / "validation" / "v82_web_backup" / stamp
        backup.mkdir(parents=True, exist_ok=False)
        shutil.copy2(index, backup / "index.html")
        shutil.copy2(webapp, backup / "webapp.py")
        index.write_text(new_index, encoding="utf-8", newline="\n")
        webapp.write_text(new_webapp, encoding="utf-8", newline="\n")

    # Keep V78 scoped assets current as V82 depends on its Tactical tab.
    v78_assets = assets.parent / "v78"
    for name in ("tactical_v78.js", "tactical_v78.css"):
        source = v78_assets / name
        if not source.is_file():
            raise ValueError(f"V82_V78_ASSET_MISSING:{name}")
        shutil.copy2(source, root / "web" / name)
    for name in ("tactical_profit_v82.js", "tactical_profit_v82.css"):
        source = assets / name
        if not source.is_file():
            raise ValueError(f"V82_ASSET_MISSING:{name}")
        shutil.copy2(source, root / "web" / name)

    after = {"index": v78.digest(index), "webapp": v78.digest(webapp)}
    report = {
        "status": "SUCCESS",
        "mode": "ADDITIVE_APPROVED_WEB_PROFIT_PAPER",
        "changed": changed,
        "before_sha256": before,
        "after_sha256": after,
        "backup_dir": str(backup) if backup else None,
        "assets": [
            "web/tactical_v78.js", "web/tactical_v78.css",
            "web/tactical_profit_v82.js", "web/tactical_profit_v82.css",
        ],
        "endpoint": "/api/dashboard-v82",
        "credentials_or_state_touched": False,
        "existing_layout_replaced": False,
        "live_order_endpoint_added": False,
    }
    output = root / "validation" / "v82_web_integration_report.json"
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
