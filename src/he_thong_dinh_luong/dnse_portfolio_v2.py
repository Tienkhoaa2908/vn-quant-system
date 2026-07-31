"""Corrected read-only DNSE portfolio sync.

The v1 importer remains available for artifact compatibility.  This wrapper runs
it in a staging directory, corrects cash semantics and action priority, adds the
required foreign-trading time window, then publishes an immutable v2 snapshot.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from io import StringIO
import json
import os
from pathlib import Path
import shutil
from typing import Mapping
from zipfile import ZIP_DEFLATED, ZipFile

from . import dnse_portfolio as legacy
from .dnse_portfolio import DnseReadOnlyClient, list_masked_accounts
from .nguon_dnse import DnseRestSource
from .portfolio_planner import Holding, PortfolioStore
from .portfolio_safety import (
    action_label,
    derive_cash_semantics,
    foreign_trading_params,
    resolve_position_action,
)

VN_TZ = timezone(timedelta(hours=7))
SCHEMA_VERSION = "dnse_portfolio_analysis_v2"


def _float(value: object, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return default


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON_OBJECT_REQUIRED:{path.name}")
    return value


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    fields = list(rows[0]) if rows else ["symbol", "quantity", "action", "action_label"]
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    path.write_bytes(buffer.getvalue().encode("utf-8-sig"))


def _select_account(
    reader: DnseReadOnlyClient,
    account_no: str | None,
) -> tuple[str, str]:
    accounts = list_masked_accounts(reader)
    if not accounts:
        raise ValueError("DNSE_ACCOUNTS_EMPTY")
    if account_no:
        selected = next((item for item in accounts if item["account_no"] == account_no), None)
        if selected is None:
            raise ValueError("DNSE_ACCOUNT_NOT_FOUND")
    else:
        stock_accounts = [item for item in accounts if "DERIV" not in item["account_type"].upper()]
        selected = (stock_accounts or accounts)[0]
    return selected["account_no"], selected["masked_account"]


def _market_context(
    reader: DnseReadOnlyClient,
    symbol: str,
    now: datetime,
) -> dict[str, object]:
    output: dict[str, object] = {}
    errors: dict[str, str] = {}
    calls = {
        "latest_trade": (f"/price/{symbol}/trades/latest", {"type": "STOCK"}),
        "latest_quote": (f"/price/{symbol}/quotes/latest", {"type": "STOCK"}),
        "foreign_trading": (
            f"/price/{symbol}/foreign-trading",
            foreign_trading_params(now),
        ),
    }
    for key, (path, params) in calls.items():
        try:
            payload = reader.get(path, params=params)
            output[key] = payload if isinstance(payload, (Mapping, list)) else {}
        except Exception as exc:
            errors[key] = f"{type(exc).__name__}:{exc}"
    output["errors"] = errors
    return output


def _rebuild_archive(snapshot: Path) -> Path:
    payload_files = [
        snapshot / "portfolio_analysis.csv",
        snapshot / "portfolio_summary.json",
        snapshot / "market_context.json",
        snapshot / "indicator_methodology.json",
    ]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "as_of": _json(snapshot / "portfolio_summary.json").get("as_of"),
        "masked_account": _json(snapshot / "portfolio_summary.json").get("masked_account"),
        "read_only": True,
        "credentials_recorded": False,
        "trading_token_used": False,
        "files": {
            path.name: {"sha256": sha256(path.read_bytes()).hexdigest(), "size": path.stat().st_size}
            for path in payload_files
        },
    }
    manifest_path = snapshot / "manifest.json"
    _write_json(manifest_path, manifest)
    archive_path = snapshot / "dnse_portfolio_analysis.zip"
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        for path in (*payload_files, manifest_path):
            archive.write(path, arcname=path.name)
    return archive_path


def sync_portfolio(
    *,
    data_root: Path,
    output_dir: Path,
    account_no: str | None = None,
    read_client: DnseReadOnlyClient | None = None,
    market_source: DnseRestSource | None = None,
    sync_local_planner: bool = True,
    include_market_context: bool = True,
) -> dict[str, object]:
    root = Path(data_root)
    destination = Path(output_dir)
    if destination.exists():
        raise FileExistsError("OUTPUT_DIR_EXISTS")
    staging = destination.with_name(f".{destination.name}.staging")
    if staging.exists():
        raise FileExistsError("STAGING_DIR_EXISTS")
    now = datetime.now(VN_TZ)
    reader = read_client or DnseReadOnlyClient.from_env()
    source = market_source or DnseRestSource.from_env()
    close_reader = read_client is None
    close_source = market_source is None
    try:
        actual_account, masked_account = _select_account(reader, account_no)
        balance_payload = reader.balances(actual_account)
        cash = derive_cash_semantics(balance_payload)
        legacy.sync_portfolio(
            data_root=root,
            output_dir=staging,
            account_no=actual_account,
            read_client=reader,
            market_source=source,
            sync_local_planner=False,
            include_market_context=False,
        )
        rows_raw = _rows(staging / "portfolio_analysis.csv")
        rows: list[dict[str, object]] = []
        for raw in rows_raw:
            row: dict[str, object] = dict(raw)
            action = resolve_position_action(
                target_weight_pct=_float(raw.get("target_weight_pct")),
                current_weight_pct=_float(raw.get("current_weight_pct")),
                above_ma250=str(raw.get("above_ma250", "")).lower() == "true",
                trend_score=_float(raw.get("trend_score")),
            )
            row["action"] = action
            row["action_label"] = action_label(action)
            rows.append(row)
        _write_rows(staging / "portfolio_analysis.csv", rows)

        summary = _json(staging / "portfolio_summary.json")
        warnings = [str(item) for item in summary.get("warnings", [])] if isinstance(summary.get("warnings"), list) else []
        for warning in cash.warnings:
            if warning not in warnings:
                warnings.append(warning)
        stock_value = _float(summary.get("stock_market_value_vnd"))
        nav = _float(summary.get("net_liquidation_value_vnd"))
        position_values = [_float(row.get("market_value_vnd")) for row in rows]
        summary.update(cash.payload())
        summary.update({
            "schema_version": SCHEMA_VERSION,
            "masked_account": masked_account,
            "safe_planner_cash_vnd": cash.planner_cash_vnd,
            "cash_weight": cash.total_cash_vnd / nav if nav > 0 else 0.0,
            "largest_position_nav_weight": max(position_values, default=0.0) / nav if nav > 0 else 0.0,
            "largest_position_stock_weight": max(position_values, default=0.0) / stock_value if stock_value > 0 else 0.0,
            "warnings": warnings,
            "planner_cash_source": "min(totalCash, withdrawableCash when available)",
            "buying_power_note": "broker buying power is displayed but never copied into the local planner",
        })
        _write_json(staging / "portfolio_summary.json", summary)

        context: dict[str, object] = {}
        if include_market_context:
            for row in rows:
                symbol = str(row.get("symbol") or "")
                if symbol:
                    context[symbol] = _market_context(reader, symbol, now)
        _write_json(staging / "market_context.json", context)
        archive_path = _rebuild_archive(staging)

        if sync_local_planner:
            store = PortfolioStore(root / "web-local" / "portfolio.sqlite3")
            incoming = {str(row.get("symbol")): row for row in rows if row.get("symbol")}
            for existing in store.list_holdings():
                if existing.symbol not in incoming:
                    store.delete_holding(existing.symbol)
            for row in rows:
                symbol = str(row.get("symbol") or "")
                if not symbol:
                    continue
                store.upsert_holding(Holding(
                    symbol,
                    int(_float(row.get("quantity"))),
                    Decimal(str(_float(row.get("cost_price_vnd")))),
                ))
            store.set_current_cash(max(0, int(cash.planner_cash_vnd)))

        os.replace(staging, destination)
        final_archive = destination / archive_path.name
        state_root = root / "dnse-portfolio-live"
        state_root.mkdir(parents=True, exist_ok=True)
        (state_root / "LATEST.txt").write_text(str(destination.resolve()), encoding="utf-8")
        return {
            "status": "SUCCESS",
            "schema_version": SCHEMA_VERSION,
            "masked_account": masked_account,
            "position_count": len(rows),
            "broker_buying_power_vnd": cash.broker_buying_power_vnd,
            "planner_cash_vnd": cash.planner_cash_vnd,
            "cash_semantics_status": cash.status,
            "net_liquidation_value_vnd": summary.get("net_liquidation_value_vnd"),
            "unrealized_pnl_vnd": summary.get("unrealized_pnl_vnd"),
            "output_dir": str(destination),
            "output_zip": str(final_archive),
            "read_only": True,
        }
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    finally:
        if close_source:
            source.close()
        if close_reader:
            reader.close()
