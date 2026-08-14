"""Vietnam-time boundary-safe entry point for V77.

The core V77 package is intentionally deterministic around a captured timestamp.
This driver makes the monthly-completion decision from Asia/Ho_Chi_Minh calendar
semantics regardless of the timezone/host running the command.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence
from zoneinfo import ZoneInfo

from . import paper_oos_data_lineage_v77 as core

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def run(
    *,
    store: Path,
    state_dir: Path,
    output_dir: Path,
    search_roots: Sequence[Path] = (),
    git_head: str = "UNKNOWN",
    captured_at: datetime | None = None,
    month_close_confirmed: bool = False,
) -> dict[str, object]:
    captured = captured_at or datetime.now(timezone.utc)
    if captured.tzinfo is None or captured.utcoffset() is None:
        raise ValueError("V77_CAPTURE_TIME_MUST_HAVE_TIMEZONE")
    vn_wall_day = captured.astimezone(VN_TZ).date()
    original = core._analysis_end_for_capture

    def vietnam_boundary(capture_day, _host_wall_day, confirmed):
        return original(capture_day, vn_wall_day, confirmed)

    core._analysis_end_for_capture = vietnam_boundary
    try:
        report = core.run(
            store=store,
            state_dir=state_dir,
            output_dir=output_dir,
            search_roots=search_roots,
            git_head=git_head,
            captured_at=captured,
            month_close_confirmed=month_close_confirmed,
        )
    finally:
        core._analysis_end_for_capture = original
    report["wall_date_contract"] = "ASIA_HO_CHI_MINH"
    report["capture_wall_date_vn"] = vn_wall_day.isoformat()
    (Path(output_dir) / "v77_report.json").write_text(core._json_text(report), encoding="utf-8")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    args = core._parser().parse_args(argv)
    try:
        captured = datetime.fromisoformat(args.capture_time) if args.capture_time else None
        report = run(
            store=args.store,
            state_dir=args.state_dir,
            output_dir=args.output_dir,
            search_roots=args.search_root,
            git_head=args.git_head,
            captured_at=captured,
            month_close_confirmed=args.month_close_confirmed,
        )
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "error": f"{type(exc).__name__}:{exc}"}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps({
        "status": report["status"],
        "capture_market_day": report["capture_market_day"],
        "capture_wall_date_vn": report["capture_wall_date_vn"],
        "source_signal_day": report["source_signal_day"],
        "signals_appended": report["signals_appended"],
        "champion_paper": report["paper_results"][core.CHAMPION_MODEL],
        "shadow_paper": report["paper_results"][core.SHADOW_MODEL],
        "data_gate_blockers": report["data_lineage"]["blockers"],
        "promotion_authorized": False,
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
