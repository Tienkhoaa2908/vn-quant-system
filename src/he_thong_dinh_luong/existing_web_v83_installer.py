"""Install V83 capital discipline into the already-approved 8787 workstation web.

V83 builds on V82 but changes product emphasis: capital discipline is primary;
leader/L15 research remains available only as archived evidence. The installer is
additive/idempotent and exposes one read-only endpoint. No broker/order surface.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil

from . import existing_web_v78_installer as v78
from . import existing_web_v82_installer as v82

HTML_MARK = "V83_CAPITAL_DISCIPLINE_EXISTING_WEB"
PY_MARK = "V83_CAPITAL_DISCIPLINE_BRIDGE"


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise ValueError(f"V83_INSTALL_ANCHOR_{label}_COUNT={count}")
    return text.replace(old, new, 1)


def patch_index(text: str) -> str:
    text = v82.patch_index(text)
    if 'href="/capital_discipline_v83.css"' not in text:
        text = _replace_once(
            text,
            '  <link rel="stylesheet" href="/tactical_profit_v82.css">',
            '  <link rel="stylesheet" href="/tactical_profit_v82.css">\n'
            '  <!-- V83_CAPITAL_DISCIPLINE_EXISTING_WEB -->\n'
            '  <link rel="stylesheet" href="/capital_discipline_v83.css">',
            "INDEX_CSS",
        )
    if 'src="/capital_discipline_v83.js"' not in text:
        text = _replace_once(
            text,
            '  <script src="/tactical_profit_v82.js"></script>',
            '  <script src="/tactical_profit_v82.js"></script>\n'
            '  <!-- V83_CAPITAL_DISCIPLINE_EXISTING_WEB -->\n'
            '  <script src="/capital_discipline_v83.js"></script>',
            "INDEX_JS",
        )
    return text


def patch_webapp(text: str) -> str:
    text = v82.patch_webapp(text)
    if f"# {PY_MARK}_IMPORT" not in text:
        anchor = "from he_thong_dinh_luong.local_workstation_v82_bridge import read_v82_dashboard\n"
        text = _replace_once(
            text,
            anchor,
            anchor + "\n# V83_CAPITAL_DISCIPLINE_BRIDGE_IMPORT\nfrom he_thong_dinh_luong.local_workstation_v83_bridge import read_v83_dashboard\n",
            "WEBAPP_IMPORT",
        )
    if '"/capital_discipline_v83.js"' not in text:
        text = _replace_once(
            text,
            '                "/tactical_profit_v82.css",\n',
            '                "/tactical_profit_v82.css",\n'
            '                "/capital_discipline_v83.js",\n'
            '                "/capital_discipline_v83.css",\n',
            "WEBAPP_STATIC",
        )
    if 'elif path == "/api/dashboard-v83":' not in text:
        text = _replace_once(
            text,
            '            elif path == "/api/dashboard-v82":\n'
            '                self._send_json(read_v82_dashboard(SYSTEM_ROOT))\n',
            '            elif path == "/api/dashboard-v82":\n'
            '                self._send_json(read_v82_dashboard(SYSTEM_ROOT))\n'
            '            elif path == "/api/dashboard-v83":\n'
            '                self._send_json(read_v83_dashboard(SYSTEM_ROOT))\n',
            "WEBAPP_GET",
        )
    return text


def install(system_root: Path, assets_root: Path) -> dict[str, object]:
    root = Path(system_root).resolve(); assets = Path(assets_root).resolve()
    index = root / "web" / "index.html"; webapp = root / "src" / "vn_quant_local" / "webapp.py"
    if not index.is_file() or not webapp.is_file():
        raise ValueError("V83_EXISTING_WORKSTATION_WEB_NOT_FOUND")
    before = {"index": v78.digest(index), "webapp": v78.digest(webapp)}
    index_text = index.read_text(encoding="utf-8"); webapp_text = webapp.read_text(encoding="utf-8")
    new_index = patch_index(index_text); new_webapp = patch_webapp(webapp_text)
    changed = new_index != index_text or new_webapp != webapp_text
    backup: Path | None = None
    if changed:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = root / "validation" / "v83_web_backup" / stamp
        backup.mkdir(parents=True, exist_ok=False)
        shutil.copy2(index, backup / "index.html"); shutil.copy2(webapp, backup / "webapp.py")
        index.write_text(new_index, encoding="utf-8", newline="\n"); webapp.write_text(new_webapp, encoding="utf-8", newline="\n")

    # Refresh all inherited scoped assets, then V83 assets.
    for folder, names in (
        (assets.parent / "v78", ("tactical_v78.js", "tactical_v78.css")),
        (assets.parent / "v82", ("tactical_profit_v82.js", "tactical_profit_v82.css")),
        (assets, ("capital_discipline_v83.js", "capital_discipline_v83.css")),
    ):
        for name in names:
            source = folder / name
            if not source.is_file():
                raise ValueError(f"V83_ASSET_MISSING:{name}")
            shutil.copy2(source, root / "web" / name)
    after = {"index": v78.digest(index), "webapp": v78.digest(webapp)}
    report = {
        "status": "SUCCESS",
        "mode": "PRIMARY_CAPITAL_DISCIPLINE_APPROVED_WEB",
        "changed": changed,
        "before_sha256": before,
        "after_sha256": after,
        "backup_dir": str(backup) if backup else None,
        "endpoint": "/api/dashboard-v83",
        "existing_port": 8787,
        "new_leader_research_primary": False,
        "credentials_or_state_touched": False,
        "live_order_endpoint_added": False,
    }
    output = root / "validation" / "v83_web_integration_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--system-root", type=Path, required=True); parser.add_argument("--assets-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = install(args.system_root, args.assets_root)
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "error": f"{type(exc).__name__}:{exc}"}, ensure_ascii=False)); return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
