"""LightGBM champion-challenger và publication cho forward prediction."""
from __future__ import annotations

import argparse
import csv
import json
from io import StringIO
from pathlib import Path
from typing import Callable, Mapping, Sequence
from zipfile import ZIP_DEFLATED, ZipFile

from .du_doan_tien_phuong_contract import GRID, SCHEMA_VERSION, Metrics, Row, _hash_file, _load_rows, _load_verified_input
from .du_doan_tien_phuong_features import _group_sizes, _matrix, _metrics, _rank, _relevance, _split_history

RankerFactory = Callable[[Mapping[str, object]], object]

def _default_ranker_factory(params: Mapping[str, object]) -> object:
    try:
        from lightgbm import LGBMRanker
    except ImportError as exc:
        raise ValueError("LIGHTGBM_NOT_INSTALLED: chay bang uv run --with lightgbm==4.6.0") from exc
    return LGBMRanker(**dict(params))

def _fit(model: object, train_rows: Sequence[Row], validation_rows: Sequence[Row] | None, *, top_k: int) -> tuple[list[float] | None, int | None]:
    train_x_raw, _ = _matrix(train_rows)
    train_y_raw = _relevance(train_rows)
    try:
        import numpy as np
    except ImportError as exc:
        raise ValueError("NUMPY_NOT_INSTALLED") from exc
    train_x = np.asarray(train_x_raw, dtype=float)
    train_y = np.asarray(train_y_raw, dtype=int)
    kwargs: dict[str, object] = {"group": _group_sizes(train_rows)}
    if validation_rows:
        validation_x_raw, _ = _matrix(validation_rows)
        validation_y_raw = _relevance(validation_rows)
        validation_x = np.asarray(validation_x_raw, dtype=float)
        validation_y = np.asarray(validation_y_raw, dtype=int)
        try:
            from lightgbm import early_stopping, log_evaluation
        except ImportError:
            callbacks: list[object] = []
        else:
            callbacks = [early_stopping(40, verbose=False), log_evaluation(0)]
        kwargs.update({"eval_set": [(validation_x, validation_y)], "eval_group": [_group_sizes(validation_rows)], "eval_at": [top_k], "callbacks": callbacks})
    model.fit(train_x, train_y, **kwargs)
    best_iteration = getattr(model, "best_iteration_", None)
    if validation_rows:
        validation_x_raw, _ = _matrix(validation_rows)
        validation_x = np.asarray(validation_x_raw, dtype=float)
        predictions = model.predict(validation_x, num_iteration=best_iteration if best_iteration else None)
        return [float(value) for value in predictions], int(best_iteration) if best_iteration else None
    return None, int(best_iteration) if best_iteration else None

def _grid_search(train_rows: Sequence[Row], validation_rows: Sequence[Row], *, top_k: int, seed: int, factory: RankerFactory) -> tuple[dict[str, object], Metrics, list[dict[str, object]]]:
    records: list[dict[str, object]] = []
    best: tuple[tuple[float, float, float, float, int], dict[str, object], Metrics] | None = None
    for index, raw in enumerate(GRID):
        params: dict[str, object] = {"objective": "lambdarank", "n_estimators": 400, "random_state": seed, "verbosity": -1, **raw}
        model = factory(params)
        predictions, best_iteration = _fit(model, train_rows, validation_rows, top_k=top_k)
        assert predictions is not None
        metrics = _metrics(validation_rows, predictions, top_k)
        records.append({"candidate": index + 1, "params": params, "best_iteration": best_iteration, "metrics": metrics.as_dict()})
        key = (metrics.mean_rank_ic, metrics.top_k_relative_return, metrics.precision_at_k, -metrics.mean_set_turnover, -int(raw["num_leaves"]))
        if best is None or key > best[0]:
            best = (key, dict(params), metrics)
    assert best is not None
    return best[1], best[2], records

def _champion(challenger: Metrics, momentum: Metrics) -> tuple[str, dict[str, bool]]:
    turnover_limit = min(1.0, 1.5 * max(momentum.mean_set_turnover, 0.01))
    checks = {
        "rank_ic_positive": challenger.mean_rank_ic > 0.0,
        "rank_ic_beats_momentum": challenger.mean_rank_ic > momentum.mean_rank_ic,
        "top_k_return_beats_momentum": challenger.top_k_relative_return > momentum.top_k_relative_return,
        "precision_not_worse": challenger.precision_at_k >= momentum.precision_at_k,
        "turnover_within_limit": challenger.mean_set_turnover <= turnover_limit,
    }
    return ("lightgbm_ranker" if all(checks.values()) else "momentum_baseline", checks)

