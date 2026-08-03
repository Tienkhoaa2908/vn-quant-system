"""Strict benchmark layer for the integrated V36 release.

The core V36 ledger never receives promotion authority. This layer additionally
requires a cryptographically assured VNINDEX next-open series and replaces the
legacy label-return benchmark with execution-date-matched benchmark returns.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from statistics import fmean
from typing import Mapping, Sequence

from . import integrated_data_ledger_v36 as core

BENCHMARK_COVERAGE_FILE = "benchmark_execution_coverage_v36.csv"
BENCHMARK_TEMPLATE_FILE = "vnindex_ohlcv_template_v36.csv"
REPORT_FILE = core.REPORT_FILE


def _read_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def audit_benchmark(
    path: Path | None,
    required_dates: Sequence[str],
) -> dict[str, object]:
    if path is None:
        return {
            "provided": False,
            "valid": False,
            "blocker": "V36_VNINDEX_NEXT_OPEN_SERIES_MISSING",
            "required_date_count": len(set(required_dates)),
            "covered_date_count": 0,
            "coverage_rows": [
                {"day": day, "required": True, "covered": False, "open": ""}
                for day in sorted(set(required_dates))
            ],
            "open_by_day": {},
        }
    source = Path(path).resolve()
    if not source.is_file():
        return {
            "provided": True,
            "valid": False,
            "blocker": "V36_VNINDEX_NEXT_OPEN_SERIES_NOT_FOUND",
            "required_date_count": len(set(required_dates)),
            "covered_date_count": 0,
            "coverage_rows": [],
            "open_by_day": {},
        }
    rows = _read_csv(source)
    open_by_day: dict[str, float] = {}
    duplicate_days: set[str] = set()
    invalid_rows = 0
    for row in rows:
        symbol = str(row.get("symbol") or row.get("ma") or "VNINDEX").strip().upper()
        if symbol not in {"VNINDEX", "VN-INDEX", "VN_INDEX"}:
            continue
        day = str(row.get("day") or row.get("date") or row.get("ngay") or "")[:10]
        raw = row.get("open", row.get("gia_mo_cua"))
        try:
            value = float(raw)
            valid = bool(day and math.isfinite(value) and value > 0.0)
        except (TypeError, ValueError):
            value = 0.0
            valid = False
        if not valid:
            invalid_rows += 1
            continue
        if day in open_by_day:
            duplicate_days.add(day)
        open_by_day[day] = value
    required = sorted(set(required_dates))
    coverage_rows = [
        {
            "day": day,
            "required": True,
            "covered": day in open_by_day,
            "open": open_by_day.get(day, ""),
        }
        for day in required
    ]
    covered = sum(bool(row["covered"]) for row in coverage_rows)
    valid = bool(
        rows
        and not duplicate_days
        and invalid_rows == 0
        and covered == len(required)
    )
    return {
        "provided": True,
        "path": str(source),
        "sha256": core._sha256(source),
        "row_count": len(rows),
        "unique_day_count": len(open_by_day),
        "duplicate_day_count": len(duplicate_days),
        "invalid_row_count": invalid_rows,
        "required_date_count": len(required),
        "covered_date_count": covered,
        "coverage_complete": covered == len(required),
        "valid": valid,
        "blocker": "" if valid else "V36_VNINDEX_NEXT_OPEN_SERIES_INVALID_OR_INCOMPLETE",
        "coverage_rows": coverage_rows,
        "open_by_day": open_by_day,
    }


def _required_execution_dates(
    sqlite_store: Path,
    periods: Sequence[Mapping[str, object]],
) -> list[str]:
    connection = core._connect_readonly(sqlite_store)
    dates: list[str] = []
    try:
        for index, row in enumerate(periods):
            signal = str(row.get("signal_date") or "")
            start = core._trading_day_after(connection, signal)
            boundary = (
                str(periods[index + 1].get("signal_date") or "")
                if index + 1 < len(periods)
                else str(row.get("label_end") or "")
            )
            end = core._trading_day_after(connection, boundary)
            if start is None or end is None:
                raise ValueError(f"V36_BENCHMARK_EXECUTION_DATE_MISSING:{signal}")
            dates.extend((start, end))
    finally:
        connection.close()
    return sorted(set(dates))


def _benchmark_assurance(
    assurance_path: Path | None,
    audit: Mapping[str, object],
) -> dict[str, object]:
    if assurance_path is None or not Path(assurance_path).is_file():
        return {
            "valid": False,
            "benchmark_complete": False,
            "benchmark_sha256_match": False,
            "blocker": "V36_VNINDEX_ASSURANCE_MISSING",
        }
    try:
        value = json.loads(Path(assurance_path).read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {
            "valid": False,
            "benchmark_complete": False,
            "benchmark_sha256_match": False,
            "blocker": "V36_VNINDEX_ASSURANCE_INVALID",
        }
    if not isinstance(value, Mapping):
        return {
            "valid": False,
            "benchmark_complete": False,
            "benchmark_sha256_match": False,
            "blocker": "V36_VNINDEX_ASSURANCE_NOT_OBJECT",
        }
    complete = value.get("vnindex_next_open_complete") is True
    sha_match = str(value.get("vnindex_ohlcv_sha256") or "") == str(
        audit.get("sha256") or ""
    )
    valid = bool(audit.get("valid") and complete and sha_match)
    return {
        "valid": valid,
        "benchmark_complete": complete,
        "benchmark_sha256_match": sha_match,
        "blocker": "" if valid else "V36_VNINDEX_ASSURANCE_NOT_VERIFIED",
    }


def _patch_assurance_template(output_dir: Path, benchmark: Mapping[str, object]) -> None:
    template = output_dir / core.ASSURANCE_TEMPLATE_FILE
    if not template.is_file():
        return
    value = json.loads(template.read_text(encoding="utf-8-sig"))
    value.update(
        {
            "vnindex_ohlcv_sha256": benchmark.get("sha256", "REPLACE_WITH_SHA256"),
            "vnindex_next_open_complete": False,
        }
    )
    core._write_json(template, value)
    core._write_csv(
        output_dir / BENCHMARK_TEMPLATE_FILE,
        [],
        ("symbol", "day", "open", "source", "confirmed_at"),
    )


def _patch_benchmark_metrics(
    output_dir: Path,
    benchmark: Mapping[str, object],
) -> list[dict[str, object]]:
    periods_path = output_dir / core.LEDGER_PERIODS_FILE
    summary_path = output_dir / core.LEDGER_SUMMARY_FILE
    period_rows = _read_csv(periods_path)
    summary_rows = _read_csv(summary_path)
    open_by_day = {
        str(day): float(value)
        for day, value in dict(benchmark.get("open_by_day") or {}).items()
    }
    groups: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in period_rows:
        groups.setdefault((row["strategy"], row["scenario"]), []).append(row)
    for rows in groups.values():
        rows.sort(key=lambda row: row["signal_date"])
        nav = 1.0
        for row in rows:
            start = row["execution_day"]
            end = row["period_end_execution_day"]
            benchmark_return = open_by_day[end] / open_by_day[start] - 1.0
            nav *= 1.0 + benchmark_return
            row["benchmark_return"] = benchmark_return
            row["net_excess_return"] = float(row["period_net_return"]) - benchmark_return
            row["benchmark_nav"] = nav
            row["benchmark_execution_basis"] = "VNINDEX_NEXT_OPEN_TO_NEXT_OPEN"
    if period_rows:
        fields = list(period_rows[0])
        if "benchmark_execution_basis" not in fields:
            fields.append("benchmark_execution_basis")
        core._write_csv(periods_path, period_rows, fields)
    patched: list[dict[str, object]] = []
    for summary in summary_rows:
        key = (summary["strategy"], summary["scenario"])
        rows = groups[key]
        benchmark_total = math.prod(
            1.0 + float(row["benchmark_return"]) for row in rows
        ) - 1.0
        net_total = float(summary["net_total_return"])
        excess = [float(row["net_excess_return"]) for row in rows]
        updated = dict(summary)
        updated.update(
            {
                "benchmark_total_return": benchmark_total,
                "relative_total_return": (1.0 + net_total) / (1.0 + benchmark_total) - 1.0,
                "positive_net_excess_ratio": sum(value > 0.0 for value in excess) / len(excess),
                "average_net_excess_return": fmean(excess),
                "benchmark_execution_basis": "VNINDEX_NEXT_OPEN_TO_NEXT_OPEN",
            }
        )
        patched.append(updated)
    if patched:
        core._write_csv(summary_path, patched, tuple(patched[0]))
    return patched


def run_v36_strict(
    *,
    benchmark_ohlcv: Path | None,
    **kwargs: object,
) -> dict[str, object]:
    v33 = core._verified_v33(
        Path(kwargs["v33_artifact_zip"]),
        str(kwargs.get("expected_v33_sha256") or ""),
    )
    required_dates = _required_execution_dates(
        Path(kwargs["sqlite_store"]),
        v33["periods"],
    )
    benchmark = audit_benchmark(benchmark_ohlcv, required_dates)
    benchmark_assurance = _benchmark_assurance(
        kwargs.get("data_assurance_report"),
        benchmark,
    )
    original_assurance = kwargs.get("data_assurance_report")
    if not benchmark_assurance["valid"]:
        kwargs["data_assurance_report"] = None
    report = core.run_v36(**kwargs)
    output_dir = Path(kwargs["output_dir"]).resolve()
    core._write_csv(
        output_dir / BENCHMARK_COVERAGE_FILE,
        list(benchmark.get("coverage_rows") or []),
        ("day", "required", "covered", "open"),
    )
    _patch_assurance_template(output_dir, benchmark)

    benchmark_gate = {
        "gate": "VNINDEX_NEXT_OPEN_SERIES_VERIFIED",
        "passed": bool(benchmark_assurance["valid"]),
        "blocker": "" if benchmark_assurance["valid"] else str(
            benchmark_assurance["blocker"]
        ),
    }
    report["gates"].append(benchmark_gate)
    blockers = set(report.get("blockers", []))
    if benchmark_gate["blocker"]:
        blockers.add(benchmark_gate["blocker"])
    report["blockers"] = sorted(blockers)
    core._write_csv(
        output_dir / core.READINESS_GATES_FILE,
        list(report.get("gates") or []),
        ("gate", "passed", "blocker"),
    )
    core._write_csv(
        output_dir / core.BLOCKERS_FILE,
        [{"blocker": blocker} for blocker in report["blockers"]],
        ("blocker",),
    )
    report["vnindex_benchmark"] = {
        key: value
        for key, value in benchmark.items()
        if key not in {"open_by_day", "coverage_rows"}
    }
    report["vnindex_benchmark_assurance"] = benchmark_assurance
    report["exact_vnindex_comparison_computed"] = False

    if report.get("ledger_status") == "SUCCESS":
        if not benchmark_assurance["valid"]:
            raise ValueError("V36_LEDGER_RAN_WITHOUT_EXACT_VNINDEX_ASSURANCE")
        patched = _patch_benchmark_metrics(output_dir, benchmark)
        report["ledger_summaries"] = patched
        report["exact_vnindex_comparison_computed"] = True
    elif original_assurance is not None and not benchmark_assurance["valid"]:
        report["recommendation"] = (
            "COMPLETE_VNINDEX_AND_DATA_INTEGRITY_PACK_THEN_RERUN_SAME_V36"
        )
    core._write_json(output_dir / core.REPORT_FILE, report)
    return report


run_v36 = run_v36_strict


def _parser() -> argparse.ArgumentParser:
    parser = core._parser()
    parser.add_argument("--benchmark-ohlcv", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    values = vars(args)
    benchmark = values.pop("benchmark_ohlcv")
    report = run_v36_strict(benchmark_ohlcv=benchmark, **values)
    print(json.dumps(report, ensure_ascii=True, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
