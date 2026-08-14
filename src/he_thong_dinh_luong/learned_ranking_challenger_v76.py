"""V76 learned cross-sectional ranking challenger lab on frozen C3.

Research only. Frozen C3 remains champion and exact comparator truth. Learned
challengers train only on labels completed before each prediction month. Model-
trainable history is separated from portfolio eligibility; 2026 is stress/shadow
for research selection, not a candidate-selection period.
"""
from __future__ import annotations

import bisect
import csv
import gzip
import json
import math
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from statistics import fmean, median
from typing import Mapping, Sequence

from . import c3_consolidated_selection_v75 as v75
from . import deep_portfolio_backtest_v70 as v70
from . import c3_factor_health_regime_v73 as v73
from . import weekly_micro_capital_v43 as c3

SCHEMA_VERSION = "learned_ranking_challenger_v76"
CHAMPION_MODEL = "C3_STABLE_3_PAST_IC_SHRUNK"
PRIMARY_SELECTION_END = date(2025, 12, 31)
BASE_POLICY = v75.BASE_POLICY
VALIDATION_MONTHS = 3
MIN_TRAIN_MONTHS = 12
BOTTOM_FRACTION = 0.20
CAPITALS = (100_000_000.0, 1_000_000_000.0, 10_000_000_000.0)
RIDGE_ALPHAS = (1.0, 10.0, 100.0)
LOGISTIC_CS = (0.1, 1.0, 10.0)
HGB_L2 = (1.0, 10.0)
MODEL_POLICIES = (
    BASE_POLICY,
    "V76_RIDGE_RANK",
    "V76_RIDGE_CONTEXT",
    "V76_HGB_CONTEXT",
    "V76_LOGIT_BOTTOM20_SAFE",
)
FEATURE_NAMES = (
    "low_volatility",
    "relative_strength_120",
    "high_52_week",
    "relative_20",
    "relative_10",
    "relative_5",
    "momentum_acceleration",
    "breakout_20_gap",
    "distance_ma20",
    "distance_ma50",
    "drawdown_20",
    "drawdown_60",
    "log_volume_ratio_5_20",
    "stability",
)


@dataclass(frozen=True)
class PanelRow:
    signal_day: date
    label_end: date | None
    symbol: str
    risk_on: bool
    features: tuple[float, ...]
    target_relative: float | None
    target_rank: float | None


def _read_csv(path: Path) -> list[dict[str, str]]:
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    v73._write_csv(path, rows)


