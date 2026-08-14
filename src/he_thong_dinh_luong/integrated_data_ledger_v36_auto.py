"""Automatic reference preparation inside the same integrated V36 release.

This layer removes two mechanical blockers without weakening governance:

* derive the exact VNINDEX open series from the canonical SQLite store;
* approve quarantine only when every invalid bar is high/low-range-only and
  none overlaps a V36 execution key.

It never confirms price basis, sector completeness, corporate-action
completeness, research eligibility, or live-capital permission.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Mapping, Sequence

from . import integrated_data_ledger_v36 as base
from . import integrated_data_ledger_v36_strict as strict

AUTO_BENCHMARK_FILE = "vnindex_ohlcv_derived_v36.csv"
AUTO_ASSURANCE_FILE = "data_assurance_auto_candidate_v36.json"

_INVALID_FIELDS = (
    "source_rowid",
    "day",
    "symbol",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "previous_day",
    "previous_close",
    "next_day",
    "next_open",
    "year",
    "reason_count",
    "reasons",
    "category",
    "execution_critical",
    "quarantine_required",
    "automatic_correction_allowed",
)
_ALLOWED_RANGE_REASONS = {
    "HIGH_BELOW_OPEN_OR_CLOSE",
    "LOW_ABOVE_OPEN_OR_CLOSE",
}


def _quote(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def derive_vnindex_from_sqlite(
    sqlite_store: Path,
    destination: Path,
) -> dict[str, object]:
    """Export the canonical SQLite VNINDEX opens without changing values."""
    connection = base._connect_readonly(sqlite_store)
    try:
        columns = [
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(bars)")
        ]
        resolved = base.v35._resolve_columns(columns)
        missing = [
            logical
            for logical in ("day", "symbol", "open")
            if not resolved.get(logical)
        ]
        if missing:
            raise ValueError(
                "V36_AUTO_VNINDEX_COLUMNS_MISSING:" + "|".join(missing)
            )
        day_col = _quote(str(resolved["day"]))
        symbol_col = _quote(str(resolved["symbol"]))
        open_col = _quote(str(resolved["open"]))
        rows = [
            {
                "symbol": "VNINDEX",
                "day": str(row["day"])[:10],
                "open": row["open"],
                "source": "CANONICAL_DNSE_SQLITE",
                "confirmed_at": "AUTO_DERIVED_V36",
            }
            for row in connection.execute(
                f"""
                SELECT {day_col} AS day, {open_col} AS open
                FROM bars
                WHERE UPPER(TRIM(CAST({symbol_col} AS TEXT))) IN
                      ('VNINDEX', 'VN-INDEX', 'VN_INDEX')
                ORDER BY {day_col}
                """
            )
        ]
    finally:
        connection.close()
    if not rows:
        raise ValueError("V36_AUTO_VNINDEX_ROWS_MISSING")
    destination.parent.mkdir(parents=True, exist_ok=True)
    base._write_csv(
        destination,
        rows,
        ("symbol", "day", "open", "source", "confirmed_at"),
    )
    return {
        "path": str(destination),
        "sha256": base._sha256(destination),
        "row_count": len(rows),
        "source": "CANONICAL_DNSE_SQLITE",
    }


def deterministic_quarantine_evidence(
    *,
    sqlite_store: Path,
    expected_sqlite_sha256: str,
    v33_artifact_zip: Path,
    expected_v33_sha256: str,
    v32_artifact_zip: Path,
    expected_v32_sha256: str,
    temporary_invalid_csv: Path,
) -> dict[str, object]:
    """Prove whether the invalid-bar quarantine can be machine-approved."""
    sqlite_audit = base.v35.audit_sqlite(
        sqlite_store,
        expected_sqlite_sha256,
    )
    v33 = base._verified_v33(v33_artifact_zip, expected_v33_sha256)
    v32 = base._verified_v32(v32_artifact_zip, expected_v32_sha256)
    signal_dates = [
        str(row.get("signal_date") or "")
        for row in v33["periods"]
    ]
    selections = base.rebuild_cap3_selections(
        v32["predictions"],
        signal_dates,
    )
    invalid_rows = base.extract_invalid_ohlcv(
        sqlite_store,
        sqlite_audit["resolved_columns"],
    )
    critical_keys = base.execution_critical_keys(
        sqlite_store,
        selections,
        v33["periods"],
    )
    critical_count = 0
    range_only = True
    reason_counts: dict[str, int] = {}
    for row in invalid_rows:
        key = (
            str(row.get("day") or ""),
            str(row.get("symbol") or ""),
        )
        is_critical = key in critical_keys
        row["execution_critical"] = is_critical
        critical_count += int(is_critical)
        reasons = {
            item
            for item in str(row.get("reasons") or "").split("|")
            if item
        }
        for reason in reasons:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        range_only = bool(
            range_only
            and str(row.get("category") or "")
            == "OHLC_RANGE_INCONSISTENT"
            and reasons
            and reasons <= _ALLOWED_RANGE_REASONS
        )
    base._write_csv(
        temporary_invalid_csv,
        invalid_rows,
        _INVALID_FIELDS,
    )
    invalid_sha = base._sha256(temporary_invalid_csv)
    approved = bool(range_only and critical_count == 0)
    return {
        "approved": approved,
        "invalid_row_count": len(invalid_rows),
        "execution_critical_count": critical_count,
        "range_only": range_only,
        "reason_counts": dict(sorted(reason_counts.items())),
        "invalid_ohlcv_export_sha256": invalid_sha,
        "sqlite_audit": sqlite_audit,
    }


def _load_existing_assurance(path: Path | None) -> dict[str, object]:
    if path is None or not Path(path).is_file():
        return {}
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def build_auto_assurance_candidate(
    *,
    existing_path: Path | None,
    destination: Path,
    quarantine: Mapping[str, object],
    benchmark: Mapping[str, object],
    sector_master: Path | None,
    corporate_actions: Path | None,
) -> dict[str, object]:
    """Create a non-promotional assurance candidate for the same V36 run."""
    sqlite_audit = dict(quarantine["sqlite_audit"])
    value = _load_existing_assurance(existing_path)
    evidence = list(value.get("evidence") or [])
    evidence.append(
        {
            "type": "V36_DETERMINISTIC_HIGH_LOW_QUARANTINE",
            "approved": bool(quarantine["approved"]),
            "invalid_row_count": int(quarantine["invalid_row_count"]),
            "execution_critical_count": int(
                quarantine["execution_critical_count"]
            ),
            "range_only": bool(quarantine["range_only"]),
            "reason_counts": dict(quarantine["reason_counts"]),
            "invalid_ohlcv_export_sha256": quarantine[
                "invalid_ohlcv_export_sha256"
            ],
            "ledger_fields_used": ["open", "close", "volume"],
            "high_low_used_by_ledger": False,
        }
    )
    value.update(
        {
            "schema_version": base.ASSURANCE_SCHEMA,
            "coverage_first_day": str(sqlite_audit["first_day"]),
            "coverage_last_day": str(sqlite_audit["last_day"]),
            "sqlite_sha256": str(sqlite_audit["sha256"]),
            "invalid_ohlcv_export_sha256": quarantine[
                "invalid_ohlcv_export_sha256"
            ],
            "invalid_ohlcv_quarantine_approved": bool(
                quarantine["approved"]
            ),
            "vnindex_ohlcv_sha256": str(benchmark["sha256"]),
            "vnindex_next_open_complete": True,
            "price_basis_mode": value.get(
                "price_basis_mode",
                base.PRICE_BASIS_MODE,
            ),
            "price_unit_vnd_multiplier": value.get(
                "price_unit_vnd_multiplier",
                1000,
            ),
            "price_basis_confirmed": value.get(
                "price_basis_confirmed"
            ) is True,
            "point_in_time_sector_master_complete": value.get(
                "point_in_time_sector_master_complete"
            ) is True,
            "corporate_actions_complete": value.get(
                "corporate_actions_complete"
            ) is True,
            "cash_dividend_tax_bps": value.get(
                "cash_dividend_tax_bps",
                0.0,
            ),
            "sector_master_sha256": (
                base._sha256(sector_master)
                if sector_master is not None
                and Path(sector_master).is_file()
                else str(value.get("sector_master_sha256") or "")
            ),
            "corporate_actions_sha256": (
                base._sha256(corporate_actions)
                if corporate_actions is not None
                and Path(corporate_actions).is_file()
                else str(value.get("corporate_actions_sha256") or "")
            ),
            "reviewer": "V36_DETERMINISTIC_RULE_ENGINE",
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "evidence": evidence,
        }
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    base._write_json(destination, value)
    return value


def run_v36_auto(
    *,
    benchmark_ohlcv: Path | None,
    **kwargs: object,
) -> dict[str, object]:
    """Run strict V36 with only mechanically provable blockers auto-resolved."""
    output_dir = Path(kwargs["output_dir"]).resolve()
    temporary_root = output_dir.parent / f".{output_dir.name}-auto"
    temporary_root.mkdir(parents=True, exist_ok=False)
    derived_benchmark = temporary_root / AUTO_BENCHMARK_FILE
    temporary_invalid = temporary_root / "invalid_ohlcv_rows_v36.csv"
    auto_assurance = temporary_root / AUTO_ASSURANCE_FILE
    try:
        if benchmark_ohlcv is None:
            benchmark_meta = derive_vnindex_from_sqlite(
                Path(kwargs["sqlite_store"]),
                derived_benchmark,
            )
            benchmark_ohlcv = derived_benchmark
            benchmark_source = "AUTO_DERIVED_FROM_CANONICAL_SQLITE"
        else:
            benchmark_meta = {
                "path": str(Path(benchmark_ohlcv).resolve()),
                "sha256": base._sha256(Path(benchmark_ohlcv)),
                "source": "USER_PROVIDED",
            }
            benchmark_source = "USER_PROVIDED"

        quarantine = deterministic_quarantine_evidence(
            sqlite_store=Path(kwargs["sqlite_store"]),
            expected_sqlite_sha256=str(
                kwargs.get("expected_sqlite_sha256") or ""
            ),
            v33_artifact_zip=Path(kwargs["v33_artifact_zip"]),
            expected_v33_sha256=str(
                kwargs.get("expected_v33_sha256") or ""
            ),
            v32_artifact_zip=Path(kwargs["v32_artifact_zip"]),
            expected_v32_sha256=str(
                kwargs.get("expected_v32_sha256") or ""
            ),
            temporary_invalid_csv=temporary_invalid,
        )
        original_assurance = kwargs.get("data_assurance_report")
        build_auto_assurance_candidate(
            existing_path=(
                Path(original_assurance)
                if original_assurance is not None
                else None
            ),
            destination=auto_assurance,
            quarantine=quarantine,
            benchmark=benchmark_meta,
            sector_master=(
                Path(kwargs["sector_master"])
                if kwargs.get("sector_master") is not None
                else None
            ),
            corporate_actions=(
                Path(kwargs["corporate_actions"])
                if kwargs.get("corporate_actions") is not None
                else None
            ),
        )
        kwargs["data_assurance_report"] = auto_assurance
        report = strict.run_v36_strict(
            benchmark_ohlcv=benchmark_ohlcv,
            **kwargs,
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        derived_destination = output_dir / AUTO_BENCHMARK_FILE
        if derived_benchmark.is_file():
            derived_destination.write_bytes(derived_benchmark.read_bytes())
        assurance_destination = output_dir / AUTO_ASSURANCE_FILE
        assurance_destination.write_bytes(auto_assurance.read_bytes())
        report["automatic_reference_preparation"] = {
            "vnindex_source": benchmark_source,
            "vnindex_sha256": benchmark_meta["sha256"],
            "vnindex_row_count": benchmark_meta.get("row_count"),
            "invalid_ohlcv_quarantine_machine_approved": bool(
                quarantine["approved"]
            ),
            "invalid_ohlcv_range_only": bool(quarantine["range_only"]),
            "invalid_ohlcv_execution_critical_count": int(
                quarantine["execution_critical_count"]
            ),
            "price_basis_confirmed_automatically": False,
            "sector_completeness_confirmed_automatically": False,
            "corporate_actions_completeness_confirmed_automatically": False,
        }
        base._write_json(output_dir / base.REPORT_FILE, report)
        return report
    finally:
        for child in sorted(temporary_root.glob("*")):
            if child.is_file():
                child.unlink()
        if temporary_root.exists():
            temporary_root.rmdir()


run_v36 = run_v36_auto


def _parser():
    return strict._parser()


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    values = vars(args)
    benchmark = values.pop("benchmark_ohlcv")
    report = run_v36_auto(
        benchmark_ohlcv=benchmark,
        **values,
    )
    print(
        json.dumps(
            report,
            ensure_ascii=True,
            sort_keys=True,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
