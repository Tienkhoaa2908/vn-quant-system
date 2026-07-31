"""Cross-platform wrapper for anytime snapshot with sufficient benchmark history."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Sequence
import zoneinfo

FIXED_VN_TZ = timezone(timedelta(hours=7))
BENCHMARK_LOOKBACK_DAYS = 700


def _load_impl():
    try:
        zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
    except zoneinfo.ZoneInfoNotFoundError:
        original = zoneinfo.ZoneInfo
        zoneinfo.ZoneInfo = lambda _key: FIXED_VN_TZ  # type: ignore[assignment]
        try:
            from . import anytime_snapshot as implementation
        finally:
            zoneinfo.ZoneInfo = original  # type: ignore[assignment]
        return implementation
    from . import anytime_snapshot as implementation
    return implementation


_impl = _load_impl()


class _SnapshotSource:
    """Use incremental stock fetches but force enough VNINDEX history for MA250."""

    def __init__(self, delegate: object) -> None:
        self.delegate = delegate

    def fetch(self, symbol: str, start: date, end: date, *, is_index: bool = False):
        effective_start = end - timedelta(days=BENCHMARK_LOOKBACK_DAYS) if is_index or symbol == "VNINDEX" else start
        return self.delegate.fetch(symbol, effective_start, end, is_index=is_index)

    def close(self) -> None:
        self.delegate.close()


def run(
    *,
    data_root: Path,
    output_dir: Path,
    now: datetime | None = None,
    min_coverage: float = 0.80,
) -> dict[str, object]:
    delegate = _impl.DnseRestSource.from_env()
    source = _SnapshotSource(delegate)
    try:
        return _impl.run(
            data_root=data_root,
            output_dir=output_dir,
            now=now,
            source=source,
            min_coverage=min_coverage,
        )
    finally:
        source.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m he_thong_dinh_luong.anytime_snapshot_cli")
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--min-coverage", type=float, default=0.80)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run(
            data_root=args.data_root,
            output_dir=args.output_dir,
            min_coverage=args.min_coverage,
        )
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "error": f"{type(exc).__name__}:{exc}"}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


__all__ = ["BENCHMARK_LOOKBACK_DAYS", "run", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
