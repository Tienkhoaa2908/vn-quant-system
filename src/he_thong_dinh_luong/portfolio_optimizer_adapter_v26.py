"""Optional PyPortfolioOpt allocation benchmark for VN Quant System.

The canonical allocator remains the repository's contribution-aware, odd-lot,
long-only implementation.  This adapter provides an independent minimum-
volatility benchmark with Ledoit-Wolf covariance shrinkage, a per-symbol cap and
sector caps.  It is diagnostic only and never emits orders.
"""
from __future__ import annotations

import argparse
import csv
from io import StringIO
import json
import math
from pathlib import Path
from statistics import pstdev
from typing import Mapping, Sequence

SCHEMA_VERSION = "portfolio_optimizer_adapter_v26"
REPORT_FILE = "portfolio_optimizer_v26.json"


def capped_inverse_volatility_weights(
    returns_by_symbol: Mapping[str, Sequence[float]],
    *,
    max_symbol_weight: float = 0.15,
) -> dict[str, float]:
    if not 0.0 < max_symbol_weight <= 1.0:
        raise ValueError("V26_INVALID_SYMBOL_CAP")
    if len(returns_by_symbol) < 2:
        raise ValueError("V26_TOO_FEW_SYMBOLS")
    if len(returns_by_symbol) * max_symbol_weight < 1.0 - 1e-12:
        raise ValueError("V26_SYMBOL_CAP_INFEASIBLE")
    raw: dict[str, float] = {}
    for symbol, values in returns_by_symbol.items():
        numbers = [float(value) for value in values]
        if len(numbers) < 3 or any(not math.isfinite(value) for value in numbers):
            raise ValueError(f"V26_INVALID_RETURN_HISTORY:{symbol}")
        volatility = pstdev(numbers)
        if volatility <= 0.0:
            raise ValueError(f"V26_NON_POSITIVE_VOLATILITY:{symbol}")
        raw[str(symbol)] = 1.0 / volatility
    total = sum(raw.values())
    weights = {symbol: value / total for symbol, value in raw.items()}
    fixed: dict[str, float] = {}
    remaining = dict(weights)
    remaining_mass = 1.0
    while remaining:
        scale = remaining_mass / sum(remaining.values())
        proposed = {symbol: value * scale for symbol, value in remaining.items()}
        breached = {
            symbol: value
            for symbol, value in proposed.items()
            if value > max_symbol_weight + 1e-15
        }
        if not breached:
            fixed.update(proposed)
            break
        for symbol in sorted(breached):
            fixed[symbol] = max_symbol_weight
            remaining.pop(symbol)
            remaining_mass -= max_symbol_weight
        if remaining_mass < -1e-12:
            raise ValueError("V26_SYMBOL_CAP_INFEASIBLE")
    if abs(sum(fixed.values()) - 1.0) > 1e-9:
        raise ValueError("V26_WEIGHT_NORMALIZATION_FAILED")
    return dict(sorted(fixed.items()))


def _read_sector_map(path: Path) -> dict[str, str]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    result: dict[str, str] = {}
    for row in rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        sector = str(row.get("sector") or "").strip()
        if not symbol or not sector:
            raise ValueError("V26_SECTOR_SYMBOL_AND_SECTOR_REQUIRED")
        if symbol in result and result[symbol] != sector:
            raise ValueError(f"V26_CONFLICTING_SECTOR:{symbol}")
        result[symbol] = sector
    if not result:
        raise ValueError("V26_EMPTY_SECTOR_MAP")
    return result


