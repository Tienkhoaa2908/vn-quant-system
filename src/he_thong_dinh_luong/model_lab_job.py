"""Durable wrapper for local Model Lab execution.

The run directory and status file are created before model execution. Optional
models with missing dependencies are handled by the Model Lab runner itself and
must never block baseline outputs or leave an invisible job.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Mapping, Sequence

VN_TZ = timezone(timedelta(hours=7))
STATUS_SCHEMA = "vn_quant_model_lab_job_v1"
DEFAULT_MODELS = (
    "momentum_baseline",
    "robust_technical_ensemble_v1",
    "ridge_ranker",
    "hist_gradient_boosting_ranker",
    "lightgbm_ranker",
    "xgboost_ranker",
    "torch_pairwise_mlp",
    "online_rank_ensemble_v1",
)


def _now() -> str:
    return datetime.now(VN_TZ).isoformat(timespec="seconds")


def _hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _write_status(
    run_dir: Path,
    *,
    status: str,
    phase: str,
    progress: float,
    message: str,
    input_sha256: str | None = None,
    artifacts_dir: Path | None = None,
    cached_from: Path | None = None,
    error: str | None = None,
) -> None:
    _write_json(
        run_dir / "run_status.json",
        {
            "schema_version": STATUS_SCHEMA,
            "status": status,
            "phase": phase,
            "progress": max(0.0, min(1.0, float(progress))),
            "message": message,
            "updated_at": _now(),
            "input_zip_sha256": input_sha256,
            "artifacts_dir": str(artifacts_dir.resolve()) if artifacts_dir else None,
            "cached_from": str(cached_from.resolve()) if cached_from else None,
            "error": error,
            "credentials_recorded": False,
            "trading_enabled": False,
        },
    )


def _latest_matching(
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
        if manifest.get("status") != "SUCCESS":
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
    root = Path(repo_root).resolve()
    data = Path(data_root).resolve()
    source = Path(input_zip).resolve()
    run_dir = Path(output_dir).resolve()
    requested = tuple(dict.fromkeys(str(name).strip() for name in models if str(name).strip()))
    if run_dir.exists():
        raise FileExistsError("MODEL_LAB_JOB_OUTPUT_EXISTS")
    run_dir.mkdir(parents=True)
    _write_status(
        run_dir,
        status="RUNNING",
        phase="PREFLIGHT",
        progress=0.02,
        message="Đã tạo output; đang kiểm tra prediction_input.zip.",
    )
    if not source.is_file():
        error = f"MODEL_LAB_INPUT_MISSING:{source}"
        _write_status(run_dir, status="FAILED", phase="PREFLIGHT", progress=1.0, message="Thiếu prediction_input.zip.", error=error)
        raise FileNotFoundError(error)
    input_sha = _hash(source)
    runs_root = data / "model-lab-live" / "runs"
    if reuse_unchanged:
        cached = _latest_matching(
            runs_root,
            input_sha256=input_sha,
            models=requested,
            evaluation_months=evaluation_months,
            top_k=top_k,
            exclude=run_dir,
        )
        if cached is not None:
            artifacts = cached / "artifacts"
            _write_status(
                run_dir,
                status="CACHED",
                phase="COMPLETE",
                progress=1.0,
                message="Input và cấu hình không đổi; dùng lại kết quả đã kiểm định.",
                input_sha256=input_sha,
                artifacts_dir=artifacts,
                cached_from=cached,
            )
            runs_root.parent.mkdir(parents=True, exist_ok=True)
            (runs_root.parent / "LATEST.txt").write_text(str(cached.resolve()) + "\n", encoding="utf-8")
            return {"status": "CACHED", "run_dir": str(run_dir), "cached_from": str(cached), "artifacts_dir": str(artifacts)}

    artifacts = run_dir / "artifacts"
    _write_status(
        run_dir,
        status="RUNNING",
        phase="WALK_FORWARD_BACKTEST",
        progress=0.15,
        message="Đang chạy nhiều model. Model thiếu dependency sẽ bị SKIPPED riêng.",
        input_sha256=input_sha,
        artifacts_dir=artifacts,
    )
    environment = os.environ.copy()
    environment.update({
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONPATH": str(root / "src"),
    })
    command = (
        sys.executable,
        "-m",
        "he_thong_dinh_luong.model_lab",
        "--input-zip",
        str(source),
        "--output-dir",
        str(artifacts),
        "--models",
        ",".join(requested),
        "--evaluation-months",
        str(evaluation_months),
        "--top-k",
        str(top_k),
    )
    print("MODEL_LAB_COMMAND:" + " ".join(command), flush=True)
    process = subprocess.Popen(command, cwd=root, env=environment)
    started = time.monotonic()
    next_heartbeat = started + 10.0
    while process.poll() is None:
        elapsed = time.monotonic() - started
        if elapsed >= timeout_seconds:
            process.terminate()
            process.wait(timeout=15)
            error = f"MODEL_LAB_TIMEOUT:{timeout_seconds}"
            _write_status(run_dir, status="FAILED", phase="WALK_FORWARD_BACKTEST", progress=1.0, message="Model Lab quá thời gian cho phép.", input_sha256=input_sha, artifacts_dir=artifacts, error=error)
            raise TimeoutError(error)
        if time.monotonic() >= next_heartbeat:
            print(f"MODEL_LAB_HEARTBEAT:{int(elapsed)}s", flush=True)
            next_heartbeat = time.monotonic() + 10.0
        time.sleep(0.5)
    code = int(process.returncode or 0)
    if code != 0 or not (artifacts / "manifest.json").is_file():
        error = f"MODEL_LAB_RUN_FAILED:{code}"
        _write_status(run_dir, status="FAILED", phase="WALK_FORWARD_BACKTEST", progress=1.0, message="Model Lab thất bại; xem log trên giao diện.", input_sha256=input_sha, artifacts_dir=artifacts, error=error)
        raise RuntimeError(error)
    _write_status(
        run_dir,
        status="SUCCESS",
        phase="COMPLETE",
        progress=1.0,
        message="Leaderboard, backtest và output ZIP đã sẵn sàng.",
        input_sha256=input_sha,
        artifacts_dir=artifacts,
    )
    runs_root.parent.mkdir(parents=True, exist_ok=True)
    (runs_root.parent / "LATEST.txt").write_text(str(run_dir.resolve()) + "\n", encoding="utf-8")
    return {"status": "SUCCESS", "run_dir": str(run_dir), "artifacts_dir": str(artifacts)}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m he_thong_dinh_luong.model_lab_job")
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
        print(json.dumps({"status": "FAILED", "error": f"{type(exc).__name__}:{exc}"}, ensure_ascii=False, sort_keys=True), flush=True)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
