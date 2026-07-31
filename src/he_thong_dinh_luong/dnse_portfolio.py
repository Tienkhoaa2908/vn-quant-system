"""Read-only DNSE portfolio import and integrated technical analysis.

No trading token is accepted. The client only permits a small GET allowlist and never
persists an unmasked account number, API key or API secret.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from importlib import metadata
from io import StringIO
import json
from math import isfinite
import os
from pathlib import Path
import re
from statistics import fmean
from typing import Any, Callable, Mapping, Protocol, Sequence
from zipfile import ZIP_DEFLATED, ZipFile

from .nguon_dnse import DNSE_BASE_URL, DNSE_SDK_VERSION, DnseRestSource
from .portfolio_planner import Holding, PortfolioStore
from .technical_indicators import compute_indicators

VN_TZ = timezone(timedelta(hours=7))
SCHEMA_VERSION = "dnse_portfolio_analysis_v1"


class _JsonResponse(Protocol):
    def json(self) -> object: ...


class _Client(Protocol):
    def get(self, path: str, **kwargs: Any) -> _JsonResponse: ...
    def close(self) -> None: ...


ClientFactory = Callable[[str, str, str, float], _Client]


def _default_client_factory(api_key: str, api_secret: str, base_url: str, timeout: float) -> _Client:
    try:
        from dnse import DnseClient
    except ImportError as exc:
        raise RuntimeError(f"DNSE_SDK_NOT_INSTALLED:{DNSE_SDK_VERSION}") from exc
    return DnseClient(api_key=api_key, api_secret=api_secret, base_url=base_url, timeout=timeout)


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _csv_bytes(rows: Sequence[Mapping[str, object]], fields: Sequence[str]) -> bytes:
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    return buffer.getvalue().encode("utf-8-sig")


def _float(value: object, default: float = 0.0) -> float:
    try:
        result = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return default
    return result if isfinite(result) else default


def _int(value: object, default: int = 0) -> int:
    result = _float(value, float(default))
    return int(result) if result >= 0 else default


def _mask_account(value: str) -> str:
    normalized = value.strip()
    if len(normalized) <= 4:
        return "*" * len(normalized)
    return "*" * max(4, len(normalized) - 4) + normalized[-4:]


def _extract_list(payload: object, *keys: str) -> list[Mapping[str, object]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, Mapping)]
    if isinstance(payload, Mapping):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, Mapping)]
        data = payload.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, Mapping)]
        if isinstance(data, Mapping):
            return _extract_list(data, *keys)
    return []


def _find_number(payload: object, names: Sequence[str], default: float = 0.0) -> float:
    wanted = {name.lower() for name in names}
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if str(key).lower() in wanted:
                result = _float(value, float("nan"))
                if isfinite(result):
                    return result
        for value in payload.values():
            result = _find_number(value, names, float("nan"))
            if isfinite(result):
                return result
    return default


def _account_id(account: Mapping[str, object]) -> str:
    for key in ("id", "accountNo", "account_no", "accountId"):
        value = str(account.get(key) or "").strip()
        if value:
            return value
    return ""


def _price_vnd(value: object, reference_vnd: float) -> float:
    raw = _float(value)
    if raw <= 0:
        return reference_vnd
    candidates = (raw, raw * 1000.0)
    if reference_vnd <= 0:
        return raw * 1000.0 if raw < 1000 else raw
    return min(candidates, key=lambda candidate: abs(candidate / reference_vnd - 1.0))


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _latest_analysis(data_root: Path) -> tuple[Path, list[dict[str, str]], list[dict[str, str]], dict[str, object]]:
    candidates: list[Path] = []
    for pattern in ("anytime-web-*", "snapshot-web-*", "eod-web-*", "eod-dnse-*", "eod-dnse-vci-*"):
        candidates.extend(path for path in data_root.glob(pattern) if path.is_dir())
    for run in sorted(set(candidates), key=lambda path: path.stat().st_mtime, reverse=True):
        prediction = run / "prediction" / "latest_prediction.csv"
        allocation = run / "paper_portfolio.csv"
        model = run / "prediction" / "model_comparison.json"
        manifest = run / "manifest.json"
        if prediction.is_file() and allocation.is_file() and model.is_file() and _read_json(manifest).get("status") == "SUCCESS":
            return run, _read_csv(prediction), _read_csv(allocation), _read_json(model)
    raise ValueError("PORTFOLIO_ANALYSIS_BASE_NOT_FOUND")


class DnseReadOnlyClient:
    """Minimal DNSE GET client with an explicit read-only endpoint allowlist."""

    _ACCOUNT = re.compile(r"^/accounts(?:/[A-Za-z0-9_-]+/(?:balances|positions))?$")
    _MARKET = re.compile(r"^/price/[A-Za-z0-9._-]+/(?:trades/latest|quotes/latest|foreign-trading)$")

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        *,
        base_url: str = DNSE_BASE_URL,
        timeout: float = 30.0,
        client_factory: ClientFactory = _default_client_factory,
    ) -> None:
        if not api_key.strip() or not api_secret.strip():
            raise ValueError("DNSE_CREDENTIALS_MISSING")
        if metadata.version("dnse") != DNSE_SDK_VERSION:
            raise RuntimeError("DNSE_SDK_VERSION_MISMATCH")
        self._client = client_factory(api_key.strip(), api_secret.strip(), base_url.rstrip("/"), timeout)

    @classmethod
    def from_env(cls, **kwargs: object) -> "DnseReadOnlyClient":
        return cls(os.environ.get("DNSE_API_KEY", ""), os.environ.get("DNSE_API_SECRET", ""), **kwargs)

    def close(self) -> None:
        self._client.close()

    def get(self, path: str, *, params: Mapping[str, object] | None = None) -> object:
        if not (self._ACCOUNT.fullmatch(path) or self._MARKET.fullmatch(path)):
            raise ValueError(f"DNSE_READ_ONLY_ENDPOINT_REJECTED:{path}")
        response = self._client.get(path, params=dict(params or {}))
        return response.json()

    def accounts(self) -> list[Mapping[str, object]]:
        return _extract_list(self.get("/accounts"), "accounts")

    def balances(self, account_no: str) -> object:
        return self.get(f"/accounts/{account_no}/balances")

    def positions(self, account_no: str) -> list[Mapping[str, object]]:
        payload = self.get(
            f"/accounts/{account_no}/positions",
            params={"marketType": "STOCK", "pageSize": 1000},
        )
        return _extract_list(payload, "positions")

    def market_context(self, symbol: str) -> dict[str, object]:
        output: dict[str, object] = {}
        errors: dict[str, str] = {}
        endpoints = {
            "latest_trade": f"/price/{symbol}/trades/latest",
            "latest_quote": f"/price/{symbol}/quotes/latest",
            "foreign_trading": f"/price/{symbol}/foreign-trading",
        }
        for name, path in endpoints.items():
            try:
                payload = self.get(path, params={"type": "STOCK"})
                output[name] = payload if isinstance(payload, (Mapping, list)) else {}
            except Exception as exc:
                errors[name] = f"{type(exc).__name__}:{exc}"
        output["errors"] = errors
        return output


def list_masked_accounts(client: DnseReadOnlyClient) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for account in client.accounts():
        account_no = _account_id(account)
        if not account_no:
            continue
        output.append({
            "account_no": account_no,
            "masked_account": _mask_account(account_no),
            "account_type": str(account.get("accountType") or account.get("type") or "STOCK"),
        })
    return output


def _normalize_position(raw: Mapping[str, object]) -> dict[str, object] | None:
    symbol = str(raw.get("symbol") or raw.get("instrument") or "").strip().upper()
    if not symbol:
        return None
    quantity = _int(
        raw.get("openQuantity")
        or raw.get("tradeQuantity")
        or raw.get("accumulateQuantity")
        or raw.get("quantity")
    )
    if quantity <= 0:
        return None
    return {
        "symbol": symbol,
        "quantity": quantity,
        "sellable_quantity": _int(raw.get("tradeQuantity") or raw.get("availableQuantity") or quantity),
        "cost_price_raw": _float(raw.get("costPrice") or raw.get("averagePrice") or raw.get("avgPrice")),
        "market_price_raw": _float(raw.get("marketPrice") or raw.get("currentPrice") or raw.get("price")),
        "break_even_price_raw": _float(raw.get("breakEvenPrice")),
        "status": str(raw.get("status") or "OPEN"),
        "loan_package_id": str(raw.get("loanPackageId") or ""),
    }


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
    now = datetime.now(VN_TZ)
    reader = read_client or DnseReadOnlyClient.from_env()
    source = market_source or DnseRestSource.from_env()
    close_reader, close_source = read_client is None, market_source is None
    try:
        accounts = list_masked_accounts(reader)
        if not accounts:
            raise ValueError("DNSE_ACCOUNTS_EMPTY")
        selected = None
        if account_no:
            selected = next((item for item in accounts if item["account_no"] == account_no), None)
            if selected is None:
                raise ValueError("DNSE_ACCOUNT_NOT_FOUND")
        else:
            stock_accounts = [item for item in accounts if "DERIV" not in item["account_type"].upper()]
            selected = (stock_accounts or accounts)[0]
        actual_account = selected["account_no"]
        masked_account = selected["masked_account"]
        balance_payload = reader.balances(actual_account)
        raw_positions = reader.positions(actual_account)
        positions = [item for item in (_normalize_position(raw) for raw in raw_positions) if item is not None]
        run, prediction_rows, allocation_rows, model = _latest_analysis(root)
        prediction_by_symbol = {
            str(row.get("symbol") or "").upper(): row for row in prediction_rows
        }
        target_by_symbol = {
            str(row.get("symbol") or "").upper(): _float(row.get("target_weight_pct"))
            for row in allocation_rows
        }
        analysis_rows: list[dict[str, object]] = []
        context: dict[str, object] = {}
        start = now.date() - timedelta(days=550)
        for position in sorted(positions, key=lambda item: str(item["symbol"])):
            symbol = str(position["symbol"])
            bars = tuple(source.fetch(symbol, start, now.date()))
            if not bars:
                raise ValueError(f"DNSE_PORTFOLIO_OHLC_EMPTY:{symbol}")
            indicators = compute_indicators(bars)
            reference_vnd = float(bars[-1].close) * 1000.0
            market_price = _price_vnd(position["market_price_raw"], reference_vnd)
            cost_price = _price_vnd(position["cost_price_raw"], market_price)
            quantity = int(position["quantity"])
            market_value = quantity * market_price
            cost_value = quantity * cost_price
            pnl = market_value - cost_value
            pnl_pct = pnl / cost_value if cost_value > 0 else 0.0
            prediction = prediction_by_symbol.get(symbol, {})
            target_weight = target_by_symbol.get(symbol, 0.0)
            ranking_rank = prediction.get("ranking_rank") or prediction.get("champion_rank") or ""
            ranking_score = prediction.get("ranking_score") or prediction.get("reference_score") or ""
            above_ma250 = bool(indicators.get("above_ma250"))
            trend_score = _float(indicators.get("trend_score"))
            action = "HOLD_MONITOR"
            if target_weight <= 0 and not above_ma250:
                action = "REVIEW_REDUCE_OUTSIDE_TARGET"
            elif target_weight <= 0:
                action = "NO_ADD_OUTSIDE_TARGET"
            elif above_ma250 and trend_score >= 0.60:
                action = "TARGET_ELIGIBLE"
            else:
                action = "WAIT_TREND_CONFIRMATION"
            analysis_rows.append({
                "symbol": symbol,
                "quantity": quantity,
                "sellable_quantity": position["sellable_quantity"],
                "cost_price_vnd": round(cost_price, 2),
                "market_price_vnd": round(market_price, 2),
                "market_value_vnd": round(market_value, 2),
                "unrealized_pnl_vnd": round(pnl, 2),
                "unrealized_pnl_pct": pnl_pct,
                "target_weight_pct": target_weight,
                "ranking_model": prediction.get("ranking_model") or model.get("ranking_model") or "",
                "ranking_rank": ranking_rank,
                "ranking_score": ranking_score,
                "champion_model": prediction.get("champion_model") or model.get("champion_model") or "",
                "above_ma250": above_ma250,
                "trend_score": trend_score,
                "rsi14": indicators.get("rsi14"),
                "macd_histogram": indicators.get("macd_histogram"),
                "atr14_pct": indicators.get("atr14_pct"),
                "bollinger_position20": indicators.get("bollinger_position20"),
                "stochastic14": indicators.get("stochastic14"),
                "volume_ratio20": indicators.get("volume_ratio20"),
                "obv_change20": indicators.get("obv_change20"),
                "return_20": indicators.get("return_20"),
                "return_60": indicators.get("return_60"),
                "drawdown_52week": indicators.get("drawdown_52week"),
                "indicator_bar_count": indicators.get("bar_count"),
                "indicator_warnings": "|".join(str(value) for value in indicators.get("warnings", [])),
                "action": action,
            })
            if include_market_context:
                context[symbol] = reader.market_context(symbol)
    finally:
        if close_source:
            source.close()
        if close_reader:
            reader.close()

    available_cash = _find_number(balance_payload, ("availableCash", "available_cash", "withdrawableCash"))
    total_cash = _find_number(balance_payload, ("totalCash", "total_cash"), available_cash)
    debt = _find_number(balance_payload, ("totalDebt", "total_debt", "debt"))
    stock_value = sum(_float(row["market_value_vnd"]) for row in analysis_rows)
    total_assets = stock_value + total_cash
    net_liquidation = total_assets - debt
    unrealized = sum(_float(row["unrealized_pnl_vnd"]) for row in analysis_rows)
    for row in analysis_rows:
        row["current_weight_pct"] = (
            100.0 * _float(row["market_value_vnd"]) / net_liquidation
            if net_liquidation > 0 else 0.0
        )
        target_value = net_liquidation * _float(row["target_weight_pct"]) / 100.0
        row["target_gap_vnd"] = round(target_value - _float(row["market_value_vnd"]), 2)
        if _float(row["current_weight_pct"]) > _float(row["target_weight_pct"]) + 2.0:
            row["action"] = "NO_ADD_OVERWEIGHT"

    weights = [
        _float(row["market_value_vnd"]) / stock_value
        for row in analysis_rows if stock_value > 0
    ]
    hhi = sum(weight * weight for weight in weights)
    effective_positions = 1.0 / hhi if hhi > 0 else 0.0
    largest_weight = max(weights, default=0.0)
    trend_health = (
        sum(weight * _float(row["trend_score"]) for weight, row in zip(weights, analysis_rows))
        if weights else 0.0
    )
    target_coverage = (
        sum(_float(row["market_value_vnd"]) for row in analysis_rows if _float(row["target_weight_pct"]) > 0) / stock_value
        if stock_value > 0 else 0.0
    )
    warnings: list[str] = []
    if largest_weight > 0.15:
        warnings.append("LIVE_PORTFOLIO_SYMBOL_CAP_EXCEEDED")
    if model.get("research_eligible") is not True:
        warnings.append("MODEL_RESEARCH_ELIGIBLE_FALSE")
    if model.get("robust_validation_status") != "PASS":
        warnings.append("ROBUST_VALIDATION_NOT_PASS")
    warnings.append("SECTOR_CAP_NOT_ENFORCED_WITHOUT_TRUSTED_SECTOR_MASTER")
    summary = {
        "schema_version": SCHEMA_VERSION,
        "as_of": now.isoformat(timespec="seconds"),
        "masked_account": masked_account,
        "source": "dnse_openapi_read_only",
        "position_count": len(analysis_rows),
        "available_cash_vnd": available_cash,
        "total_cash_vnd": total_cash,
        "total_debt_vnd": debt,
        "stock_market_value_vnd": stock_value,
        "net_liquidation_value_vnd": net_liquidation,
        "unrealized_pnl_vnd": unrealized,
        "cash_weight": total_cash / net_liquidation if net_liquidation > 0 else 0.0,
        "largest_position_weight": largest_weight,
        "concentration_hhi": hhi,
        "effective_position_count": effective_positions,
        "weighted_trend_health": trend_health,
        "target_coverage": target_coverage,
        "market_regime": model.get("market_regime"),
        "capital_budget_pct": model.get("capital_budget_pct"),
        "champion_model": model.get("champion_model"),
        "ranking_model": model.get("ranking_model") or model.get("reference_model"),
        "analysis_run": run.name,
        "warnings": warnings,
        "read_only": True,
        "trading_token_used": False,
        "research_eligible": False,
    }

    destination.mkdir(parents=True)
    fields = tuple(analysis_rows[0]) if analysis_rows else (
        "symbol", "quantity", "market_value_vnd", "action"
    )
    positions_path = destination / "portfolio_analysis.csv"
    positions_path.write_bytes(_csv_bytes(analysis_rows, fields))
    summary_path = destination / "portfolio_summary.json"
    summary_path.write_bytes(_json_bytes(summary))
    context_path = destination / "market_context.json"
    context_path.write_bytes(_json_bytes(context))
    methodology_path = destination / "indicator_methodology.json"
    methodology_path.write_bytes(_json_bytes({
        "source": "DNSE OHLCV calculated locally",
        "indicators": [
            "RSI14 Wilder", "MACD 12-26-9", "Bollinger 20x2", "ATR14 percent",
            "Stochastic14", "OBV change20", "volume ratio20", "MA20/60/120/250",
            "returns 20/60/120/250", "52-week drawdown", "composite trend score",
        ],
        "reason": "same formulas can be reproduced in backtest and live analysis",
        "precomputed_broker_indicator_dependency": False,
    }))
    files = (positions_path, summary_path, context_path, methodology_path)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "as_of": summary["as_of"],
        "masked_account": masked_account,
        "read_only": True,
        "credentials_recorded": False,
        "trading_token_used": False,
        "files": {
            path.name: {"sha256": sha256(path.read_bytes()).hexdigest(), "size": path.stat().st_size}
            for path in files
        },
    }
    manifest_path = destination / "manifest.json"
    manifest_path.write_bytes(_json_bytes(manifest))
    archive_path = destination / "dnse_portfolio_analysis.zip"
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        for path in (*files, manifest_path):
            archive.write(path, arcname=path.name)

    if sync_local_planner:
        store = PortfolioStore(root / "web-local" / "portfolio.sqlite3")
        incoming = {str(row["symbol"]): row for row in analysis_rows}
        for existing in store.list_holdings():
            if existing.symbol not in incoming:
                store.delete_holding(existing.symbol)
        for row in analysis_rows:
            store.upsert_holding(Holding(
                str(row["symbol"]),
                int(row["quantity"]),
                Decimal(str(row["cost_price_vnd"])),
            ))
        store.set_current_cash(max(0, int(available_cash)))

    state_root = root / "dnse-portfolio-live"
    state_root.mkdir(parents=True, exist_ok=True)
    (state_root / "LATEST.txt").write_text(str(destination.resolve()), encoding="utf-8")
    return {
        "status": "SUCCESS",
        "masked_account": masked_account,
        "position_count": len(analysis_rows),
        "available_cash_vnd": available_cash,
        "net_liquidation_value_vnd": net_liquidation,
        "unrealized_pnl_vnd": unrealized,
        "output_dir": str(destination),
        "output_zip": str(archive_path),
        "read_only": True,
    }
