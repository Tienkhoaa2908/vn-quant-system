"""Frozen V64 research-cohort contract. No order or portfolio actions."""
from __future__ import annotations

from typing import Mapping

COHORT_IDS = (
    "R01_RANK_OUT20",
    "R02_MA20_REL5_WEAK",
    "R03_DRAWDOWN20",
    "L01_NEW_TOP5",
    "L02_NEW_TOP5_TREND",
    "L03_NEW_TOP5_PERSIST",
)


def cohort_matches(cohort_id: str, row: Mapping[str, object]) -> bool:
    canonical = int(row["canonical_rank"]) <= 10
    emerging = int(row["canonical_rank"]) > 10
    rank = int(row["preview_rank"])
    prior_rank = int(row["prior_preview_rank"])
    d20 = float(row["distance_ma20"])
    rel5 = float(row["relative_5"])
    dd20 = float(row["drawdown_20"])
    if cohort_id == "R01_RANK_OUT20":
        return canonical and rank > 20
    if cohort_id == "R02_MA20_REL5_WEAK":
        return canonical and d20 < 0.0 and rel5 <= -0.03
    if cohort_id == "R03_DRAWDOWN20":
        return canonical and dd20 <= -0.08
    if cohort_id == "L01_NEW_TOP5":
        return emerging and rank <= 5
    if cohort_id == "L02_NEW_TOP5_TREND":
        return emerging and rank <= 5 and d20 >= 0.0
    if cohort_id == "L03_NEW_TOP5_PERSIST":
        return emerging and rank <= 5 and prior_rank <= 5 and d20 >= 0.0
    raise ValueError(cohort_id)
