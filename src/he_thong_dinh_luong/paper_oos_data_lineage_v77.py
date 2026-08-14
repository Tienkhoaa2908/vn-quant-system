"""V77 fresh paper-OOS registry plus local data-lineage gate audit.

This package intentionally does NOT search for another historical champion. Frozen
C3 remains champion; V76 Ridge rank is a zero-capital shadow. The first run freezes
an immutable OOS experiment boundary. Later runs only append model targets when the
latest completed monthly source snapshot changes, then replay those captured targets
from the capture-market-day to the exact next available session open.

Historical bars before the freeze can be used to fit the already-frozen algorithms,
but paper P&L begins only after the freeze/capture boundary. Data-gate audit is
fail-closed and never mutates the market store.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sqlite3
import tempfile
from contextlib import closing
from dataclasses import fields
from datetime import date, datetime, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from statistics import fmean
from typing import Iterable, Mapping, Sequence

from . import c3_hose_consolidated_v68_safe as v68safe
from . import c3_hose_native_driver_v67 as c3driver
from . import deep_portfolio_backtest_v70 as v70
from . import learned_ranking_challenger_v76 as v76
from . import market_store_basis_audit_v67 as basis_audit
from . import paper_trading_daily as paper
from .mo_phong import chay_mo_phong
from .mo_phong.mo_hinh import thanh_gia

SCHEMA_VERSION = "paper_oos_data_lineage_v77"
FREEZE_SCHEMA = "v77_paper_oos_freeze_v1"
CHAMPION_MODEL = "C3_STABLE_3_PAST_IC_SHRUNK"
SHADOW_MODEL = "V76_RIDGE_RANK"
PRIMARY_VARIANT = "GAP18_CLEAN"
PRIMARY_ALLOCATOR = "EQUAL"
PRICE_MULTIPLIER = 1000.0
INITIAL_CAPITAL_VND = 1_000_000_000
PAPER_COST_CONTRACT = "V70_BASE_APPROX_NO_TRANSFER_FEE"
BUY_FEE_BPS = Decimal("2.7")
SELL_FEE_BPS = Decimal("2.7")
SELL_TAX_BPS = Decimal("10")
SLIPPAGE_BPS = Decimal("5")
LOT_SIZE = 100
MAX_EVIDENCE_FILES = 500
MAX_EVIDENCE_BYTES = 5_000_000

SIGNAL_FIELDS = (
    "paper_signal_day",
    "source_signal_day",
    "captured_at",
    "model_id",
    "variant_id",
    "allocator",
    "symbol",
    "rank",
    "model_score",
    "target_weight_pct",
    "risk_on",
    "git_head",
    "store_sha256",
)


def _json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _sha_file(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha_bytes(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({str(k) for row in rows for k in row.keys()}) if rows else ["empty"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            cooked: dict[str, object] = {}
            for key in fieldnames:
                value = row.get(key)
                if isinstance(value, (dict, list, tuple, set)):
                    value = json.dumps(value, ensure_ascii=False, sort_keys=True)
                cooked[key] = value
            writer.writerow(cooked)


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _month_key(day: date) -> tuple[int, int]:
    return day.year, day.month


def _first_of_month(day: date) -> date:
    return date(day.year, day.month, 1)


def _next_month(day: date) -> date:
    return date(day.year + (1 if day.month == 12 else 0), 1 if day.month == 12 else day.month + 1, 1)


def _latest_market_day(store: Path) -> date:
    uri = Path(store).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        cols = {str(r[1]).lower(): str(r[1]) for r in db.execute('PRAGMA table_info("bars")')}
        if not {"day", "symbol"}.issubset(cols):
            raise ValueError("V77_BARS_DAY_SYMBOL_COLUMNS_MISSING")
        q = lambda x: '"' + x.replace('"', '""') + '"'
        row = db.execute(
            f"SELECT MAX({q(cols['day'])}) FROM bars WHERE UPPER({q(cols['symbol'])}) IN ('VNINDEX','VN-INDEX','VN_INDEX')"
        ).fetchone()
    if row is None or row[0] is None:
        raise ValueError("V77_VNINDEX_LATEST_DAY_MISSING")
    return date.fromisoformat(str(row[0])[:10])


def _store_inventory(store: Path) -> dict[str, object]:
    uri = Path(store).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        tables = [
            str(r[0]) for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            if not str(r[0]).startswith("sqlite_")
        ]
        schema = {
            table: [str(r[1]) for r in db.execute(f'PRAGMA table_info("{table.replace(chr(34), chr(34)*2)}")')]
            for table in tables
        }
        if "bars" not in schema:
            raise ValueError("V77_BARS_TABLE_MISSING")
        cols = {c.lower(): c for c in schema["bars"]}
        q = lambda x: '"' + x.replace('"', '""') + '"'
        required = {"symbol", "day", "asset_type"}
        if not required.issubset(cols):
            raise ValueError("V77_BARS_REQUIRED_COLUMNS_MISSING")
        row_count = int(db.execute("SELECT COUNT(*) FROM bars").fetchone()[0])
        stock_count = int(db.execute(
            f"SELECT COUNT(DISTINCT {q(cols['symbol'])}) FROM bars WHERE UPPER(COALESCE({q(cols['asset_type'])},''))='STOCK'"
        ).fetchone()[0])
        first_day, last_day = db.execute(f"SELECT MIN({q(cols['day'])}),MAX({q(cols['day'])}) FROM bars").fetchone()
        basis_counts: dict[str, int] = {}
        if "price_basis" in cols:
            for value, count in db.execute(
                f"SELECT COALESCE({q(cols['price_basis'])},''),COUNT(*) FROM bars GROUP BY COALESCE({q(cols['price_basis'])},'') ORDER BY 1"
            ):
                basis_counts[str(value or "").strip()] = int(count)
        exchange_counts: dict[str, int] = {}
        if "exchange" in cols:
            for value, count in db.execute(
                f"SELECT COALESCE({q(cols['exchange'])},''),COUNT(*) FROM bars WHERE UPPER(COALESCE({q(cols['asset_type'])},''))='STOCK' GROUP BY COALESCE({q(cols['exchange'])},'') ORDER BY 1"
            ):
                exchange_counts[str(value or "").strip()] = int(count)
    return {
        "tables": schema,
        "bar_row_count": row_count,
        "stock_symbol_count": stock_count,
        "first_day": str(first_day)[:10] if first_day else None,
        "last_day": str(last_day)[:10] if last_day else None,
        "price_basis_counts": basis_counts,
        "exchange_counts": exchange_counts,
    }


def _price_basis_from_store(inventory: Mapping[str, object]) -> tuple[bool, str, list[str]]:
    counts = dict(inventory.get("price_basis_counts") or {})
    if not counts:
        return False, "UNKNOWN", ["PRICE_BASIS_COLUMN_MISSING_OR_EMPTY"]
    aliases = {
        "ADJUSTED": "ADJUSTED",
        "DIEU_CHINH": "ADJUSTED",
        "ĐIỀU_CHỈNH": "ADJUSTED",
        "UNADJUSTED": "UNADJUSTED",
        "KHONG_DIEU_CHINH": "UNADJUSTED",
        "KHÔNG_ĐIỀU_CHỈNH": "UNADJUSTED",
    }
    unknown = {"", "UNKNOWN", "UNCONFIRMED", "CHUA_XAC_NHAN", "CHƯA_XÁC_NHẬN", "NONE", "NULL"}
    normalized: set[str] = set()
    blockers: list[str] = []
    for raw, count in counts.items():
        key = str(raw).strip().upper()
        if count <= 0:
            continue
        if key in unknown:
            blockers.append(f"PRICE_BASIS_UNCONFIRMED_VALUE:{raw or '<EMPTY>'}")
        elif key in aliases:
            normalized.add(aliases[key])
        else:
            blockers.append(f"PRICE_BASIS_UNKNOWN_VALUE:{raw}")
    if len(normalized) > 1:
        blockers.append("PRICE_BASIS_MIXED_CONFIRMED_VALUES")
    passed = not blockers and len(normalized) == 1
    return passed, next(iter(normalized)) if len(normalized) == 1 else "UNKNOWN", sorted(set(blockers))


def _candidate_json_files(search_roots: Sequence[Path]) -> list[Path]:
    keywords = (
        "membership", "coverage", "lineage", "certificate", "chung_nhan", "hose",
        "corporate", "hanh_dong", "sector", "nganh", "price_basis", "basis",
    )
    seen: set[Path] = set()
    output: list[Path] = []
    for root in search_roots:
        root = Path(root)
        if not root.exists():
            continue
        paths = [root] if root.is_file() else root.rglob("*.json")
        for path in paths:
            try:
                resolved = path.resolve()
                if resolved in seen or not path.is_file() or path.stat().st_size > MAX_EVIDENCE_BYTES:
                    continue
            except OSError:
                continue
            name = path.name.lower()
            if not any(token in name for token in keywords):
                continue
            seen.add(resolved)
            output.append(path)
            if len(output) >= MAX_EVIDENCE_FILES:
                return sorted(output)
    return sorted(output)


def _walk_dicts(value: object) -> Iterable[Mapping[str, object]]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _date_covers(record: Mapping[str, object], target: date) -> bool:
    try:
        start = date.fromisoformat(str(record.get("range_start"))[:10])
        end = date.fromisoformat(str(record.get("range_end"))[:10])
    except (TypeError, ValueError):
        return False
    return start <= target < end or start <= target <= end


def _scan_evidence(search_roots: Sequence[Path], *, target_day: date, store_sha: str) -> dict[str, object]:
    candidates: list[dict[str, object]] = []
    passes = {
        "pit_hose_membership": False,
        "corporate_actions": False,
        "pit_sector_master": False,
        "price_basis_certificate": False,
    }
    for path in _candidate_json_files(search_roots):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        for record in _walk_dicts(payload):
            contract = str(record.get("contract_version") or record.get("schema_version") or "")
            matched: list[str] = []
            nonfixture = record.get("is_fixture") is False
            research = record.get("research_eligible") is True
            complete = record.get("complete") is True or record.get("inventory_complete") is True
            gaps = record.get("gaps") or []
            conflicts = record.get("conflicts") or []
            covers = _date_covers(record, target_day)
            if contract in {"pit_hose_membership_v1", "hose_membership_interval_v1"}:
                matched.append("pit_hose_membership")
                if nonfixture and research and complete and not gaps and not conflicts and covers:
                    passes["pit_hose_membership"] = True
            if contract == "pit_sector_master_v1":
                matched.append("pit_sector_master")
                if nonfixture and research and complete and not gaps and not conflicts and covers:
                    passes["pit_sector_master"] = True
            if "inventory_complete" in record and "research_eligible" in record and "is_fixture" in record:
                matched.append("corporate_actions")
                if nonfixture and research and record.get("inventory_complete") is True and not conflicts and covers:
                    passes["corporate_actions"] = True
            if contract == "price_basis_certificate_v1":
                matched.append("price_basis_certificate")
                bound_sha = str(record.get("store_sha256") or "")
                basis = str(record.get("price_basis") or "").upper()
                if (
                    nonfixture and research and record.get("confirmed") is True
                    and bound_sha == store_sha and basis in {"ADJUSTED", "UNADJUSTED"}
                    and not conflicts
                ):
                    passes["price_basis_certificate"] = True
            if matched:
                candidates.append({
                    "path": str(path),
                    "sha256": _sha_file(path),
                    "contract": contract,
                    "matched_gates": matched,
                    "research_eligible": record.get("research_eligible"),
                    "is_fixture": record.get("is_fixture"),
                    "covers_target_day": covers,
                })
    return {"passes": passes, "candidates": candidates, "files_scanned": len(_candidate_json_files(search_roots))}


def _lineage_audit(store: Path, search_roots: Sequence[Path]) -> dict[str, object]:
    store_sha = _sha_file(store)
    inventory = _store_inventory(store)
    target_day = date.fromisoformat(str(inventory["last_day"]))
    basis_pass, basis_name, basis_blockers = _price_basis_from_store(inventory)
    evidence = _scan_evidence(search_roots, target_day=target_day, store_sha=store_sha)
    passes = dict(evidence["passes"])
    price_pass = basis_pass or bool(passes["price_basis_certificate"])
    blockers: list[str] = []
    if not passes["pit_hose_membership"]:
        blockers.append("PIT_HOSE_MEMBERSHIP_LINEAGE_INCOMPLETE")
    if not price_pass:
        blockers.append("PRICE_BASIS_UNCONFIRMED")
    if not passes["corporate_actions"]:
        blockers.append("CORPORATE_ACTION_INVENTORY_INCOMPLETE")
    if not passes["pit_sector_master"]:
        blockers.append("PIT_SECTOR_MASTER_INCOMPLETE")
    return {
        "store_sha256": store_sha,
        "store_inventory": inventory,
        "price_basis": {
            "passed": price_pass,
            "store_basis_passed": basis_pass,
            "store_basis": basis_name,
            "blockers": basis_blockers,
            "external_bound_certificate_passed": bool(passes["price_basis_certificate"]),
        },
        "pit_hose_membership": {"passed": bool(passes["pit_hose_membership"])},
        "corporate_actions": {"passed": bool(passes["corporate_actions"])},
        "pit_sector_master": {"passed": bool(passes["pit_sector_master"])},
        "evidence_scan": evidence,
        "canonical_data_gates_passed": not blockers,
        "blockers": blockers,
        "paper_oos_allowed_despite_open_gates": True,
        "promotion_authorized": False,
    }


def _gap18_symbols(store: Path, *, cutoff: date | None = None) -> tuple[list[str], dict[str, object]]:
    report = basis_audit.build_report(store)
    gap_symbols = {
        str(row.get("symbol") or "").upper()
        for row in report.get("gap_events", [])
        if isinstance(row, Mapping)
        and (cutoff is None or date.fromisoformat(str(row.get("day"))[:10]) <= cutoff)
    }
    all_symbols = set(v76._all_store_symbols(store))
    return sorted(all_symbols - gap_symbols), report


def _freeze_manifest(
    *,
    state_dir: Path,
    store: Path,
    git_head: str,
    captured_at: datetime,
    fixed_symbols: Sequence[str],
) -> dict[str, object]:
    path = state_dir / "freeze_manifest.json"
    store_sha = _sha_file(store)
    latest = _latest_market_day(store)
    candidate = {
        "schema_version": FREEZE_SCHEMA,
        "created_at": captured_at.astimezone(timezone.utc).isoformat(),
        "freeze_market_day": latest.isoformat(),
        "store_sha256_at_freeze": store_sha,
        "git_head_at_freeze": git_head,
        "champion_model": CHAMPION_MODEL,
        "shadow_model": SHADOW_MODEL,
        "primary_variant": PRIMARY_VARIANT,
        "primary_allocator": PRIMARY_ALLOCATOR,
        "variant_symbols": list(fixed_symbols),
        "paper_cost_contract": PAPER_COST_CONTRACT,
        "year_2026_historical_results_used_for_future_model_changes": False,
        "future_model_mutation_allowed": False,
        "capital_authorized": False,
    }
    if path.is_file():
        existing = json.loads(path.read_text(encoding="utf-8-sig"))
        immutable_keys = (
            "schema_version", "freeze_market_day", "store_sha256_at_freeze", "git_head_at_freeze",
            "champion_model", "shadow_model", "primary_variant", "primary_allocator", "variant_symbols",
            "future_model_mutation_allowed", "capital_authorized",
        )
        for key in immutable_keys:
            if existing.get(key) != candidate.get(key):
                # Store SHA/git HEAD naturally change after freeze. Their original values are immutable,
                # so compare only the experiment definition below, not current invocation metadata.
                if key in {"store_sha256_at_freeze", "git_head_at_freeze", "freeze_market_day"}:
                    continue
                raise ValueError(f"V77_FREEZE_MANIFEST_CONFLICT:{key}")
        return existing
    state_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_text(candidate), encoding="utf-8")
    return candidate


def _analysis_end_for_capture(capture_day: date, wall_date: date, month_close_confirmed: bool) -> date:
    if month_close_confirmed:
        return _next_month(capture_day)
    if _month_key(capture_day) < _month_key(wall_date):
        return _first_of_month(wall_date)
    return _first_of_month(capture_day)


def _build_rank_snapshot(
    *,
    store: Path,
    fixed_symbols: Sequence[str],
    capture_day: date,
    wall_date: date,
    month_close_confirmed: bool,
) -> dict[str, object]:
    analysis_end = _analysis_end_for_capture(capture_day, wall_date, month_close_confirmed)
    with tempfile.TemporaryDirectory(prefix="v77_diag_") as tmp:
        diag = Path(tmp) / "diagnostic.sqlite3"
        v68safe._safe_create_diagnostic_store(store, diag, fixed_symbols)
        v68safe.install_resource_safe_sqlite_paths()
        market67 = c3driver.core.load_market(diag, price_multiplier=PRICE_MULTIPLIER)
        snapshots, _training, _rank_rows, _weights = c3driver._build_monthly_c3(
            market=market67,
            analysis_end=analysis_end,
        )
        if not snapshots:
            raise ValueError("V77_C3_SNAPSHOT_EMPTY")
        snapshot = snapshots[-1]
        source_day = snapshot.day
        if source_day > capture_day:
            raise ValueError("V77_SOURCE_SIGNAL_AFTER_CAPTURE")
        c3_rows = [
            {"symbol": symbol, "rank": rank, "score": float(snapshot.scores[symbol])}
            for rank, symbol in enumerate(snapshot.ranking, start=1)
        ]

        market70 = v70.load_market(diag, fixed_symbols)
        panel, ic_rows = v76._build_panel(market70, fixed_symbols, end=source_day)
        panel_map = {(row.signal_day, row.symbol): row for row in panel}
        test = [panel_map.get((source_day, symbol)) for symbol in snapshot.ranking]
        if any(row is None for row in test):
            missing = [snapshot.ranking[i] for i, row in enumerate(test) if row is None]
            raise ValueError("V77_RIDGE_TEST_FEATURE_MISSING:" + ",".join(missing))
        split = v76._split_safe_history(panel, source_day)
        if split is None:
            raise ValueError("V77_RIDGE_INSUFFICIENT_SAFE_HISTORY")
        train, validation = split
        scores, meta = v76._fit_ridge(
            train,
            validation,
            [row for row in test if row is not None],
            ic_rows,
            context=False,
        )
        ridge_scored = sorted(
            [(snapshot.ranking[i], float(scores[i])) for i in range(len(scores))],
            key=lambda item: (-item[1], item[0]),
        )
        ridge_rows = [
            {"symbol": symbol, "rank": rank, "score": score}
            for rank, (symbol, score) in enumerate(ridge_scored, start=1)
        ]
    return {
        "capture_day": capture_day.isoformat(),
        "source_signal_day": source_day.isoformat(),
        "analysis_end": analysis_end.isoformat(),
        "risk_on": bool(snapshot.risk_on),
        "eligible_count": int(snapshot.eligible_count),
        "history_months": int(snapshot.history_months),
        "c3_weights": dict(snapshot.weights),
        "ridge_fit": meta,
        "rankings": {
            CHAMPION_MODEL: c3_rows,
            SHADOW_MODEL: ridge_rows,
        },
    }


def _signal_payload(rows: Sequence[Mapping[str, object]]) -> bytes:
    from io import StringIO
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=SIGNAL_FIELDS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in SIGNAL_FIELDS})
    return stream.getvalue().encode("utf-8")


def _model_signal_files(state_dir: Path, model_id: str) -> list[Path]:
    safe = model_id.lower().replace("/", "_")
    return sorted((state_dir / "signals" / safe).glob("*.csv"))


def _existing_source_days(state_dir: Path, model_id: str) -> set[str]:
    days: set[str] = set()
    for path in _model_signal_files(state_dir, model_id):
        for row in _read_csv(path):
            if row.get("source_signal_day"):
                days.add(row["source_signal_day"])
    return days


def _record_model_signal(
    *,
    state_dir: Path,
    model_id: str,
    capture_day: date,
    source_day: date,
    captured_at: datetime,
    ranking: Sequence[Mapping[str, object]],
    risk_on: bool,
    git_head: str,
    store_sha: str,
) -> tuple[Path | None, bool]:
    if source_day.isoformat() in _existing_source_days(state_dir, model_id):
        return None, False
    top = list(ranking[:10])
    if len(top) < 10:
        raise ValueError(f"V77_TOP10_INCOMPLETE:{model_id}")
    weight = Decimal("10")
    rows = [
        {
            "paper_signal_day": capture_day.isoformat(),
            "source_signal_day": source_day.isoformat(),
            "captured_at": captured_at.astimezone(timezone.utc).isoformat(),
            "model_id": model_id,
            "variant_id": PRIMARY_VARIANT,
            "allocator": PRIMARY_ALLOCATOR,
            "symbol": str(row["symbol"]),
            "rank": int(row["rank"]),
            "model_score": float(row["score"]),
            "target_weight_pct": str(weight),
            "risk_on": str(bool(risk_on)).lower(),
            "git_head": git_head,
            "store_sha256": store_sha,
        }
        for row in top
    ]
    payload = _signal_payload(rows)
    digest = _sha_bytes(payload)
    safe = model_id.lower().replace("/", "_")
    directory = state_dir / "signals" / safe
    directory.mkdir(parents=True, exist_ok=True)
    same_capture = sorted(directory.glob(f"{capture_day.isoformat()}_*.csv"))
    for path in same_capture:
        if path.read_bytes() == payload:
            return path, False
        raise ValueError(f"V77_SIGNAL_CONFLICT:{model_id}:{capture_day}")
    path = directory / f"{capture_day.isoformat()}_{source_day.isoformat()}_{digest[:12]}.csv"
    path.write_bytes(payload)
    return path, True


def _all_model_signals(state_dir: Path, model_id: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for path in _model_signal_files(state_dir, model_id):
        for row in _read_csv(path):
            key = (row["paper_signal_day"], row["symbol"])
            if key in seen:
                raise ValueError(f"V77_DUPLICATE_SIGNAL:{model_id}:{key[0]}:{key[1]}")
            seen.add(key)
            rows.append(row)
    return sorted(rows, key=lambda row: (row["paper_signal_day"], int(row["rank"]), row["symbol"]))


def _store_price_rows(store: Path, symbols: set[str], first_day: date) -> list[thanh_gia]:
    uri = Path(store).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        cols = {str(r[1]).lower(): str(r[1]) for r in db.execute('PRAGMA table_info("bars")')}
        required = {"symbol", "day", "open", "close", "volume", "asset_type"}
        if not required.issubset(cols):
            raise ValueError("V77_PRICE_REPLAY_COLUMNS_MISSING")
        q = lambda x: '"' + x.replace('"', '""') + '"'
        sql = (
            f"SELECT {q(cols['symbol'])},{q(cols['day'])},{q(cols['open'])},{q(cols['close'])},{q(cols['volume'])},{q(cols['asset_type'])} "
            f"FROM bars WHERE {q(cols['day'])}>=? ORDER BY {q(cols['day'])},{q(cols['symbol'])}"
        )
        output: list[thanh_gia] = []
        for symbol, raw_day, open_price, close_price, volume, asset_type in db.execute(sql, (first_day.isoformat(),)):
            sym = str(symbol or "").strip().upper()
            if sym not in symbols or str(asset_type or "").strip().upper() != "STOCK":
                continue
            day = date.fromisoformat(str(raw_day)[:10])
            try:
                op = Decimal(str(open_price))
                cl = Decimal(str(close_price))
                vol = int(volume or 0)
            except Exception:
                continue
            if op <= 0 or cl <= 0 or vol < 0:
                continue
            output.append(thanh_gia(
                ma=sym,
                ngay=day,
                gia_mo_cua=op,
                gia_dong_cua=cl,
                khoi_luong=vol,
                thuoc_tap_co_phieu=True,
                dat_thanh_khoan=True,
            ))
    if not output:
        raise ValueError("V77_PAPER_PRICE_ROWS_EMPTY")
    return output


def _dataclass_rows(items: Sequence[object]) -> list[dict[str, object]]:
    if not items:
        return []
    names = [field.name for field in fields(items[0])]
    output = []
    for item in items:
        row = {}
        for name in names:
            value = getattr(item, name)
            if isinstance(value, Decimal):
                value = str(value)
            elif isinstance(value, date):
                value = value.isoformat()
            row[name] = value
        output.append(row)
    return output


def _replay_model(state_dir: Path, store: Path, model_id: str, output_dir: Path) -> dict[str, object]:
    signals = _all_model_signals(state_dir, model_id)
    if not signals:
        return {"model_id": model_id, "status": "WAITING_FOR_SIGNAL", "signal_count": 0}
    symbols = {row["symbol"] for row in signals}
    first_day = min(date.fromisoformat(row["paper_signal_day"]) for row in signals)
    prices = _store_price_rows(store, symbols, first_day)
    paper_rows = [
        {
            "signal_date": row["paper_signal_day"],
            "symbol": row["symbol"],
            "champion_model": model_id,
            "rank": row["rank"],
            "target_weight_pct": row["target_weight_pct"],
            "status": "FROZEN_FRESH_OOS",
            "source_zip_sha256": "V77_DIRECT_STORE_SIGNAL",
        }
        for row in signals
    ]
    config = paper._config(
        initial_capital_vnd=INITIAL_CAPITAL_VND,
        buy_fee_bps=BUY_FEE_BPS,
        sell_fee_bps=SELL_FEE_BPS,
        sell_tax_bps=SELL_TAX_BPS,
        slippage_bps=SLIPPAGE_BPS,
        lot_size=LOT_SIZE,
    )
    result = chay_mo_phong(prices, paper._targets(paper_rows), config)
    latest_market = max(row.ngay for row in prices)
    orders = paper._order_rows(result, latest_market)
    nav_rows = _dataclass_rows(result.nav)
    fill_rows = _dataclass_rows(result.khop_lenh)
    position_rows = _dataclass_rows(result.vi_the_hang_ngay)
    safe = model_id.lower().replace("/", "_")
    _write_csv(output_dir / f"v77_{safe}_nav.csv", nav_rows)
    _write_csv(output_dir / f"v77_{safe}_fills.csv", fill_rows)
    _write_csv(output_dir / f"v77_{safe}_orders.csv", orders)
    _write_csv(output_dir / f"v77_{safe}_positions_daily.csv", position_rows)
    nav_values = [row.nav for row in result.nav]
    last_nav = nav_values[-1]
    freeze_day = date.fromisoformat(json.loads((state_dir / "freeze_manifest.json").read_text(encoding="utf-8"))["freeze_market_day"])
    fresh_sessions = [row for row in result.nav if row.ngay > freeze_day]
    pending = sum(row["status"] == "PENDING_NEXT_SESSION" for row in orders)
    return {
        "model_id": model_id,
        "status": "ACTIVE" if result.khop_lenh else "PENDING_FIRST_EXECUTION",
        "signal_date_count": len({row["paper_signal_day"] for row in signals}),
        "source_signal_date_count": len({row["source_signal_day"] for row in signals}),
        "fill_count": len(result.khop_lenh),
        "pending_order_count": pending,
        "latest_market_day": latest_market.isoformat(),
        "latest_nav_vnd": float(last_nav * Decimal("1000")),
        "total_return": float(last_nav / config.von_ban_dau - Decimal("1")),
        "max_drawdown": float(paper._max_drawdown(nav_values)),
        "fresh_oos_session_count": len(fresh_sessions),
        "paper_cost_contract": PAPER_COST_CONTRACT,
        "transfer_fee_modeled": False,
        "research_only": True,
        "capital_authorized": False,
    }


def _requirements() -> dict[str, object]:
    return {
        "pit_hose_membership": {
            "contract_version": "pit_hose_membership_v1",
            "required": ["range_start", "range_end", "complete=true", "gaps=[]", "conflicts=[]", "research_eligible=true", "is_fixture=false", "source_document_ids"],
        },
        "price_basis": {
            "preferred_store_state": "all bars use one explicit ADJUSTED or UNADJUSTED basis",
            "external_certificate_contract": "price_basis_certificate_v1",
            "external_certificate_must_bind_store_sha256": True,
        },
        "corporate_actions": {
            "required": ["range_start", "range_end", "inventory_complete=true", "conflicts=[]", "research_eligible=true", "is_fixture=false", "source_document_ids"],
        },
        "pit_sector_master": {
            "contract_version": "pit_sector_master_v1",
            "required": ["range_start", "range_end", "complete=true", "gaps=[]", "conflicts=[]", "research_eligible=true", "is_fixture=false", "source_document_ids"],
        },
        "rule": "Paper OOS may run with blockers, but promotion/canonical HOSE claims remain fail-closed.",
    }


def run(
    *,
    store: Path,
    state_dir: Path,
    output_dir: Path,
    search_roots: Sequence[Path] = (),
    git_head: str = "UNKNOWN",
    captured_at: datetime | None = None,
    month_close_confirmed: bool = False,
) -> dict[str, object]:
    store = Path(store)
    if not store.is_file():
        raise ValueError("V77_STORE_NOT_FOUND")
    captured_at = captured_at or datetime.now(timezone.utc)
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("V77_CAPTURE_TIME_MUST_HAVE_TIMEZONE")
    state_dir = Path(state_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    before_sha = _sha_file(store)
    capture_day = _latest_market_day(store)

    if (state_dir / "freeze_manifest.json").is_file():
        freeze = json.loads((state_dir / "freeze_manifest.json").read_text(encoding="utf-8-sig"))
        fixed_symbols = [str(x).upper() for x in freeze["variant_symbols"]]
        basis_report = basis_audit.build_report(store)
    else:
        fixed_symbols, basis_report = _gap18_symbols(store, cutoff=capture_day)
        if len(fixed_symbols) < 10:
            raise ValueError("V77_GAP18_FIXED_UNIVERSE_TOO_SMALL")
        freeze = _freeze_manifest(
            state_dir=state_dir,
            store=store,
            git_head=git_head,
            captured_at=captured_at,
            fixed_symbols=fixed_symbols,
        )

    wall_date = captured_at.astimezone(timezone.utc).date()
    rank_snapshot = _build_rank_snapshot(
        store=store,
        fixed_symbols=fixed_symbols,
        capture_day=capture_day,
        wall_date=wall_date,
        month_close_confirmed=month_close_confirmed,
    )
    source_day = date.fromisoformat(rank_snapshot["source_signal_day"])
    store_sha = _sha_file(store)
    appended: dict[str, bool] = {}
    signal_paths: dict[str, str | None] = {}
    for model_id in (CHAMPION_MODEL, SHADOW_MODEL):
        path, created = _record_model_signal(
            state_dir=state_dir,
            model_id=model_id,
            capture_day=capture_day,
            source_day=source_day,
            captured_at=captured_at,
            ranking=rank_snapshot["rankings"][model_id],
            risk_on=bool(rank_snapshot["risk_on"]),
            git_head=git_head,
            store_sha=store_sha,
        )
        appended[model_id] = created
        signal_paths[model_id] = str(path) if path else None

    lineage = _lineage_audit(store, search_roots)
    paper_results = {
        CHAMPION_MODEL: _replay_model(state_dir, store, CHAMPION_MODEL, output_dir),
        SHADOW_MODEL: _replay_model(state_dir, store, SHADOW_MODEL, output_dir),
    }
    champion = paper_results[CHAMPION_MODEL]
    shadow = paper_results[SHADOW_MODEL]
    comparison = {
        "champion_model": CHAMPION_MODEL,
        "shadow_model": SHADOW_MODEL,
        "champion_total_return": champion.get("total_return"),
        "shadow_total_return": shadow.get("total_return"),
        "shadow_minus_champion_total_return": (
            float(shadow["total_return"]) - float(champion["total_return"])
            if "total_return" in shadow and "total_return" in champion else None
        ),
        "champion_latest_nav_vnd": champion.get("latest_nav_vnd"),
        "shadow_latest_nav_vnd": shadow.get("latest_nav_vnd"),
        "fresh_oos_session_count": min(
            int(champion.get("fresh_oos_session_count") or 0),
            int(shadow.get("fresh_oos_session_count") or 0),
        ),
        "promotion_authorized": False,
    }

    rank_rows: list[dict[str, object]] = []
    for model_id, rows in rank_snapshot["rankings"].items():
        for row in rows:
            rank_rows.append({
                "capture_market_day": capture_day.isoformat(),
                "source_signal_day": source_day.isoformat(),
                "model_id": model_id,
                "risk_on": rank_snapshot["risk_on"],
                **dict(row),
            })
    _write_csv(output_dir / "v77_current_rankings.csv", rank_rows)
    _write_csv(output_dir / "v77_paper_summary.csv", list(paper_results.values()))
    (output_dir / "v77_data_lineage_report.json").write_text(_json_text(lineage), encoding="utf-8")
    (output_dir / "v77_evidence_requirements.json").write_text(_json_text(_requirements()), encoding="utf-8")
    (output_dir / "v77_freeze_manifest_copy.json").write_text(_json_text(freeze), encoding="utf-8")

    after_sha = _sha_file(store)
    if after_sha != before_sha:
        raise RuntimeError("V77_MARKET_STORE_MUTATED")
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "champion_model": CHAMPION_MODEL,
        "shadow_model": SHADOW_MODEL,
        "champion_replaced": False,
        "primary_variant": PRIMARY_VARIANT,
        "primary_allocator": PRIMARY_ALLOCATOR,
        "freeze": freeze,
        "capture_market_day": capture_day.isoformat(),
        "source_signal_day": source_day.isoformat(),
        "capture_wall_time": captured_at.isoformat(),
        "source_to_capture_calendar_lag_days": (capture_day - source_day).days,
        "month_close_confirmed": month_close_confirmed,
        "fixed_variant_symbol_count": len(fixed_symbols),
        "basis_gap_event_count": len(basis_report.get("gap_events", [])),
        "signals_appended": appended,
        "signal_paths": signal_paths,
        "ranking_snapshot": {
            "risk_on": rank_snapshot["risk_on"],
            "eligible_count": rank_snapshot["eligible_count"],
            "history_months": rank_snapshot["history_months"],
            "c3_weights": rank_snapshot["c3_weights"],
            "ridge_fit": rank_snapshot["ridge_fit"],
        },
        "paper_results": paper_results,
        "paper_comparison": comparison,
        "data_lineage": lineage,
        "store_sha256_before": before_sha,
        "store_sha256_after": after_sha,
        "store_mutated": False,
        "fresh_oos_only_for_promotion_evidence": True,
        "historical_2026_results_not_counted_as_fresh_oos": True,
        "paper_oos_can_run_with_open_data_gates": True,
        "canonical_data_gates_passed": lineage["canonical_data_gates_passed"],
        "promotion_authorized": False,
        "live_orders_allowed": False,
    }
    (output_dir / "v77_report.json").write_text(_json_text(report), encoding="utf-8")
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m he_thong_dinh_luong.paper_oos_data_lineage_v77")
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--search-root", type=Path, action="append", default=[])
    parser.add_argument("--git-head", default="UNKNOWN")
    parser.add_argument("--capture-time", default=None, help="timezone-aware ISO8601; default now UTC")
    parser.add_argument("--month-close-confirmed", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        captured = datetime.fromisoformat(args.capture_time) if args.capture_time else None
        report = run(
            store=args.store,
            state_dir=args.state_dir,
            output_dir=args.output_dir,
            search_roots=args.search_root,
            git_head=args.git_head,
            captured_at=captured,
            month_close_confirmed=args.month_close_confirmed,
        )
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "error": f"{type(exc).__name__}:{exc}"}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps({
        "status": report["status"],
        "capture_market_day": report["capture_market_day"],
        "source_signal_day": report["source_signal_day"],
        "signals_appended": report["signals_appended"],
        "champion_paper": report["paper_results"][CHAMPION_MODEL],
        "shadow_paper": report["paper_results"][SHADOW_MODEL],
        "data_gate_blockers": report["data_lineage"]["blockers"],
        "promotion_authorized": False,
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