def _write_weights(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    fields = ["symbol", "sector", "weight"]
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    Path(path).write_text(buffer.getvalue(), encoding="utf-8-sig", newline="")


def run_pypfopt_min_volatility(
    prices_csv: Path,
    sectors_csv: Path,
    output_dir: Path,
    *,
    as_of: str | None = None,
    lookback_sessions: int = 252,
    minimum_observations: int = 120,
    max_symbol_weight: float = 0.15,
    max_sector_weight: float = 0.25,
) -> dict[str, object]:
    if lookback_sessions < minimum_observations:
        raise ValueError("V26_LOOKBACK_BELOW_MINIMUM_OBSERVATIONS")
    if minimum_observations < 20:
        raise ValueError("V26_MINIMUM_OBSERVATIONS_TOO_SMALL")
    if not 0.0 < max_symbol_weight <= 1.0:
        raise ValueError("V26_INVALID_SYMBOL_CAP")
    if not 0.0 < max_sector_weight <= 1.0:
        raise ValueError("V26_INVALID_SECTOR_CAP")
    source = Path(prices_csv).resolve()
    sectors_path = Path(sectors_csv).resolve()
    destination = Path(output_dir).resolve()
    if not source.is_file():
        raise ValueError("V26_PRICES_CSV_NOT_FOUND")
    if not sectors_path.is_file():
        raise ValueError("V26_SECTORS_CSV_NOT_FOUND")
    if destination.exists():
        raise FileExistsError(f"V26_OPTIMIZER_OUTPUT_EXISTS:{destination}")

    try:
        import pandas as pd
        from pypfopt import EfficientFrontier, risk_models
    except ImportError as exc:
        raise RuntimeError(
            "V26_PYPORTFOLIOOPT_NOT_INSTALLED:install pandas and PyPortfolioOpt"
        ) from exc

    sector_map = _read_sector_map(sectors_path)
    frame = pd.read_csv(source)
    required = {"day", "symbol", "close"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError("V26_PRICE_COLUMNS_MISSING:" + "|".join(sorted(missing)))
    frame = frame.loc[:, ["day", "symbol", "close"]].copy()
    frame["day"] = pd.to_datetime(frame["day"], errors="raise")
    frame["symbol"] = frame["symbol"].astype(str).str.upper().str.strip()
    frame["close"] = pd.to_numeric(frame["close"], errors="raise")
    if as_of:
        frame = frame[frame["day"] <= pd.Timestamp(as_of)]
    if frame.empty:
        raise ValueError("V26_NO_PRICES_BEFORE_AS_OF")
    duplicates = frame.duplicated(subset=["day", "symbol"], keep=False)
    if bool(duplicates.any()):
        raise ValueError("V26_DUPLICATE_PRICE_DAY_SYMBOL")
    pivot = frame.pivot(index="day", columns="symbol", values="close").sort_index()
    pivot = pivot.tail(lookback_sessions)
    counts = pivot.notna().sum(axis=0)
    symbols = sorted(
        symbol
        for symbol in pivot.columns
        if int(counts[symbol]) >= minimum_observations and symbol in sector_map
    )
    if len(symbols) < 8:
        raise ValueError(f"V26_TOO_FEW_OPTIMIZABLE_SYMBOLS:{len(symbols)}")
    if len(symbols) * max_symbol_weight < 1.0 - 1e-12:
        raise ValueError("V26_SYMBOL_CAP_INFEASIBLE")
    sector_counts: dict[str, int] = {}
    for symbol in symbols:
        sector = sector_map[symbol]
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
    if len(sector_counts) * max_sector_weight < 1.0 - 1e-12:
        raise ValueError("V26_SECTOR_CAP_INFEASIBLE")
    prices = pivot.loc[:, symbols].dropna(axis=0, how="any")
    if len(prices) < minimum_observations:
        raise ValueError(
            f"V26_TOO_FEW_COMMON_PRICE_OBSERVATIONS:{len(prices)}<{minimum_observations}"
        )
    if bool((prices <= 0.0).any().any()):
        raise ValueError("V26_NON_POSITIVE_PRICE")

    covariance = risk_models.CovarianceShrinkage(prices).ledoit_wolf()
    optimiser = EfficientFrontier(
        expected_returns=None,
        cov_matrix=covariance,
        weight_bounds=(0.0, max_symbol_weight),
    )
    mapper = {symbol: sector_map[symbol] for symbol in symbols}
    sector_upper = {sector: max_sector_weight for sector in sorted(set(mapper.values()))}
    optimiser.add_sector_constraints(mapper, {}, sector_upper)
    raw_weights = optimiser.min_volatility()
    weights = {
        str(symbol): float(value)
        for symbol, value in raw_weights.items()
        if float(value) > 1e-8
    }
    total = sum(weights.values())
    if total <= 0.0:
        raise ValueError("V26_OPTIMIZER_RETURNED_EMPTY_WEIGHTS")
    weights = {symbol: value / total for symbol, value in weights.items()}

    sector_weights: dict[str, float] = {}
    for symbol, weight in weights.items():
        sector = mapper[symbol]
        sector_weights[sector] = sector_weights.get(sector, 0.0) + weight
    symbol_cap_violation = max(weights.values()) - max_symbol_weight
    sector_cap_violation = max(sector_weights.values()) - max_sector_weight
    if symbol_cap_violation > 1e-6:
        raise ValueError("V26_OPTIMIZER_SYMBOL_CAP_VIOLATION")
    if sector_cap_violation > 1e-6:
        raise ValueError("V26_OPTIMIZER_SECTOR_CAP_VIOLATION")

    vector = pd.Series(weights).reindex(covariance.index).fillna(0.0)
    variance = float(vector.T @ covariance @ vector)
    annualized_volatility = math.sqrt(max(0.0, variance))
    returns = prices.pct_change().dropna()
    inverse_input = {
        symbol: [float(value) for value in returns[symbol].dropna().tolist()]
        for symbol in symbols
    }
    inverse_weights = capped_inverse_volatility_weights(
        inverse_input,
        max_symbol_weight=max_symbol_weight,
    )

    destination.mkdir(parents=True)
    try:
        weight_rows = [
            {
                "symbol": symbol,
                "sector": mapper[symbol],
                "weight": weights[symbol],
            }
            for symbol in sorted(weights)
        ]
        inverse_rows = [
            {
                "symbol": symbol,
                "sector": mapper[symbol],
                "weight": inverse_weights[symbol],
            }
            for symbol in sorted(inverse_weights)
        ]
        _write_weights(destination / "pypfopt_min_vol_weights_v26.csv", weight_rows)
        _write_weights(destination / "inverse_vol_reference_weights_v26.csv", inverse_rows)
        report = {
            "schema_version": SCHEMA_VERSION,
            "status": "SUCCESS",
            "method": "PYPFOPT_MIN_VOLATILITY_LEDOIT_WOLF",
            "prices_csv": str(source),
            "sectors_csv": str(sectors_path),
            "output_dir": str(destination),
            "as_of": str(prices.index[-1].date()),
            "first_price_day": str(prices.index[0].date()),
            "last_price_day": str(prices.index[-1].date()),
            "common_observation_count": len(prices),
            "eligible_symbol_count": len(symbols),
            "selected_symbol_count": len(weights),
            "max_symbol_weight": max_symbol_weight,
            "max_sector_weight": max_sector_weight,
            "annualized_volatility": annualized_volatility,
            "weights": weights,
            "sector_weights": dict(sorted(sector_weights.items())),
            "inverse_volatility_reference_weights": inverse_weights,
            "allocation_replaces_canonical_allocator": False,
            "diagnostic_only": True,
            "research_eligible": False,
            "live_capital_approved": False,
            "automatic_live_orders_allowed": False,
        }
        (destination / REPORT_FILE).write_text(
            json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        return report
    except Exception:
        for path in destination.glob("*"):
            if path.is_file():
                path.unlink()
        destination.rmdir()
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m he_thong_dinh_luong.portfolio_optimizer_adapter_v26"
    )
    parser.add_argument("--prices-csv", type=Path, required=True)
    parser.add_argument("--sectors-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--as-of")
    parser.add_argument("--lookback-sessions", type=int, default=252)
    parser.add_argument("--minimum-observations", type=int, default=120)
    parser.add_argument("--max-symbol-weight", type=float, default=0.15)
    parser.add_argument("--max-sector-weight", type=float, default=0.25)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_pypfopt_min_volatility(
            args.prices_csv,
            args.sectors_csv,
            args.output_dir,
            as_of=args.as_of,
            lookback_sessions=args.lookback_sessions,
            minimum_observations=args.minimum_observations,
            max_symbol_weight=args.max_symbol_weight,
            max_sector_weight=args.max_sector_weight,
        )
    except Exception as exc:
        print(json.dumps({
            "status": "FAILED",
            "error": f"{type(exc).__name__}:{exc}",
        }, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps({
        "status": result["status"],
        "output_dir": result["output_dir"],
        "report": str(Path(result["output_dir"]) / REPORT_FILE),
        "selected_symbol_count": result["selected_symbol_count"],
        "live_capital_approved": False,
    }, ensure_ascii=False, sort_keys=True))
    return 0


__all__ = [
    "SCHEMA_VERSION",
    "REPORT_FILE",
    "capped_inverse_volatility_weights",
    "run_pypfopt_min_volatility",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
