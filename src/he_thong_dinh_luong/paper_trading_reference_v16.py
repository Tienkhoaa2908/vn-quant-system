"""Guarded paper-trading entrypoint for the frozen v15 reference policy.

The wrapper validates that the daily signal uses the frozen champion, requires a
current paper monitor snapshot, blocks new signals when the kill switch is
active, and supplies DNSE cash-account cost defaults. It never sends live orders.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import json
from pathlib import Path
from typing import Mapping, Sequence

from . import paper_trading_daily as base
from .reference_operations_v16 import (
    PAPER_MONITOR_SCHEMA,
    REFERENCE_POLICY_SCHEMA,
)

SCHEMA_VERSION = "paper_trading_reference_v16"


def _read_json(path: Path, error: str) -> dict[str, object]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(error) from exc
    if not isinstance(value, dict):
        raise ValueError(error)
    return value


def _load_policy(path: Path) -> dict[str, object]:
    policy = _read_json(path, "PAPER_REFERENCE_POLICY_INVALID")
    if policy.get("schema_version") != REFERENCE_POLICY_SCHEMA:
        raise ValueError("PAPER_REFERENCE_POLICY_SCHEMA_INVALID")
    if policy.get("status") != "FROZEN_HISTORICAL_REFERENCE":
        raise ValueError("PAPER_REFERENCE_POLICY_NOT_FROZEN")
    model = policy.get("model")
    permissions = policy.get("permissions")
    if not isinstance(model, Mapping) or not isinstance(permissions, Mapping):
        raise ValueError("PAPER_REFERENCE_POLICY_CONTRACT_INVALID")
    if permissions.get("paper_trading_allowed") is not True:
        raise ValueError("PAPER_REFERENCE_POLICY_PAPER_NOT_ALLOWED")
    if permissions.get("live_capital_approved") is not False:
        raise ValueError("PAPER_REFERENCE_POLICY_LIVE_APPROVAL_INVALID")
    return policy


def _load_monitor(path: Path, *, policy_id: str) -> dict[str, object]:
    monitor = _read_json(path, "PAPER_REFERENCE_MONITOR_INVALID")
    if monitor.get("schema_version") != PAPER_MONITOR_SCHEMA:
        raise ValueError("PAPER_REFERENCE_MONITOR_SCHEMA_INVALID")
    if str(monitor.get("policy_id") or "") != policy_id:
        raise ValueError("PAPER_REFERENCE_MONITOR_POLICY_MISMATCH")
    if monitor.get("live_capital_approved") is not False:
        raise ValueError("PAPER_REFERENCE_MONITOR_LIVE_APPROVAL_INVALID")
    return monitor


def run(
    *,
    daily_output: Path,
    publication_dir: Path,
    state_dir: Path,
    policy_path: Path,
    monitor_path: Path,
    initial_capital_vnd: int = 1_000_000_000,
    buy_fee_bps: Decimal = Decimal("2.7"),
    sell_fee_bps: Decimal = Decimal("3.0"),
    sell_tax_bps: Decimal = Decimal("10"),
    slippage_bps: Decimal = Decimal("5"),
    lot_size: int = 100,
) -> dict[str, object]:
    policy = _load_policy(Path(policy_path))
    policy_id = str(policy.get("policy_id") or "")
    if not policy_id:
        raise ValueError("PAPER_REFERENCE_POLICY_ID_MISSING")
    monitor = _load_monitor(Path(monitor_path), policy_id=policy_id)
    if monitor.get("block_new_positions") is True:
        triggers = monitor.get("kill_switch_triggers")
        detail = "|".join(str(value) for value in triggers) if isinstance(triggers, list) else "UNKNOWN"
        raise ValueError(f"PAPER_REFERENCE_KILL_SWITCH_ACTIVE:{detail}")

    signal_rows, _, _ = base._load_daily_signal(Path(daily_output))
    champions = {
        str(row.get("champion_model") or "").strip()
        for row in signal_rows
    }
    frozen_model = str(dict(policy["model"]).get("champion") or "")
    if champions != {frozen_model}:
        raise ValueError(
            "PAPER_REFERENCE_CHAMPION_MISMATCH:"
            + "|".join(sorted(champions))
            + f":EXPECTED:{frozen_model}"
        )

    result = base.run(
        daily_output=Path(daily_output),
        publication_dir=Path(publication_dir),
        state_dir=Path(state_dir),
        initial_capital_vnd=initial_capital_vnd,
        buy_fee_bps=buy_fee_bps,
        sell_fee_bps=sell_fee_bps,
        sell_tax_bps=sell_tax_bps,
        slippage_bps=slippage_bps,
        lot_size=lot_size,
    )
    return {
        **result,
        "schema_version": SCHEMA_VERSION,
        "reference_policy_id": policy_id,
        "reference_model": frozen_model,
        "paper_monitor_status": monitor.get("status"),
        "dnse_cost_defaults": {
            "buy_fee_bps": str(buy_fee_bps),
            "sell_fee_bps": str(sell_fee_bps),
            "sell_tax_bps": str(sell_tax_bps),
            "slippage_bps_each_side": str(slippage_bps),
        },
        "automatic_live_orders_allowed": False,
        "live_capital_approved": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m he_thong_dinh_luong.paper_trading_reference_v16"
    )
    parser.add_argument("--daily-output", type=Path, required=True)
    parser.add_argument("--publication-dir", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--monitor", type=Path, required=True)
    parser.add_argument("--initial-capital-vnd", type=int, default=1_000_000_000)
    parser.add_argument("--buy-fee-bps", type=Decimal, default=Decimal("2.7"))
    parser.add_argument("--sell-fee-bps", type=Decimal, default=Decimal("3.0"))
    parser.add_argument("--sell-tax-bps", type=Decimal, default=Decimal("10"))
    parser.add_argument("--slippage-bps", type=Decimal, default=Decimal("5"))
    parser.add_argument("--lot-size", type=int, default=100)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run(
            daily_output=args.daily_output,
            publication_dir=args.publication_dir,
            state_dir=args.state_dir,
            policy_path=args.policy,
            monitor_path=args.monitor,
            initial_capital_vnd=args.initial_capital_vnd,
            buy_fee_bps=args.buy_fee_bps,
            sell_fee_bps=args.sell_fee_bps,
            sell_tax_bps=args.sell_tax_bps,
            slippage_bps=args.slippage_bps,
            lot_size=args.lot_size,
        )
    except Exception as exc:
        print(json.dumps({
            "status": "FAILED",
            "error": f"{type(exc).__name__}:{exc}",
        }, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


__all__ = ["SCHEMA_VERSION", "run", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
