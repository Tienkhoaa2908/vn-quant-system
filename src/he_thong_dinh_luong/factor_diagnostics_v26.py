"""Alphalens-style diagnostics for existing Model Lab OOS predictions.

The implementation is native to this repository so the canonical research
contract remains deterministic and dependency-light.  It adds independent
factor diagnostics: monthly rank IC, quantile returns, top-minus-bottom spread,
Top-K turnover, rolling IC and subperiod stability.  It does not retrain a model
or change any historical reference gate.
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from io import StringIO
import json
import math
from pathlib import Path
from statistics import fmean, median
from typing import Mapping, Sequence

SCHEMA_VERSION = "factor_diagnostics_v26"
REPORT_FILE = "factor_diagnostics_v26.json"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        return
    fields = list(rows[0].keys())
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    Path(path).write_text(buffer.getvalue(), encoding="utf-8-sig", newline="")


def _float(row: Mapping[str, object], key: str) -> float:
    value = row.get(key)
    if value in (None, ""):
        raise ValueError(f"V26_FACTOR_MISSING_NUMERIC:{key}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"V26_FACTOR_NON_FINITE:{key}")
    return number


def _average_ranks(values: Sequence[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: (item[1], item[0]))
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(indexed):
        end = cursor + 1
        while end < len(indexed) and indexed[end][1] == indexed[cursor][1]:
            end += 1
        average = (cursor + 1 + end) / 2.0
        for position in range(cursor, end):
            ranks[indexed[position][0]] = average
        cursor = end
    return ranks


def _pearson(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or len(left) < 3:
        return 0.0
    left_mean = fmean(left)
    right_mean = fmean(right)
    numerator = sum(
        (x - left_mean) * (y - right_mean)
        for x, y in zip(left, right)
    )
    denominator = math.sqrt(
        sum((x - left_mean) ** 2 for x in left)
        * sum((y - right_mean) ** 2 for y in right)
    )
    return numerator / denominator if denominator > 0.0 else 0.0


def _spearman(scores: Sequence[float], returns: Sequence[float]) -> float:
    return _pearson(_average_ranks(scores), _average_ranks(returns))


def _compound(values: Sequence[float]) -> float:
    nav = 1.0
    for value in values:
        nav *= 1.0 + float(value)
    return nav - 1.0


def _rolling_means(values: Sequence[float], window: int) -> list[float]:
    if window <= 0:
        raise ValueError("V26_FACTOR_ROLLING_WINDOW_MUST_BE_POSITIVE")
    if len(values) < window:
        return []
    return [fmean(values[index - window:index]) for index in range(window, len(values) + 1)]


def analyze_predictions(
    prediction_rows: Sequence[Mapping[str, object]],
    *,
    quantiles: int = 5,
    top_k: int = 10,
    rolling_months: int = 12,
) -> dict[str, object]:
    if quantiles < 2:
        raise ValueError("V26_FACTOR_QUANTILES_TOO_SMALL")
    if top_k < 1:
        raise ValueError("V26_FACTOR_TOP_K_MUST_BE_POSITIVE")
    grouped: dict[tuple[str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in prediction_rows:
        model = str(row.get("model") or "")
        day = str(row.get("test_date") or "")
        symbol = str(row.get("symbol") or "")
        if not model or not day or not symbol:
            raise ValueError("V26_FACTOR_MODEL_DATE_SYMBOL_REQUIRED")
        grouped[(model, day)].append(row)
    if not grouped:
        raise ValueError("V26_FACTOR_NO_PREDICTIONS")

    by_model: dict[str, list[tuple[str, list[Mapping[str, object]]]]] = defaultdict(list)
    for (model, day), rows in grouped.items():
        by_model[model].append((day, rows))

    period_rows: list[dict[str, object]] = []
    quantile_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []

    for model in sorted(by_model):
        periods = sorted(by_model[model], key=lambda item: item[0])
        previous_top: set[str] = set()
        model_periods: list[dict[str, object]] = []
        quantile_returns_by_period: list[dict[int, float]] = []

        for day, rows in periods:
            if len(rows) < max(3, quantiles):
                raise ValueError(f"V26_FACTOR_TOO_FEW_SYMBOLS:{model}:{day}:{len(rows)}")
            symbols = [str(row.get("symbol") or "") for row in rows]
            if len(set(symbols)) != len(symbols):
                raise ValueError(f"V26_FACTOR_DUPLICATE_SYMBOL:{model}:{day}")
            scores = [_float(row, "score") for row in rows]
            relative = [_float(row, "relative_return") for row in rows]
            rank_ic = _spearman(scores, relative)

            ascending = sorted(
                rows,
                key=lambda row: (_float(row, "score"), str(row.get("symbol") or "")),
            )
            quantile_members: dict[int, list[Mapping[str, object]]] = defaultdict(list)
            for index, row in enumerate(ascending):
                bucket = min(quantiles, index * quantiles // len(ascending) + 1)
                quantile_members[bucket].append(row)

            day_quantile_returns: dict[int, float] = {}
            day_quantile_relative: dict[int, float] = {}
            for bucket in range(1, quantiles + 1):
                members = quantile_members.get(bucket, [])
                if not members:
                    raise ValueError(f"V26_FACTOR_EMPTY_QUANTILE:{model}:{day}:{bucket}")
                stock_return = fmean(_float(row, "stock_return") for row in members)
                relative_return = fmean(_float(row, "relative_return") for row in members)
                day_quantile_returns[bucket] = stock_return
                day_quantile_relative[bucket] = relative_return
                quantile_rows.append({
                    "model": model,
                    "test_date": day,
                    "quantile": bucket,
                    "symbol_count": len(members),
                    "mean_stock_return": stock_return,
                    "mean_relative_return": relative_return,
                    "symbols": "|".join(sorted(str(row.get("symbol") or "") for row in members)),
                })

            ranked = sorted(
                rows,
                key=lambda row: (
                    int(float(row.get("rank") or 10**9)),
                    -_float(row, "score"),
                    str(row.get("symbol") or ""),
                ),
            )
            top_symbols = {str(row.get("symbol") or "") for row in ranked[:top_k]}
            turnover = 1.0 if not previous_top else 1.0 - len(previous_top & top_symbols) / top_k
            top_return = day_quantile_returns[quantiles]
            bottom_return = day_quantile_returns[1]
            spread = top_return - bottom_return
            record = {
                "model": model,
                "test_date": day,
                "symbol_count": len(rows),
                "rank_ic": rank_ic,
                "top_quantile_return": top_return,
                "bottom_quantile_return": bottom_return,
                "top_minus_bottom_return": spread,
                "top_quantile_relative_return": day_quantile_relative[quantiles],
                "bottom_quantile_relative_return": day_quantile_relative[1],
                "top_k_turnover": turnover,
                "top_k_symbols": "|".join(sorted(top_symbols)),
            }
            period_rows.append(record)
            model_periods.append(record)
            quantile_returns_by_period.append(day_quantile_returns)
            previous_top = top_symbols

        ic_values = [float(row["rank_ic"]) for row in model_periods]
        spreads = [float(row["top_minus_bottom_return"]) for row in model_periods]
        top_returns = [float(row["top_quantile_return"]) for row in model_periods]
        bottom_returns = [float(row["bottom_quantile_return"]) for row in model_periods]
        turnovers = [float(row["top_k_turnover"]) for row in model_periods]
        midpoint = len(model_periods) // 2
        rolling = _rolling_means(ic_values, rolling_months)
        best_index = max(range(len(spreads)), key=spreads.__getitem__)
        top_without_best = [value for index, value in enumerate(top_returns) if index != best_index]
        bottom_without_best = [value for index, value in enumerate(bottom_returns) if index != best_index]
        summary_rows.append({
            "model": model,
            "period_count": len(model_periods),
            "first_test_date": str(model_periods[0]["test_date"]),
            "last_test_date": str(model_periods[-1]["test_date"]),
            "mean_rank_ic": fmean(ic_values),
            "median_rank_ic": median(ic_values),
            "positive_rank_ic_ratio": sum(value > 0.0 for value in ic_values) / len(ic_values),
            "first_half_mean_rank_ic": fmean(ic_values[:midpoint]) if midpoint else 0.0,
            "second_half_mean_rank_ic": fmean(ic_values[midpoint:]),
            "rolling_ic_window_months": rolling_months,
            "rolling_ic_minimum": min(rolling) if rolling else 0.0,
            "rolling_ic_maximum": max(rolling) if rolling else 0.0,
            "mean_top_minus_bottom_return": fmean(spreads),
            "positive_top_minus_bottom_ratio": sum(value > 0.0 for value in spreads) / len(spreads),
            "top_quantile_compound_return": _compound(top_returns),
            "bottom_quantile_compound_return": _compound(bottom_returns),
            "top_minus_bottom_compound_difference": _compound(top_returns) - _compound(bottom_returns),
            "leave_best_period_out_top_minus_bottom_compound_difference": (
                _compound(top_without_best) - _compound(bottom_without_best)
            ),
            "best_spread_test_date": str(model_periods[best_index]["test_date"]),
            "best_spread_return": spreads[best_index],
            "mean_top_k_turnover": fmean(turnovers),
            "sector_analysis_status": (
                "AVAILABLE" if all("sector" in row and row.get("sector") not in (None, "") for _, rows in periods for row in rows)
                else "SECTOR_COLUMN_NOT_AVAILABLE"
            ),
            "actionable": False,
        })

    summary_rows.sort(
        key=lambda row: (
            float(row["mean_rank_ic"]),
            float(row["top_minus_bottom_compound_difference"]),
            -float(row["mean_top_k_turnover"]),
        ),
        reverse=True,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "quantiles": quantiles,
        "top_k": top_k,
        "rolling_months": rolling_months,
        "model_count": len(summary_rows),
        "summary_rows": summary_rows,
        "period_rows": period_rows,
        "quantile_rows": quantile_rows,
        "diagnostic_only": True,
        "historical_reference_gate_modified": False,
        "research_eligible": False,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }


def run_factor_diagnostics(
    predictions_csv: Path,
    output_dir: Path,
    *,
    quantiles: int = 5,
    top_k: int = 10,
    rolling_months: int = 12,
) -> dict[str, object]:
    source = Path(predictions_csv).resolve()
    destination = Path(output_dir).resolve()
    if not source.is_file():
        raise ValueError("V26_FACTOR_PREDICTIONS_NOT_FOUND")
    if destination.exists():
        raise FileExistsError(f"V26_FACTOR_OUTPUT_EXISTS:{destination}")
    destination.mkdir(parents=True)
    try:
        result = analyze_predictions(
            _read_csv(source),
            quantiles=quantiles,
            top_k=top_k,
            rolling_months=rolling_months,
        )
        _write_csv(destination / "factor_summary_v26.csv", result["summary_rows"])
        _write_csv(destination / "factor_periods_v26.csv", result["period_rows"])
        _write_csv(destination / "factor_quantiles_v26.csv", result["quantile_rows"])
        report = {
            **result,
            "predictions_csv": str(source),
            "output_dir": str(destination),
        }
        (destination / REPORT_FILE).write_text(
            json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        return report
    except Exception:
        for path in sorted(destination.glob("*")):
            if path.is_file():
                path.unlink()
        destination.rmdir()
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m he_thong_dinh_luong.factor_diagnostics_v26"
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--predictions-csv", type=Path)
    source.add_argument("--model-output", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--quantiles", type=int, default=5)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--rolling-months", type=int, default=12)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    source = args.predictions_csv or (args.model_output / "oos_predictions.csv")
    try:
        result = run_factor_diagnostics(
            source,
            args.output_dir,
            quantiles=args.quantiles,
            top_k=args.top_k,
            rolling_months=args.rolling_months,
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
        "model_count": result["model_count"],
        "report": str(Path(result["output_dir"]) / REPORT_FILE),
        "live_capital_approved": False,
    }, ensure_ascii=False, sort_keys=True))
    return 0


__all__ = [
    "SCHEMA_VERSION",
    "REPORT_FILE",
    "analyze_predictions",
    "run_factor_diagnostics",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
