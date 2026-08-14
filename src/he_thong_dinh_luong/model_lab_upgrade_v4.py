"""Model Lab v4: cost-safe defaults and reference-only turnover diagnostics.

This layer preserves every v3 research gate. It adds a predeclared Top-K
retention buffer, regime diagnostics, and explicit fail-closed sector
neutralization requirements without converting diagnostics into trade advice.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
from math import isfinite
from pathlib import Path
from statistics import fmean
from typing import Mapping, Sequence
from zipfile import ZipFile

from . import model_lab_runner_v2 as quality_runner
from . import model_lab_upgrade_v3 as v3
from .model_lab_core import DEFAULT_MODELS

SCHEMA_VERSION = "vn_quant_model_lab_upgrade_v4"
DEFAULT_SELL_TAX_BPS = 10.0
DEFAULT_BUFFER_RATIO = 0.50


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]], fields: Sequence[str]) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    path.write_text(buffer.getvalue(), encoding="utf-8-sig", newline="")


def _float(row: Mapping[str, object], field: str) -> float:
    value = float(row.get(field, 0.0) or 0.0)
    if not isfinite(value):
        raise ValueError(f"MODEL_LAB_NONFINITE:{field}")
    return value


def _int(row: Mapping[str, object], field: str) -> int:
    return int(float(row.get(field, 0) or 0))


def _drawdown(values: Sequence[float]) -> float:
    peak = 0.0
    worst = 0.0
    for value in values:
        peak = max(peak, float(value))
        if peak > 0.0:
            worst = min(worst, float(value) / peak - 1.0)
    return worst


def buffered_top_k_periods(
    prediction_rows: Sequence[Mapping[str, object]],
    *,
    top_k: int,
    hold_buffer: int,
    buy_fee_bps: float,
    sell_fee_bps: float,
    sell_tax_bps: float,
    slippage_bps: float,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Apply a fixed rank buffer using only current scores and prior holdings.

    Existing holdings are retained while their current rank is no worse than
    ``top_k + hold_buffer``. Vacancies are filled from the current ranking.
    The rule is deterministic and never reads current-period returns to select.
    """
    if top_k <= 0:
        raise ValueError("MODEL_LAB_BUFFER_TOP_K_NONPOSITIVE")
    if hold_buffer < 0:
        raise ValueError("MODEL_LAB_BUFFER_NEGATIVE")
    if not prediction_rows:
        raise ValueError("MODEL_LAB_BUFFER_PREDICTIONS_EMPTY")
    by_day: dict[str, list[Mapping[str, object]]] = {}
    models = {str(row.get("model") or "") for row in prediction_rows}
    if len(models) != 1 or "" in models:
        raise ValueError("MODEL_LAB_BUFFER_SINGLE_MODEL_REQUIRED")
    model = next(iter(models))
    for row in prediction_rows:
        day = str(row.get("test_date") or "")
        symbol = str(row.get("symbol") or "").strip().upper()
        if not day or not symbol:
            raise ValueError("MODEL_LAB_BUFFER_KEY_MISSING")
        by_day.setdefault(day, []).append(row)

    previous: set[str] = set()
    nav = 1.0
    gross_nav = 1.0
    benchmark_nav = 1.0
    total_cost = 0.0
    turnovers: list[float] = []
    excess_returns: list[float] = []
    nav_values: list[float] = []
    periods: list[dict[str, object]] = []
    entry_cost = (buy_fee_bps + slippage_bps) / 10_000.0
    round_trip_cost = (
        buy_fee_bps + sell_fee_bps + sell_tax_bps + 2.0 * slippage_bps
    ) / 10_000.0

    for period_index, day in enumerate(sorted(by_day)):
        ranked = sorted(
            by_day[day],
            key=lambda row: (_int(row, "rank"), str(row.get("symbol") or "")),
        )
        by_symbol = {
            str(row.get("symbol") or "").strip().upper(): row for row in ranked
        }
        target_count = min(top_k, len(ranked))
        retain_limit = top_k + hold_buffer
        retained = sorted(
            (
                symbol
                for symbol in previous
                if symbol in by_symbol and _int(by_symbol[symbol], "rank") <= retain_limit
            ),
            key=lambda symbol: (_int(by_symbol[symbol], "rank"), symbol),
        )
        selected = retained[:target_count]
        selected_set = set(selected)
        for row in ranked:
            if len(selected) >= target_count:
                break
            symbol = str(row.get("symbol") or "").strip().upper()
            if symbol not in selected_set:
                selected.append(symbol)
                selected_set.add(symbol)
        if not selected:
            raise ValueError(f"MODEL_LAB_BUFFER_SELECTION_EMPTY:{day}")

        selected_rows = [by_symbol[symbol] for symbol in selected]
        gross_return = fmean(_float(row, "stock_return") for row in selected_rows)
        benchmark_return = fmean(_float(row, "benchmark_return") for row in selected_rows)
        turnover = (
            1.0
            if not previous
            else 1.0 - len(selected_set & previous) / max(len(selected_set), 1)
        )
        cost_rate = entry_cost if period_index == 0 else turnover * round_trip_cost
        net_return = gross_return - cost_rate
        net_excess = net_return - benchmark_return

        gross_nav *= max(1e-9, 1.0 + gross_return)
        nav *= max(1e-9, 1.0 + net_return)
        benchmark_nav *= max(1e-9, 1.0 + benchmark_return)
        total_cost += cost_rate
        turnovers.append(turnover)
        excess_returns.append(net_excess)
        nav_values.append(nav)

        label_end = max(str(row.get("label_end") or "") for row in selected_rows)
        periods.append({
            "model": model,
            "strategy": "predeclared_top_k_retention_buffer",
            "signal_date": day,
            "label_end": label_end,
            "top_k": top_k,
            "hold_buffer": hold_buffer,
            "retain_rank_limit": retain_limit,
            "selected_symbols": "|".join(sorted(selected_set)),
            "gross_return": gross_return,
            "benchmark_return": benchmark_return,
            "turnover": turnover,
            "estimated_cost_rate": cost_rate,
            "net_return": net_return,
            "net_excess_return": net_excess,
            "net_nav": nav,
            "benchmark_nav": benchmark_nav,
            "relative_nav": nav / benchmark_nav if benchmark_nav > 0.0 else 0.0,
            "actionable": "false",
        })
        previous = selected_set

    summary = {
        "model": model,
        "strategy": "predeclared_top_k_retention_buffer",
        "period_count": len(periods),
        "top_k": top_k,
        "hold_buffer": hold_buffer,
        "retain_rank_limit": top_k + hold_buffer,
        "gross_total_return": gross_nav - 1.0,
        "net_total_return": nav - 1.0,
        "benchmark_total_return": benchmark_nav - 1.0,
        "relative_total_return": nav / benchmark_nav - 1.0 if benchmark_nav > 0.0 else 0.0,
        "mean_turnover": fmean(turnovers) if turnovers else 0.0,
        "estimated_cost_drag_sum": total_cost,
        "average_net_excess_return": fmean(excess_returns) if excess_returns else 0.0,
        "positive_net_excess_ratio": (
            fmean(1.0 if value > 0.0 else 0.0 for value in excess_returns)
            if excess_returns else 0.0
        ),
        "max_drawdown": _drawdown(nav_values),
        "selection_uses_realized_returns": False,
        "research_gate_unchanged": True,
        "actionable": False,
    }
    return summary, periods


