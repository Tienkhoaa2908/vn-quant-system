"""Install V78 into the existing V55 local web without redesigning it.

Only two scoped assets and narrow HTTP bridge hooks are added. Existing original
files are backed up before the first modification. Data/state/credentials are not
touched.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import shutil

KNOWN_INDEX_SHA = "c4b26ce2d59cd92c1f2c2d1985eab34e7f9bf260f4562eed9de94476a461b1f5"
KNOWN_WEBAPP_SHA = "99d1ec1ef6347280094c35e6ec737a77489078b2f909822eea4d35342096cc78"
HTML_MARK = "V78_TACTICAL_EXISTING_WEB"
PY_MARK = "V78_TACTICAL_BRIDGE"


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise ValueError(f"V78_INSTALL_ANCHOR_{label}_COUNT={count}")
    return text.replace(old, new, 1)


def patch_index(text: str) -> str:
    if f"<!-- {HTML_MARK} -->" in text:
        return text
    text = replace_once(
        text,
        '  <link rel="stylesheet" href="/performance_v51.css">',
        '  <link rel="stylesheet" href="/performance_v51.css">\n'
        '  <!-- V78_TACTICAL_EXISTING_WEB -->\n'
        '  <link rel="stylesheet" href="/tactical_v78.css">',
        "INDEX_CSS",
    )
    text = replace_once(
        text,
        '  <script src="/performance_v51.js"></script>',
        '  <script src="/performance_v51.js"></script>\n'
        '  <!-- V78_TACTICAL_EXISTING_WEB -->\n'
        '  <script src="/tactical_v78.js"></script>',
        "INDEX_JS",
    )
    return text


def patch_webapp(text: str) -> str:
    if f"# {PY_MARK}_IMPORT" not in text:
        anchor = "from urllib.parse import parse_qs, urlparse\n"
        insert = (
            anchor
            + "\n# V78_TACTICAL_BRIDGE_IMPORT\n"
            + "from he_thong_dinh_luong.local_workstation_v78_bridge import (\n"
            + "    read_v78_tactical_snapshot,\n"
            + "    refresh_v78_tactical_snapshot,\n"
            + ")\n"
        )
        text = replace_once(text, anchor, insert, "WEBAPP_IMPORT")
    if "def _refresh_v78_tactical_soft()" not in text:
        anchor = "\ndef _refresh_market_signals() -> dict[str, object]:\n"
        insert = '''\ndef _refresh_v78_tactical_soft() -> dict[str, object]:
    try:
        return refresh_v78_tactical_snapshot(SYSTEM_ROOT)
    except Exception as exc:
        return {
            "status": "UNAVAILABLE",
            "message": str(exc) or type(exc).__name__,
            "live_orders_allowed": False,
        }


def _refresh_market_signals() -> dict[str, object]:
'''
        text = replace_once(text, anchor, insert, "WEBAPP_SOFT_HELPER")
    if '"tactical_v78": _refresh_v78_tactical_soft(),' not in text:
        text = replace_once(
            text,
            '        "market_sync": market_sync,\n'
            '        "canonical": canonical,\n'
            '        "preview": {',
            '        "market_sync": market_sync,\n'
            '        "canonical": canonical,\n'
            '        "tactical_v78": _refresh_v78_tactical_soft(),\n'
            '        "preview": {',
            "WEBAPP_MODEL_REFRESH",
        )
    if '"/tactical_v78.js"' not in text:
        text = replace_once(
            text,
            '                "/performance_v51.css",\n',
            '                "/performance_v51.css",\n'
            '                "/tactical_v78.js",\n'
            '                "/tactical_v78.css",\n',
            "WEBAPP_STATIC",
        )
    if 'value["tactical_v78"] = read_v78_tactical_snapshot(SYSTEM_ROOT)' not in text:
        text = replace_once(
            text,
            '                value["signal_refresh"] = signal_refresh_status()\n'
            '                self._send_json(value)\n',
            '                value["signal_refresh"] = signal_refresh_status()\n'
            '                value["tactical_v78"] = read_v78_tactical_snapshot(SYSTEM_ROOT)\n'
            '                self._send_json(value)\n',
            "WEBAPP_STATUS",
        )
    if 'elif path == "/api/tactical-v78":' not in text:
        text = replace_once(
            text,
            '            elif path == "/api/performance":\n'
            '                self._send_json(performance_status())\n',
            '            elif path == "/api/performance":\n'
            '                self._send_json(performance_status())\n'
            '            elif path == "/api/tactical-v78":\n'
            '                self._send_json(read_v78_tactical_snapshot(SYSTEM_ROOT))\n',
            "WEBAPP_GET",
        )
    if '"/api/actions/tactical-v78": _refresh_v78_tactical_soft,' not in text:
        text = replace_once(
            text,
            '                "/api/performance/refresh": refresh_performance,\n',
            '                "/api/performance/refresh": refresh_performance,\n'
            '                "/api/actions/tactical-v78": _refresh_v78_tactical_soft,\n',
            "WEBAPP_POST",
        )
    return text


def install(system_root: Path, assets_root: Path) -> dict[str, object]:
    root = Path(system_root).resolve()
    assets = Path(assets_root).resolve()
    index = root / "web" / "index.html"
    webapp = root / "src" / "vn_quant_local" / "webapp.py"
    if not index.is_file() or not webapp.is_file():
        raise ValueError("V78_EXISTING_WORKSTATION_WEB_NOT_FOUND")

    before = {"index": digest(index), "webapp": digest(webapp)}
    index_text = index.read_text(encoding="utf-8")
    webapp_text = webapp.read_text(encoding="utf-8")
    new_index = patch_index(index_text)
    new_webapp = patch_webapp(webapp_text)
    changed = new_index != index_text or new_webapp != webapp_text
    backup: Path | None = None

    if changed:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = root / "validation" / "v78_web_backup" / stamp
        backup.mkdir(parents=True, exist_ok=False)
        shutil.copy2(index, backup / "index.html")
        shutil.copy2(webapp, backup / "webapp.py")
        index.write_text(new_index, encoding="utf-8", newline="\n")
        webapp.write_text(new_webapp, encoding="utf-8", newline="\n")

    for name in ("tactical_v78.js", "tactical_v78.css"):
        source = assets / name
        if not source.is_file():
            raise ValueError(f"V78_ASSET_MISSING:{name}")
        shutil.copy2(source, root / "web" / name)

    after = {"index": digest(index), "webapp": digest(webapp)}
    report = {
        "status": "SUCCESS",
        "mode": "ADDITIVE_EXISTING_WEB_ONLY",
        "changed": changed,
        "known_liked_baseline_detected": (
            before["index"] == KNOWN_INDEX_SHA
            and before["webapp"] == KNOWN_WEBAPP_SHA
        ),
        "before_sha256": before,
        "after_sha256": after,
        "backup_dir": str(backup) if backup else None,
        "assets": ["web/tactical_v78.js", "web/tactical_v78.css"],
        "credentials_or_state_touched": False,
        "existing_layout_replaced": False,
    }
    output = root / "validation" / "v78_web_integration_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--system-root", type=Path, required=True)
    parser.add_argument("--assets-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = install(args.system_root, args.assets_root)
    except Exception as exc:
        print(json.dumps({
            "status": "FAILED",
            "error": f"{type(exc).__name__}:{exc}",
        }, ensure_ascii=False))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
