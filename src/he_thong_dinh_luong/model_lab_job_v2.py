"""Durable Model Lab job with quality-v2-aware caching."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from . import model_lab_job as legacy

QUALITY_SCHEMA = "vn_quant_model_lab_quality_v2"
DEFAULT_MODELS = legacy.DEFAULT_MODELS


def _quality_cache(
    runs_root: Path,
    *,
    input_sha256: str,
    models: Sequence[str],
    evaluation_months: int,
    top_k: int,
    exclude: Path,
) -> Path | None:
    matches: list[Path] = []
    if not runs_root.is_dir():
        return None
    for run in runs_root.iterdir():
        if not run.is_dir() or run.resolve() == exclude.resolve():
            continue
        summary_path = run / "artifacts" / "model_lab_summary.json"
        manifest_path = run / "artifacts" / "manifest.json"
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        walk = summary.get("walk_forward") if isinstance(summary, dict) else None
        backtest = summary.get("backtest_contract") if isinstance(summary, dict) else None
        if not isinstance(walk, dict) or not isinstance(backtest, dict):
            continue
        if manifest.get("status") != "SUCCESS" or summary.get("schema_version") != QUALITY_SCHEMA:
            continue
        if summary.get("input_zip_sha256") != input_sha256:
            continue
        if tuple(summary.get("requested_models") or ()) != tuple(models):
            continue
        if int(walk.get("evaluation_months_requested") or -1) != evaluation_months:
            continue
        if int(backtest.get("top_k") or -1) != top_k:
            continue
        matches.append(run)
    return max(matches, key=lambda path: path.stat().st_mtime) if matches else None


def run_job(
    *,
    repo_root: Path,
    data_root: Path,
    input_zip: Path,
    output_dir: Path,
    models: Sequence[str] = DEFAULT_MODELS,
    evaluation_months: int = 24,
    top_k: int = 10,
    reuse_unchanged: bool = True,
    timeout_seconds: int = 7200,
) -> dict[str, object]:
    source = Path(input_zip).resolve()
    run_dir = Path(output_dir).resolve()
    requested = tuple(dict.fromkeys(str(name).strip() for name in models if str(name).strip()))
    if reuse_unchanged and source.is_file():
        input_sha = legacy._hash(source)
        cached = _quality_cache(
            Path(data_root).resolve() / "model-lab-live" / "runs",
            input_sha256=input_sha,
            models=requested,
            evaluation_months=evaluation_months,
            top_k=top_k,
            exclude=run_dir,
        )
        if cached is not None:
            run_dir.mkdir(parents=True)
            artifacts = cached / "artifacts"
            legacy._write_status(
                run_dir,
                status="CACHED",
                phase="COMPLETE",
                progress=1.0,
                message="Input, cấu hình và quality gate v2 không đổi; dùng lại kết quả.",
                input_sha256=input_sha,
                artifacts_dir=artifacts,
                cached_from=cached,
            )
            latest = Path(data_root).resolve() / "model-lab-live" / "LATEST.txt"
            latest.parent.mkdir(parents=True, exist_ok=True)
            latest.write_text(str(cached.resolve()) + "\n", encoding="utf-8")
            return {
                "status": "CACHED",
                "run_dir": str(run_dir),
                "cached_from": str(cached),
                "artifacts_dir": str(artifacts),
            }
    return legacy.run_job(
        repo_root=repo_root,
        data_root=data_root,
        input_zip=input_zip,
        output_dir=output_dir,
        models=requested,
        evaluation_months=evaluation_months,
        top_k=top_k,
        reuse_unchanged=False,
        timeout_seconds=timeout_seconds,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m he_thong_dinh_luong.model_lab_job_v2")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--input-zip", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS))
    parser.add_argument("--evaluation-months", type=int, default=24)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--no-reuse", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=7200)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_job(
            repo_root=args.repo_root,
            data_root=args.data_root,
            input_zip=args.input_zip,
            output_dir=args.output_dir,
            models=tuple(name.strip() for name in args.models.split(",") if name.strip()),
            evaluation_months=args.evaluation_months,
            top_k=args.top_k,
            reuse_unchanged=not args.no_reuse,
            timeout_seconds=args.timeout_seconds,
        )
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "error": f"{type(exc).__name__}:{exc}"}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