def _compounded(rows: Sequence[Mapping[str, object]], field: str) -> float:
    nav = 1.0
    for row in rows:
        nav *= max(1e-9, 1.0 + _float(row, field))
    return nav - 1.0


def _load_regime_by_date(input_zip: Path) -> tuple[dict[str, str], str]:
    values: dict[str, set[str]] = {}
    with ZipFile(input_zip) as archive:
        try:
            payload = archive.read("feature_raw.csv").decode("utf-8-sig")
        except KeyError:
            return {}, "FEATURE_RAW_MISSING"
    reader = csv.DictReader(io.StringIO(payload))
    if reader.fieldnames is None or "vnindex_tren_ma250" not in reader.fieldnames:
        return {}, "VNINDEX_MA250_FEATURE_MISSING"
    for row in reader:
        day = str(row.get("ngay") or "")
        raw = str(row.get("vnindex_tren_ma250") or "").strip().lower()
        if not day or raw == "":
            continue
        if raw in {"true", "1"}:
            regime = "RISK_ON"
        elif raw in {"false", "0"}:
            regime = "RISK_OFF"
        else:
            return {}, f"VNINDEX_MA250_INVALID:{raw}"
        values.setdefault(day, set()).add(regime)
    if any(len(items) != 1 for items in values.values()):
        return {}, "VNINDEX_MA250_AMBIGUOUS"
    return {day: next(iter(items)) for day, items in values.items()}, "PASS"


