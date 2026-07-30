"""Core khong phu thuoc UI cho bang dieu khien web local.

Chi dung thu vien chuan de CI kiem thu ma khong can NiceGUI. Credential DNSE
chi den tu environment cua process; khong ghi vao SQLite, command line hay log.
"""
from __future__ import annotations

from collections import deque
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
import csv
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import uuid
from typing import Iterable, Iterator, Mapping, Sequence

VN_TZ = timezone(timedelta(hours=7))
ACTIVE_JOB_STATUSES = ("QUEUED", "RUNNING")
TERMINAL_JOB_STATUSES = ("SUCCESS", "FAILED", "INTERRUPTED")


@dataclass(frozen=True)
class LocalWebConfig:
    repo_root: Path
    data_root: Path
    host: str = "127.0.0.1"
    port: int = 8088

    def __post_init__(self) -> None:
        if not self.host:
            raise ValueError("WEB_HOST_EMPTY")
        if not 1 <= self.port <= 65535:
            raise ValueError("WEB_PORT_INVALID")

    @property
    def ui_state_dir(self) -> Path:
        return self.data_root / "web-local"

    @property
    def jobs_db(self) -> Path:
        return self.ui_state_dir / "jobs.sqlite3"

    @property
    def logs_dir(self) -> Path:
        return self.ui_state_dir / "logs"

    @property
    def paper_state_dir(self) -> Path:
        return self.data_root / "paper-trading-live"


@dataclass(frozen=True)
class PipelineStep:
    name: str
    command: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.name or not self.command:
            raise ValueError("PIPELINE_STEP_INVALID")


@dataclass(frozen=True)
class DailyPipelineRequest:
    target_date: date | None = None
    secondary_source: str = "vci"
    crosscheck_sample_size: int = 20
    min_coverage: float = 0.95
    price_tolerance_bps: float = 10.0
    volume_tolerance_ratio: float = 0.05
    initial_capital_vnd: int = 1_000_000_000
    buy_fee_bps: float = 15.0
    sell_fee_bps: float = 15.0
    sell_tax_bps: float = 100.0
    slippage_bps: float = 10.0
    lot_size: int = 100

    def __post_init__(self) -> None:
        if self.secondary_source not in {"kbs", "vci"}:
            raise ValueError("SECONDARY_SOURCE_INVALID")
        if self.crosscheck_sample_size < 0:
            raise ValueError("CROSSCHECK_SAMPLE_SIZE_INVALID")
        if not 0 < self.min_coverage <= 1:
            raise ValueError("MIN_COVERAGE_INVALID")
        if self.price_tolerance_bps < 0 or self.volume_tolerance_ratio < 0:
            raise ValueError("CROSSCHECK_TOLERANCE_INVALID")
        if self.initial_capital_vnd <= 0 or self.initial_capital_vnd % 1000:
            raise ValueError("INITIAL_CAPITAL_VND_INVALID")
        if min(self.buy_fee_bps, self.sell_fee_bps, self.sell_tax_bps, self.slippage_bps) < 0:
            raise ValueError("TRADING_COST_INVALID")
        if self.lot_size <= 0:
            raise ValueError("LOT_SIZE_INVALID")


@dataclass(frozen=True)
class PaperScenarioRequest:
    initial_capital_vnd: int = 1_000_000_000
    buy_fee_bps: float = 15.0
    sell_fee_bps: float = 15.0
    sell_tax_bps: float = 100.0
    slippage_bps: float = 10.0
    lot_size: int = 100

    def __post_init__(self) -> None:
        DailyPipelineRequest(
            initial_capital_vnd=self.initial_capital_vnd,
            buy_fee_bps=self.buy_fee_bps,
            sell_fee_bps=self.sell_fee_bps,
            sell_tax_bps=self.sell_tax_bps,
            slippage_bps=self.slippage_bps,
            lot_size=self.lot_size,
        )


def _now_text() -> str:
    return datetime.now(VN_TZ).isoformat(timespec="seconds")


def new_run_id() -> str:
    return datetime.now(VN_TZ).strftime("%Y%m%d_%H%M%S")


def _json_default(value: object) -> object:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"NOT_JSON_SERIALIZABLE:{type(value).__name__}")


def _json_load(path: Path, default: object) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return default


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


