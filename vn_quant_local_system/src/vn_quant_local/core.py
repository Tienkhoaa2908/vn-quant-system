"""Hạ tầng dữ liệu và audit trail cho VN Quant Local Workstation.

Module này chỉ dùng thư viện chuẩn. Kho dữ liệu thị trường nằm bên trong
``vn_quant_local_system/data`` và được cập nhật incremental từ DNSE thông qua
adapter đã có trong repository chính.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sqlite3
from typing import Iterator, Mapping, Sequence

SYSTEM_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = SYSTEM_ROOT.parent
CONFIG_PATH = SYSTEM_ROOT / "config.json"


@dataclass(frozen=True)
class Paths:
    root: Path
    market_db: Path
    reference_zip: Path
    state_db: Path
    outputs: Path
    logs: Path
    validation_artifacts: Path
    validation_sources: Path


def load_config() -> dict[str, object]:
    if not CONFIG_PATH.is_file():
        raise FileNotFoundError(f"Không tìm thấy cấu hình: {CONFIG_PATH}")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def paths() -> Paths:
    config = load_config()
    data = config.get("paths", {})
    if not isinstance(data, Mapping):
        raise ValueError("config.paths phải là object")
    return Paths(
        root=SYSTEM_ROOT,
        market_db=SYSTEM_ROOT / str(data.get("market_db", "data/market/dnse_ohlcv.sqlite3")),
        reference_zip=SYSTEM_ROOT / str(data.get("reference_zip", "data/reference/daily_prediction_input_v22.zip")),
        state_db=SYSTEM_ROOT / str(data.get("state_db", "data/state/workstation.sqlite3")),
        outputs=SYSTEM_ROOT / str(data.get("outputs", "outputs")),
        logs=SYSTEM_ROOT / str(data.get("logs", "logs")),
        validation_artifacts=SYSTEM_ROOT / str(data.get("validation_artifacts", "validation/artifacts")),
        validation_sources=SYSTEM_ROOT / str(data.get("validation_sources", "validation/source_snapshots")),
    )


def sha256_file(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def ensure_directories() -> Paths:
    p = paths()
    for directory in (
        p.market_db.parent,
        p.reference_zip.parent,
        p.state_db.parent,
        p.outputs,
        p.logs,
        p.validation_artifacts,
        p.validation_sources,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    return p


def _state_schema(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        PRAGMA journal_mode=WAL;
        PRAGMA foreign_keys=ON;

        CREATE TABLE IF NOT EXISTS metadata(
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS runs(
            run_id TEXT PRIMARY KEY,
            run_type TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL,
            details_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS rankings(
            run_id TEXT NOT NULL,
            signal_day TEXT NOT NULL,
            signal_kind TEXT NOT NULL,
            rank INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            score REAL NOT NULL,
            low_volatility_pct REAL NOT NULL,
            relative_strength_120_pct REAL NOT NULL,
            high_52_week_pct REAL NOT NULL,
            volatility_60 REAL NOT NULL,
            close_price REAL NOT NULL,
            above_ma250 INTEGER NOT NULL,
            eligible INTEGER NOT NULL,
            PRIMARY KEY(run_id, signal_kind, symbol),
            FOREIGN KEY(run_id) REFERENCES runs(run_id)
        );

        CREATE INDEX IF NOT EXISTS idx_rankings_signal
        ON rankings(signal_day, signal_kind, rank);

        CREATE TABLE IF NOT EXISTS holdings(
            symbol TEXT PRIMARY KEY,
            quantity INTEGER NOT NULL CHECK(quantity >= 0),
            average_cost REAL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS account_state(
            singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
            cash_vnd REAL NOT NULL,
            weekly_contribution_vnd REAL NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS weekly_plans(
            plan_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            ranking_run_id TEXT NOT NULL,
            contribution_vnd REAL NOT NULL,
            available_cash_vnd REAL NOT NULL,
            buy_symbol TEXT,
            buy_quantity INTEGER NOT NULL,
            estimated_buy_value_vnd REAL NOT NULL,
            sell_symbols_json TEXT NOT NULL,
            rationale_json TEXT NOT NULL,
            research_only INTEGER NOT NULL,
            FOREIGN KEY(ranking_run_id) REFERENCES runs(run_id)
        );
        """
    )
    row = db.execute("SELECT 1 FROM account_state WHERE singleton=1").fetchone()
    if row is None:
        config = load_config()
        policy = config.get("weekly_policy", {})
        contribution = (
            float(policy.get("default_contribution_vnd", 250_000))
            if isinstance(policy, Mapping)
            else 250_000.0
        )
        db.execute(
            "INSERT INTO account_state VALUES(1,?,?,?)",
            (0.0, contribution, utc_now()),
        )
    db.commit()


@contextmanager
def state_db() -> Iterator[sqlite3.Connection]:
    p = ensure_directories()
    db = sqlite3.connect(p.state_db)
    db.row_factory = sqlite3.Row
    try:
        _state_schema(db)
        yield db
        db.commit()
    finally:
        db.close()