def _write_gz(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    v73._write_gz(path, rows)


def _all_store_symbols(store: Path) -> list[str]:
    uri = store.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        cols = {str(r[1]).lower(): str(r[1]) for r in db.execute('PRAGMA table_info("bars")')}
        if not {"symbol", "asset_type"}.issubset(cols):
            raise ValueError("V76_STORE_SYMBOL_COLUMNS_MISSING")
        q = lambda name: '"' + name.replace('"', '""') + '"'
        sql = (
            f"SELECT DISTINCT {q(cols['symbol'])} FROM bars "
            f"WHERE UPPER(COALESCE({q(cols['asset_type'])},''))='STOCK' ORDER BY 1"
        )
        return [str(row[0]).strip().upper() for row in db.execute(sql) if str(row[0] or "").strip()]


def _variant_symbols(v68_output: Path, variant_dir: Path, all_symbols: Sequence[str]) -> tuple[list[str], str]:
    variant = variant_dir.name
    all_set = set(all_symbols)
    basis_path = v68_output / "v68_basis_audit.json"
    basis = json.loads(basis_path.read_text(encoding="utf-8-sig")) if basis_path.is_file() else {}
    gaps = {
        str(row.get("symbol") or "").upper()
        for row in basis.get("gap_events", [])
        if isinstance(row, dict)
    }
    seams = {
        str(row.get("symbol") or "").upper()
        for row in basis.get("mixed_basis_seam_candidates", [])
        if isinstance(row, dict)
    }
    if variant == "BROAD_PROVISIONAL":
        return sorted(all_set), "ALL_LOCAL_STOCKS_TRAINABLE_HISTORY"
    if variant == "SEAM_CLEAN":
        return sorted(all_set - seams), "ALL_LOCAL_STOCKS_MINUS_PROVENANCE_SEAMS"
    if variant == "GAP18_CLEAN":
        return sorted(all_set - gaps), "ALL_LOCAL_STOCKS_MINUS_GE18PCT_GAP_SYMBOLS"
    observed = {
        str(row["symbol"]).strip().upper()
        for row in _read_csv(variant_dir / "v67_c3_monthly_rankings.csv.gz")
        if row.get("symbol")
    }
    if not observed:
        raise ValueError(f"V76_UNKNOWN_VARIANT_SYMBOL_SET:{variant}")
    return sorted(observed), "FALLBACK_EVER_PORTFOLIO_ELIGIBLE_SYMBOLS"


def _std(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = fmean(values)
    return math.sqrt(sum((x - avg) ** 2 for x in values) / (len(values) - 1))


def _ret(market: v70.Market, symbol: str, pos: int, lag: int) -> float | None:
    if pos < lag:
        return None
    now = market.sc.get((symbol, market.cal[pos]))
    old = market.sc.get((symbol, market.cal[pos - lag]))
    if now is None or old is None or old <= 0:
        return None
    return float(now) / float(old) - 1.0


def _iret(market: v70.Market, pos: int, lag: int) -> float | None:
    if pos < lag:
        return None
    now = market.ic.get(market.cal[pos])
    old = market.ic.get(market.cal[pos - lag])
    if now is None or old is None or old <= 0:
        return None
    return float(now) / float(old) - 1.0


def _risk_on(market: v70.Market, pos: int) -> bool:
    if pos < 249:
        return False
    current = market.ic.get(market.cal[pos])
    window = [market.ic.get(day) for day in market.cal[pos - 249:pos + 1]]
    if current is None or any(x is None or x <= 0 for x in window):
        return False
    return float(current) >= fmean(float(x) for x in window)


def _raw_features(market: v70.Market, symbol: str, day: date) -> dict[str, float] | None:
    pos = bisect.bisect_left(market.cal, day)
    if pos >= len(market.cal) or market.cal[pos] != day or pos < 250:
        return None
    days250 = market.cal[pos - 249:pos + 1]
    closes = [market.sc.get((symbol, d)) for d in days250]
    if any(x is None or x <= 0 for x in closes):
        return None
    c = [float(x) for x in closes]
    r5, r10, r20, r120 = (_ret(market, symbol, pos, lag) for lag in (5, 10, 20, 120))
    i5, i10, i20, i120 = (_iret(market, pos, lag) for lag in (5, 10, 20, 120))
    if None in (r5, r10, r20, r120, i5, i10, i20, i120):
        return None
    tail61 = c[-61:]
    returns60 = [tail61[i] / tail61[i - 1] - 1.0 for i in range(1, len(tail61))]
    vol60 = _std(returns60)
    vol20 = _std(returns60[-20:])
    if vol60 <= 0:
        return None
    ma20 = fmean(c[-20:])
    ma50 = fmean(c[-50:])
    prior20 = c[-21:-1]
    volumes20 = [float(market.vol.get((symbol, d), 0)) for d in market.cal[pos - 19:pos + 1]]
    avg20 = fmean(volumes20)
    avg5 = fmean(volumes20[-5:])
    rel120 = float(r120) - float(i120)
    rel20 = float(r20) - float(i20)
    return {
        "low_volatility": -vol60,
        "relative_strength_120": rel120,
        "high_52_week": c[-1] / max(c),
        "relative_20": rel20,
        "relative_10": float(r10) - float(i10),
        "relative_5": float(r5) - float(i5),
        "momentum_acceleration": rel20 - rel120 / 6.0,
        "breakout_20_gap": c[-1] / max(prior20) - 1.0,
        "distance_ma20": c[-1] / ma20 - 1.0,
        "distance_ma50": c[-1] / ma50 - 1.0,
        "drawdown_20": c[-1] / max(c[-20:]) - 1.0,
        "drawdown_60": c[-1] / max(c[-60:]) - 1.0,
        "log_volume_ratio_5_20": math.log(max(1e-9, avg5 / avg20)) if avg20 > 0 else 0.0,
        "stability": -(vol20 / vol60),
    }


def _label(market: v70.Market, symbol: str, day: date, horizon: int = 20) -> tuple[date, float] | None:
    pos = bisect.bisect_left(market.cal, day)
    if pos >= len(market.cal) or market.cal[pos] != day:
        return None
    end_pos = pos + horizon
    if end_pos >= len(market.cal):
        return None
    end = market.cal[end_pos]
    s0 = market.sc.get((symbol, day))
    s1 = market.sc.get((symbol, end))
    b0 = market.ic.get(day)
    b1 = market.ic.get(end)
    if not all(x is not None and x > 0 for x in (s0, s1, b0, b1)):
        return None
    return end, float(s1) / float(s0) - float(b1) / float(b0)


def _monthly_days(calendar: Sequence[date], end: date) -> list[date]:
    by_month: dict[tuple[int, int], date] = {}
    for day in calendar:
        if day <= end:
            by_month[(day.year, day.month)] = day
    return [by_month[key] for key in sorted(by_month)]


def _build_panel(
    market: v70.Market,
    symbols: Sequence[str],
    *,
    end: date,
) -> tuple[list[PanelRow], list[dict[str, object]]]:
    raw_by_day: dict[date, list[tuple[str, dict[str, float], tuple[date, float] | None]]] = {}
    for day in _monthly_days(market.cal, end):
        pos = bisect.bisect_left(market.cal, day)
        if pos < 250:
            continue
        group = []
        for symbol in symbols:
            values = _raw_features(market, symbol, day)
            if values is None:
                continue
            group.append((symbol, values, _label(market, symbol, day)))
        if len(group) >= 8:
            raw_by_day[day] = group

    rows: list[PanelRow] = []
    ic_rows: list[dict[str, object]] = []
    for day, group in sorted(raw_by_day.items()):
        pct_by_feature: dict[str, dict[str, float]] = {}
        symbols_day = [symbol for symbol, _, _ in group]
        for name in FEATURE_NAMES:
            pct = c3.average_percentile([float(values[name]) for _, values, _ in group])
            pct_by_feature[name] = dict(zip(symbols_day, [float(x) for x in pct]))

        labeled = [(symbol, label) for symbol, _, label in group if label is not None]
        target_pct: dict[str, float] = {}
        if len(labeled) >= 8:
            ranks = c3.average_percentile([float(label[1]) for _, label in labeled])
            target_pct = dict(zip([symbol for symbol, _ in labeled], [float(x) for x in ranks]))
            label_end = max(label[0] for _, label in labeled)
            record: dict[str, object] = {
                "signal_day": day.isoformat(),
                "label_end": label_end.isoformat(),
                "labeled_count": len(labeled),
            }
            targets = [target_pct[symbol] for symbol, _ in labeled]
            for name in ("relative_strength_120", "high_52_week", "relative_20", "momentum_acceleration"):
                xs = [pct_by_feature[name][symbol] for symbol, _ in labeled]
                record[f"ic_{name}"] = v75._pearson(xs, targets)
            ic_rows.append(record)

        risk = _risk_on(market, bisect.bisect_left(market.cal, day))
        label_map = {symbol: label for symbol, label in labeled}
        for symbol, _values, _ in group:
            label = label_map.get(symbol)
            rows.append(
                PanelRow(
                    signal_day=day,
                    label_end=label[0] if label else None,
                    symbol=symbol,
                    risk_on=risk,
                    features=tuple(pct_by_feature[name][symbol] for name in FEATURE_NAMES),
                    target_relative=float(label[1]) if label else None,
                    target_rank=target_pct.get(symbol),
                )
            )
    return rows, ic_rows


def _context(ic_rows: Sequence[Mapping[str, object]], signal_day: date) -> tuple[float, float]:
    safe = [
        row for row in ic_rows
        if date.fromisoformat(str(row["signal_day"])) < signal_day
        and date.fromisoformat(str(row["label_end"])) < signal_day
    ][-3:]
    if len(safe) < 3:
        return 0.0, 0.0
    return (
        fmean(float(row["ic_relative_strength_120"]) for row in safe),
        fmean(float(row["ic_high_52_week"]) for row in safe),
    )


def _vector(row: PanelRow, ic_rows: Sequence[Mapping[str, object]], mode: str) -> list[float]:
    base = [float(x) for x in row.features]
    if mode == "BASE":
        return base
    rs, high = _context(ic_rows, row.signal_day)
    risk = 1.0 if row.risk_on else -1.0
    if mode == "CONTEXT":
        return base + [x * risk for x in base] + [x * rs for x in base] + [x * high for x in base]
    if mode == "TREE_CONTEXT":
        return base + [risk, rs, high] + [x * rs for x in base] + [x * high for x in base]
    raise ValueError(f"V76_UNKNOWN_VECTOR_MODE:{mode}")


def _mean_monthly_ic(rows: Sequence[PanelRow], scores: Sequence[float]) -> float:
    if len(rows) != len(scores):
        raise ValueError("V76_SCORE_LENGTH_MISMATCH")
    by_day: dict[date, list[tuple[float, float]]] = {}
    for row, score in zip(rows, scores):
        if row.target_rank is not None:
            by_day.setdefault(row.signal_day, []).append((float(score), float(row.target_rank)))
    vals = []
    for pairs in by_day.values():
        if len(pairs) >= 5:
            sx = c3.average_percentile([x for x, _ in pairs])
            sy = [y for _, y in pairs]
            vals.append(v75._pearson([float(x) for x in sx], sy))
    return fmean(vals) if vals else -1.0


def _safe_targets(rows: Sequence[PanelRow]) -> list[int]:
    return [1 if float(row.target_rank or 0.0) > BOTTOM_FRACTION else 0 for row in rows]


def _bottom_recall(rows: Sequence[PanelRow], safe_scores: Sequence[float]) -> float:
    by_day: dict[date, list[tuple[PanelRow, float]]] = {}
    for row, score in zip(rows, safe_scores):
        by_day.setdefault(row.signal_day, []).append((row, float(score)))
    recalls = []
    for pairs in by_day.values():
        count = max(1, math.ceil(len(pairs) * BOTTOM_FRACTION))
        actual = {
            row.symbol for row, _ in sorted(pairs, key=lambda item: (float(item[0].target_rank or 0.0), item[0].symbol))[:count]
        }
        predicted = {
            row.symbol for row, _ in sorted(pairs, key=lambda item: (item[1], item[0].symbol))[:count]
        }
        recalls.append(len(actual & predicted) / len(actual))
    return fmean(recalls) if recalls else 0.0


def _fit_ridge(
    train: Sequence[PanelRow],
    validation: Sequence[PanelRow],
    test: Sequence[PanelRow],
    ic_rows: Sequence[Mapping[str, object]],
    *,
    context: bool,
) -> tuple[list[float], dict[str, object]]:
    try:
        from sklearn.linear_model import Ridge
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise ValueError("V76_SKLEARN_NOT_INSTALLED") from exc
    mode = "CONTEXT" if context else "BASE"
    tx = [_vector(row, ic_rows, mode) for row in train]
    vx = [_vector(row, ic_rows, mode) for row in validation]
    xx = [_vector(row, ic_rows, mode) for row in test]
    ty = [float(row.target_rank) for row in train]
    choices = []
    for alpha in RIDGE_ALPHAS:
        model = make_pipeline(StandardScaler(), Ridge(alpha=alpha, fit_intercept=True))
        model.fit(tx, ty)
        val_scores = [float(x) for x in model.predict(vx)]
        choices.append((_mean_monthly_ic(validation, val_scores), alpha))
    val_ic, alpha = max(choices, key=lambda item: (item[0], -item[1]))
    fit = list(train) + list(validation)
    model = make_pipeline(StandardScaler(), Ridge(alpha=alpha, fit_intercept=True))
    model.fit([_vector(row, ic_rows, mode) for row in fit], [float(row.target_rank) for row in fit])
    scores = [float(x) for x in model.predict(xx)]
    return scores, {
        "selected_alpha": alpha,
        "validation_mean_rank_ic": val_ic,
        "context_interactions": context,
        "uses_only_completed_labels": True,
    }


def _fit_hgb(
    train: Sequence[PanelRow],
    validation: Sequence[PanelRow],
    test: Sequence[PanelRow],
    ic_rows: Sequence[Mapping[str, object]],
) -> tuple[list[float], dict[str, object]]:
    try:
        from sklearn.ensemble import HistGradientBoostingRegressor
    except ImportError as exc:
        raise ValueError("V76_SKLEARN_NOT_INSTALLED") from exc
    tx = [_vector(row, ic_rows, "TREE_CONTEXT") for row in train]
    vx = [_vector(row, ic_rows, "TREE_CONTEXT") for row in validation]
    xx = [_vector(row, ic_rows, "TREE_CONTEXT") for row in test]
    ty = [float(row.target_rank) for row in train]
    choices = []
    for l2 in HGB_L2:
        model = HistGradientBoostingRegressor(
            learning_rate=0.05,
            max_iter=80,
            max_leaf_nodes=15,
            min_samples_leaf=20,
            l2_regularization=l2,
            random_state=20260814,
        )
        model.fit(tx, ty)
        val_scores = [float(x) for x in model.predict(vx)]
        choices.append((_mean_monthly_ic(validation, val_scores), l2))
    val_ic, l2 = max(choices, key=lambda item: (item[0], -item[1]))
    fit = list(train) + list(validation)
    model = HistGradientBoostingRegressor(
        learning_rate=0.05,
        max_iter=80,
        max_leaf_nodes=15,
        min_samples_leaf=20,
        l2_regularization=l2,
        random_state=20260814,
    )
    model.fit([_vector(row, ic_rows, "TREE_CONTEXT") for row in fit], [float(row.target_rank) for row in fit])
    scores = [float(x) for x in model.predict(xx)]
    return scores, {
        "selected_l2": l2,
        "validation_mean_rank_ic": val_ic,
        "context_features": True,
        "uses_only_completed_labels": True,
    }


def _fit_logistic(
    train: Sequence[PanelRow],
    validation: Sequence[PanelRow],
    test: Sequence[PanelRow],
    ic_rows: Sequence[Mapping[str, object]],
) -> tuple[list[float], dict[str, object]]:
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise ValueError("V76_SKLEARN_NOT_INSTALLED") from exc
    tx = [_vector(row, ic_rows, "BASE") for row in train]
    vx = [_vector(row, ic_rows, "BASE") for row in validation]
    xx = [_vector(row, ic_rows, "BASE") for row in test]
    ty = _safe_targets(train)
    if len(set(ty)) < 2:
        raise ValueError("V76_BOTTOM_TARGET_SINGLE_CLASS")
    choices = []
    for cval in LOGISTIC_CS:
        model = make_pipeline(
            StandardScaler(),
            LogisticRegression(C=cval, class_weight="balanced", max_iter=2000, solver="liblinear", random_state=20260814),
        )
        model.fit(tx, ty)
        val_scores = [float(x) for x in model.predict_proba(vx)[:, 1]]
        choices.append((_bottom_recall(validation, val_scores), _mean_monthly_ic(validation, val_scores), cval))
    recall, val_ic, cval = max(choices, key=lambda item: (item[0], item[1], -item[2]))
    fit = list(train) + list(validation)
    fy = _safe_targets(fit)
    if len(set(fy)) < 2:
        raise ValueError("V76_BOTTOM_REFIT_SINGLE_CLASS")
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=cval, class_weight="balanced", max_iter=2000, solver="liblinear", random_state=20260814),
    )
    model.fit([_vector(row, ic_rows, "BASE") for row in fit], fy)
    scores = [float(x) for x in model.predict_proba(xx)[:, 1]]
    return scores, {
        "selected_c": cval,
        "validation_bottom20_recall": recall,
        "validation_mean_rank_ic": val_ic,
        "uses_only_completed_labels": True,
    }