def _regime_rows(
    periods: Sequence[Mapping[str, object]],
    regime_by_date: Mapping[str, str],
) -> tuple[list[dict[str, object]], int]:
    grouped: dict[tuple[str, str], list[Mapping[str, object]]] = {}
    missing = 0
    for row in periods:
        day = str(row.get("signal_date") or "")
        regime = regime_by_date.get(day)
        if regime is None:
            missing += 1
            continue
        grouped.setdefault((str(row.get("model") or ""), regime), []).append(row)
    output: list[dict[str, object]] = []
    for (model, regime), rows in sorted(grouped.items()):
        net_total = _compounded(rows, "net_return")
        benchmark_total = _compounded(rows, "benchmark_return")
        output.append({
            "model": model,
            "regime": regime,
            "period_count": len(rows),
            "net_total_return": net_total,
            "benchmark_total_return": benchmark_total,
            "relative_total_return": (
                (1.0 + net_total) / (1.0 + benchmark_total) - 1.0
                if benchmark_total > -1.0 else 0.0
            ),
            "average_net_excess_return": fmean(
                _float(row, "net_excess_return") for row in rows
            ),
            "positive_net_excess_ratio": fmean(
                1.0 if _float(row, "net_excess_return") > 0.0 else 0.0
                for row in rows
            ),
            "mean_turnover": fmean(_float(row, "turnover") for row in rows),
            "actionable": "false",
        })
    return output, missing