def _latest_glob(root: Path, pattern: str) -> Path | None:
    candidates = [path for path in root.glob(pattern) if path.is_file()]
    return max(candidates, key=lambda item: item.stat().st_mtime) if candidates else None


def bootstrap_local_data(*, overwrite: bool = False) -> dict[str, object]:
    """Tạo kho local từ canonical 11 năm và lưu bằng chứng kiểm định.

    Dữ liệu lớn không được commit lên Git. Hàm này copy dữ liệu vào đúng thư mục
    workstation trên máy người dùng và ghi hash để có thể kiểm định lại.
    """
    p = ensure_directories()
    config = load_config()
    sources = config.get("bootstrap_sources", {})
    if not isinstance(sources, Mapping):
        raise ValueError("config.bootstrap_sources phải là object")

    market_source = Path(os.path.expandvars(str(sources.get("market_store", "")))).expanduser()
    reference_root = Path(os.path.expandvars(str(sources.get("reference_root", "")))).expanduser()
    reference_pattern = str(
        sources.get(
            "reference_glob",
            "historical-research-input-v22-*/daily_prediction_input.zip",
        )
    )
    reference_source = _latest_glob(reference_root, reference_pattern)

    copied: dict[str, object] = {}
    if not p.market_db.exists() or overwrite:
        if not market_source.is_file():
            raise FileNotFoundError(f"Không tìm thấy canonical market store: {market_source}")
        shutil.copy2(market_source, p.market_db)
        copied["market_db"] = str(p.market_db)
    if not p.reference_zip.exists() or overwrite:
        if reference_source is None:
            raise FileNotFoundError(
                f"Không tìm thấy reference ZIP trong {reference_root} / {reference_pattern}"
            )
        shutil.copy2(reference_source, p.reference_zip)
        copied["reference_zip"] = str(p.reference_zip)

    archive_validation_evidence()
    with state_db() as db:
        for key, path in (
            ("market_db_sha256", p.market_db),
            ("reference_zip_sha256", p.reference_zip),
        ):
            db.execute(
                "INSERT INTO metadata(key,value,updated_at) VALUES(?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (key, sha256_file(path), utc_now()),
            )
    return {
        "status": "SUCCESS",
        "copied": copied,
        "market_db": str(p.market_db),
        "market_db_sha256": sha256_file(p.market_db),
        "reference_zip": str(p.reference_zip),
        "reference_zip_sha256": sha256_file(p.reference_zip),
    }


def archive_validation_evidence() -> dict[str, object]:
    p = ensure_directories()
    config = load_config()
    validation = config.get("validation_archive", {})
    if not isinstance(validation, Mapping):
        validation = {}

    copied_sources: list[str] = []
    for relative in validation.get("source_files", []):
        source = REPO_ROOT / str(relative)
        if not source.is_file():
            continue
        destination = p.validation_sources / str(relative).replace("/", "__")
        shutil.copy2(source, destination)
        copied_sources.append(str(destination.relative_to(SYSTEM_ROOT)))

    copied_artifacts: list[str] = []
    artifact_dir = REPO_ROOT / "artifacts"
    for pattern in validation.get("artifact_globs", []):
        latest = _latest_glob(artifact_dir, str(pattern)) if artifact_dir.is_dir() else None
        if latest is None:
            continue
        destination = p.validation_artifacts / latest.name
        shutil.copy2(latest, destination)
        copied_artifacts.append(str(destination.relative_to(SYSTEM_ROOT)))

    manifest = {
        "archived_at": utc_now(),
        "source_files": [
            {"path": item, "sha256": sha256_file(SYSTEM_ROOT / item)}
            for item in copied_sources
        ],
        "artifacts": [
            {"path": item, "sha256": sha256_file(SYSTEM_ROOT / item)}
            for item in copied_artifacts
        ],
    }
    manifest_path = p.validation_artifacts.parent / "archive_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def market_coverage() -> dict[str, object]:
    p = paths()
    if not p.market_db.is_file():
        return {"status": "MISSING", "path": str(p.market_db)}
    db = sqlite3.connect(p.market_db)
    db.row_factory = sqlite3.Row
    try:
        rows = db.execute(
            """
            SELECT upper(asset_type) asset_type,
                   COUNT(*) row_count,
                   COUNT(DISTINCT symbol) symbol_count,
                   MIN(day) first_day,
                   MAX(day) last_day
            FROM bars
            GROUP BY upper(asset_type)
            ORDER BY upper(asset_type)
            """
        ).fetchall()
        conflicts = db.execute("SELECT COUNT(*) FROM conflicts").fetchone()[0]
    finally:
        db.close()
    return {
        "status": "READY" if rows else "EMPTY",
        "path": str(p.market_db),
        "sha256": sha256_file(p.market_db),
        "coverage": [dict(row) for row in rows],
        "conflict_count": int(conflicts),
    }