def _split_safe_history(rows: Sequence[PanelRow], test_day: date) -> tuple[list[PanelRow], list[PanelRow]] | None:
    safe = [
        row for row in rows
        if row.target_rank is not None
        and row.label_end is not None
        and row.signal_day < test_day
        and row.label_end < test_day
    ]
    months = sorted({row.signal_day for row in safe})
    if len(months) < MIN_TRAIN_MONTHS + VALIDATION_MONTHS:
        return None
    val_months = set(months[-VALIDATION_MONTHS:])
    first_val = min(val_months)
    train = [row for row in safe if row.signal_day < first_val and row.label_end is not None and row.label_end < first_val]
    validation = [row for row in safe if row.signal_day in val_months]
    if len({row.signal_day for row in train}) < MIN_TRAIN_MONTHS or len({row.signal_day for row in validation}) < VALIDATION_MONTHS:
        return None
    return train, validation


def _recorded_eligible(variant_dir: Path) -> tuple[dict[date, list[dict[str, object]]], dict[tuple[date, str], tuple[date, float]]]:
    by_day: dict[date, list[dict[str, object]]] = {}
    for raw in _read_csv(variant_dir / "v67_c3_monthly_rankings.csv.gz"):
        try:
            day = date.fromisoformat(raw["signal_day"])
            row = {
                "symbol": str(raw["symbol"]).strip().upper(),
                "rank": int(raw["rank"]),
                "score": float(raw["score"]),
                "risk_on": v70._bool(raw.get("risk_on")),
            }
        except Exception:
            continue
        by_day.setdefault(day, []).append(row)
    for day in by_day:
        by_day[day].sort(key=lambda row: (int(row["rank"]), str(row["symbol"])))
    labels = v75._load_labels(variant_dir)
    return by_day, labels


