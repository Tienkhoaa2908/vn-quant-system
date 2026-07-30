"""Replay cac tin hieu paper OOS da ghi nhan voi mot cau hinh chi phi/von rieng.

Day la scenario research tren tin hieu da ton tai, khong tao lai tin hieu qua khu va
khong gui lenh that.
"""
from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal
from pathlib import Path
import shutil
from typing import Mapping, Sequence
from zipfile import ZIP_DEFLATED, ZipFile

from .mo_phong import chay_mo_phong
from .paper_trading_daily import (
    _config,
    _csv_bytes,
    _dataclass_rows,
    _json_bytes,
    _load_all_signals,
    _max_drawdown,
    _order_rows,
    _read_publication,
    _sha_file,
    _targets,
)

SCHEMA_VERSION = "paper_scenario_v1"


def _text(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def _write_csv(path: Path, rows: list[dict[str, object]], fields: Sequence[str]) -> None:
    if not fields:
        path.write_text("", encoding="utf-8")
        return
    path.write_bytes(_csv_bytes(rows, fields))


def run(
    *,
    state_dir: Path,
    publication_dir: Path,
    output_dir: Path,
    initial_capital_vnd: int = 1_000_000_000,
    buy_fee_bps: Decimal = Decimal("15"),
    sell_fee_bps: Decimal = Decimal("15"),
    sell_tax_bps: Decimal = Decimal("100"),
    slippage_bps: Decimal = Decimal("10"),
    lot_size: int = 100,
) -> dict[str, object]:
    destination = Path(output_dir)
    if destination.exists():
        raise FileExistsError("PAPER_SCENARIO_OUTPUT_EXISTS")
    signal_rows, signal_digest = _load_all_signals(Path(state_dir))
    signal_dates = sorted({date.fromisoformat(row["signal_date"]) for row in signal_rows})
    symbols = {row["symbol"] for row in signal_rows}
    prices, latest_market_date, publication_sha = _read_publication(
        Path(publication_dir), symbols, signal_dates[0]
    )
    if signal_dates[-1] > latest_market_date:
        raise ValueError("PAPER_SCENARIO_SIGNAL_AFTER_MARKET_DATE")
    config = _config(
        initial_capital_vnd=initial_capital_vnd,
        buy_fee_bps=buy_fee_bps,
        sell_fee_bps=sell_fee_bps,
        sell_tax_bps=sell_tax_bps,
        slippage_bps=slippage_bps,
        lot_size=lot_size,
    )
    result = chay_mo_phong(prices, _targets(signal_rows), config)

    staging = destination.with_name(destination.name + ".staging")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        signal_fields = tuple(signal_rows[0])
        _write_csv(
            staging / "signals.csv",
            [{key: _text(value) for key, value in row.items()} for row in signal_rows],
            signal_fields,
        )
        orders = _order_rows(result, latest_market_date)
        order_fields = tuple(orders[0]) if orders else (
            "order_id", "signal_date", "execution_date", "symbol", "side",
            "requested_quantity", "quantity", "status", "reason",
            "reduced_quantity", "reduction_reason",
        )
        _write_csv(staging / "orders.csv", orders, order_fields)

        fills, fill_fields = _dataclass_rows(result.khop_lenh)
        positions, position_fields = _dataclass_rows(result.vi_the_hang_ngay)
        nav, nav_fields = _dataclass_rows(result.nav)
        ledger, ledger_fields = _dataclass_rows(result.so_cai)
        _write_csv(staging / "fills.csv", fills, fill_fields or ("ma_lenh",))
        _write_csv(staging / "positions_daily.csv", positions, position_fields or ("ngay",))
        _write_csv(staging / "nav.csv", nav, nav_fields or ("ngay", "nav"))
        _write_csv(staging / "ledger.csv", ledger, ledger_fields or ("ngay", "nav"))

        initial_nav = config.von_ban_dau
        latest_nav = result.nav[-1].nav if result.nav else initial_nav
        nav_values = [row.nav for row in result.nav]
        gross_trade_value = sum(
            (fill.gia_tri_giao_dich for fill in result.khop_lenh), Decimal("0")
        )
        total_cost = sum(
            (fill.phi + fill.thue + fill.chi_phi_truot_gia for fill in result.khop_lenh),
            Decimal("0"),
        )
        pending_count = sum(1 for row in orders if row["status"] == "PENDING_NEXT_SESSION")
        rejected_count = sum(1 for row in orders if row["status"] == "tu_choi")
        metrics: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "status": "SUCCESS",
            "signal_date_start": signal_dates[0].isoformat(),
            "signal_date_end": signal_dates[-1].isoformat(),
            "latest_market_date": latest_market_date.isoformat(),
            "signal_date_count": len(signal_dates),
            "signal_row_count": len(signal_rows),
            "order_count": len(orders),
            "fill_count": len(result.khop_lenh),
            "pending_order_count": pending_count,
            "rejected_order_count": rejected_count,
            "initial_nav_vnd": str(initial_nav * Decimal("1000")),
            "latest_nav_vnd": str(latest_nav * Decimal("1000")),
            "total_return": str(latest_nav / initial_nav - Decimal("1")),
            "max_drawdown": str(_max_drawdown(nav_values)),
            "gross_trade_value_vnd": str(gross_trade_value * Decimal("1000")),
            "gross_turnover_on_initial_capital": str(
                gross_trade_value / initial_nav if initial_nav else Decimal("0")
            ),
            "total_cost_vnd": str(total_cost * Decimal("1000")),
            "configuration": config.thanh_tu_dien(),
            "technical_validation_only": True,
            "research_eligible": False,
            "limitations": [
                "replays_recorded_oos_signals_only",
                "does_not_reconstruct_unrecorded_historical_signals",
                "price_basis_unconfirmed",
                "corporate_action_inventory_incomplete",
            ],
        }
        (staging / "metrics.json").write_bytes(_json_bytes(metrics))

        product_names = (
            "signals.csv", "orders.csv", "fills.csv", "positions_daily.csv",
            "nav.csv", "ledger.csv", "metrics.json",
        )
        manifest: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "status": "SUCCESS",
            "signal_store_digest": signal_digest,
            "publication_sha256": publication_sha,
            "technical_validation_only": True,
            "research_eligible": False,
            "files": {
                name: {
                    "sha256": _sha_file(staging / name),
                    "size": (staging / name).stat().st_size,
                }
                for name in product_names
            },
        }
        (staging / "manifest.json").write_bytes(_json_bytes(manifest))
        with ZipFile(staging / "paper_scenario.zip", "w", compression=ZIP_DEFLATED) as archive:
            for name in (*product_names, "manifest.json"):
                archive.write(staging / name, arcname=name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging.replace(destination)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return {
        "status": "SUCCESS",
        "output_dir": str(destination),
        "output_zip": str(destination / "paper_scenario.zip"),
        "latest_nav_vnd": metrics["latest_nav_vnd"],
        "total_return": metrics["total_return"],
        "max_drawdown": metrics["max_drawdown"],
        "fill_count": metrics["fill_count"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m he_thong_dinh_luong.paper_scenario")
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--publication-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--initial-capital-vnd", type=int, default=1_000_000_000)
    parser.add_argument("--buy-fee-bps", type=Decimal, default=Decimal("15"))
    parser.add_argument("--sell-fee-bps", type=Decimal, default=Decimal("15"))
    parser.add_argument("--sell-tax-bps", type=Decimal, default=Decimal("100"))
    parser.add_argument("--slippage-bps", type=Decimal, default=Decimal("10"))
    parser.add_argument("--lot-size", type=int, default=100)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run(
            state_dir=args.state_dir,
            publication_dir=args.publication_dir,
            output_dir=args.output_dir,
            initial_capital_vnd=args.initial_capital_vnd,
            buy_fee_bps=args.buy_fee_bps,
            sell_fee_bps=args.sell_fee_bps,
            sell_tax_bps=args.sell_tax_bps,
            slippage_bps=args.slippage_bps,
            lot_size=args.lot_size,
        )
    except Exception as exc:
        import json
        print(json.dumps({
            "status": "FAILED",
            "error": f"{type(exc).__name__}:{exc}",
        }, ensure_ascii=False, sort_keys=True))
        return 2
    import json
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