def _regime(forward_rows: Sequence[Row]) -> tuple[str, int, str]:
    first = forward_rows[0].features
    above = first["vnindex_tren_ma250"] >= 0.5
    momentum = first["vnindex_momentum_60"]
    if above and momentum > 0.0:
        return "RISK_ON", 100, "TECHNICAL_HEURISTIC_NOT_VALIDATED"
    if above or momentum > 0.0:
        return "NEUTRAL", 50, "TECHNICAL_HEURISTIC_NOT_VALIDATED"
    return "RISK_OFF", 25, "TECHNICAL_HEURISTIC_NOT_VALIDATED"

def _csv_text(rows: Sequence[Mapping[str, object]], fields: Sequence[str]) -> str:
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    return buffer.getvalue()

def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

def run_forward_prediction(*, input_zip: Path, output_dir: Path, top_k: int = 10, validation_months: int = 12, seed: int = 20260730, ranker_factory: RankerFactory | None = None) -> dict[str, object]:
    if top_k <= 0:
        raise ValueError("TOP_K_MUST_BE_POSITIVE")
    destination = Path(output_dir)
    if destination.exists():
        raise FileExistsError("OUTPUT_DIR_EXISTS")
    blobs, input_manifest, input_sha = _load_verified_input(Path(input_zip))
    history, forward_rows, forward_day = _load_rows(blobs)
    train_rows, validation_rows, validation_start = _split_history(history, validation_months)
    factory = ranker_factory or _default_ranker_factory
    best_params, lgbm_metrics, grid_records = _grid_search(train_rows, validation_rows, top_k=top_k, seed=seed, factory=factory)
    momentum_validation = [row.features["dong_luong_12_1"] for row in validation_rows]
    momentum_metrics = _metrics(validation_rows, momentum_validation, top_k)
    champion, gate_checks = _champion(lgbm_metrics, momentum_metrics)
    final_rows = [row for row in history if row.label_end is not None and row.label_end < forward_day]
    final_model = factory(best_params)
    _fit(final_model, final_rows, None, top_k=top_k)
    forward_x_raw, feature_names = _matrix(forward_rows)
    try:
        import numpy as np
    except ImportError as exc:
        raise ValueError("NUMPY_NOT_INSTALLED") from exc
    forward_x = np.asarray(forward_x_raw, dtype=float)
    best_iteration = getattr(final_model, "best_iteration_", None)
    lgbm_raw = [float(value) for value in final_model.predict(forward_x, num_iteration=best_iteration if best_iteration else None)]
    momentum_raw = [row.features["dong_luong_12_1"] for row in forward_rows]
    lgbm_percentile = _rank(lgbm_raw)
    momentum_percentile = _rank(momentum_raw)
    champion_scores = lgbm_percentile if champion == "lightgbm_ranker" else momentum_percentile
    ensemble = [0.7 * lgbm + 0.3 * momentum for lgbm, momentum in zip(lgbm_percentile, momentum_percentile)]
    ordered = sorted(range(len(forward_rows)), key=lambda index: (-champion_scores[index], forward_rows[index].ma))
    rank_by_index = {index: rank + 1 for rank, index in enumerate(ordered)}
    regime, capital_budget, regime_note = _regime(forward_rows)
    selected_count = min(top_k, len(forward_rows))
    per_name_weight = capital_budget / selected_count if selected_count else 0.0
    output_rows: list[dict[str, object]] = []
    for index in ordered:
        row = forward_rows[index]
        rank = rank_by_index[index]
        selected = rank <= top_k
        output_rows.append({
            "signal_date": row.ngay.isoformat(),
            "symbol": row.ma,
            "champion_model": champion,
            "champion_score": format(champion_scores[index], ".12g"),
            "champion_rank": rank,
            "selected_top_k": str(selected).lower(),
            "technical_weight_pct": format(per_name_weight, ".12g") if selected else "0",
            "lightgbm_score_raw": format(lgbm_raw[index], ".12g"),
            "lightgbm_percentile": format(lgbm_percentile[index], ".12g"),
            "momentum_12_1": format(momentum_raw[index], ".12g"),
            "momentum_percentile": format(momentum_percentile[index], ".12g"),
            "ensemble_score": format(ensemble[index], ".12g"),
            "above_ma250": str(row.features["gia_tren_ma250"] >= 0.5).lower(),
            "relative_strength_120": format(row.features["suc_manh_tuong_doi_120"], ".12g"),
            "market_regime": regime,
            "capital_budget_pct": capital_budget,
            "capital_budget_note": regime_note,
            "research_eligible": "false",
        })
    logistic_metrics = json.loads(blobs["chi_so_mo_hinh.json"])
    comparison = {
        "schema_version": SCHEMA_VERSION,
        "signal_date": forward_day.isoformat(),
        "validation_start": validation_start.isoformat(),
        "validation_months": validation_months,
        "top_k": top_k,
        "champion_model": champion,
        "champion_gate_checks": gate_checks,
        "momentum_validation": momentum_metrics.as_dict(),
        "lightgbm_validation": lgbm_metrics.as_dict(),
        "lightgbm_grid": grid_records,
        "selected_lightgbm_params": best_params,
        "legacy_model_metrics": logistic_metrics,
        "feature_names": list(feature_names),
        "training_row_count": len(final_rows),
        "forward_candidate_count": len(forward_rows),
        "market_regime": regime,
        "capital_budget_pct": capital_budget,
        "capital_budget_note": regime_note,
        "input_zip_sha256": input_sha,
        "input_manifest_schema": input_manifest.get("manifest_schema_version"),
        "technical_validation_only": True,
        "research_eligible": False,
        "limitations": ["technical_candidate_union_not_point_in_time", "price_basis_unconfirmed", "corporate_action_inventory_incomplete", "capital_budget_is_unvalidated_heuristic"],
    }
    top_symbols = [forward_rows[index].ma for index in ordered[:top_k]]
    summary = "\n".join([
        f"Signal date: {forward_day.isoformat()}",
        f"Champion: {champion}",
        f"Market regime: {regime}",
        f"Technical capital budget: {capital_budget}%",
        f"Top {top_k}: {', '.join(top_symbols)}",
        f"LightGBM validation: Rank IC={lgbm_metrics.mean_rank_ic:.6f}, Precision@K={lgbm_metrics.precision_at_k:.6f}, Top-K relative return={lgbm_metrics.top_k_relative_return:.6f}",
        f"Momentum validation: Rank IC={momentum_metrics.mean_rank_ic:.6f}, Precision@K={momentum_metrics.precision_at_k:.6f}, Top-K relative return={momentum_metrics.top_k_relative_return:.6f}",
        "Research eligible: false",
        "Use: technical ranking only; not an investment recommendation.",
        "",
    ])
    destination.mkdir(parents=True)
    predictions_path = destination / "latest_prediction.csv"
    comparison_path = destination / "model_comparison.json"
    summary_path = destination / "prediction_summary.txt"
    predictions_path.write_text(_csv_text(output_rows, tuple(output_rows[0])), encoding="utf-8-sig")
    _write_json(comparison_path, comparison)
    summary_path.write_text(summary, encoding="utf-8")
    file_hashes = {path.name: {"sha256": _hash_file(path), "size": path.stat().st_size} for path in (predictions_path, comparison_path, summary_path)}
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "input_zip_sha256": input_sha,
        "files": file_hashes,
        "champion_model": champion,
        "signal_date": forward_day.isoformat(),
        "technical_validation_only": True,
        "research_eligible": False,
    }
    manifest_path = destination / "manifest.json"
    _write_json(manifest_path, manifest)
    archive_path = destination / "forward_prediction_output.zip"
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        for path in (predictions_path, comparison_path, summary_path, manifest_path):
            archive.write(path, arcname=path.name)
    return {
        "status": "SUCCESS",
        "signal_date": forward_day.isoformat(),
        "champion_model": champion,
        "market_regime": regime,
        "capital_budget_pct": capital_budget,
        "top_symbols": top_symbols,
        "output_zip": str(archive_path),
    }

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m he_thong_dinh_luong.nghien_cuu_moc_4.du_doan_tien_phuong")
    parser.add_argument("--input-zip", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--validation-months", type=int, default=12)
    parser.add_argument("--seed", type=int, default=20260730)
    return parser

def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_forward_prediction(input_zip=args.input_zip, output_dir=args.output_dir, top_k=args.top_k, validation_months=args.validation_months, seed=args.seed)
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "error": str(exc)}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