def build_walkforward_rankings(
    panel: Sequence[PanelRow],
    ic_rows: Sequence[Mapping[str, object]],
    variant_dir: Path,
) -> tuple[dict[str, list[v70.Snap]], list[dict[str, object]], list[dict[str, object]], dict[str, date]]:
    eligible_by_day, _ = _recorded_eligible(variant_dir)
    panel_map = {(row.signal_day, row.symbol): row for row in panel}
    snaps = {policy: [] for policy in MODEL_POLICIES}
    rank_rows: list[dict[str, object]] = []
    fit_rows: list[dict[str, object]] = []
    starts: dict[str, date] = {}

    for day, recorded in sorted(eligible_by_day.items()):
        base_syms = tuple(str(row["symbol"]) for row in recorded[:10])
        risk = bool(recorded[0]["risk_on"]) if recorded else False
        snaps[BASE_POLICY].append(v70.Snap(day, base_syms, risk))
        for row in recorded:
            rank_rows.append({
                "signal_day": day.isoformat(), "policy_id": BASE_POLICY, "symbol": row["symbol"],
                "rank": row["rank"], "score": row["score"], "risk_on": risk, "model_fitted": True,
            })

        test_rows = [panel_map.get((day, str(row["symbol"]))) for row in recorded]
        if any(row is None for row in test_rows):
            missing = [recorded[i]["symbol"] for i, row in enumerate(test_rows) if row is None]
            raise ValueError(f"V76_ELIGIBLE_FEATURE_MISSING:{variant_dir.name}:{day}:{','.join(missing)}")
        test = [row for row in test_rows if row is not None]
        split = _split_safe_history(panel, day)

        policy_scores: dict[str, list[float]] = {}
        policy_meta: dict[str, dict[str, object]] = {}
        if split is not None:
            train, validation = split
            fitters = (
                ("V76_RIDGE_RANK", lambda: _fit_ridge(train, validation, test, ic_rows, context=False)),
                ("V76_RIDGE_CONTEXT", lambda: _fit_ridge(train, validation, test, ic_rows, context=True)),
                ("V76_HGB_CONTEXT", lambda: _fit_hgb(train, validation, test, ic_rows)),
                ("V76_LOGIT_BOTTOM20_SAFE", lambda: _fit_logistic(train, validation, test, ic_rows)),
            )
            for policy, fn in fitters:
                try:
                    scores, meta = fn()
                    policy_scores[policy] = scores
                    policy_meta[policy] = meta
                    starts.setdefault(policy, day)
                except Exception as exc:
                    policy_meta[policy] = {"fit_error": f"{type(exc).__name__}:{exc}", "fallback_to_frozen": True}
        for policy in MODEL_POLICIES[1:]:
            fitted = policy in policy_scores
            if fitted:
                scored = sorted(
                    [(test[i].symbol, float(policy_scores[policy][i])) for i in range(len(test))],
                    key=lambda item: (-item[1], item[0]),
                )
            else:
                scored = [(str(row["symbol"]), float(row["score"])) for row in recorded]
            snaps[policy].append(v70.Snap(day, tuple(symbol for symbol, _ in scored[:10]), risk))
            for rank, (symbol, score) in enumerate(scored, start=1):
                rank_rows.append({
                    "signal_day": day.isoformat(), "policy_id": policy, "symbol": symbol,
                    "rank": rank, "score": score, "risk_on": risk, "model_fitted": fitted,
                })
            meta = policy_meta.get(policy, {"fallback_to_frozen": True})
            fit_rows.append({
                "signal_day": day.isoformat(),
                "policy_id": policy,
                "model_fitted": fitted,
                "train_month_count": len({row.signal_day for row in split[0]}) if split else 0,
                "validation_month_count": len({row.signal_day for row in split[1]}) if split else 0,
                "train_row_count": len(split[0]) if split else 0,
                "validation_row_count": len(split[1]) if split else 0,
                "test_eligible_count": len(test),
                "year_2026_used_for_research_selection": False,
                **meta,
            })
    return snaps, rank_rows, fit_rows, starts


