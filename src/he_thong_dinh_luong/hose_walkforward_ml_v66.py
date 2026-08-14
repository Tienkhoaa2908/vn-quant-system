"""V66 purged walk-forward ML study on the HOSE master panel.

Research-only. Uses only data/labels available before each test period.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from datetime import date
import gzip
import json
import math
from pathlib import Path
from statistics import fmean, median
from typing import Mapping, Sequence

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from . import hose_master_panel_v66 as panel

SCHEMA_VERSION = "hose_walkforward_ml_v66"
TASKS = ("OPPORTUNITY", "DAMAGE")
LOGISTIC_C_GRID = (0.03, 0.1, 0.3, 1.0, 3.0)
TREE_GRID = (
    (0.03, 7, 30, 1.0), (0.03, 15, 30, 1.0), (0.05, 15, 30, 1.0),
    (0.05, 31, 40, 1.0), (0.08, 15, 40, 2.0), (0.08, 31, 50, 2.0),
)
ABLATIONS = {
    "MOMENTUM_RELATIVE": ("return_5", "return_20", "return_60", "return_120", "relative_5", "relative_20", "relative_60", "relative_120", "cs_rel20", "cs_rel120"),
    "TREND": ("distance_ma10", "distance_ma20", "distance_ma50", "distance_ma100", "distance_ma250", "ma20_slope5", "breakout_20_gap", "breakdown_20_low_gap", "cs_ma20"),
    "RISK": ("drawdown_20", "drawdown_60", "drawdown_250", "realized_vol_10", "realized_vol_20", "realized_vol_60", "vol_ratio_20_60", "range_20", "cs_lowvol", "cs_drawdown20"),
    "LIQUIDITY_VOLUME": ("volume_ratio_5_20", "log_adv20_vnd", "zero_volume_60", "cs_volume", "cs_adv20"),
    "MARKET": ("index_return_20", "index_return_60", "index_distance_ma250"),
    "ALL": panel.FEATURE_FIELDS,
}


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _float(value: object) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("V66_NON_FINITE_MODEL_FIELD")
    return result


def load_panel(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError("V66_PANEL_HEADER_MISSING")
        missing = set(panel.PANEL_FIELDS) - set(reader.fieldnames)
        if missing:
            raise ValueError("V66_PANEL_FIELDS_MISSING:" + "|".join(sorted(missing)))
        for raw in reader:
            if str(raw.get("feature_complete", "")).lower() not in {"true", "1"}:
                continue
            if raw.get("target_opportunity_10") in ("", None) and raw.get("target_damage_10") in ("", None):
                continue
            try:
                item: dict[str, object] = {
                    "signal_day": date.fromisoformat(str(raw["signal_day"])), "symbol": str(raw["symbol"]).upper(),
                    "label_end_20": date.fromisoformat(str(raw["label_end_20"])), "eligible_long": _truthy(raw["eligible_long"]),
                    "liquid_universe": _truthy(raw["liquid_universe"]), "market_risk_on": _truthy(raw["market_risk_on"]),
                    "fwd_excess_10": _float(raw["fwd_excess_10"]), "fwd_return_10": _float(raw["fwd_return_10"]), "mae_10": _float(raw["mae_10"]),
                }
                for field in panel.FEATURE_FIELDS:
                    item[field] = _float(raw[field])
                if raw.get("target_opportunity_10") not in ("", None):
                    item["target_opportunity_10"] = int(raw["target_opportunity_10"])
                if raw.get("target_damage_10") not in ("", None):
                    item["target_damage_10"] = int(raw["target_damage_10"])
            except (TypeError, ValueError):
                continue
            rows.append(item)
    rows.sort(key=lambda row: (row["signal_day"], row["symbol"]))
    if not rows:
        raise ValueError("V66_NO_MODEL_ROWS")
    return rows


def task_rows(rows: Sequence[Mapping[str, object]], task: str) -> list[Mapping[str, object]]:
    if task == "OPPORTUNITY":
        return [row for row in rows if bool(row["eligible_long"]) and "target_opportunity_10" in row]
    if task == "DAMAGE":
        return [row for row in rows if bool(row["liquid_universe"]) and "target_damage_10" in row]
    raise ValueError(task)


def _target_field(task: str) -> str:
    return "target_opportunity_10" if task == "OPPORTUNITY" else "target_damage_10"


def _xy(rows: Sequence[Mapping[str, object]], features: Sequence[str], task: str) -> tuple[np.ndarray, np.ndarray]:
    return (
        np.asarray([[float(row[field]) for field in features] for row in rows], dtype=float),
        np.asarray([int(row[_target_field(task)]) for row in rows], dtype=int),
    )


def _safe_auc(y: np.ndarray, score: np.ndarray) -> float:
    return float(roc_auc_score(y, score)) if len(set(y.tolist())) >= 2 else float("nan")


def _safe_ap(y: np.ndarray, score: np.ndarray) -> float:
    return float(average_precision_score(y, score)) if np.sum(y) > 0 else float("nan")


def _model_metrics(y: np.ndarray, score: np.ndarray) -> dict[str, float]:
    return {"auc": _safe_auc(y, score), "average_precision": _safe_ap(y, score), "brier": float(brier_score_loss(y, score)), "positive_rate": float(np.mean(y))}


def _weekly_top_metrics(rows: Sequence[Mapping[str, object]], score: np.ndarray, task: str, fraction: float = 0.10) -> dict[str, float]:
    by_day: dict[date, list[int]] = defaultdict(list)
    for idx, row in enumerate(rows):
        by_day[row["signal_day"]].append(idx)
    selected: list[int] = []
    for indices in by_day.values():
        count = max(1, int(math.ceil(len(indices) * fraction)))
        selected.extend(sorted(indices, key=lambda i: float(score[i]), reverse=True)[:count])
    if not selected:
        return {"selected_row_count": 0, "weekly_selected_count": 0}
    excess = [float(rows[i]["fwd_excess_10"]) for i in selected]
    returns = [float(rows[i]["fwd_return_10"]) for i in selected]
    mae = [float(rows[i]["mae_10"]) for i in selected]
    labels = [int(rows[i][_target_field(task)]) for i in selected]
    output = {
        "selected_row_count": len(selected), "weekly_selected_count": len(by_day), "selected_target_rate": fmean(labels),
        "selected_mean_fwd_excess_10": fmean(excess), "selected_median_fwd_excess_10": median(excess),
        "selected_excess_positive_rate": sum(value > 0 for value in excess) / len(excess),
        "selected_mean_fwd_return_10": fmean(returns), "selected_median_mae_10": median(mae),
    }
    if task == "DAMAGE":
        positives = sum(int(row[_target_field(task)]) for row in rows)
        output["damage_recall_top_decile"] = sum(labels) / positives if positives else 0.0
    return output


def _logistic(C: float) -> Pipeline:
    return Pipeline([
        ("scale", StandardScaler()),
        ("model", LogisticRegression(C=C, max_iter=3000, solver="lbfgs", class_weight="balanced", random_state=20260814)),
    ])


def _tree(params: tuple[float, int, int, float]) -> HistGradientBoostingClassifier:
    learning_rate, leaves, min_leaf, l2 = params
    return HistGradientBoostingClassifier(
        learning_rate=learning_rate, max_iter=250, max_leaf_nodes=leaves, min_samples_leaf=min_leaf,
        l2_regularization=l2, early_stopping=True, validation_fraction=0.15, n_iter_no_change=20, random_state=20260814,
    )


def _choose_logistic(train: Sequence[Mapping[str, object]], validation: Sequence[Mapping[str, object]], features: Sequence[str], task: str) -> tuple[float, list[dict[str, object]]]:
    x_train, y_train = _xy(train, features, task); x_val, y_val = _xy(validation, features, task)
    trials: list[dict[str, object]] = []
    best: tuple[float, float, float] | None = None; best_c = LOGISTIC_C_GRID[0]
    for C in LOGISTIC_C_GRID:
        model = _logistic(C); model.fit(x_train, y_train); score = model.predict_proba(x_val)[:, 1]
        auc, ap = _safe_auc(y_val, score), _safe_ap(y_val, score)
        criterion = (-1.0 if not math.isfinite(auc) else auc, -1.0 if not math.isfinite(ap) else ap, -abs(math.log10(C)))
        trials.append({"C": C, "validation_auc": auc, "validation_ap": ap})
        if best is None or criterion > best:
            best, best_c = criterion, C
    return best_c, trials


def _choose_tree(train: Sequence[Mapping[str, object]], validation: Sequence[Mapping[str, object]], features: Sequence[str], task: str) -> tuple[tuple[float, int, int, float], list[dict[str, object]]]:
    x_train, y_train = _xy(train, features, task); x_val, y_val = _xy(validation, features, task)
    trials: list[dict[str, object]] = []
    best_key: tuple[float, float, float] | None = None; best_params = TREE_GRID[0]
    for params in TREE_GRID:
        model = _tree(params); model.fit(x_train, y_train); score = model.predict_proba(x_val)[:, 1]
        auc, ap = _safe_auc(y_val, score), _safe_ap(y_val, score)
        key = (-1.0 if not math.isfinite(auc) else auc, -1.0 if not math.isfinite(ap) else ap, -params[1])
        trials.append({"learning_rate": params[0], "max_leaf_nodes": params[1], "min_samples_leaf": params[2], "l2_regularization": params[3], "validation_auc": auc, "validation_ap": ap})
        if best_key is None or key > best_key:
            best_key, best_params = key, params
    return best_params, trials


def _folds(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    years = sorted({row["signal_day"].year for row in rows})
    output: list[dict[str, object]] = []
    for test_year in years:
        prior = [year for year in years if year < test_year]
        if len(prior) < 4:
            continue
        validation_year = prior[-1]
        test_rows = [row for row in rows if row["signal_day"].year == test_year]
        if len({row["signal_day"] for row in test_rows}) < 10:
            continue
        test_start = min(row["signal_day"] for row in test_rows)
        val_rows = [row for row in rows if row["signal_day"].year == validation_year and row["label_end_20"] < test_start]
        if len({row["signal_day"] for row in val_rows}) < 10:
            continue
        val_start = min(row["signal_day"] for row in val_rows)
        train_rows = [row for row in rows if row["signal_day"].year < validation_year and row["label_end_20"] < val_start]
        if len(train_rows) < 200:
            continue
        output.append({"test_year": test_year, "validation_year": validation_year, "train": train_rows, "validation": val_rows, "test": test_rows})
    return output


def _calibration_bins(rows: Sequence[Mapping[str, object]], scores: Sequence[float], task: str, bins: int = 10) -> list[dict[str, object]]:
    order = np.argsort(np.asarray(scores)); chunks = np.array_split(order, bins); output = []
    for i, chunk in enumerate(chunks, start=1):
        if len(chunk) == 0:
            continue
        ys = [int(rows[int(idx)][_target_field(task)]) for idx in chunk]
        sc = [float(scores[int(idx)]) for idx in chunk]
        excess = [float(rows[int(idx)]["fwd_excess_10"]) for idx in chunk]
        output.append({"bin": i, "row_count": len(chunk), "mean_score": fmean(sc), "target_rate": fmean(ys), "mean_fwd_excess_10": fmean(excess)})
    return output


def _baseline_score(rows: Sequence[Mapping[str, object]], task: str) -> np.ndarray:
    if task == "OPPORTUNITY":
        return np.asarray([(float(row["cs_rel20"]) + float(row["cs_rel120"]) + float(row["cs_volume"]) + float(row["cs_ma20"])) / 4.0 for row in rows])
    return np.asarray([((1.0 - float(row["cs_rel20"])) + (1.0 - float(row["cs_drawdown20"])) + max(0.0, -float(row["distance_ma20"]) * 5.0) + max(0.0, float(row["vol_ratio_20_60"]) - 1.0)) for row in rows])


def run_task(rows: Sequence[Mapping[str, object]], task: str) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    task_data = task_rows(rows, task); folds = _folds(task_data)
    if not folds:
        raise ValueError(f"V66_NO_WALKFORWARD_FOLDS:{task}")
    fold_results: list[dict[str, object]] = []; trials: list[dict[str, object]] = []; coefficients: list[dict[str, object]] = []; calibration: list[dict[str, object]] = []; ablations: list[dict[str, object]] = []
    for fold in folds:
        train, val, test = fold["train"], fold["validation"], fold["test"]
        fit_rows = list(train) + list(val); test_year = int(fold["test_year"])
        best_c, log_trials = _choose_logistic(train, val, panel.FEATURE_FIELDS, task)
        best_tree, tree_trials = _choose_tree(train, val, panel.FEATURE_FIELDS, task)
        trials.extend({"task": task, "test_year": test_year, "model": "LOGISTIC", **item} for item in log_trials)
        trials.extend({"task": task, "test_year": test_year, "model": "HIST_GB", **item} for item in tree_trials)
        x_fit, y_fit = _xy(fit_rows, panel.FEATURE_FIELDS, task); x_test, y_test = _xy(test, panel.FEATURE_FIELDS, task)
        log_model = _logistic(best_c); log_model.fit(x_fit, y_fit); log_score = log_model.predict_proba(x_test)[:, 1]
        tree_model = _tree(best_tree); tree_model.fit(x_fit, y_fit); tree_score = tree_model.predict_proba(x_test)[:, 1]
        baseline = _baseline_score(test, task)
        for model_name, score in (("LOGISTIC", log_score), ("HIST_GB", tree_score), ("HEURISTIC_BASELINE", baseline)):
            metrics = _model_metrics(y_test, score) if model_name != "HEURISTIC_BASELINE" else {"auc": _safe_auc(y_test, score), "average_precision": _safe_ap(y_test, score), "brier": float("nan"), "positive_rate": float(np.mean(y_test))}
            top = _weekly_top_metrics(test, score, task)
            fold_results.append({
                "task": task, "test_year": test_year, "validation_year": int(fold["validation_year"]), "model": model_name,
                "train_row_count": len(train), "validation_row_count": len(val), "test_row_count": len(test),
                "train_last_label_end": max(row["label_end_20"] for row in train).isoformat(), "test_first_signal_day": min(row["signal_day"] for row in test).isoformat(),
                "purge_ok": max(row["label_end_20"] for row in fit_rows) < min(row["signal_day"] for row in test),
                "selected_logistic_C": best_c if model_name == "LOGISTIC" else "", "selected_tree_params": "|".join(map(str, best_tree)) if model_name == "HIST_GB" else "",
                **metrics, **top,
            })
            calibration.extend({"task": task, "test_year": test_year, "model": model_name, **item} for item in _calibration_bins(test, score, task))
        for field, value in zip(panel.FEATURE_FIELDS, log_model.named_steps["model"].coef_[0]):
            coefficients.append({"task": task, "test_year": test_year, "feature": field, "standardized_coefficient": float(value)})
        for ablation_name, fields in ABLATIONS.items():
            model = _logistic(best_c); xa_fit, ya_fit = _xy(fit_rows, fields, task); xa_test, ya_test = _xy(test, fields, task)
            model.fit(xa_fit, ya_fit); score = model.predict_proba(xa_test)[:, 1]
            ablations.append({"task": task, "test_year": test_year, "ablation": ablation_name, "feature_count": len(fields), "auc": _safe_auc(ya_test, score), "average_precision": _safe_ap(ya_test, score), **_weekly_top_metrics(test, score, task)})
    return fold_results, trials, coefficients, calibration, ablations


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        return
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n"); writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _summary(folds: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in folds:
        grouped[(str(row["task"]), str(row["model"]))].append(row)
    output = []
    for (task, model), items in sorted(grouped.items()):
        aucs = [float(row["auc"]) for row in items if math.isfinite(float(row["auc"]))]; aps = [float(row["average_precision"]) for row in items if math.isfinite(float(row["average_precision"]))]
        excess = [float(row["selected_mean_fwd_excess_10"]) for row in items]; target_rate = [float(row["selected_target_rate"]) for row in items]
        output.append({
            "task": task, "model": model, "fold_count": len(items), "median_auc": median(aucs) if aucs else "", "mean_auc": fmean(aucs) if aucs else "",
            "median_average_precision": median(aps) if aps else "", "median_selected_mean_fwd_excess_10": median(excess),
            "positive_selected_excess_year_count": sum(value > 0 for value in excess), "median_selected_target_rate": median(target_rate),
            "all_purge_checks_pass": all(bool(row["purge_ok"]) for row in items),
        })
    return output


def run_study(*, panel_path: Path, output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True); rows = load_panel(panel_path)
    all_folds: list[dict[str, object]] = []; all_trials: list[dict[str, object]] = []; all_coef: list[dict[str, object]] = []; all_cal: list[dict[str, object]] = []; all_ablation: list[dict[str, object]] = []
    for task in TASKS:
        folds, trials, coefficients, calibration, ablations = run_task(rows, task)
        all_folds.extend(folds); all_trials.extend(trials); all_coef.extend(coefficients); all_cal.extend(calibration); all_ablation.extend(ablations)
    summary = _summary(all_folds)
    _write_csv(output_dir / "v66_walkforward_folds.csv", all_folds); _write_csv(output_dir / "v66_hyperparameter_trials.csv", all_trials)
    _write_csv(output_dir / "v66_logistic_coefficients.csv", all_coef); _write_csv(output_dir / "v66_calibration_bins.csv", all_cal)
    _write_csv(output_dir / "v66_feature_family_ablations.csv", all_ablation); _write_csv(output_dir / "v66_model_summary.csv", summary)
    dates = [row["signal_day"] for row in rows]
    report = {
        "schema_version": SCHEMA_VERSION, "status": "SUCCESS", "panel_path": str(panel_path), "model_row_count": len(rows), "distinct_symbol_count": len({row["symbol"] for row in rows}),
        "first_signal_day": min(dates).isoformat(), "last_signal_day": max(dates).isoformat(), "tasks": list(TASKS), "models": ["LOGISTIC", "HIST_GB", "HEURISTIC_BASELINE"],
        "hyperparameter_selection": "INNER_TIME_VALIDATION_ONLY", "walkforward": "EXPANDING_PURGED_BY_LABEL_END", "random_cross_validation_used": False,
        "future_test_rows_used_for_fit": False, "feature_family_ablations": list(ABLATIONS), "master_panel_is_primary_ml_input": True, "v22_used_as_training_input": False,
        "research_only": True, "automatic_live_orders_allowed": False,
        "limitations": [
            "corporate-action and price-basis lineage must be interpreted with the panel data audit",
            "historical data has been repeatedly observed in prior research; this is walk-forward evidence, not pristine untouched OOS",
            "portfolio sizing and simultaneous action policy are intentionally deferred",
            "HistGradientBoosting is a nonlinear sklearn benchmark; LightGBM promotion is deferred until the HOSE panel passes data-lineage audit",
        ],
        "summary": summary,
    }
    (output_dir / "v66_ml_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--panel", type=Path, required=True); parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv); report = run_study(panel_path=args.panel, output_dir=args.output_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
