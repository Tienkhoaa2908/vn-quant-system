"""Robust technical reference score and dynamic portfolio weighting.

The module is intentionally dependency-free. It does not claim alpha: the caller must
publish validation metrics and keep the champion gate fail-closed. The score is used to
make a technical ranking easier to interpret and to avoid equal-weight allocation.
"""
from __future__ import annotations

from collections import defaultdict
from math import sqrt
from statistics import fmean, pstdev
from typing import Mapping, Sequence

REFERENCE_MODEL = "robust_technical_ensemble_v1"
ALLOCATOR_MODEL = "conviction_inverse_volatility_v1"
COMPONENT_WEIGHTS: Mapping[str, float] = {
    "momentum_12_1": 0.28,
    "relative_strength_120": 0.22,
    "momentum_over_volatility": 0.18,
    "trend_structure": 0.12,
    "low_volatility": 0.10,
    "momentum_consistency": 0.10,
}


def average_percentile(values: Sequence[float]) -> list[float]:
    if not values:
        return []
    order = sorted(range(len(values)), key=lambda index: (float(values[index]), index))
    denominator = max(len(values) - 1, 1)
    output = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and float(values[order[end]]) == float(values[order[start]]):
            end += 1
        value = ((start + end - 1) / 2.0) / denominator
        for position in range(start, end):
            output[order[position]] = value
        start = end
    return output


def _feature(row: object, name: str, default: float = 0.0) -> float:
    features = getattr(row, "features", row)
    if not isinstance(features, Mapping):
        return default
    try:
        return float(features.get(name, default))
    except (TypeError, ValueError):
        return default


def _raw_components(row: object) -> dict[str, float]:
    momentum = _feature(row, "dong_luong_12_1")
    relative_strength = _feature(row, "suc_manh_tuong_doi_120")
    volatility = max(_feature(row, "bien_dong_60"), 1e-6)
    trend = fmean(
        _feature(row, name)
        for name in ("khoang_cach_ma60", "khoang_cach_ma120", "khoang_cach_ma250")
    )
    consistency = fmean(
        1.0 if _feature(row, name) > 0.0 else 0.0
        for name in ("loi_nhuan_20", "loi_nhuan_60", "loi_nhuan_120", "loi_nhuan_250")
    )
    return {
        "momentum_12_1": momentum,
        "relative_strength_120": relative_strength,
        "momentum_over_volatility": momentum / volatility,
        "trend_structure": trend,
        "low_volatility": -volatility,
        "momentum_consistency": consistency,
    }


def reference_scores(rows: Sequence[object]) -> tuple[list[float], list[dict[str, float]], list[float]]:
    """Return cross-sectional score, ranked components and agreement confidence.

    Ranking is performed independently for every signal date when rows expose ``ngay``;
    plain mappings without a date are treated as one cross-section.
    """
    if not rows:
        return [], [], []
    by_day: dict[object, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        by_day[getattr(row, "ngay", None)].append(index)
    scores = [0.0] * len(rows)
    ranked_components: list[dict[str, float]] = [{} for _ in rows]
    confidence = [0.0] * len(rows)
    for indexes in by_day.values():
        raw = {index: _raw_components(rows[index]) for index in indexes}
        for component in COMPONENT_WEIGHTS:
            percentiles = average_percentile([raw[index][component] for index in indexes])
            for local_index, row_index in enumerate(indexes):
                ranked_components[row_index][component] = percentiles[local_index]
        for row_index in indexes:
            component_values = ranked_components[row_index]
            scores[row_index] = sum(
                COMPONENT_WEIGHTS[name] * component_values[name]
                for name in COMPONENT_WEIGHTS
            )
            dispersion = pstdev(component_values.values()) if len(component_values) > 1 else 0.0
            # Agreement is highest when components point in the same direction.
            confidence[row_index] = max(0.0, min(1.0, 1.0 - dispersion / 0.5))
    return scores, ranked_components, confidence


def dynamic_capital_budget(
    *,
    regime: str,
    validation_rank_ic: float,
    validation_top_return: float,
    breadth_above_ma250: float,
    provisional: bool = False,
) -> int:
    """Risk budget in percent of total equity, rounded to a 5-point grid."""
    base = {"RISK_ON": 80.0, "NEUTRAL": 50.0, "RISK_OFF": 25.0}.get(regime, 20.0)
    if validation_rank_ic > 0.0 and validation_top_return > 0.0:
        evidence = 1.0
    elif validation_rank_ic > 0.0 or validation_top_return > 0.0:
        evidence = 0.85
    else:
        evidence = 0.65
    breadth = max(0.0, min(1.0, float(breadth_above_ma250)))
    breadth_multiplier = 0.75 + 0.5 * breadth
    provisional_multiplier = 0.80 if provisional else 1.0
    raw = base * evidence * breadth_multiplier * provisional_multiplier
    rounded = int(round(raw / 5.0) * 5)
    return max(10, min(100, rounded))


def _capped_normalize(raw: Mapping[str, float], budget_pct: float, cap_pct: float) -> dict[str, float]:
    if budget_pct <= 0 or not raw:
        return {symbol: 0.0 for symbol in raw}
    remaining = set(raw)
    result = {symbol: 0.0 for symbol in raw}
    remaining_budget = float(budget_pct)
    while remaining and remaining_budget > 1e-12:
        total_raw = sum(max(float(raw[symbol]), 0.0) for symbol in remaining)
        if total_raw <= 0:
            break
        capped: set[str] = set()
        for symbol in sorted(remaining):
            proposed = remaining_budget * max(float(raw[symbol]), 0.0) / total_raw
            room = max(0.0, cap_pct - result[symbol])
            if proposed >= room - 1e-12:
                result[symbol] += room
                remaining_budget -= room
                capped.add(symbol)
        if not capped:
            for symbol in remaining:
                result[symbol] += remaining_budget * max(float(raw[symbol]), 0.0) / total_raw
            remaining_budget = 0.0
        remaining -= capped
    return result


def optimized_weights(
    *,
    symbols: Sequence[str],
    scores: Sequence[float],
    confidence: Sequence[float],
    volatility_60: Sequence[float],
    eligible: Sequence[bool],
    budget_pct: float,
    top_k: int,
    max_symbol_weight_pct: float = 15.0,
) -> tuple[dict[str, float], list[str]]:
    """Conviction × inverse-volatility weighting with a hard per-symbol cap."""
    lengths = {len(symbols), len(scores), len(confidence), len(volatility_60), len(eligible)}
    if len(lengths) != 1:
        raise ValueError("WEIGHT_INPUT_LENGTH_MISMATCH")
    if top_k <= 0 or max_symbol_weight_pct <= 0:
        raise ValueError("WEIGHT_CONFIG_INVALID")
    candidates = [index for index in range(len(symbols)) if bool(eligible[index])]
    candidates.sort(key=lambda index: (-float(scores[index]), symbols[index]))
    selected = candidates[:top_k]
    raw: dict[str, float] = {}
    for index in selected:
        conviction = max(float(scores[index]) - 0.45, 0.03)
        agreement = 0.5 + 0.5 * max(0.0, min(1.0, float(confidence[index])))
        volatility = max(abs(float(volatility_60[index])), 0.005)
        raw[symbols[index]] = (conviction ** 1.35) * agreement / sqrt(volatility)
    weights = _capped_normalize(raw, float(budget_pct), float(max_symbol_weight_pct))
    return weights, [symbols[index] for index in selected]