def _rank_ic_diagnostics(
    variant: str,
    rank_rows: Sequence[Mapping[str, object]],
    labels: Mapping[tuple[date, str], tuple[date, float]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    grouped: dict[tuple[date, str], list[Mapping[str, object]]] = {}
    for row in rank_rows:
        grouped.setdefault((date.fromisoformat(str(row["signal_day"])), str(row["policy_id"])), []).append(row)
    monthly = []
    for (day, policy), group in sorted(grouped.items()):
        pairs = []
        for row in group:
            label = labels.get((day, str(row["symbol"])))
            if label is not None:
                pairs.append((float(row["score"]), float(label[1])))
        if len(pairs) < 8:
            continue
        sx = c3.average_percentile([x for x, _ in pairs])
        sy = c3.average_percentile([y for _, y in pairs])
        monthly.append({
            "variant_id": variant,
            "signal_day": day.isoformat(),
            "policy_id": policy,
            "rank_ic": v75._pearson([float(x) for x in sx], [float(y) for y in sy]),
            "n": len(pairs),
            "phase": "PRE2026_PRIMARY" if day <= PRIMARY_SELECTION_END else "2026_OBSERVED_SHADOW",
        })
    summary = []
    for policy in sorted({str(row["policy_id"]) for row in monthly}):
        pre = [float(row["rank_ic"]) for row in monthly if row["policy_id"] == policy and row["phase"] == "PRE2026_PRIMARY"]
        stress = [float(row["rank_ic"]) for row in monthly if row["policy_id"] == policy and row["phase"] == "2026_OBSERVED_SHADOW"]
        if pre:
            summary.append({
                "variant_id": variant,
                "policy_id": policy,
                "pre2026_month_count": len(pre),
                "pre2026_mean_rank_ic": fmean(pre),
                "pre2026_median_rank_ic": median(pre),
                "pre2026_positive_ic_rate": sum(x > 0 for x in pre) / len(pre),
                "y2026_mean_rank_ic": fmean(stress) if stress else None,
                "year_2026_used_for_selection": False,
            })
    return monthly, summary


def _coverage(
    variant: str,
    symbols: Sequence[str],
    symbol_contract: str,
    panel: Sequence[PanelRow],
    variant_dir: Path,
) -> dict[str, object]:
    eligible_by_day, _ = _recorded_eligible(variant_dir)
    eligible_keys = {(day, str(row["symbol"])) for day, rows in eligible_by_day.items() for row in rows}
    labeled = [row for row in panel if row.target_rank is not None]
    overlap = sum((row.signal_day, row.symbol) in eligible_keys for row in labeled)
    months = sorted({row.signal_day for row in panel})
    labeled_months = sorted({row.signal_day for row in labeled})
    return {
        "variant_id": variant,
        "variant_symbol_count": len(symbols),
        "variant_symbol_contract": symbol_contract,
        "feature_complete_row_count": len(panel),
        "label_complete_trainable_row_count": len(labeled),
        "portfolio_eligible_overlap_row_count": overlap,
        "trainable_nonportfolio_row_count": len(labeled) - overlap,
        "first_feature_month": months[0].isoformat() if months else None,
        "last_feature_month": months[-1].isoformat() if months else None,
        "first_labeled_month": labeled_months[0].isoformat() if labeled_months else None,
        "last_labeled_month": labeled_months[-1].isoformat() if labeled_months else None,
        "portfolio_eligibility_used_as_training_filter": False,
        "label_contract": "CLOSE_T_TO_CLOSE_T_PLUS_20_BENCHMARK_RELATIVE",
    }


def _focus_rank_audit(rank_rows: Sequence[Mapping[str, object]], variant: str) -> list[dict[str, object]]:
    focus = {"VIC", "NVL", "PNJ", "VPI", "TLG"}
    out = []
    for row in rank_rows:
        day = str(row.get("signal_day"))
        if not day.startswith("2026-03") and not day.startswith("2026-04"):
            continue
        if str(row.get("symbol")) not in focus:
            continue
        out.append({"variant_id": variant, **dict(row), "used_for_selection": False})
    return out


def analyze(
    *,
    v68_output: Path,
    v70_output: Path,
    store: Path,
    output_dir: Path,
    signflip_samples: int = 10_000,
    bootstrap_samples: int = 5_000,
) -> dict[str, object]:
    report70 = json.loads((v70_output / "v70_report.json").read_text(encoding="utf-8-sig"))
    if report70.get("status") != "SUCCESS" or report70.get("champion_model") != CHAMPION_MODEL:
        raise ValueError("V76_V70_BASELINE_INVALID")
    variants_root = v68_output / "variants"
    if not variants_root.is_dir():
        raise ValueError("V76_V68_VARIANTS_MISSING")
    variant_dirs = sorted(path for path in variants_root.iterdir() if path.is_dir())
    all_symbols = _all_store_symbols(store)
    market = v70.load_market(store, all_symbols)
    max_signal = max(
        date.fromisoformat(row["signal_day"])
        for vd in variant_dirs
        for row in _read_csv(vd / "v67_c3_monthly_rankings.csv.gz")
        if row.get("signal_day")
    )

    all_summary: list[dict[str, object]] = []
    all_monthly: list[dict[str, object]] = []
    all_annual: list[dict[str, object]] = []
    all_rolling: list[dict[str, object]] = []
    all_daily: list[dict[str, object]] = []
    all_ledger: list[dict[str, object]] = []
    all_missing: list[dict[str, object]] = []
    all_capital: list[dict[str, object]] = []
    all_rank_rows: list[dict[str, object]] = []
    all_fit_rows: list[dict[str, object]] = []
    all_ic_rows: list[dict[str, object]] = []
    all_rank_ic_monthly: list[dict[str, object]] = []
    all_rank_ic_summary: list[dict[str, object]] = []
    all_capture_monthly: list[dict[str, object]] = []
    all_capture_summary: list[dict[str, object]] = []
    all_coverage: list[dict[str, object]] = []
    all_focus: list[dict[str, object]] = []
    policy_start: dict[str, date] = {}

    for vd in variant_dirs:
        symbols, symbol_contract = _variant_symbols(v68_output, vd, all_symbols)
        panel, ic_rows = _build_panel(market, symbols, end=max_signal)
        all_coverage.append(_coverage(vd.name, symbols, symbol_contract, panel, vd))
        all_ic_rows += [{"variant_id": vd.name, **dict(row)} for row in ic_rows]
        snaps, ranking_rows, fit_rows, starts = build_walkforward_rankings(panel, ic_rows, vd)
        all_rank_rows += [{"variant_id": vd.name, **dict(row)} for row in ranking_rows]
        all_fit_rows += [{"variant_id": vd.name, **dict(row)} for row in fit_rows]
        for policy, start in starts.items():
            policy_start[policy] = max(policy_start.get(policy, start), start)
        _, labels = _recorded_eligible(vd)
        rim, ris = _rank_ic_diagnostics(vd.name, ranking_rows, labels)
        all_rank_ic_monthly += rim
        all_rank_ic_summary += ris
        cm, cs = v75._winner_capture(vd.name, ranking_rows, labels)
        all_capture_monthly += cm
        all_capture_summary += cs
        all_focus += _focus_rank_audit(ranking_rows, vd.name)
        for policy, policy_snaps in sorted(snaps.items()):
            for allocator in ("EQUAL", "INVOL60"):
                result = v75._run_policy(market, policy_snaps, vd.name, policy, allocator, 1.0)
                all_summary += result["summary"]
                all_monthly += result["monthly"]
                all_annual += result["annual"]
                all_rolling += result["rolling"]
                all_daily += result["daily"]
                all_ledger += result["ledger"]
                all_missing += result["missing"]
                all_capital += result["capital"]

    audit = v75._baseline_audit(v70_output, all_summary)
    inference = v75.candidate_inference(
        all_monthly,
        all_daily,
        policy_start,
        signflip_samples=signflip_samples,
        bootstrap_samples=bootstrap_samples,
    )
    shadow = v75._shadow_2026(all_annual, all_monthly)
    watchlist = [row for row in inference if bool(row.get("diagnostic_watchlist_gate_passed"))]

    capture_map = {(str(row["variant_id"]), str(row["policy_id"])): row for row in all_capture_summary}
    robust_models = []
    for policy in MODEL_POLICIES[1:]:
        passes = [row for row in watchlist if str(row.get("policy_id")) == policy]
        clean_capture = capture_map.get(("GAP18_CLEAN", policy))
        capture_ok = bool(
            clean_capture
            and float(clean_capture.get("mean_capture_delta_vs_frozen") or 0.0) > 0.0
            and float(clean_capture.get("mean_contamination_delta_vs_frozen") or 0.0) <= 0.0
        )
        if len({str(row.get("variant_id")) for row in passes}) >= 2 and capture_ok:
            robust_models.append(policy)

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "v76_training_coverage.csv", all_coverage)
    _write_csv(output_dir / "v76_context_ic_history.csv", all_ic_rows)
    _write_csv(output_dir / "v76_model_fit_history.csv", all_fit_rows)
    _write_gz(output_dir / "v76_candidate_rankings.csv.gz", all_rank_rows)
    _write_csv(output_dir / "v76_rank_ic_monthly.csv", all_rank_ic_monthly)
    _write_csv(output_dir / "v76_rank_ic_summary.csv", all_rank_ic_summary)
    _write_csv(output_dir / "v76_winner_capture_monthly.csv", all_capture_monthly)
    _write_csv(output_dir / "v76_winner_capture_summary.csv", all_capture_summary)
    _write_csv(output_dir / "v76_backtest_summary.csv", all_summary)
    _write_csv(output_dir / "v76_monthly_returns.csv", all_monthly)
    _write_csv(output_dir / "v76_annual_returns.csv", all_annual)
    _write_csv(output_dir / "v76_rolling_alpha.csv", all_rolling)
    _write_csv(output_dir / "v76_candidate_inference.csv", inference)
    _write_csv(output_dir / "v76_2026_shadow.csv", shadow)
    _write_csv(output_dir / "v76_focus_rank_audit_2026.csv", all_focus)
    _write_csv(output_dir / "v76_capital_sensitivity.csv", all_capital)
    _write_csv(output_dir / "v76_missing_price_events.csv", all_missing)
    _write_gz(output_dir / "v76_daily_equity_base.csv.gz", all_daily)
    _write_gz(output_dir / "v76_trade_ledger_base.csv.gz", all_ledger)

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "research_only": True,
        "champion_model": CHAMPION_MODEL,
        "champion_replaced": False,
        "challenger_models": list(MODEL_POLICIES[1:]),
        "model_trainable_history_separate_from_portfolio_eligibility": True,
        "c3_training_label": "CLOSE_T_TO_CLOSE_T_PLUS_20_BENCHMARK_RELATIVE",
        "tradable_execution": "NEXT_SESSION_OPEN",
        "walk_forward_protocol": "EXPANDING_PURGED_COMPLETED_LABELS_WITH_PRIOR_3_MONTH_VALIDATION",
        "primary_selection_end": PRIMARY_SELECTION_END.isoformat(),
        "year_2026_used_for_candidate_selection": False,
        "year_2026_completed_labels_may_update_predeclared_online_model_causally": True,
        "baseline_reconstruction_audit": audit,
        "deep_backtest_completed": True,
        "allocators": ["EQUAL", "INVOL60"],
        "cost_scenarios": [cost.name for cost in v70.COSTS],
        "capital_sensitivity_vnd": list(CAPITALS),
        "candidate_inference_count": len(inference),
        "diagnostic_watchlist_count": len(watchlist),
        "diagnostic_watchlist": watchlist,
        "robust_progression_model_count": len(robust_models),
        "robust_progression_models": robust_models,
        "pit_hose_gate_closed": False,
        "price_basis_gate_closed": False,
        "canonical_hose_claim_authorized": False,
        "promotion_authorized": False,
        "automatic_live_orders_allowed": False,
    }
    (output_dir / "v76_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--v68-output", type=Path, required=True)
    parser.add_argument("--v70-output", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--signflip-samples", type=int, default=10_000)
    parser.add_argument("--bootstrap-samples", type=int, default=5_000)
    args = parser.parse_args(argv)
    report = analyze(
        v68_output=args.v68_output,
        v70_output=args.v70_output,
        store=args.store,
        output_dir=args.output_dir,
        signflip_samples=args.signflip_samples,
        bootstrap_samples=args.bootstrap_samples,
    )
    print(json.dumps({
        "status": report["status"],
        "champion_model": report["champion_model"],
        "diagnostic_watchlist_count": report["diagnostic_watchlist_count"],
        "robust_progression_model_count": report["robust_progression_model_count"],
        "promotion_authorized": report["promotion_authorized"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())