def sync_incremental_market_data(*, end: date | None = None, lookback_days: int = 14) -> dict[str, object]:
    """Bổ sung các phiên còn thiếu vào store local.

    DNSE credentials vẫn lấy từ environment theo adapter canonical của repository.
    Không ghi ngược vào kho cũ bên ngoài workstation.
    """
    p = paths()
    if not p.market_db.is_file():
        raise FileNotFoundError("Chưa bootstrap market database local")
    db = sqlite3.connect(p.market_db)
    try:
        symbols = [
            str(row[0])
            for row in db.execute(
                "SELECT DISTINCT symbol FROM bars WHERE upper(asset_type)='STOCK' ORDER BY symbol"
            ).fetchall()
        ]
        last_day_raw = db.execute("SELECT MAX(day) FROM bars").fetchone()[0]
    finally:
        db.close()
    if not symbols or not last_day_raw:
        raise ValueError("Local market store không có dữ liệu STOCK")

    from he_thong_dinh_luong.dnse_historical_store_v20 import sync_historical_store

    last_day = date.fromisoformat(str(last_day_raw))
    final_end = end or datetime.now().astimezone().date()
    start = min(last_day + timedelta(days=1), final_end)
    start = min(start, final_end) - timedelta(days=max(lookback_days, 0))
    result = sync_historical_store(
        store_path=p.market_db,
        symbols=symbols,
        start=start,
        end=final_end,
        include_vnindex=True,
        force_refresh=False,
    )
    with state_db() as state:
        state.execute(
            "INSERT INTO metadata(key,value,updated_at) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            ("last_market_sync", json.dumps(result, sort_keys=True), utc_now()),
        )
    return result


def account_snapshot() -> dict[str, object]:
    with state_db() as db:
        account = db.execute("SELECT * FROM account_state WHERE singleton=1").fetchone()
        holdings = [dict(row) for row in db.execute(
            "SELECT symbol,quantity,average_cost,updated_at FROM holdings WHERE quantity>0 ORDER BY symbol"
        ).fetchall()]
    return {"account": dict(account), "holdings": holdings}


def replace_account(*, cash_vnd: float, weekly_contribution_vnd: float, holdings: Sequence[Mapping[str, object]]) -> dict[str, object]:
    if cash_vnd < 0 or weekly_contribution_vnd <= 0:
        raise ValueError("Cash phải >=0 và contribution phải >0")
    normalized: list[tuple[str, int, float | None]] = []
    for row in holdings:
        symbol = str(row.get("symbol") or "").strip().upper()
        quantity = int(row.get("quantity") or 0)
        average_cost_raw = row.get("average_cost")
        average_cost = float(average_cost_raw) if average_cost_raw not in (None, "") else None
        if not symbol or quantity < 0:
            raise ValueError("Holding không hợp lệ")
        if quantity > 0:
            normalized.append((symbol, quantity, average_cost))
    now = utc_now()
    with state_db() as db:
        db.execute("DELETE FROM holdings")
        db.executemany(
            "INSERT INTO holdings(symbol,quantity,average_cost,updated_at) VALUES(?,?,?,?)",
            [(symbol, quantity, average_cost, now) for symbol, quantity, average_cost in normalized],
        )
        db.execute(
            "UPDATE account_state SET cash_vnd=?,weekly_contribution_vnd=?,updated_at=? WHERE singleton=1",
            (float(cash_vnd), float(weekly_contribution_vnd), now),
        )
    return account_snapshot()


def latest_ranking_run(signal_kind: str = "MONTHLY_CANONICAL") -> dict[str, object] | None:
    with state_db() as db:
        run = db.execute(
            """
            SELECT r.* FROM runs r
            WHERE r.run_type='MODEL' AND r.status='SUCCESS'
              AND EXISTS(
                SELECT 1 FROM rankings k
                WHERE k.run_id=r.run_id AND k.signal_kind=?
              )
            ORDER BY r.finished_at DESC LIMIT 1
            """,
            (signal_kind,),
        ).fetchone()
        if run is None:
            return None
        ranking = [dict(row) for row in db.execute(
            "SELECT * FROM rankings WHERE run_id=? AND signal_kind=? ORDER BY rank",
            (run["run_id"], signal_kind),
        ).fetchall()]
    return {"run": dict(run), "ranking": ranking}


def workstation_status() -> dict[str, object]:
    p = ensure_directories()
    ranking = latest_ranking_run()
    return {
        "system_root": str(SYSTEM_ROOT),
        "repo_root": str(REPO_ROOT),
        "market": market_coverage(),
        "reference_zip": {
            "status": "READY" if p.reference_zip.is_file() else "MISSING",
            "path": str(p.reference_zip),
            "sha256": sha256_file(p.reference_zip) if p.reference_zip.is_file() else None,
        },
        "latest_monthly_ranking": ranking,
        "account": account_snapshot(),
        "permissions": {
            "research_only": True,
            "live_capital_approved": False,
            "automatic_live_orders_allowed": False,
        },
    }
