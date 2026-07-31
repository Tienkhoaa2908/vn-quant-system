"""Independent OOS diagnostics for technical ranking models.

The audit is intentionally lightweight and deterministic. Validation dates are the
monthly cross-sections already defined by the forward-prediction contract.
"""
from __future__ import annotations

from math import sqrt
from pathlib import Path
from statistics import fmean, median, pstdev
from typing import Mapping, Sequence

from .nghien_cuu_moc_4.du_doan_tien_phuong_contract import Row, _load_rows, _load_verified_input
from .nghien_cuu_moc_4.du_doan_tien_phuong_features import _rank, _split_history
from .portfolio_weighting import REFERENCE_MODEL, reference_scores


def _pearson(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    mean_left, mean_right = fmean(left), fmean(right)
    numerator = sum((x - mean_left) * (y - mean_right) for x, y in zip(left, right))
    denominator = sqrt(
        sum((x - mean_left) ** 2 for x in left)
        * sum((y - mean_right) ** 2 for y in right)
    )
    return numerator / denominator if denominator > 0 else 0.0


def _daily(rows: Sequence[Row], scores: Sequence[float], top_k: int) -> list[dict[str, object]]:
    if len(rows) != len(scores):
        raise ValueError("AUDIT_LENGTH_MISMATCH")
    by_day: dict[object, list[int]] = {}
    for index, row in enumerate(rows):
        if row.relative_return is None:
            raise ValueError("AUDIT_LABEL_REQUIRED")
        by_day.setdefault(row.ngay, []).append(index)
    output: list[dict[str, object]] = []
    previous: set[str] | None = None
    for day in sorted(by_day):
        indexes = by_day[day]
        selected_indexes = sorted(
            indexes,
            key=lambda index: (-float(scores[index]), rows[index].ma),
        )[: min(top_k, len(indexes))]
        selected = {rows[index].ma for index in selected_indexes}
        turnover = (
            0.0
            if previous is None
            else 1.0 - len(previous & selected) / max(min(top_k, len(selected)), 1)
        )
        targets = [float(rows[index].relative_return) for index in indexes]
        local_scores = [float(scores[index]) for index in indexes]
        selected_returns = [float(rows[index].relative_return) for index in selected_indexes]
        output.append({
            "signal_date": day.isoformat(),
            "rank_ic": _pearson(_rank(local_scores), _rank(targets)),
            "precision_at_k": fmean(1.0 if value > 0 else 0.0 for value in selected_returns),
            "top_k_relative_return": fmean(selected_returns),
            "set_turnover": turnover,
            "selected_symbols": sorted(selected),
        })
        previous = selected
    return output


def _aggregate(daily: Sequence[Mapping[str, object]], *, cost_bps: float) -> dict[str, object]:
    if not daily:
        raise ValueError("AUDIT_DAILY_EMPTY")
    rank_ic = [float(row["rank_ic"]) for row in daily]
    precision = [float(row["precision_at_k"]) for row in daily]
    relative = [float(row["top_k_relative_return"]) for row in daily]
    turnover = [float(row["set_turnover"]) for row in daily]
    # Round-trip cost sensitivity estimate: two trading legs times set turnover.
    after_cost = [
        value - 2.0 * turn * float(cost_bps) / 10_000.0
        for value, turn in zip(relative, turnover)
    ]
    return {
        "day_count": len(daily),
        "mean_rank_ic": fmean(rank_ic),
        "median_rank_ic": median(rank_ic),
        "rank_ic_std": pstdev(rank_ic) if len(rank_ic) > 1 else 0.0,
        "positive_rank_ic_ratio": fmean(1.0 if value > 0 else 0.0 for value in rank_ic),
        "precision_at_k": fmean(precision),
        "top_k_relative_return": fmean(relative),
        "positive_top_k_return_ratio": fmean(1.0 if value > 0 else 0.0 for value in relative),
        "mean_set_turnover": fmean(turnover),
        "cost_sensitivity_bps": float(cost_bps),
        "top_k_relative_return_after_cost_estimate": fmean(after_cost),
    }


def audit_prediction_input(
    input_zip: Path,
    *,
    validation_months: int = 12,
    top_k: int = 10,
    cost_bps: float = 35.0,
) -> dict[str, object]:
    blobs, manifest, input_sha = _load_verified_input(Path(input_zip))
    history, _, _ = _load_rows(blobs)
    _, validation, validation_start = _split_history(history, validation_months)
    momentum_scores = [row.features["dong_luong_12_1"] for row in validation]
    robust_scores, _, _ = reference_scores(validation)
    momentum_daily = _daily(validation, momentum_scores, top_k)
    robust_daily = _daily(validation, robust_scores, top_k)
    return {
        "schema_version": "model_quality_audit_v1",
        "validation_start": validation_start.isoformat(),
        "validation_months": validation_months,
        "top_k": top_k,
        "input_zip_sha256": input_sha,
        "input_manifest_schema": manifest.get("manifest_schema_version"),
        "momentum_validation": _aggregate(momentum_daily, cost_bps=cost_bps),
        "robust_reference_validation": _aggregate(robust_daily, cost_bps=cost_bps),
        "momentum_monthly_diagnostics": momentum_daily,
        "robust_reference_monthly_diagnostics": robust_daily,
        "reference_model": REFERENCE_MODEL,
        "technical_validation_only": True,
        "research_eligible": False,
    }
