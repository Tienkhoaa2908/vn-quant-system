"""Quality-gated wrapper around the Model Lab runner.

The legacy runner remains responsible for leakage-safe training and backtesting.
This module audits its complete outputs before publication, rejects degenerate
scores, prevents contaminated ensembles, and suppresses a forward watchlist when
no model passes the research gate.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from hashlib import sha256
from io import StringIO
import json
from math import isfinite
from pathlib import Path
from statistics import fmean, pstdev
from typing import Mapping, Sequence
from zipfile import ZIP_DEFLATED, ZipFile

from .model_lab_core import ENSEMBLE_MODEL, ModelEvaluation, select_research_champion
from .model_lab_runner import run_model_lab as run_legacy_model_lab

QUALITY_SCHEMA = "vn_quant_model_lab_quality_v2"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]], fields: Sequence[str]) -> None:
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    path.write_text(buffer.getvalue(), encoding="utf-8-sig", newline="")


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def score_diagnostics(values: Sequence[float]) -> dict[str, object]:
    numbers = [float(value) for value in values]
    finite = [value for value in numbers if isfinite(value)]
    unique = len(set(finite))
    span = max(finite) - min(finite) if finite else 0.0
    dispersion = pstdev(finite) if len(finite) > 1 else 0.0
    degenerate = (
        len(finite) != len(numbers)
        or len(numbers) < 2
        or unique < 2
        or span <= 1e-12
        or dispersion <= 1e-13
    )
    return {
        "count": len(numbers),
        "finite_count": len(finite),
        "unique_count": unique,
        "range": span,
        "std": dispersion,
        "degenerate": degenerate,
    }


def _model_score_audit(
    oos_rows: Sequence[Mapping[str, str]],
    forward_rows: Sequence[Mapping[str, str]],
) -> dict[str, dict[str, object]]:
    by_fold: dict[tuple[str, str], list[float]] = {}
    for row in oos_rows:
        key = (str(row.get("model") or ""), str(row.get("test_date") or ""))
        try:
            by_fold.setdefault(key, []).append(float(row.get("score") or 0.0))
        except ValueError:
            by_fold.setdefault(key, []).append(float("nan"))
    forward: dict[str, list[float]] = {}
    for row in forward_rows:
        name = str(row.get("model") or "")
        try:
            forward.setdefault(name, []).append(float(row.get("score") or 0.0))
        except ValueError:
            forward.setdefault(name, []).append(float("nan"))
    models = sorted({name for name, _ in by_fold} | set(forward))
    result: dict[str, dict[str, object]] = {}
    for model in models:
        folds = [score_diagnostics(values) for (name, _), values in by_fold.items() if name == model]
        bad = sum(1 for item in folds if item["degenerate"])
        forward_diag = score_diagnostics(forward.get(model, ())) if model in forward else {
            "count": 0, "finite_count": 0, "unique_count": 0,
            "range": 0.0, "std": 0.0, "degenerate": True,
        }
        ratio = bad / len(folds) if folds else 1.0
        result[model] = {
            "fold_count": len(folds),
            "degenerate_fold_count": bad,
            "degenerate_fold_ratio": ratio,
            "oos_status": "DEGENERATE" if ratio > 0.10 else "PASS",
            "forward": forward_diag,
            "forward_status": "DEGENERATE" if forward_diag["degenerate"] else "PASS",
        }
    return result


def _grade(evaluations: Mapping[str, ModelEvaluation], champion: str) -> str:
    if champion == "NO_MODEL_APPROVED":
        return "RED_NO_PREDICTIVE_VALUE"
    selected = evaluations[champion]
    rank_ic = float(selected.metrics.get("mean_rank_ic", 0.0) or 0.0)
    excess = float(selected.backtest.get("average_net_excess_return", 0.0) or 0.0)
    stable = float(selected.metrics.get("positive_rank_ic_ratio", 0.0) or 0.0)
    if rank_ic >= 0.03 and excess > 0.0 and stable >= 0.60:
        return "GREEN_PAPER_CANDIDATE"
    return "YELLOW_WEAK_POSITIVE_EVIDENCE"


def _rebuild_manifest_and_zip(output: Path, summary: Mapping[str, object]) -> None:
    archive = output / "model_lab_output.zip"
    if archive.exists():
        archive.unlink()
    manifest_path = output / "manifest.json"
    if manifest_path.exists():
        manifest_path.unlink()
    files: dict[str, dict[str, object]] = {}
    for path in sorted(output.iterdir()):
        if not path.is_file() or path.name in {"manifest.json", "model_lab_output.zip"}:
            continue
        payload = path.read_bytes()
        files[path.name] = {"sha256": sha256(payload).hexdigest(), "size": len(payload)}
    manifest = {
        "schema_version": QUALITY_SCHEMA,
        "status": "SUCCESS",
        "signal_date": summary.get("signal_date"),
        "research_champion": summary.get("research_champion"),
        "evidence_grade": summary.get("evidence_grade"),
        "forward_watchlist_published": summary.get("forward_watchlist_published"),
        "live_capital_approved": False,
        "credentials_recorded": False,
        "files": files,
    }
    _write_json(manifest_path, manifest)
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as zipped:
        for path in sorted(output.iterdir()):
            if path.is_file() and path != archive:
                zipped.write(path, arcname=path.name)


def audit_and_republish(output_dir: Path) -> dict[str, object]:
    output = Path(output_dir)
    summary_path = output / "model_lab_summary.json"
    leaderboard_path = output / "model_leaderboard.csv"
    oos_path = output / "oos_predictions.csv"
    forward_path = output / "forward_model_scores.csv"
    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    leaderboard = _read_csv(leaderboard_path)
    oos_rows = _read_csv(oos_path)
    forward_rows = _read_csv(forward_path)
    audit = _model_score_audit(oos_rows, forward_rows)

    raw_evaluations = summary.get("evaluations") if isinstance(summary.get("evaluations"), Mapping) else {}
    evaluations: dict[str, ModelEvaluation] = {}
    for name, raw in raw_evaluations.items():
        item = raw if isinstance(raw, Mapping) else {}
        status = str(item.get("status") or "FAILED")
        error = str(item.get("error") or "") or None
        score_state = audit.get(str(name), {})
        if score_state.get("oos_status") == "DEGENERATE":
            status = "DEGENERATE"
            error = "DEGENERATE_OOS_SCORE"
        evaluations[str(name)] = ModelEvaluation(
            model=str(name),
            status=status,
            metrics=item.get("metrics") if isinstance(item.get("metrics"), Mapping) else {},
            backtest=item.get("backtest") if isinstance(item.get("backtest"), Mapping) else {},
            gate=item.get("gate") if isinstance(item.get("gate"), Mapping) else {},
            error=error,
        )

    positive_components = []
    for name, evaluation in evaluations.items():
        if name == ENSEMBLE_MODEL or evaluation.status != "SUCCESS":
            continue
        score_state = audit.get(name, {})
        if score_state.get("forward_status") != "PASS":
            continue
        mean_ic = float(evaluation.metrics.get("mean_rank_ic", 0.0) or 0.0)
        stable = float(evaluation.metrics.get("positive_rank_ic_ratio", 0.0) or 0.0)
        if mean_ic > 0.0 and stable >= 0.50:
            positive_components.append(name)
    ensemble = evaluations.get(ENSEMBLE_MODEL)
    if ensemble is not None and len(positive_components) < 2:
        evaluations[ENSEMBLE_MODEL] = ModelEvaluation(
            ENSEMBLE_MODEL,
            "DISQUALIFIED",
            ensemble.metrics,
            ensemble.backtest,
            {key: False for key in ensemble.gate} or {"positive_component_count": False},
            "ENSEMBLE_REQUIRES_AT_LEAST_TWO_POSITIVE_COMPONENTS",
        )

    champion, reason = select_research_champion(evaluations)
    if champion != "NO_MODEL_APPROVED":
        state = audit.get(champion, {})
        if state.get("forward_status") != "PASS":
            champion = "NO_MODEL_APPROVED"
            reason = "CHAMPION_FORWARD_SCORE_DEGENERATE"
    grade = _grade(evaluations, champion)
    reference = champion if champion != "NO_MODEL_APPROVED" else "NO_MODEL_APPROVED"
    top_k = int((summary.get("backtest_contract") or {}).get("top_k", 10))

    for row in forward_rows:
        original = str(row.get("selected_top_k") or "false").lower()
        row["diagnostic_top_k"] = original
        name = str(row.get("model") or "")
        approved = champion != "NO_MODEL_APPROVED" and name == champion
        try:
            rank = int(float(row.get("rank") or 10**9))
        except ValueError:
            rank = 10**9
        row["selected_top_k"] = str(approved and rank <= top_k).lower()
        row["research_approved"] = str(approved).lower()
        row["reference_model"] = reference
        row["research_champion"] = champion
        row["quality_status"] = (
            audit.get(name, {}).get("oos_status")
            if audit.get(name, {}).get("oos_status") != "PASS"
            else audit.get(name, {}).get("forward_status", "UNKNOWN")
        )
    forward_fields = list(forward_rows[0].keys()) if forward_rows else []
    _write_csv(forward_path, forward_rows, forward_fields)

    leaderboard_by_name = {str(row.get("model") or ""): row for row in leaderboard}
    for name, evaluation in evaluations.items():
        row = leaderboard_by_name.get(name)
        if row is None:
            continue
        row["status"] = evaluation.status
        row["error"] = evaluation.error or ""
        row["gate_passed"] = str(
            evaluation.status == "SUCCESS" and bool(evaluation.gate) and all(evaluation.gate.values())
        ).lower()
        state = audit.get(name, {})
        row["degenerate_fold_ratio"] = state.get("degenerate_fold_ratio", "")
        row["forward_score_status"] = state.get("forward_status", "UNKNOWN")
    leaderboard_fields = list(leaderboard[0].keys()) if leaderboard else []
    _write_csv(leaderboard_path, leaderboard, leaderboard_fields)

    summary["schema_version"] = QUALITY_SCHEMA
    summary["research_champion"] = champion
    summary["champion_reason"] = reason
    summary["reference_model_for_forward_watchlist"] = reference
    summary["forward_watchlist_published"] = champion != "NO_MODEL_APPROVED"
    summary["evidence_grade"] = grade
    summary["deployment_status"] = "PAPER_ONLY" if champion != "NO_MODEL_APPROVED" else "NO_MODEL_APPROVED"
    summary["live_capital_approved"] = False
    summary["research_eligible"] = False
    summary["score_quality_audit"] = audit
    summary["ensemble_positive_components"] = positive_components
    summary["quality_gate_contract"] = {
        "degenerate_oos_fold_ratio_max": 0.10,
        "forward_score_must_vary": True,
        "ensemble_minimum_positive_components": 2,
        "no_fallback_reference_when_gate_fails": True,
    }
    summary["evaluations"] = {
        name: {
            "status": evaluation.status,
            "metrics": dict(evaluation.metrics),
            "backtest": dict(evaluation.backtest),
            "gate": dict(evaluation.gate),
            "error": evaluation.error,
        }
        for name, evaluation in evaluations.items()
    }
    _write_json(summary_path, summary)
    _write_json(output / "score_quality_audit.json", {
        "schema_version": QUALITY_SCHEMA,
        "status": "PASS" if not any(
            item.get("oos_status") == "DEGENERATE" for item in audit.values()
        ) else "DEGENERATE_MODELS_REJECTED",
        "models": audit,
        "positive_ensemble_components": positive_components,
        "research_champion": champion,
        "forward_watchlist_published": champion != "NO_MODEL_APPROVED",
    })
    report = [
        "VN QUANT MODEL LAB — QUALITY GATE V2",
        f"Signal date: {summary.get('signal_date')}",
        f"Research champion: {champion}",
        f"Reason: {reason}",
        f"Evidence grade: {grade}",
        f"Forward watchlist published: {str(champion != 'NO_MODEL_APPROVED').lower()}",
        "Live capital approved: false",
        "",
        "Degenerate scores and contaminated ensembles are rejected before publication.",
        "No model passing the research gate means no forward reference watchlist.",
        "",
    ]
    (output / "model_lab_report.txt").write_text("\n".join(report), encoding="utf-8")
    _rebuild_manifest_and_zip(output, summary)
    return {
        "status": "SUCCESS",
        "research_champion": champion,
        "champion_reason": reason,
        "evidence_grade": grade,
        "forward_watchlist_published": champion != "NO_MODEL_APPROVED",
        "output_dir": str(output),
        "output_zip": str(output / "model_lab_output.zip"),
        "live_capital_approved": False,
    }


def run_model_lab(**kwargs) -> dict[str, object]:
    result = run_legacy_model_lab(**kwargs)
    audited = audit_and_republish(Path(kwargs["output_dir"]))
    return {**result, **audited}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m he_thong_dinh_luong.model_lab")
    parser.add_argument("--input-zip", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--models", required=True)
    parser.add_argument("--evaluation-months", type=int, default=24)
    parser.add_argument("--minimum-train-months", type=int, default=24)
    parser.add_argument("--inner-validation-months", type=int, default=3)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260731)
    parser.add_argument("--strict-dependencies", action="store_true")
    parser.add_argument("--buy-fee-bps", type=float, default=15.0)
    parser.add_argument("--sell-fee-bps", type=float, default=15.0)
    parser.add_argument("--sell-tax-bps", type=float, default=100.0)
    parser.add_argument("--slippage-bps", type=float, default=10.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_model_lab(
            input_zip=args.input_zip,
            output_dir=args.output_dir,
            models=tuple(name.strip() for name in args.models.split(",") if name.strip()),
            evaluation_months=args.evaluation_months,
            minimum_train_months=args.minimum_train_months,
            inner_validation_months=args.inner_validation_months,
            top_k=args.top_k,
            seed=args.seed,
            strict_dependencies=args.strict_dependencies,
            buy_fee_bps=args.buy_fee_bps,
            sell_fee_bps=args.sell_fee_bps,
            sell_tax_bps=args.sell_tax_bps,
            slippage_bps=args.slippage_bps,
        )
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "error": f"{type(exc).__name__}:{exc}"}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0