class JobStore:
    """SQLite job ledger voi connection ngan han, dong ro rang tren Windows."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    output_dir TEXT NOT NULL,
                    log_path TEXT NOT NULL,
                    parameters_json TEXT NOT NULL,
                    return_code INTEGER,
                    error TEXT NOT NULL DEFAULT ''
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC)"
            )

    def interrupt_stale_jobs(self) -> int:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET status='INTERRUPTED', stage='process_restarted', finished_at=?,
                    error=CASE WHEN error='' THEN 'UI_PROCESS_RESTARTED' ELSE error END
                WHERE status IN ('QUEUED','RUNNING')
                """,
                (_now_text(),),
            )
            return int(cursor.rowcount)

    def create_job(
        self,
        *,
        kind: str,
        output_dir: Path,
        log_path: Path,
        parameters: Mapping[str, object],
    ) -> str:
        if not kind:
            raise ValueError("JOB_KIND_EMPTY")
        with self._lock, self._connection() as connection:
            active = connection.execute(
                "SELECT id FROM jobs WHERE status IN ('QUEUED','RUNNING') LIMIT 1"
            ).fetchone()
            if active is not None:
                raise ValueError(f"JOB_ALREADY_ACTIVE:{active['id']}")
            job_id = uuid.uuid4().hex
            connection.execute(
                """
                INSERT INTO jobs (
                    id, kind, status, stage, created_at, output_dir, log_path,
                    parameters_json, error
                ) VALUES (?, ?, 'QUEUED', 'waiting', ?, ?, ?, ?, '')
                """,
                (
                    job_id,
                    kind,
                    _now_text(),
                    str(Path(output_dir).resolve()),
                    str(Path(log_path).resolve()),
                    json.dumps(
                        dict(parameters), ensure_ascii=False, sort_keys=True,
                        default=_json_default,
                    ),
                ),
            )
            return job_id

    def update(
        self,
        job_id: str,
        *,
        status: str | None = None,
        stage: str | None = None,
        started: bool = False,
        finished: bool = False,
        return_code: int | None = None,
        error: str | None = None,
    ) -> None:
        fields: list[str] = []
        values: list[object] = []
        if status is not None:
            if status not in (*ACTIVE_JOB_STATUSES, *TERMINAL_JOB_STATUSES):
                raise ValueError("JOB_STATUS_INVALID")
            fields.append("status=?")
            values.append(status)
        if stage is not None:
            fields.append("stage=?")
            values.append(stage)
        if started:
            fields.append("started_at=?")
            values.append(_now_text())
        if finished:
            fields.append("finished_at=?")
            values.append(_now_text())
        if return_code is not None:
            fields.append("return_code=?")
            values.append(return_code)
        if error is not None:
            fields.append("error=?")
            values.append(error[:4000])
        if not fields:
            return
        values.append(job_id)
        with self._connection() as connection:
            cursor = connection.execute(
                f"UPDATE jobs SET {', '.join(fields)} WHERE id=?", values
            )
            if cursor.rowcount != 1:
                raise ValueError(f"JOB_NOT_FOUND:{job_id}")

    def get(self, job_id: str) -> dict[str, object] | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            return dict(row) if row is not None else None

    def active(self) -> dict[str, object] | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM jobs WHERE status IN ('QUEUED','RUNNING')
                ORDER BY created_at DESC LIMIT 1
                """
            ).fetchone()
            return dict(row) if row is not None else None

    def recent(self, limit: int = 30) -> list[dict[str, object]]:
        if limit <= 0:
            raise ValueError("JOB_LIMIT_INVALID")
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(row) for row in rows]


def build_daily_pipeline(
    config: LocalWebConfig,
    request: DailyPipelineRequest,
    *,
    run_id: str | None = None,
) -> tuple[Path, tuple[PipelineStep, ...]]:
    output_dir = config.data_root / f"eod-web-{run_id or new_run_id()}"
    eod_command = [
        sys.executable, "-m", "he_thong_dinh_luong.eod_hang_ngay_cli",
        "--data-root", str(config.data_root),
        "--output-dir", str(output_dir),
        "--primary-source", "dnse",
        "--secondary-source", request.secondary_source,
        "--crosscheck-policy", "advisory",
        "--crosscheck-sample-size", str(request.crosscheck_sample_size),
        "--min-coverage", str(request.min_coverage),
        "--price-tolerance-bps", str(request.price_tolerance_bps),
        "--volume-tolerance-ratio", str(request.volume_tolerance_ratio),
    ]
    if request.target_date is not None:
        eod_command.extend(("--target-date", request.target_date.isoformat()))
    paper_command = (
        sys.executable, "-m", "he_thong_dinh_luong.paper_trading_daily",
        "--daily-output", str(output_dir / "daily_quant_output.zip"),
        "--publication-dir", str(output_dir / "updated_publication"),
        "--state-dir", str(config.paper_state_dir),
        "--initial-capital-vnd", str(request.initial_capital_vnd),
        "--buy-fee-bps", str(request.buy_fee_bps),
        "--sell-fee-bps", str(request.sell_fee_bps),
        "--sell-tax-bps", str(request.sell_tax_bps),
        "--slippage-bps", str(request.slippage_bps),
        "--lot-size", str(request.lot_size),
    )
    return output_dir, (
        PipelineStep("fetch_validate_predict_allocate", tuple(eod_command)),
        PipelineStep("update_paper_trading", paper_command),
    )


def build_paper_scenario(
    config: LocalWebConfig,
    request: PaperScenarioRequest,
    *,
    publication_dir: Path,
    run_id: str | None = None,
) -> tuple[Path, tuple[PipelineStep, ...]]:
    output_dir = config.data_root / "paper-scenarios" / f"scenario-{run_id or new_run_id()}"
    command = (
        sys.executable, "-m", "he_thong_dinh_luong.paper_scenario",
        "--state-dir", str(config.paper_state_dir),
        "--publication-dir", str(publication_dir),
        "--output-dir", str(output_dir),
        "--initial-capital-vnd", str(request.initial_capital_vnd),
        "--buy-fee-bps", str(request.buy_fee_bps),
        "--sell-fee-bps", str(request.sell_fee_bps),
        "--sell-tax-bps", str(request.sell_tax_bps),
        "--slippage-bps", str(request.slippage_bps),
        "--lot-size", str(request.lot_size),
    )
    return output_dir, (PipelineStep("replay_recorded_oos_signals", command),)


def execute_job(
    *,
    store: JobStore,
    job_id: str,
    config: LocalWebConfig,
    steps: Sequence[PipelineStep],
    extra_env: Mapping[str, str] | None = None,
) -> int:
    job = store.get(job_id)
    if job is None:
        raise ValueError(f"JOB_NOT_FOUND:{job_id}")
    log_path = Path(str(job["log_path"]))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.update({
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONPATH": str(config.repo_root / "src"),
    })
    if extra_env:
        environment.update({str(key): str(value) for key, value in extra_env.items()})
    store.update(job_id, status="RUNNING", stage="starting", started=True)
    try:
        with log_path.open("a", encoding="utf-8", newline="") as log:
            log.write(f"===== JOB {job_id} START {_now_text()} =====\n")
            for index, step in enumerate(steps, start=1):
                stage = f"{index}/{len(steps)}:{step.name}"
                store.update(job_id, stage=stage)
                log.write(f"\n===== STEP {stage} =====\n")
                log.flush()
                process = subprocess.Popen(
                    step.command,
                    cwd=config.repo_root,
                    env=environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                )
                assert process.stdout is not None
                for line in process.stdout:
                    log.write(line)
                    log.flush()
                return_code = process.wait()
                log.write(f"===== STEP EXIT {return_code} =====\n")
                log.flush()
                if return_code != 0:
                    store.update(
                        job_id, status="FAILED", stage=stage, finished=True,
                        return_code=return_code,
                        error=f"STEP_FAILED:{step.name}:{return_code}",
                    )
                    return return_code
            log.write(f"===== JOB SUCCESS {_now_text()} =====\n")
        store.update(
            job_id, status="SUCCESS", stage="completed", finished=True,
            return_code=0, error="",
        )
        return 0
    except Exception as exc:
        message = f"{type(exc).__name__}:{exc}"
        try:
            with log_path.open("a", encoding="utf-8") as log:
                log.write(f"\n===== JOB EXCEPTION {message} =====\n")
        finally:
            store.update(
                job_id, status="FAILED", stage="exception", finished=True,
                return_code=2, error=message,
            )
        return 2


def create_daily_job(
    store: JobStore,
    config: LocalWebConfig,
    request: DailyPipelineRequest,
) -> tuple[str, Path, tuple[PipelineStep, ...]]:
    output_dir, steps = build_daily_pipeline(config, request)
    log_path = config.logs_dir / f"{output_dir.name}.log"
    job_id = store.create_job(
        kind="daily_pipeline", output_dir=output_dir, log_path=log_path,
        parameters=asdict(request),
    )
    return job_id, output_dir, steps


def create_scenario_job(
    store: JobStore,
    config: LocalWebConfig,
    request: PaperScenarioRequest,
    *,
    publication_dir: Path,
) -> tuple[str, Path, tuple[PipelineStep, ...]]:
    output_dir, steps = build_paper_scenario(
        config, request, publication_dir=publication_dir
    )
    log_path = config.logs_dir / f"{output_dir.name}.log"
    parameters = asdict(request)
    parameters["publication_dir"] = str(publication_dir)
    job_id = store.create_job(
        kind="paper_scenario", output_dir=output_dir, log_path=log_path,
        parameters=parameters,
    )
    return job_id, output_dir, steps


def _candidate_eod_dirs(data_root: Path) -> Iterable[Path]:
    for pattern in ("eod-web-*", "eod-dnse-*", "eod-dnse-vci-*"):
        yield from data_root.glob(pattern)


def discover_eod_runs(data_root: Path, limit: int = 100) -> list[dict[str, object]]:
    if limit <= 0:
        raise ValueError("EOD_RUN_LIMIT_INVALID")
    rows: list[dict[str, object]] = []
    seen: set[Path] = set()
    for path in _candidate_eod_dirs(Path(data_root)):
        if not path.is_dir() or path.resolve() in seen:
            continue
        seen.add(path.resolve())
        manifest = _json_load(path / "manifest.json", {})
        quality = _json_load(path / "data_quality_report.json", {})
        manifest = manifest if isinstance(manifest, dict) else {}
        quality = quality if isinstance(quality, dict) else {}
        rows.append({
            "path": str(path.resolve()),
            "name": path.name,
            "mtime": path.stat().st_mtime,
            "status": manifest.get("status", "INCOMPLETE"),
            "session_date": manifest.get("session_date") or quality.get("session_date") or "",
            "primary_coverage": manifest.get("primary_coverage", quality.get("primary_coverage")),
            "secondary_match_ratio": manifest.get(
                "secondary_sample_match_ratio", quality.get("secondary_match_ratio")
            ),
            "quality_tier": manifest.get("quality_tier", quality.get("quality_tier", "")),
            "has_zip": (path / "daily_quant_output.zip").is_file(),
            "has_publication": (
                path / "updated_publication" / "du_lieu_gia_mo_dong_khoi_luong.csv"
            ).is_file(),
        })
    rows.sort(key=lambda row: float(row["mtime"]), reverse=True)
    return rows[:limit]


def latest_successful_eod(data_root: Path) -> Path | None:
    for row in discover_eod_runs(data_root):
        if row["status"] == "SUCCESS" and row["has_zip"] and row["has_publication"]:
            return Path(str(row["path"]))
    return None


def latest_paper_snapshot(data_root: Path) -> Path | None:
    latest_file = Path(data_root) / "paper-trading-live" / "LATEST.txt"
    try:
        path = Path(latest_file.read_text(encoding="utf-8-sig").strip())
    except OSError:
        return None
    return path if path.is_dir() and _under(path, Path(data_root)) else None


def read_csv_rows(
    path: Path,
    *,
    limit: int = 500,
    symbol: str | None = None,
    tail: bool = False,
) -> list[dict[str, str]]:
    if limit <= 0:
        raise ValueError("CSV_LIMIT_INVALID")
    if not path.is_file():
        return []
    target = symbol.strip().upper() if symbol else None
    selected: deque[dict[str, str]] = deque(maxlen=limit)
    output: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            normalized = {str(key): str(value or "") for key, value in row.items()}
            if target:
                row_symbol = (normalized.get("ma") or normalized.get("symbol") or "").upper()
                if row_symbol != target:
                    continue
            if tail:
                selected.append(normalized)
            else:
                output.append(normalized)
                if len(output) >= limit:
                    break
    return list(selected) if tail else output


def artifact_paths(eod_run: Path) -> dict[str, Path]:
    return {
        "manifest": eod_run / "manifest.json",
        "quality": eod_run / "data_quality_report.json",
        "summary": eod_run / "daily_prediction_summary.txt",
        "prediction": eod_run / "prediction" / "latest_prediction.csv",
        "model": eod_run / "prediction" / "model_comparison.json",
        "allocation": eod_run / "paper_portfolio.csv",
        "publication": eod_run / "updated_publication" / "du_lieu_gia_mo_dong_khoi_luong.csv",
        "zip": eod_run / "daily_quant_output.zip",
    }


def load_overview(config: LocalWebConfig) -> dict[str, object]:
    eod = latest_successful_eod(config.data_root)
    paper = latest_paper_snapshot(config.data_root)
    result: dict[str, object] = {
        "data_root": str(config.data_root.resolve()),
        "repo_root": str(config.repo_root.resolve()),
        "credential_loaded": bool(os.environ.get("DNSE_API_KEY") and os.environ.get("DNSE_API_SECRET")),
        "prediction_input_present": (config.data_root / "prediction_input.zip").is_file(),
        "latest_eod_dir": str(eod) if eod else "",
        "latest_paper_snapshot": str(paper) if paper else "",
    }
    if eod:
        paths = artifact_paths(eod)
        manifest = _json_load(paths["manifest"], {})
        model = _json_load(paths["model"], {})
        if isinstance(manifest, dict):
            result.update({
                "session_date": manifest.get("session_date", ""),
                "quality_tier": manifest.get("quality_tier", ""),
                "primary_coverage": manifest.get("primary_coverage"),
                "secondary_match_ratio": manifest.get("secondary_sample_match_ratio"),
            })
        if isinstance(model, dict):
            result.update({
                "champion_model": model.get("champion_model", ""),
                "market_regime": model.get("market_regime", ""),
                "capital_budget_pct": model.get("capital_budget_pct"),
                "research_eligible": model.get("research_eligible", False),
            })
    if paper:
        metrics = _json_load(paper / "metrics.json", {})
        if isinstance(metrics, dict):
            result.update({
                "paper_status": metrics.get("status", ""),
                "paper_latest_nav_vnd": metrics.get("latest_nav_vnd"),
                "paper_total_return": metrics.get("total_return"),
                "paper_max_drawdown": metrics.get("max_drawdown"),
                "paper_fill_count": metrics.get("fill_count"),
                "paper_pending_order_count": metrics.get("pending_order_count"),
            })
    return result


def _latest_file(config: LocalWebConfig, key: str) -> Path | None:
    run = latest_successful_eod(config.data_root)
    return artifact_paths(run)[key] if run else None


def load_latest_predictions(config: LocalWebConfig, limit: int = 200) -> list[dict[str, str]]:
    path = _latest_file(config, "prediction")
    return read_csv_rows(path, limit=limit) if path else []


def load_latest_allocation(config: LocalWebConfig, limit: int = 200) -> list[dict[str, str]]:
    path = _latest_file(config, "allocation")
    return read_csv_rows(path, limit=limit) if path else []


def load_latest_prices(
    config: LocalWebConfig,
    *,
    symbol: str | None = None,
    limit: int = 500,
) -> list[dict[str, str]]:
    path = _latest_file(config, "publication")
    return read_csv_rows(path, limit=limit, symbol=symbol, tail=True) if path else []


def _load_latest_json(config: LocalWebConfig, key: str) -> dict[str, object]:
    path = _latest_file(config, key)
    value = _json_load(path, {}) if path else {}
    return value if isinstance(value, dict) else {}


def load_model_comparison(config: LocalWebConfig) -> dict[str, object]:
    return _load_latest_json(config, "model")


def load_quality_report(config: LocalWebConfig) -> dict[str, object]:
    return _load_latest_json(config, "quality")


def load_paper_nav(config: LocalWebConfig, limit: int = 1000) -> list[dict[str, str]]:
    snapshot = latest_paper_snapshot(config.data_root)
    return read_csv_rows(snapshot / "nav.csv", limit=limit) if snapshot else []


def load_paper_positions(config: LocalWebConfig, limit: int = 1000) -> list[dict[str, str]]:
    snapshot = latest_paper_snapshot(config.data_root)
    return read_csv_rows(snapshot / "positions_daily.csv", limit=limit, tail=True) if snapshot else []


def read_log_tail(path: Path, max_lines: int = 300) -> str:
    if max_lines <= 0 or not path.is_file():
        return ""
    lines: deque[str] = deque(maxlen=max_lines)
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        lines.extend(stream)
    return "".join(lines)


def latest_publication_dir(config: LocalWebConfig) -> Path | None:
    run = latest_successful_eod(config.data_root)
    return run / "updated_publication" if run else None