def publish_v4_diagnostics(
    *,
    output_dir: Path,
    input_zip: Path,
    top_k: int,
    hold_buffer: int,
    buy_fee_bps: float,
    sell_fee_bps: float,
    sell_tax_bps: float,
    slippage_bps: float,
) -> dict[str, object]:
    output = Path(output_dir)
    predictions = _read_csv(output / "oos_predictions.csv")
    baseline_periods = _read_csv(output / "oos_backtest_periods.csv")
    by_model: dict[str, list[dict[str, str]]] = {}
    baseline_by_model: dict[str, list[dict[str, str]]] = {}
    for row in predictions:
        by_model.setdefault(str(row.get("model") or ""), []).append(row)
    for row in baseline_periods:
        baseline_by_model.setdefault(str(row.get("model") or ""), []).append(row)

    diagnostic_rows: list[dict[str, object]] = []
    buffered_periods: list[dict[str, object]] = []
    for model in sorted(by_model):
        metrics, periods = buffered_top_k_periods(
            by_model[model],
            top_k=top_k,
            hold_buffer=hold_buffer,
            buy_fee_bps=buy_fee_bps,
            sell_fee_bps=sell_fee_bps,
            sell_tax_bps=sell_tax_bps,
            slippage_bps=slippage_bps,
        )
        baseline = baseline_by_model.get(model, [])
        baseline_turnover = (
            fmean(_float(row, "turnover") for row in baseline) if baseline else 0.0
        )
        baseline_total = _compounded(baseline, "net_return") if baseline else 0.0
        diagnostic_rows.append({
            **metrics,
            "baseline_top_k_net_total_return": baseline_total,
            "net_total_return_delta_vs_top_k": (
                float(metrics["net_total_return"]) - baseline_total
            ),
            "baseline_top_k_mean_turnover": baseline_turnover,
            "turnover_reduction_vs_top_k": (
                baseline_turnover - float(metrics["mean_turnover"])
            ),
        })
        buffered_periods.extend(periods)

    diagnostic_fields = (
        "model", "strategy", "period_count", "top_k", "hold_buffer",
        "retain_rank_limit", "gross_total_return", "net_total_return",
        "benchmark_total_return", "relative_total_return", "mean_turnover",
        "baseline_top_k_mean_turnover", "turnover_reduction_vs_top_k",
        "estimated_cost_drag_sum", "average_net_excess_return",
        "positive_net_excess_ratio", "max_drawdown",
        "baseline_top_k_net_total_return", "net_total_return_delta_vs_top_k",
        "selection_uses_realized_returns", "research_gate_unchanged", "actionable",
    )
    period_fields = (
        "model", "strategy", "signal_date", "label_end", "top_k", "hold_buffer",
        "retain_rank_limit", "selected_symbols", "gross_return",
        "benchmark_return", "turnover", "estimated_cost_rate", "net_return",
        "net_excess_return", "net_nav", "benchmark_nav", "relative_nav",
        "actionable",
    )
    _write_csv(output / "turnover_buffer_diagnostic.csv", diagnostic_rows, diagnostic_fields)
    _write_csv(output / "turnover_buffer_periods.csv", buffered_periods, period_fields)

    regime_by_date, regime_source_status = _load_regime_by_date(Path(input_zip))
    regime_rows, missing_regime_periods = _regime_rows(buffered_periods, regime_by_date)
    regime_fields = (
        "model", "regime", "period_count", "net_total_return",
        "benchmark_total_return", "relative_total_return",
        "average_net_excess_return", "positive_net_excess_ratio",
        "mean_turnover", "actionable",
    )
    _write_csv(output / "regime_diagnostic.csv", regime_rows, regime_fields)
    regime_status = (
        "REFERENCE_ONLY"
        if regime_source_status == "PASS" and missing_regime_periods == 0
        else "INCOMPLETE_FAIL_CLOSED"
    )

    summary_path = output / "model_lab_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    summary["base_upgrade_schema_version"] = v3.SCHEMA_VERSION
    summary["upgrade_schema_version"] = SCHEMA_VERSION
    summary["turnover_buffer_diagnostic"] = {
        "status": "REFERENCE_ONLY",
        "policy": "retain_prior_holding_while_rank_lte_top_k_plus_buffer",
        "top_k": top_k,
        "hold_buffer": hold_buffer,
        "buffer_ratio": hold_buffer / top_k,
        "predeclared_not_oos_optimized": True,
        "selection_uses_realized_returns": False,
        "research_gate_unchanged": True,
        "actionable": False,
        "files": [
            "turnover_buffer_diagnostic.csv",
            "turnover_buffer_periods.csv",
        ],
    }
    summary["regime_diagnostic_v4"] = {
        "status": regime_status,
        "regime_source": "feature_raw.vnindex_tren_ma250",
        "source_status": regime_source_status,
        "missing_period_rows": missing_regime_periods,
        "research_gate_unchanged": True,
        "actionable": False,
        "file": "regime_diagnostic.csv",
    }
    summary["sector_neutralization_contract_v4"] = {
        "status": "BLOCKED_MISSING_POINT_IN_TIME_SECTOR",
        "required_input": "sector_pit_by_signal_date_and_symbol",
        "ticker_name_inference_forbidden": True,
        "model_training_unchanged": True,
        "actionable": False,
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    with (output / "model_lab_report.txt").open("a", encoding="utf-8") as stream:
        stream.write("\nMODEL LAB UPGRADE V4\n")
        stream.write(
            f"Turnover buffer diagnostic: top_k={top_k}; hold_buffer={hold_buffer}; "
            "reference-only; research gate unchanged.\n"
        )
        stream.write(
            f"Regime diagnostic: {regime_status}; source={regime_source_status}; "
            f"missing_period_rows={missing_regime_periods}.\n"
        )
        stream.write(
            "Sector neutralization: blocked until point-in-time sector data is supplied; "
            "ticker inference is forbidden.\n"
        )
    quality_runner._rebuild_manifest_and_zip(output, summary)
    best_turnover_reduction = max(
        (
            float(row["turnover_reduction_vs_top_k"])
            for row in diagnostic_rows
        ),
        default=0.0,
    )
    return {
        "upgrade_schema_version": SCHEMA_VERSION,
        "turnover_buffer_status": "REFERENCE_ONLY",
        "turnover_buffer_models": len(diagnostic_rows),
        "best_turnover_reduction": best_turnover_reduction,
        "regime_diagnostic_status": regime_status,
        "sector_neutralization_status": "BLOCKED_MISSING_POINT_IN_TIME_SECTOR",
    }


def run_model_lab(**kwargs: object) -> dict[str, object]:
    top_k = int(kwargs.get("top_k", 10) or 10)
    raw_buffer = kwargs.pop("turnover_buffer", None)
    hold_buffer = (
        max(1, int(top_k * DEFAULT_BUFFER_RATIO))
        if raw_buffer is None
        else int(raw_buffer)
    )
    kwargs.setdefault("sell_tax_bps", DEFAULT_SELL_TAX_BPS)
    output_dir = Path(str(kwargs["output_dir"]))
    input_zip = Path(str(kwargs["input_zip"]))
    result = v3.run_model_lab(**kwargs)
    diagnostics = publish_v4_diagnostics(
        output_dir=output_dir,
        input_zip=input_zip,
        top_k=top_k,
        hold_buffer=hold_buffer,
        buy_fee_bps=float(kwargs.get("buy_fee_bps", 15.0) or 15.0),
        sell_fee_bps=float(kwargs.get("sell_fee_bps", 15.0) or 15.0),
        sell_tax_bps=float(kwargs.get("sell_tax_bps", DEFAULT_SELL_TAX_BPS) or 0.0),
        slippage_bps=float(kwargs.get("slippage_bps", 10.0) or 10.0),
    )
    return {**result, **diagnostics}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m he_thong_dinh_luong.model_lab")
    parser.add_argument("--input-zip", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS))
    parser.add_argument("--evaluation-months", type=int, default=24)
    parser.add_argument("--minimum-train-months", type=int, default=24)
    parser.add_argument("--inner-validation-months", type=int, default=3)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument(
        "--turnover-buffer",
        type=int,
        default=None,
        help="Retain prior holdings while rank <= top_k + buffer; default is 50% of top_k.",
    )
    parser.add_argument("--seed", type=int, default=20260731)
    parser.add_argument("--strict-dependencies", action="store_true")
    parser.add_argument("--buy-fee-bps", type=float, default=15.0)
    parser.add_argument("--sell-fee-bps", type=float, default=15.0)
    parser.add_argument("--sell-tax-bps", type=float, default=DEFAULT_SELL_TAX_BPS)
    parser.add_argument("--slippage-bps", type=float, default=10.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = run_model_lab(
        input_zip=args.input_zip,
        output_dir=args.output_dir,
        models=tuple(item.strip() for item in args.models.split(",") if item.strip()),
        evaluation_months=args.evaluation_months,
        minimum_train_months=args.minimum_train_months,
        inner_validation_months=args.inner_validation_months,
        top_k=args.top_k,
        turnover_buffer=args.turnover_buffer,
        seed=args.seed,
        strict_dependencies=args.strict_dependencies,
        buy_fee_bps=args.buy_fee_bps,
        sell_fee_bps=args.sell_fee_bps,
        sell_tax_bps=args.sell_tax_bps,
        slippage_bps=args.slippage_bps,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


__all__ = [
    "SCHEMA_VERSION",
    "DEFAULT_SELL_TAX_BPS",
    "DEFAULT_BUFFER_RATIO",
    "buffered_top_k_periods",
    "publish_v4_diagnostics",
    "run_model_lab",
    "main",
]
