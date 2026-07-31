"""Leakage-safe walk-forward evaluation and label-horizon portfolio backtest.

This module is dependency-light.  Optional ML libraries live in
``model_lab_models`` so CI can validate the research contract without installing
large workstation dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import sqrt
from statistics import fmean, pstdev
from typing import Mapping, Sequence

from .nghien_cuu_moc_4.du_doan_tien_phuong_contract import Metrics, Row
from .nghien_cuu_moc_4.du_doan_tien_phuong_features import _metrics, _rank

SCHEMA_VERSION = "vn_quant_model_lab_v1"
ENSEMBLE_MODEL = "online_rank_ensemble_v1"
BASE_MODELS = (
    "momentum_baseline",
    "robust_technical_ensemble_v1",
    "ridge_ranker",
    "hist_gradient_boosting_ranker",
    "lightgbm_ranker",
    "xgboost_ranker",
    "torch_pairwise_mlp",
)
DEFAULT_MODELS = BASE_MODELS + (ENSEMBLE_MODEL,)


@dataclass(frozen=True)
class Outcome:
    day: date
    symbol: str
    label_end: date
    stock_return: float
    benchmark_return: float
    relative_return: float


@dataclass(frozen=True)
class WalkForwardFold:
    fold_id: str
    test_day: date
    train_rows: tuple[Row, ...]
    validation_rows: tuple[Row, ...]
    test_rows: tuple[Row, ...]


@dataclass(frozen=True)
class BacktestConfig:
    top_k: int = 10
    periods_per_year: int = 12
    buy_fee_bps: float = 15.0
    sell_fee_bps: float = 15.0
    sell_tax_bps: float = 100.0
    slippage_bps: float = 10.0

    def __post_init__(self) -> None:
        if self.top_k <= 0 or self.periods_per_year <= 0:
            raise ValueError("MODEL_LAB_BACKTEST_POSITIVE_INTS_REQUIRED")
        for name in ("buy_fee_bps", "sell_fee_bps", "sell_tax_bps", "slippage_bps"):
            value = float(getattr(self, name))
            if value < 0.0 or value >= 10_000.0:
                raise ValueError(f"MODEL_LAB_INVALID_BPS:{name}")

    @property
    def entry_cost_rate(self) -> float:
        return (self.buy_fee_bps + self.slippage_bps) / 10_000.0

    @property
    def rebalance_round_trip_rate(self) -> float:
        return (
            self.buy_fee_bps
            + self.sell_fee_bps
            + self.sell_tax_bps
            + 2.0 * self.slippage_bps
        ) / 10_000.0


@dataclass(frozen=True)
class ModelEvaluation:
    model: str
    status: str
    metrics: Mapping[str, object]
    backtest: Mapping[str, object]
    gate: Mapping[str, bool]
    error: str | None = None


def build_walk_forward_folds(
    rows: Sequence[Row],
    *,
    evaluation_months: int,
    minimum_train_months: int = 24,
    inner_validation_months: int = 3,
) -> list[WalkForwardFold]:
    """Create expanding folds with label-end purge.

    A row may enter train/validation only when its label is fully known before
    the test date.  Validation is the latest eligible block and is never the
    current test date.
    """
    if evaluation_months < 3:
        raise ValueError("MODEL_LAB_EVALUATION_MONTHS_TOO_SMALL")
    if minimum_train_months < 12:
        raise ValueError("MODEL_LAB_MINIMUM_TRAIN_MONTHS_TOO_SMALL")
    if inner_validation_months < 1:
        raise ValueError("MODEL_LAB_INNER_VALIDATION_MONTHS_TOO_SMALL")
    dates = sorted({row.ngay for row in rows})
    if len(dates) <= minimum_train_months:
        raise ValueError("MODEL_LAB_INSUFFICIENT_DATES")
    candidate_test_dates = dates[-min(evaluation_months, len(dates)):]
    folds: list[WalkForwardFold] = []
    for test_day in candidate_test_dates:
        eligible = [
            row for row in rows
            if row.ngay < test_day and row.label_end is not None and row.label_end < test_day
        ]
        eligible_dates = sorted({row.ngay for row in eligible})
        if len(eligible_dates) < minimum_train_months + inner_validation_months:
            continue
        validation_dates = set(eligible_dates[-inner_validation_months:])
        validation_start = min(validation_dates)
        train = tuple(
            row for row in eligible
            if row.ngay not in validation_dates
            and row.label_end is not None
            and row.label_end < validation_start
        )
        validation = tuple(row for row in eligible if row.ngay in validation_dates)
        test = tuple(row for row in rows if row.ngay == test_day)
        if not train or not validation or not test:
            continue
        folds.append(WalkForwardFold(
            fold_id=f"wf_{test_day.isoformat()}",
            test_day=test_day,
            train_rows=train,
            validation_rows=validation,
            test_rows=test,
        ))
    if len(folds) < 3:
        raise ValueError("MODEL_LAB_TOO_FEW_VALID_FOLDS")
    return folds


def model_rank_metrics(rows: Sequence[Row], scores: Sequence[float], top_k: int) -> dict[str, object]:
    base: Metrics = _metrics(rows, scores, top_k)
    by_day: dict[date, list[int]] = {}
    for index, row in enumerate(rows):
        by_day.setdefault(row.ngay, []).append(index)
    daily_ic: list[float] = []
    daily_returns: list[float] = []
    for day in sorted(by_day):
        indexes = by_day[day]
        daily_scores = [float(scores[index]) for index in indexes]
        daily_targets = [float(rows[index].relative_return or 0.0) for index in indexes]
        rank_score = _rank(daily_scores)
        rank_target = _rank(daily_targets)
        mean_left = fmean(rank_score)
        mean_right = fmean(rank_target)
        numerator = sum((x - mean_left) * (y - mean_right) for x, y in zip(rank_score, rank_target))
        denominator = sqrt(
            sum((x - mean_left) ** 2 for x in rank_score)
            * sum((y - mean_right) ** 2 for y in rank_target)
        )
        daily_ic.append(numerator / denominator if denominator > 0 else 0.0)
        selected = sorted(indexes, key=lambda index: (-float(scores[index]), rows[index].ma))[:top_k]
        daily_returns.append(fmean(float(rows[index].relative_return or 0.0) for index in selected))
    result = dict(base.as_dict())
    result.update({
        "median_rank_ic": sorted(daily_ic)[len(daily_ic) // 2] if daily_ic else 0.0,
        "rank_ic_std": pstdev(daily_ic) if len(daily_ic) > 1 else 0.0,
        "positive_rank_ic_ratio": fmean(1.0 if value > 0.0 else 0.0 for value in daily_ic) if daily_ic else 0.0,
        "positive_top_k_return_ratio": fmean(1.0 if value > 0.0 else 0.0 for value in daily_returns) if daily_returns else 0.0,
    })
    return result


def _drawdown(nav: Sequence[float]) -> float:
    peak = 0.0
    worst = 0.0
    for value in nav:
        peak = max(peak, value)
        if peak > 0.0:
            worst = min(worst, value / peak - 1.0)
    return worst


def backtest_top_k(
    *,
    model: str,
    rows: Sequence[Row],
    scores: Sequence[float],
    outcomes: Mapping[tuple[date, str], Outcome],
    config: BacktestConfig,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    """Backtest non-overlapping monthly label horizons with explicit cost drag.

    This is not the execution engine: labels are close(T) to close(T+H).  The
    artifact therefore names this a label-horizon backtest and never claims T+1
    fill fidelity.
    """
    if len(rows) != len(scores):
        raise ValueError("MODEL_LAB_BACKTEST_LENGTH_MISMATCH")
    by_day: dict[date, list[int]] = {}
    for index, row in enumerate(rows):
        by_day.setdefault(row.ngay, []).append(index)
    previous: set[str] = set()
    nav = 1.0
    benchmark_nav = 1.0
    gross_nav = 1.0
    period_rows: list[dict[str, object]] = []
    nav_rows: list[dict[str, object]] = []
    net_returns: list[float] = []
    excess_returns: list[float] = []
    turnovers: list[float] = []
    total_cost = 0.0
    for period_index, day in enumerate(sorted(by_day)):
        indexes = by_day[day]
        selected_indexes = sorted(
            indexes,
            key=lambda index: (-float(scores[index]), rows[index].ma),
        )[: min(config.top_k, len(indexes))]
        selected = {rows[index].ma for index in selected_indexes}
        selected_outcomes: list[Outcome] = []
        for index in selected_indexes:
            key = (rows[index].ngay, rows[index].ma)
            outcome = outcomes.get(key)
            if outcome is None:
                raise ValueError(f"MODEL_LAB_OUTCOME_MISSING:{key[0]}:{key[1]}")
            selected_outcomes.append(outcome)
        gross_return = fmean(item.stock_return for item in selected_outcomes)
        benchmark_return = fmean(item.benchmark_return for item in selected_outcomes)
        gross_excess = gross_return - benchmark_return
        turnover = 1.0 if not previous else 1.0 - len(selected & previous) / max(len(selected), 1)
        cost_rate = config.entry_cost_rate if period_index == 0 else turnover * config.rebalance_round_trip_rate
        net_return = gross_return - cost_rate
        net_excess = net_return - benchmark_return
        gross_nav *= max(1e-9, 1.0 + gross_return)
        nav *= max(1e-9, 1.0 + net_return)
        benchmark_nav *= max(1e-9, 1.0 + benchmark_return)
        total_cost += cost_rate
        net_returns.append(net_return)
        excess_returns.append(net_excess)
        turnovers.append(turnover)
        end_day = max(item.label_end for item in selected_outcomes)
        period_rows.append({
            "model": model,
            "signal_date": day.isoformat(),
            "label_end": end_day.isoformat(),
            "selected_symbols": "|".join(sorted(selected)),
            "gross_return": gross_return,
            "benchmark_return": benchmark_return,
            "gross_excess_return": gross_excess,
            "turnover": turnover,
            "estimated_cost_rate": cost_rate,
            "net_return": net_return,
            "net_excess_return": net_excess,
        })
        nav_rows.append({
            "model": model,
            "date": end_day.isoformat(),
            "net_nav": nav,
            "gross_nav": gross_nav,
            "benchmark_nav": benchmark_nav,
            "relative_nav": nav / benchmark_nav if benchmark_nav > 0 else 0.0,
        })
        previous = selected
    periods = len(net_returns)
    years = periods / config.periods_per_year if periods else 0.0
    cagr = nav ** (1.0 / years) - 1.0 if years > 0.0 and nav > 0.0 else 0.0
    volatility = pstdev(net_returns) * sqrt(config.periods_per_year) if len(net_returns) > 1 else 0.0
    mean_return = fmean(net_returns) if net_returns else 0.0
    sharpe = (
        mean_return / pstdev(net_returns) * sqrt(config.periods_per_year)
        if len(net_returns) > 1 and pstdev(net_returns) > 0.0 else 0.0
    )
    metrics = {
        "backtest_type": "monthly_label_horizon_close_to_close",
        "execution_engine_used": False,
        "period_count": periods,
        "total_return": nav - 1.0,
        "gross_total_return": gross_nav - 1.0,
        "benchmark_total_return": benchmark_nav - 1.0,
        "relative_total_return": nav / benchmark_nav - 1.0 if benchmark_nav > 0 else 0.0,
        "cagr": cagr,
        "annualized_volatility": volatility,
        "sharpe": sharpe,
        "max_drawdown": _drawdown([float(row["net_nav"]) for row in nav_rows]),
        "average_net_excess_return": fmean(excess_returns) if excess_returns else 0.0,
        "positive_net_excess_ratio": fmean(1.0 if value > 0 else 0.0 for value in excess_returns) if excess_returns else 0.0,
        "mean_turnover": fmean(turnovers) if turnovers else 0.0,
        "estimated_cost_drag_sum": total_cost,
        "cost_assumptions_bps": {
            "buy_fee": config.buy_fee_bps,
            "sell_fee": config.sell_fee_bps,
            "sell_tax": config.sell_tax_bps,
            "slippage_each_side": config.slippage_bps,
        },
    }
    return metrics, period_rows, nav_rows


def online_ensemble_weights(
    prior_ic: Mapping[str, Sequence[float]],
    available_models: Sequence[str],
    *,
    max_weight: float = 0.40,
) -> dict[str, float]:
    """Weights use only completed prior folds.

    Positive and stable IC is rewarded.  When no model has positive prior IC,
    weights are equal; no current-fold label is available to this function.
    """
    models = [name for name in available_models if name != ENSEMBLE_MODEL]
    if not models:
        raise ValueError("MODEL_LAB_ENSEMBLE_NO_BASE_MODELS")
    quality: dict[str, float] = {}
    for name in models:
        history = [float(value) for value in prior_ic.get(name, ())]
        if len(history) < 3:
            quality[name] = 0.0
            continue
        mean_ic = fmean(history)
        dispersion = pstdev(history) if len(history) > 1 else 0.0
        quality[name] = max(0.0, mean_ic) / max(0.02, dispersion)
    if sum(quality.values()) <= 0.0:
        return {name: 1.0 / len(models) for name in models}
    raw = {name: value / sum(quality.values()) for name, value in quality.items()}
    capped = {name: min(max_weight, value) for name, value in raw.items()}
    remaining = 1.0 - sum(capped.values())
    uncapped = [name for name in models if raw[name] < max_weight]
    while remaining > 1e-12 and uncapped:
        addition = remaining / len(uncapped)
        next_uncapped: list[str] = []
        for name in uncapped:
            room = max_weight - capped[name]
            applied = min(room, addition)
            capped[name] += applied
            remaining -= applied
            if capped[name] < max_weight - 1e-12:
                next_uncapped.append(name)
        if next_uncapped == uncapped and addition <= 1e-12:
            break
        uncapped = next_uncapped
    if remaining > 1e-9:
        # More models are required for a strict cap; distribute the residual so
        # the contract remains normalized and record the actual weights.
        for name in models:
            capped[name] += remaining / len(models)
        remaining = 0.0
    total = sum(capped.values())
    return {name: value / total for name, value in capped.items()}


def ensemble_scores(
    scores_by_model: Mapping[str, Sequence[float]],
    weights: Mapping[str, float],
) -> list[float]:
    names = [name for name in weights if name in scores_by_model]
    if not names:
        raise ValueError("MODEL_LAB_ENSEMBLE_SCORES_EMPTY")
    lengths = {len(scores_by_model[name]) for name in names}
    if len(lengths) != 1:
        raise ValueError("MODEL_LAB_ENSEMBLE_LENGTH_MISMATCH")
    ranked = {name: _rank([float(value) for value in scores_by_model[name]]) for name in names}
    total_weight = sum(float(weights[name]) for name in names)
    if total_weight <= 0.0:
        raise ValueError("MODEL_LAB_ENSEMBLE_WEIGHT_NONPOSITIVE")
    length = lengths.pop()
    return [
        sum(float(weights[name]) * ranked[name][index] for name in names) / total_weight
        for index in range(length)
    ]


def candidate_gate(
    candidate_metrics: Mapping[str, object],
    candidate_backtest: Mapping[str, object],
    baseline_metrics: Mapping[str, object],
    baseline_backtest: Mapping[str, object],
) -> dict[str, bool]:
    return {
        "enough_oos_periods": int(candidate_backtest.get("period_count", 0) or 0) >= 18,
        "rank_ic_positive": float(candidate_metrics.get("mean_rank_ic", 0.0) or 0.0) > 0.0,
        "rank_ic_stable": float(candidate_metrics.get("positive_rank_ic_ratio", 0.0) or 0.0) >= 0.55,
        "net_excess_positive": float(candidate_backtest.get("average_net_excess_return", 0.0) or 0.0) > 0.0,
        "relative_total_return_positive": float(candidate_backtest.get("relative_total_return", 0.0) or 0.0) > 0.0,
        "sharpe_positive": float(candidate_backtest.get("sharpe", 0.0) or 0.0) > 0.0,
        "beats_momentum_rank_ic": float(candidate_metrics.get("mean_rank_ic", 0.0) or 0.0) > float(baseline_metrics.get("mean_rank_ic", 0.0) or 0.0),
        "beats_momentum_net_excess": float(candidate_backtest.get("average_net_excess_return", 0.0) or 0.0) > float(baseline_backtest.get("average_net_excess_return", 0.0) or 0.0),
        "turnover_controlled": float(candidate_backtest.get("mean_turnover", 1.0) or 1.0) <= 0.60,
        "drawdown_not_materially_worse": float(candidate_backtest.get("max_drawdown", -1.0) or -1.0) >= float(baseline_backtest.get("max_drawdown", -1.0) or -1.0) - 0.05,
    }


def select_research_champion(evaluations: Mapping[str, ModelEvaluation]) -> tuple[str, str]:
    momentum = evaluations.get("momentum_baseline")
    if momentum is None or momentum.status != "SUCCESS":
        return "NO_MODEL_APPROVED", "MOMENTUM_BASELINE_MISSING"
    eligible: list[tuple[tuple[float, float, float, float], str]] = []
    for name, evaluation in evaluations.items():
        if name == "momentum_baseline" or evaluation.status != "SUCCESS":
            continue
        if all(evaluation.gate.values()):
            eligible.append((
                (
                    float(evaluation.backtest.get("relative_total_return", 0.0) or 0.0),
                    float(evaluation.metrics.get("mean_rank_ic", 0.0) or 0.0),
                    float(evaluation.backtest.get("sharpe", 0.0) or 0.0),
                    -float(evaluation.backtest.get("mean_turnover", 1.0) or 1.0),
                ),
                name,
            ))
    if eligible:
        eligible.sort(reverse=True)
        return eligible[0][1], "CHALLENGER_PASSED_ALL_GATES"
    baseline_ok = (
        float(momentum.metrics.get("mean_rank_ic", 0.0) or 0.0) > 0.0
        and float(momentum.backtest.get("average_net_excess_return", 0.0) or 0.0) > 0.0
        and int(momentum.backtest.get("period_count", 0) or 0) >= 18
    )
    return (
        ("momentum_baseline", "NO_CHALLENGER_PASSED;MOMENTUM_POSITIVE")
        if baseline_ok
        else ("NO_MODEL_APPROVED", "ALL_MODELS_FAILED_RESEARCH_GATE")
    )
