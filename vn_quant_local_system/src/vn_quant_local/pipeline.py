"""Command-line orchestration for VN Quant Local Workstation."""
from __future__ import annotations

import argparse
from datetime import date
import json
from typing import Sequence

from .c3_model import run_model
from .core import (
    account_snapshot,
    archive_validation_evidence,
    bootstrap_local_data,
    replace_account,
    workstation_status,
)
from .data_sources import credential_status, sync_incremental_market_data_local
from .weekly_plan import create_weekly_plan, latest_weekly_plan


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="VN Quant Local Workstation")
    sub = parser.add_subparsers(dest="command", required=True)
    bootstrap = sub.add_parser("bootstrap")
    bootstrap.add_argument("--overwrite", action="store_true")
    sub.add_parser("status")
    sub.add_parser("data-source-status")
    sync = sub.add_parser("sync")
    sync.add_argument("--end", type=date.fromisoformat)
    sync.add_argument("--lookback-days", type=int, default=14)
    sub.add_parser("model")
    sub.add_parser("plan")
    sub.add_parser("archive-validation")
    full = sub.add_parser("full")
    full.add_argument("--skip-sync", action="store_true")
    full.add_argument("--overwrite-bootstrap", action="store_true")
    account = sub.add_parser("account")
    account.add_argument("--cash", type=float)
    account.add_argument("--contribution", type=float)
    account.add_argument("--holdings-json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "bootstrap":
            result = bootstrap_local_data(overwrite=args.overwrite)
        elif args.command == "status":
            result = workstation_status()
            result["latest_weekly_plan"] = latest_weekly_plan()
            result["data_source"] = credential_status()
        elif args.command == "data-source-status":
            result = credential_status()
        elif args.command == "sync":
            result = sync_incremental_market_data_local(
                end=args.end,
                lookback_days=args.lookback_days,
            )
        elif args.command == "model":
            result = run_model()
        elif args.command == "plan":
            result = create_weekly_plan()
        elif args.command == "archive-validation":
            result = archive_validation_evidence()
        elif args.command == "account":
            if args.cash is None and args.contribution is None and args.holdings_json is None:
                result = account_snapshot()
            else:
                current = account_snapshot()
                result = replace_account(
                    cash_vnd=(
                        args.cash
                        if args.cash is not None
                        else float(current["account"]["cash_vnd"])
                    ),
                    weekly_contribution_vnd=(
                        args.contribution
                        if args.contribution is not None
                        else float(current["account"]["weekly_contribution_vnd"])
                    ),
                    holdings=(
                        json.loads(args.holdings_json)
                        if args.holdings_json is not None
                        else current["holdings"]
                    ),
                )
        elif args.command == "full":
            stages: dict[str, object] = {}
            stages["bootstrap"] = bootstrap_local_data(
                overwrite=args.overwrite_bootstrap
            )
            if not args.skip_sync:
                stages["sync"] = sync_incremental_market_data_local()
            stages["model"] = run_model()
            stages["plan"] = create_weekly_plan()
            result = {"status": "SUCCESS", "stages": stages}
        else:
            raise ValueError(f"Command không hỗ trợ: {args.command}")
    except Exception as exc:
        _print({"status": "FAILED", "error": f"{type(exc).__name__}:{exc}"})
        return 2
    _print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
