"""V40 robustness gate for the V39 research-only cash ledger.

The module validates a V39 analysis bundle, measures statistical and economic
robustness, and freezes a 12-period shadow-paper protocol. It never upgrades
research evidence to live-capital approval.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
from io import StringIO
import json
import math
from pathlib import Path
import random
from statistics import fmean
from typing import Mapping, Sequence
from zipfile import ZipFile

SCHEMA_VERSION = "vn_quant_v40_research_robustness_v1"
REPORT_FILE = "research_robustness_v40.json"
SCORECARD_FILE = "strategy_scorecard_v40.csv"
YEARLY_FILE = "yearly_stability_v40.csv"
INFLUENCE_FILE = "period_influence_v40.csv"
DECISION_FILE = "research_gate_decision_v40.json"
PROTOCOL_FILE = "shadow_paper_protocol_v40.json"
MANIFEST_FILE = "manifest_v40.json"
README_FILE = "README_FIRST.txt"
CONCLUSION_FILE = "V40_CONCLUSION.txt"

REQUIRED = {
    "manifest_v39.json",
    "research_ledger_assumptions_v39.json",
    "research_ledger_periods_v39.csv",
    "research_ledger_report_v39.json",
    "research_ledger_summary_v39.csv",
}
PRIMARY = "FROZEN_SELECTION_FULLY_INVESTED"
CHALLENGER = "MVP_REGIME_CASH_OVERLAY_DIAGNOSTIC"


def _sha_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _sha_file(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_csv_bytes(data: bytes) -> list[dict[str, str]]:
    with StringIO(data.decode("utf-8-sig"), newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]], fields: Sequence[str]) -> None:
    with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _write_json(path: Path, value: object) -> None:
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _load_v39(path: Path) -> dict[str, object]:
    source = Path(path).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"V40_V39_BUNDLE_MISSING:{source}")
    with ZipFile(source) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"V40_V39_ZIP_CRC_FAILED:{bad}")
        names = set(archive.namelist())
        missing = sorted(REQUIRED - names)
        if missing:
            raise ValueError("V40_V39_REQUIRED_MISSING:" + "|".join(missing))
        manifest = json.loads(archive.read("manifest_v39.json").decode("utf-8-sig"))
        if not isinstance(manifest, Mapping):
            raise ValueError("V40_V39_MANIFEST_NOT_OBJECT")
        listed = manifest.get("files")
        if not isinstance(listed, list):
            raise ValueError("V40_V39_MANIFEST_FILES_INVALID")
        for row in listed:
            if not isinstance(row, Mapping):
                raise ValueError("V40_V39_MANIFEST_ROW_INVALID")
            name = str(row.get("path") or "")
            if name not in names:
                raise ValueError(f"V40_V39_MANIFEST_MEMBER_MISSING:{name}")
            payload = archive.read(name)
            if len(payload) != int(row.get("size_bytes") or -1):
                raise ValueError(f"V40_V39_MANIFEST_SIZE_MISMATCH:{name}")
            if _sha_bytes(payload) != str(row.get("sha256") or ""):
                raise ValueError(f"V40_V39_MANIFEST_HASH_MISMATCH:{name}")
        periods = _read_csv_bytes(archive.read("research_ledger_periods_v39.csv"))
        summary = _read_csv_bytes(archive.read("research_ledger_summary_v39.csv"))
        assumptions = json.loads(archive.read("research_ledger_assumptions_v39.json").decode("utf-8-sig"))
        report = json.loads(archive.read("research_ledger_report_v39.json").decode("utf-8-sig"))
    if not isinstance(assumptions, Mapping) or not isinstance(report, Mapping):
        raise ValueError("V40_V39_JSON_NOT_OBJECT")
    if assumptions.get("status") != "RESEARCH_ONLY_COMPUTED":
        raise ValueError("V40_V39_NOT_RESEARCH_ONLY_COMPUTED")
    return {
        "source": str(source),
        "source_sha256": _sha_file(source),
        "periods": periods,
        "summary": summary,
        "assumptions": dict(assumptions),
        "report": dict(report),
    }


def _number(row: Mapping[str, object], key: str) -> float:
    try:
        value = float(row.get(key) or 0.0)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"V40_NUMBER_INVALID:{key}") from exc
    if not math.isfinite(value):
        raise ValueError(f"V40_NUMBER_NONFINITE:{key}")
    return value


def _compound(values: Sequence[float]) -> float:
    return math.prod(1.0 + value for value in values) - 1.0


def _newey_west_t(values: Sequence[float], lag: int = 3) -> tuple[float, float, float]:
    data = [float(value) for value in values]
    if len(data) < lag + 3:
        raise ValueError("V40_NEWEY_WEST_SAMPLE_TOO_SMALL")
    mean = fmean(data)
    residual = [value - mean for value in data]
    n = len(data)
    variance = sum(value * value for value in residual) / n
    for offset in range(1, lag + 1):
        covariance = sum(
            residual[index] * residual[index - offset]
            for index in range(offset, n)
        ) / n
        weight = 1.0 - offset / (lag + 1.0)
        variance += 2.0 * weight * covariance
    standard_error = math.sqrt(max(variance, 0.0) / n)
    t_stat = mean / standard_error if standard_error > 0.0 else 0.0
    return t_stat, mean, standard_error


def _block_bootstrap(
    strategy_returns: Sequence[float],
    benchmark_returns: Sequence[float],
    *,
    block_length: int,
    draws: int,
    seed: int,
) -> dict[str, float]:
    strategy = list(strategy_returns)
    benchmark = list(benchmark_returns)
    if len(strategy) != len(benchmark) or len(strategy) < block_length:
        raise ValueError("V40_BOOTSTRAP_INPUT_INVALID")
    rng = random.Random(seed)
    starts = list(range(0, len(strategy) - block_length + 1))
    outperform = 0
    positive = 0
    relative: list[float] = []
    for _ in range(draws):
        indices: list[int] = []
        while len(indices) < len(strategy):
            start = rng.choice(starts)
            indices.extend(range(start, start + block_length))
        indices = indices[: len(strategy)]
        strategy_total = _compound([strategy[index] for index in indices])
        benchmark_total = _compound([benchmark[index] for index in indices])
        outperform += int(strategy_total > benchmark_total)
        positive += int(strategy_total > 0.0)
        relative.append((1.0 + strategy_total) / (1.0 + benchmark_total) - 1.0)
    relative.sort()

    def quantile(probability: float) -> float:
        position = probability * (len(relative) - 1)
        lower = int(math.floor(position))
        upper = int(math.ceil(position))
        if lower == upper:
            return relative[lower]
        weight = position - lower
        return relative[lower] * (1.0 - weight) + relative[upper] * weight

    return {
        "draws": draws,
        "block_length": block_length,
        "probability_outperform_benchmark": outperform / draws,
        "probability_positive_total_return": positive / draws,
        "relative_return_p05": quantile(0.05),
        "relative_return_median": quantile(0.50),
        "relative_return_p95": quantile(0.95),
    }


def _leave_one_out(strategy_returns: Sequence[float], benchmark_returns: Sequence[float]) -> dict[str, object]:
    relative: list[float] = []
    totals: list[float] = []
    for omitted in range(len(strategy_returns)):
        strategy_total = _compound([
            value for index, value in enumerate(strategy_returns) if index != omitted
        ])
        benchmark_total = _compound([
            value for index, value in enumerate(benchmark_returns) if index != omitted
        ])
        relative.append((1.0 + strategy_total) / (1.0 + benchmark_total) - 1.0)
        totals.append(strategy_total)
    return {
        "all_leave_one_period_out_outperform": all(value > 0.0 for value in relative),
        "minimum_leave_one_period_out_relative_return": min(relative),
        "maximum_leave_one_period_out_relative_return": max(relative),
        "minimum_leave_one_period_out_total_return": min(totals),
    }


def _year_rows(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[Mapping[str, object]]] = {}
    for row in rows:
        year = str(row.get("signal_date") or "")[:4]
        grouped.setdefault(year, []).append(row)
    output: list[dict[str, object]] = []
    for year, group in sorted(grouped.items()):
        strategy_total = _compound([_number(row, "period_net_return") for row in group])
        benchmark_total = _compound([_number(row, "benchmark_return") for row in group])
        relative = (1.0 + strategy_total) / (1.0 + benchmark_total) - 1.0
        output.append({
            "year": year,
            "period_count": len(group),
            "strategy_total_return": strategy_total,
            "benchmark_total_return": benchmark_total,
            "relative_total_return": relative,
            "outperformed": relative > 0.0,
        })
    return output


def _influence_rows(rows: Sequence[Mapping[str, object]], strategy: str, scenario: str) -> list[dict[str, object]]:
    log_values = [math.log1p(_number(row, "period_net_return")) for row in rows]
    denominator = sum(abs(value) for value in log_values)
    output: list[dict[str, object]] = []
    strategy_returns = [_number(row, "period_net_return") for row in rows]
    benchmark_returns = [_number(row, "benchmark_return") for row in rows]
    for index, row in enumerate(rows):
        without_strategy = _compound([
            value for position, value in enumerate(strategy_returns) if position != index
        ])
        without_benchmark = _compound([
            value for position, value in enumerate(benchmark_returns) if position != index
        ])
        output.append({
            "strategy": strategy,
            "scenario": scenario,
            "signal_date": row.get("signal_date", ""),
            "period_net_return": strategy_returns[index],
            "benchmark_return": benchmark_returns[index],
            "net_excess_return": _number(row, "net_excess_return"),
            "absolute_log_return_share": abs(log_values[index]) / denominator if denominator else 0.0,
            "leave_one_out_relative_return": (
                (1.0 + without_strategy) / (1.0 + without_benchmark) - 1.0
            ),
        })
    output.sort(key=lambda row: float(row["absolute_log_return_share"]), reverse=True)
    return output


def _summary_index(rows: Sequence[Mapping[str, object]]) -> dict[tuple[str, str], Mapping[str, object]]:
    result: dict[tuple[str, str], Mapping[str, object]] = {}
    for row in rows:
        key = (str(row.get("strategy") or ""), str(row.get("scenario") or ""))
        if key in result:
            raise ValueError(f"V40_DUPLICATE_SUMMARY:{key}")
        result[key] = row
    return result


def _break_even_slippage(summary: Mapping[tuple[str, str], Mapping[str, object]], strategy: str) -> float:
    base = summary[(strategy, "BASE")]
    stress = summary[(strategy, "STRESS")]
    base_return = _number(base, "net_total_return")
    stress_return = _number(stress, "net_total_return")
    benchmark = _number(base, "benchmark_total_return")
    slope = (stress_return - base_return) / 5.0
    if slope >= 0.0:
        return math.inf
    return 5.0 + (benchmark - base_return) / slope


def analyze_v40(
    *,
    v39_analysis_zip: Path,
    output_dir: Path,
    bootstrap_draws: int = 20_000,
    bootstrap_seed: int = 2908,
) -> dict[str, object]:
    if bootstrap_draws < 1_000:
        raise ValueError("V40_BOOTSTRAP_DRAWS_TOO_SMALL")
    source = _load_v39(v39_analysis_zip)
    output = Path(output_dir).resolve()
    if output.exists():
        raise FileExistsError(f"V40_OUTPUT_EXISTS:{output}")
    output.mkdir(parents=True)

    periods = list(source["periods"])
    summary_rows = list(source["summary"])
    summary = _summary_index(summary_rows)
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in periods:
        key = (str(row.get("strategy") or ""), str(row.get("scenario") or ""))
        grouped.setdefault(key, []).append(dict(row))
    for rows in grouped.values():
        rows.sort(key=lambda row: str(row.get("signal_date") or ""))

    strategies = sorted({key[0] for key in grouped})
    scorecards: list[dict[str, object]] = []
    yearly_output: list[dict[str, object]] = []
    influence_output: list[dict[str, object]] = []
    detailed: dict[str, object] = {}

    for strategy in strategies:
        if (strategy, "BASE") not in grouped or (strategy, "STRESS") not in grouped:
            raise ValueError(f"V40_SCENARIO_MISSING:{strategy}")
        strategy_detail: dict[str, object] = {}
        for scenario in ("BASE", "STRESS"):
            rows = grouped[(strategy, scenario)]
            strategy_returns = [_number(row, "period_net_return") for row in rows]
            benchmark_returns = [_number(row, "benchmark_return") for row in rows]
            excess_returns = [_number(row, "net_excess_return") for row in rows]
            t_stat, mean_excess, standard_error = _newey_west_t(excess_returns)
            bootstrap = _block_bootstrap(
                strategy_returns,
                benchmark_returns,
                block_length=3,
                draws=bootstrap_draws,
                seed=bootstrap_seed + (0 if scenario == "BASE" else 1),
            )
            leave_one_out = _leave_one_out(strategy_returns, benchmark_returns)
            year_rows = _year_rows(rows)
            influence = _influence_rows(rows, strategy, scenario)
            yearly_output.extend({
                "strategy": strategy,
                "scenario": scenario,
                **row,
            } for row in year_rows)
            influence_output.extend(influence)
            strategy_detail[scenario.lower()] = {
                "period_count": len(rows),
                "newey_west_lag": 3,
                "newey_west_t_stat": t_stat,
                "mean_period_excess_return": mean_excess,
                "newey_west_standard_error": standard_error,
                "bootstrap": bootstrap,
                "leave_one_out": leave_one_out,
                "positive_year_count": sum(bool(row["outperformed"]) for row in year_rows),
                "year_count": len(year_rows),
                "max_absolute_log_return_share": max(
                    float(row["absolute_log_return_share"]) for row in influence
                ),
                "most_influential_signal_date": influence[0]["signal_date"],
            }

        break_even = _break_even_slippage(summary, strategy)
        base = strategy_detail["base"]
        stress = strategy_detail["stress"]
        base_summary = summary[(strategy, "BASE")]
        stress_summary = summary[(strategy, "STRESS")]
        gates = {
            "base_cumulative_outperformance": _number(base_summary, "relative_total_return") > 0.0,
            "stress_cumulative_outperformance": _number(stress_summary, "relative_total_return") > 0.0,
            "base_bootstrap_probability_at_least_75pct": (
                base["bootstrap"]["probability_outperform_benchmark"] >= 0.75
            ),
            "stress_bootstrap_probability_at_least_75pct": (
                stress["bootstrap"]["probability_outperform_benchmark"] >= 0.75
            ),
            "base_newey_west_t_at_least_1": base["newey_west_t_stat"] >= 1.0,
            "stress_newey_west_t_at_least_1": stress["newey_west_t_stat"] >= 1.0,
            "positive_relative_years_at_least_3": base["positive_year_count"] >= 3,
            "leave_one_period_out_always_outperforms": (
                base["leave_one_out"]["all_leave_one_period_out_outperform"]
                and stress["leave_one_out"]["all_leave_one_period_out_outperform"]
            ),
            "base_max_drawdown_within_25pct": _number(base_summary, "max_drawdown") >= -0.25,
            "break_even_slippage_at_least_25bps": break_even >= 25.0,
            "single_period_log_share_below_15pct": (
                base["max_absolute_log_return_share"] <= 0.15
                and stress["max_absolute_log_return_share"] <= 0.15
            ),
        }
        passed = sum(gates.values())
        total = len(gates)
        approved = all(gates.values())
        recommendation = (
            "APPROVE_AS_PRIMARY_SHADOW_PAPER_RESEARCH"
            if approved and strategy == PRIMARY
            else "APPROVE_AS_SHADOW_PAPER_CHALLENGER"
            if approved
            else "RETAIN_AS_RESEARCH_CHALLENGER_NOT_PRIMARY"
        )
        scorecards.append({
            "strategy": strategy,
            "gate_pass_count": passed,
            "gate_total_count": total,
            "all_gates_passed": approved,
            "recommendation": recommendation,
            "base_net_total_return": _number(base_summary, "net_total_return"),
            "stress_net_total_return": _number(stress_summary, "net_total_return"),
            "benchmark_total_return": _number(base_summary, "benchmark_total_return"),
            "base_relative_total_return": _number(base_summary, "relative_total_return"),
            "stress_relative_total_return": _number(stress_summary, "relative_total_return"),
            "base_max_drawdown": _number(base_summary, "max_drawdown"),
            "stress_max_drawdown": _number(stress_summary, "max_drawdown"),
            "base_bootstrap_probability_outperform": base["bootstrap"]["probability_outperform_benchmark"],
            "stress_bootstrap_probability_outperform": stress["bootstrap"]["probability_outperform_benchmark"],
            "base_newey_west_t_stat": base["newey_west_t_stat"],
            "stress_newey_west_t_stat": stress["newey_west_t_stat"],
            "positive_relative_year_count": base["positive_year_count"],
            "year_count": base["year_count"],
            "break_even_slippage_bps_each_side_linear": break_even,
            "minimum_leave_one_out_relative_return_base": base["leave_one_out"]["minimum_leave_one_period_out_relative_return"],
            "minimum_leave_one_out_relative_return_stress": stress["leave_one_out"]["minimum_leave_one_period_out_relative_return"],
            "max_absolute_log_return_share_base": base["max_absolute_log_return_share"],
        })
        strategy_detail["break_even_slippage_bps_each_side_linear"] = break_even
        strategy_detail["gates"] = gates
        strategy_detail["gate_pass_count"] = passed
        strategy_detail["gate_total_count"] = total
        strategy_detail["recommendation"] = recommendation
        detailed[strategy] = strategy_detail

    primary = next(row for row in scorecards if row["strategy"] == PRIMARY)
    challenger = next((row for row in scorecards if row["strategy"] == CHALLENGER), None)
    research_approved = bool(primary["all_gates_passed"])
    decision = {
        "schema_version": "vn_quant_v40_research_gate_decision_v1",
        "status": "SHADOW_PAPER_RESEARCH_APPROVED" if research_approved else "RESEARCH_GATE_NOT_PASSED",
        "primary_strategy": PRIMARY,
        "primary_recommendation": primary["recommendation"],
        "challenger_strategy": CHALLENGER if challenger else "",
        "challenger_recommendation": challenger["recommendation"] if challenger else "",
        "tuning_allowed": False,
        "historical_policy_refit_allowed": False,
        "shadow_paper_orders_only": True,
        "broker_order_submission_allowed": False,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
        "strict_data_blockers_preserved": list(source["report"].get("strict_blockers") or []),
    }
    protocol = {
        "schema_version": "vn_quant_v40_shadow_paper_protocol_v1",
        "status": "FROZEN_FOR_FORWARD_OBSERVATION" if research_approved else "NOT_ACTIVATED",
        "policy_id": source["assumptions"].get("policy_id"),
        "primary_strategy": PRIMARY,
        "challenger_strategy": CHALLENGER,
        "observation_count_required": 12,
        "cadence": "MONTHLY",
        "first_eligible_signal": "FIRST_SIGNAL_AFTER_2026-07-31",
        "selection_breadth": 10,
        "fixed_voluntary_replacement_cap": 3,
        "allocation": "INVERSE_VOLATILITY_60_SESSION",
        "max_symbol_weight": 0.15,
        "primary_budget": 1.0,
        "challenger_regime_budgets": {"risk_on": 0.80, "risk_off": 0.25},
        "execution_assumption": "NEXT_MARKET_DAY_OPEN",
        "lot_size": 100,
        "base_slippage_bps_each_side": 5.0,
        "stress_slippage_bps_each_side": 10.0,
        "record_each_period": [
            "signal_snapshot_hash",
            "selected_symbols",
            "target_weights",
            "paper_quantities",
            "reference_execution_prices",
            "fees_tax_slippage",
            "turnover",
            "portfolio_return",
            "vnindex_return",
            "drawdown",
            "data_quality_failures",
            "operational_failures",
        ],
        "forward_success_conditions": {
            "completed_periods": 12,
            "no_policy_refit": True,
            "stress_net_return_not_worse_than_benchmark": True,
            "data_quality_fail_closed": True,
            "account_sync_verified": True,
            "position_reconciliation_verified_before_any_live_review": True,
        },
        "live_promotion_automatic": False,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": decision["status"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_v39_analysis_zip": source["source"],
        "source_v39_analysis_sha256": source["source_sha256"],
        "bootstrap_draws": bootstrap_draws,
        "bootstrap_seed": bootstrap_seed,
        "gate_definition": {
            "bootstrap_probability_threshold": 0.75,
            "newey_west_t_threshold": 1.0,
            "minimum_positive_relative_years": 3,
            "maximum_drawdown": -0.25,
            "minimum_break_even_slippage_bps_each_side": 25.0,
            "maximum_single_period_absolute_log_share": 0.15,
        },
        "strategies": detailed,
        "decision": decision,
        "strict_exact_cash_ledger": False,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }

    _write_json(output / REPORT_FILE, report)
    _write_csv(
        output / SCORECARD_FILE,
        scorecards,
        (
            "strategy", "gate_pass_count", "gate_total_count", "all_gates_passed",
            "recommendation", "base_net_total_return", "stress_net_total_return",
            "benchmark_total_return", "base_relative_total_return",
            "stress_relative_total_return", "base_max_drawdown", "stress_max_drawdown",
            "base_bootstrap_probability_outperform",
            "stress_bootstrap_probability_outperform", "base_newey_west_t_stat",
            "stress_newey_west_t_stat", "positive_relative_year_count", "year_count",
            "break_even_slippage_bps_each_side_linear",
            "minimum_leave_one_out_relative_return_base",
            "minimum_leave_one_out_relative_return_stress",
            "max_absolute_log_return_share_base",
        ),
    )
    _write_csv(
        output / YEARLY_FILE,
        yearly_output,
        (
            "strategy", "scenario", "year", "period_count", "strategy_total_return",
            "benchmark_total_return", "relative_total_return", "outperformed",
        ),
    )
    _write_csv(
        output / INFLUENCE_FILE,
        influence_output,
        (
            "strategy", "scenario", "signal_date", "period_net_return",
            "benchmark_return", "net_excess_return", "absolute_log_return_share",
            "leave_one_out_relative_return",
        ),
    )
    _write_json(output / DECISION_FILE, decision)
    _write_json(output / PROTOCOL_FILE, protocol)
    (output / README_FILE).write_text(
        "V40 RESEARCH ROBUSTNESS\n\n"
        "This bundle validates the V39 research-only cash ledger and freezes a "
        "12-period shadow-paper protocol. It does not resolve sector, corporate "
        "action, price-basis or broker reconciliation blockers. It does not "
        "approve live capital or automatic orders.\n",
        encoding="utf-8",
    )
    challenger_text = (
        str(challenger["recommendation"]) if challenger is not None else "NOT_AVAILABLE"
    )
    (output / CONCLUSION_FILE).write_text(
        "V40 CONCLUSION\n\n"
        f"STATUS={decision['status']}\n"
        f"PRIMARY={PRIMARY}\n"
        f"PRIMARY_GATE={primary['gate_pass_count']}/{primary['gate_total_count']}\n"
        f"PRIMARY_RECOMMENDATION={primary['recommendation']}\n"
        f"CHALLENGER={CHALLENGER}\n"
        f"CHALLENGER_RECOMMENDATION={challenger_text}\n"
        "NEXT_STEP=12_MONTH_FIXED_POLICY_SHADOW_PAPER\n"
        "TUNING_ALLOWED=false\n"
        "BROKER_ORDER_SUBMISSION_ALLOWED=false\n"
        "LIVE_CAPITAL_APPROVED=false\n"
        "AUTOMATIC_LIVE_ORDERS_ALLOWED=false\n",
        encoding="utf-8",
    )
    files = []
    for path in sorted(output.iterdir()):
        if path.is_file() and path.name != MANIFEST_FILE:
            files.append({
                "path": path.name,
                "sha256": _sha_file(path),
                "size_bytes": path.stat().st_size,
            })
    manifest = {
        "schema_version": "vn_quant_v40_research_robustness_manifest_v1",
        "files": files,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }
    _write_json(output / MANIFEST_FILE, manifest)
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run V40 research robustness gate")
    parser.add_argument("--v39-analysis-zip", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--bootstrap-draws", type=int, default=20_000)
    parser.add_argument("--bootstrap-seed", type=int, default=2908)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = analyze_v40(
        v39_analysis_zip=args.v39_analysis_zip,
        output_dir=args.output_dir,
        bootstrap_draws=args.bootstrap_draws,
        bootstrap_seed=args.bootstrap_seed,
    )
    print(json.dumps({
        "status": report["status"],
        "report": str(Path(args.output_dir) / REPORT_FILE),
    }, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
