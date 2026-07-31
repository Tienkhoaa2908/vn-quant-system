"""CLI for read-only DNSE portfolio synchronization."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Sequence
import zoneinfo

VN_TZ = timezone(timedelta(hours=7))


def _load_sync():
    try:
        zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
    except zoneinfo.ZoneInfoNotFoundError:
        original = zoneinfo.ZoneInfo
        zoneinfo.ZoneInfo = lambda _key: VN_TZ  # type: ignore[assignment]
        try:
            from .dnse_portfolio import sync_portfolio as implementation
        finally:
            zoneinfo.ZoneInfo = original  # type: ignore[assignment]
        return implementation
    from .dnse_portfolio import sync_portfolio as implementation
    return implementation


sync_portfolio = _load_sync()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m he_thong_dinh_luong.dnse_portfolio_cli")
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--account-no")
    parser.add_argument("--no-market-context", action="store_true")
    parser.add_argument("--no-sync-local-planner", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output = args.output_dir or (
        args.data_root
        / "dnse-portfolio-live"
        / "snapshots"
        / datetime.now(VN_TZ).strftime("%Y%m%d_%H%M%S")
    )
    try:
        result = sync_portfolio(
            data_root=args.data_root,
            output_dir=output,
            account_no=args.account_no,
            include_market_context=not args.no_market_context,
            sync_local_planner=not args.no_sync_local_planner,
        )
    except Exception as exc:
        print(json.dumps({
            "status": "FAILED",
            "error": f"{type(exc).__name__}:{exc}",
            "read_only": True,
        }, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
