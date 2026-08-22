"""Install the V84 daily operating dashboard into the approved 8787 web.

V84 is web-only. It builds on V83 and consumes existing read-only endpoints
(`/api/status`, `/api/dashboard-v83`, `/api/tactical-v78`) to join the real DNSE
portfolio with C3 health and capital-discipline advisory. No new API endpoint,
credential write, broker order, state reset, or research policy is added.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil

from . import existing_web_v78_installer as v78
from . import existing_web_v83_installer as v83

HTML_MARK = "V84_MAIN_DAILY_OPERATING_DASHBOARD"


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise ValueError(f"V84_INSTALL_ANCHOR_{label}_COUNT={count}")
    return text.replace(old, new, 1)


def patch_index(text: str) -> str:
    text = v83.patch_index(text)
    if 'href="/main_operating_v84.css"' not in text:
        text = _replace_once(
            text,
            '  <link rel="stylesheet" href="/capital_discipline_v83.css">',
            '  <link rel="stylesheet" href="/capital_discipline_v83.css">\n'
            '  <!-- V84_MAIN_DAILY_OPERATING_DASHBOARD -->\n'
            '  <link rel="stylesheet" href="/main_operating_v84.css">',
            "INDEX_CSS",
        )
    if 'src="/main_operating_v84.js"' not in text:
        text = _replace_once(
            text,
            '  <script src="/capital_discipline_v83.js"></script>',
            '  <script src="/capital_discipline_v83.js"></script>\n'
            '  <!-- V84_MAIN_DAILY_OPERATING_DASHBOARD -->\n'
            '  <script src="/main_operating_v84.js"></script>',
            "INDEX_JS",
        )
    return text


def patch_webapp(text: str) -> str:
    text = v83.patch_webapp(text)
    if '"/main_operating_v84.js"' not in text:
        text = _replace_once(
            text,
            '                "/capital_discipline_v83.css",\n',
            '                "/capital_discipline_v83.css",\n'
            '                "/main_operating_v84.js",\n'
            '                "/main_operating_v84.css",\n',
            "WEBAPP_STATIC",
        )
    return text


def install(system_root: Path, assets_root: Path) -> dict[str, object]:
    root = Path(system_root).resolve(); assets = Path(assets_root).resolve()
    index = root / "web" / "index.html"; webapp = root / "src" / "vn_quant_local" / "webapp.py"
    if not index.is_file() or not webapp.is_file():
        raise ValueError("V84_EXISTING_WORKSTATION_WEB_NOT_FOUND")

    before = {"index": v78.digest(index), "webapp": v78.digest(webapp)}
    index_text = index.read_text(encoding="utf-8"); webapp_text = webapp.read_text(encoding="utf-8")
    new_index = patch_index(index_text); new_webapp = patch_webapp(webapp_text)
    changed = new_index != index_text or new_webapp != webapp_text
    backup: Path | None = None
    if changed:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = root / "validation" / "v84_web_backup" / stamp
        backup.mkdir(parents=True, exist_ok=False)
        shutil.copy2(index, backup / "index.html"); shutil.copy2(webapp, backup / "webapp.py")
        index.write_text(new_index, encoding="utf-8", newline="\n"); webapp.write_text(new_webapp, encoding="utf-8", newline="\n")

    inherited = (
        (assets.parent / "v78", ("tactical_v78.js", "tactical_v78.css")),
        (assets.parent / "v82", ("tactical_profit_v82.js", "tactical_profit_v82.css")),
        (assets.parent / "v83", ("capital_discipline_v83.js", "capital_discipline_v83.css")),
        (assets, ("main_operating_v84.js", "main_operating_v84.css")),
    )
    for folder, names in inherited:
        for name in names:
            source = folder / name
            if not source.is_file():
                raise ValueError(f"V84_ASSET_MISSING:{name}")
            shutil.copy2(source, root / "web" / name)

    after = {"index": v78.digest(index), "webapp": v78.digest(webapp)}
    report = {
        "status": "SUCCESS",
        "mode": "MAIN_DAILY_OPERATING_DASHBOARD",
        "changed": changed,
        "before_sha256": before,
        "after_sha256": after,
        "backup_dir": str(backup) if backup else None,
        "existing_port": 8787,
        "consumed_read_only_endpoints": ["/api/status", "/api/dashboard-v83", "/api/tactical-v78"],
        "new_api_endpoint_added": False,
        "research_policy_changed": False,
        "credentials_or_state_touched": False,
        "live_order_endpoint_added": False,
    }
    output = root / "validation" / "v84_web_integration_report.json"
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
