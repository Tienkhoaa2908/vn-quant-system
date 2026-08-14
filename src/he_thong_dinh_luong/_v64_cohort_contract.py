"""Frozen V64 research-cohort contract. No order or portfolio actions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Mapping

SCHEMA_VERSION = "c3_multisignal_cohort_v64"
SELECTION_END_DEFAULT = date(2026, 7, 31)
ANALYSIS_END_DEFAULT = date(2026, 8, 13)
TURNOVER_IS_VETO = False
COST_STRESS_IS_VETO = False
LIVE_MODEL_CHANGE_AUTHORIZED = False
SHADOW_FOCUS_SYMBOLS = ("VPI", "TLG", "BAF")
HORIZONS = (1, 3, 5, 10, 15, 20)
ERA_BUCKETS = (
    ("2017_2019", date(2017, 1, 1), date(2019, 12, 31)),
    ("2020_2021", date(2020, 1, 1), date(2021, 12, 31)),
    ("2022_2023", date(2022, 1, 1), date(2023, 12, 31)),
    ("2024_2026_CUTOFF", date(2024, 1, 1), SELECTION_END_DEFAULT),
)


@dataclass(frozen=True)
class CohortSpec:
    cohort_id: str
    kind: str
    family: str
    description: str


RISK_COHORTS: tuple[CohortSpec, ...] = (
    CohortSpec("R01_RANK_OUT20", "RISK", "RANK", "canonical Top-10 falls outside preview Top-20"),
    CohortSpec("R02_RANK_OUT15_MA20", "RISK", "RANK_TREND", "preview rank >15 while price is below MA20"),
    CohortSpec("R03_RANK_DROP8", "RISK", "RANK_VELOCITY", "weekly preview rank deteriorates by at least 8 places and is outside Top-10"),
    CohortSpec("R04_SCORE_DROP12", "RISK", "SCORE", "weekly preview score drops by at least 0.12"),
    CohortSpec("R05_MA20_REL5", "RISK", "TREND_RELATIVE", "below MA20 with 5-session relative return <= -3%"),
    CohortSpec("R06_MA50_REL10", "RISK", "TREND_RELATIVE", "below MA50 with 10-session relative return <= -5%"),
    CohortSpec("R07_DD20_08", "RISK", "DRAWDOWN", "drawdown from 20-session high is at least 8%"),
    CohortSpec("R08_DD60_12", "RISK", "DRAWDOWN", "drawdown from 60-session high is at least 12%"),
    CohortSpec("R09_RET5_07_VOL15", "RISK", "SHOCK_VOLUME", "5-session return <= -7% with volume ratio >=1.5"),
    CohortSpec("R10_REL5_05_VOL15", "RISK", "SHOCK_VOLUME", "5-session relative return <= -5% with volume ratio >=1.5"),
    CohortSpec("R11_VOLSHOCK_TREND", "RISK", "VOLATILITY", "20/60 realized-vol ratio >=1.5 while below MA20 and falling"),
    CohortSpec("R12_RANK_TREND_COMBO", "RISK", "COMPOSITE", "outside preview Top-10, below MA20, and negative 5-session relative return"),
    CohortSpec("R13_MULTI_2OF4", "RISK", "COMPOSITE", "at least 2 of rank weakness, MA20 break, relative weakness, 20-session drawdown"),
    CohortSpec("R14_MULTI_3OF5", "RISK", "COMPOSITE", "at least 3 of rank weakness, MA20/MA50 breaks, relative weakness, drawdown"),
    CohortSpec("R15_CONFIRM_2W", "RISK", "PERSISTENCE", "R13 composite persists across two completed weekly observations"),
    CohortSpec("R16_MA20_CROSS_DOWN", "RISK", "TREND_CROSS", "crosses from at/above MA20 to below MA20 with negative relative return"),
    CohortSpec("R17_RANK_SCORE_DOUBLE", "RISK", "RANK_SCORE", "rank worsens >=5 places and score drops >=0.08"),
    CohortSpec("R18_NEW20_LOW", "RISK", "PRICE_BREAK", "closes at/below prior 20-session low with negative 5-session relative return"),
)

LEADER_COHORTS: tuple[CohortSpec, ...] = (
    CohortSpec("L01_TOP5_RAW", "LEADER", "RANK", "new preview Top-5 leader"),
    CohortSpec("L02_TOP5_TREND", "LEADER", "TREND", "new Top-5 leader above MA20 and MA50"),
    CohortSpec("L03_TOP5_REL", "LEADER", "RELATIVE", "new Top-5 leader with positive 5/20-session relative strength"),
    CohortSpec("L04_TOP5_VOLUME", "LEADER", "VOLUME", "new Top-5 leader with volume ratio >=1 and positive 5-session relative return"),
    CohortSpec("L05_TOP5_NOT_EXT", "LEADER", "ANTI_EXTENSION", "new Top-5 leader above MA20 but <=10% extended and 5-session return <=12%"),
    CohortSpec("L06_PERSIST_TOP5", "LEADER", "PERSISTENCE", "new Top-5 leader that was also Top-5 last week and remains in uptrend"),
    CohortSpec("L07_PERSIST_TOP10_TO5", "LEADER", "PERSISTENCE", "new Top-5 leader that was Top-10 last week and remains in uptrend"),
    CohortSpec("L08_VELOCITY_20_TO5", "LEADER", "RANK_VELOCITY", "accelerates from prior rank 6-20 into Top-5 with volume confirmation"),
    CohortSpec("L09_SCORE_ACCEL", "LEADER", "SCORE", "new Top-5 leader with weekly score improvement >=0.05 and uptrend"),
    CohortSpec("L10_BREAKOUT20", "LEADER", "BREAKOUT", "new Top-10 leader at/above prior 20-session high with positive relative strength and volume"),
    CohortSpec("L11_RELATIVE_LEADER", "LEADER", "RELATIVE", "new Top-10 leader with strong 5/20-session relative strength and uptrend"),
    CohortSpec("L12_RISKON_TOP5_TREND", "LEADER", "REGIME", "L02 Top-5 trend cohort restricted to monthly risk-on regime"),
    CohortSpec("L13_MULTI_3OF5", "LEADER", "COMPOSITE", "new Top-5 leader satisfying at least 3 confirmation dimensions"),
    CohortSpec("L14_MULTI_4OF6", "LEADER", "COMPOSITE", "new Top-10 leader satisfying at least 4 of 6 confirmation dimensions"),
    CohortSpec("L15_PERSIST_REL", "LEADER", "PERSISTENCE_RELATIVE", "prior Top-10 to current Top-5 with positive relative return and volume"),
    CohortSpec("L16_PULLBACK_LEADER", "LEADER", "PULLBACK", "new Top-5 leader near MA20 with positive 20-session relative strength"),
    CohortSpec("L17_ACCEL_NOT_EXT", "LEADER", "ACCELERATION", "rank and score accelerate into Top-5 without short-horizon extension"),
    CohortSpec("L18_TOP3_TREND_VOLUME", "LEADER", "HIGH_CONVICTION", "new Top-3 leader in MA20/MA50 uptrend with volume confirmation"),
)

ALL_COHORTS = RISK_COHORTS + LEADER_COHORTS
COHORT_BY_ID = {cohort.cohort_id: cohort for cohort in ALL_COHORTS}


def _r13(row: Mapping[str, object]) -> bool:
    votes = (
        int(row["preview_rank"]) > 10,
        float(row["distance_ma20"]) < 0.0,
        float(row["relative_5"]) <= -0.03,
        float(row["drawdown_20"]) <= -0.06,
    )
    return sum(bool(value) for value in votes) >= 2


def cohort_matches(cohort_id: str, row: Mapping[str, object], prior_row: Mapping[str, object] | None = None) -> bool:
    canonical = int(row["canonical_rank"]) <= 10
    emerging = int(row["canonical_rank"]) > 10
    rank, prior_rank, rank_delta = int(row["preview_rank"]), int(row["prior_preview_rank"]), int(row["rank_delta"])
    score_delta = float(row["score_delta"])
    ma20, ma50 = float(row["distance_ma20"]), float(row["distance_ma50"])
    ret5 = float(row["return_5"])
    rel5, rel10, rel20 = float(row["relative_5"]), float(row["relative_10"]), float(row["relative_20"])
    dd20, dd60 = float(row["drawdown_20"]), float(row["drawdown_60"])
    volume_ratio = float(row["volume_ratio_5_20"])
    vol_ratio = float(row["realized_vol_ratio_20_60"])
    breakout20, low20 = float(row["breakout_20_gap"]), float(row["breakdown_20_low_gap"])
    risk_on = bool(row["risk_on"])

    if cohort_id == "R01_RANK_OUT20": return canonical and rank > 20
    if cohort_id == "R02_RANK_OUT15_MA20": return canonical and rank > 15 and ma20 < 0.0
    if cohort_id == "R03_RANK_DROP8": return canonical and rank > 10 and rank_delta >= 8
    if cohort_id == "R04_SCORE_DROP12": return canonical and score_delta <= -0.12
    if cohort_id == "R05_MA20_REL5": return canonical and ma20 < 0.0 and rel5 <= -0.03
    if cohort_id == "R06_MA50_REL10": return canonical and ma50 < 0.0 and rel10 <= -0.05
    if cohort_id == "R07_DD20_08": return canonical and dd20 <= -0.08
    if cohort_id == "R08_DD60_12": return canonical and dd60 <= -0.12
    if cohort_id == "R09_RET5_07_VOL15": return canonical and ret5 <= -0.07 and volume_ratio >= 1.5
    if cohort_id == "R10_REL5_05_VOL15": return canonical and rel5 <= -0.05 and volume_ratio >= 1.5
    if cohort_id == "R11_VOLSHOCK_TREND": return canonical and vol_ratio >= 1.5 and ma20 < 0.0 and ret5 < 0.0
    if cohort_id == "R12_RANK_TREND_COMBO": return canonical and rank > 10 and ma20 < 0.0 and rel5 < 0.0
    if cohort_id == "R13_MULTI_2OF4": return canonical and _r13(row)
    if cohort_id == "R14_MULTI_3OF5": return canonical and sum(bool(value) for value in (rank > 10, ma20 < 0.0, ma50 < 0.0, rel5 <= -0.03, dd20 <= -0.06)) >= 3
    if cohort_id == "R15_CONFIRM_2W": return canonical and _r13(row) and prior_row is not None and _r13(prior_row)
    if cohort_id == "R16_MA20_CROSS_DOWN": return canonical and prior_row is not None and float(prior_row["distance_ma20"]) >= 0.0 and ma20 < 0.0 and rel5 < 0.0
    if cohort_id == "R17_RANK_SCORE_DOUBLE": return canonical and rank_delta >= 5 and score_delta <= -0.08
    if cohort_id == "R18_NEW20_LOW": return canonical and low20 <= 0.0 and rel5 < 0.0

    trend = ma20 >= 0.0 and ma50 >= 0.0
    if cohort_id == "L01_TOP5_RAW": return emerging and rank <= 5
    if cohort_id == "L02_TOP5_TREND": return emerging and rank <= 5 and trend
    if cohort_id == "L03_TOP5_REL": return emerging and rank <= 5 and rel5 > 0.0 and rel20 > 0.0
    if cohort_id == "L04_TOP5_VOLUME": return emerging and rank <= 5 and volume_ratio >= 1.0 and rel5 > 0.0
    if cohort_id == "L05_TOP5_NOT_EXT": return emerging and rank <= 5 and 0.0 <= ma20 <= 0.10 and ret5 <= 0.12
    if cohort_id == "L06_PERSIST_TOP5": return emerging and rank <= 5 and prior_rank <= 5 and trend
    if cohort_id == "L07_PERSIST_TOP10_TO5": return emerging and rank <= 5 and prior_rank <= 10 and trend
    if cohort_id == "L08_VELOCITY_20_TO5": return emerging and rank <= 5 and 6 <= prior_rank <= 20 and prior_rank - rank >= 3 and volume_ratio >= 1.0
    if cohort_id == "L09_SCORE_ACCEL": return emerging and rank <= 5 and score_delta >= 0.05 and trend
    if cohort_id == "L10_BREAKOUT20": return emerging and rank <= 10 and breakout20 >= 0.0 and rel20 >= 0.03 and volume_ratio >= 1.0
    if cohort_id == "L11_RELATIVE_LEADER": return emerging and rank <= 10 and rel5 >= 0.03 and rel20 >= 0.05 and trend
    if cohort_id == "L12_RISKON_TOP5_TREND": return emerging and risk_on and rank <= 5 and trend
    if cohort_id == "L13_MULTI_3OF5": return emerging and rank <= 5 and sum(bool(value) for value in (ma20 >= 0.0, ma50 >= 0.0, rel5 > 0.0, volume_ratio >= 1.0, breakout20 >= 0.0)) >= 3
    if cohort_id == "L14_MULTI_4OF6": return emerging and rank <= 10 and sum(bool(value) for value in (rank <= 5, ma20 >= 0.0, ma50 >= 0.0, rel5 >= 0.02, rel20 >= 0.03, volume_ratio >= 1.0)) >= 4
    if cohort_id == "L15_PERSIST_REL": return emerging and rank <= 5 and prior_rank <= 10 and rel5 >= 0.02 and volume_ratio >= 1.0
    if cohort_id == "L16_PULLBACK_LEADER": return emerging and rank <= 5 and -0.02 <= ma20 <= 0.05 and rel20 >= 0.03
    if cohort_id == "L17_ACCEL_NOT_EXT": return emerging and rank <= 5 and prior_rank - rank >= 5 and score_delta >= 0.03 and ma20 <= 0.08 and ret5 <= 0.10
    if cohort_id == "L18_TOP3_TREND_VOLUME": return emerging and rank <= 3 and trend and volume_ratio >= 1.0
    raise ValueError(f"V64_UNKNOWN_COHORT:{cohort_id}")
