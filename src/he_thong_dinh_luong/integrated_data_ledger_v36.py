"""V36 integrated data-integrity pack and exact shadow cash-ledger engine.

The release deliberately combines the next research work into one decision unit:

* verify the frozen V34.1 C3/Top-10/fixed-cap-3 policy and its V33/V32 lineage;
* export every invalid OHLCV row with deterministic reason flags and summaries;
* verify point-in-time sector, corporate-action, price-unit and assurance data;
* rebuild the V33 cap-3 selections from V32 eligible predictions;
* run an exact quantity/cash ledger only when every required data gate passes.

A blocked data outcome is a successful audit. No return is fabricated when the
ledger cannot be run. The frozen future-paper policy is never modified and no
live-capital permission is granted.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import io
import json
import math
from pathlib import Path, PurePosixPath
import sqlite3
from statistics import fmean, pstdev
from typing import Mapping, Sequence
from urllib.parse import quote
import zipfile

from . import exact_cash_ledger_readiness_v35 as v35

SCHEMA_VERSION = "integrated_data_ledger_v36"
REPORT_FILE = "integrated_data_ledger_v36.json"
INVALID_ROWS_FILE = "invalid_ohlcv_rows_v36.csv"
INVALID_SUMMARY_FILE = "invalid_ohlcv_summary_v36.csv"
SELECTION_AUDIT_FILE = "selection_lineage_audit_v36.csv"
READINESS_GATES_FILE = "readiness_gates_v36.csv"
BLOCKERS_FILE = "blockers_v36.csv"
LEDGER_PERIODS_FILE = "exact_ledger_periods_v36.csv"
LEDGER_TRADES_FILE = "exact_ledger_trades_v36.csv"
LEDGER_HOLDINGS_FILE = "exact_ledger_holdings_v36.csv"
LEDGER_SUMMARY_FILE = "exact_ledger_summary_v36.csv"
DATA_CONTRACT_FILE = "required_data_contract_v36.json"
SECTOR_TEMPLATE_FILE = "sector_master_template_v36.csv"
ACTIONS_TEMPLATE_FILE = "corporate_actions_template_v36.csv"
ASSURANCE_TEMPLATE_FILE = "data_assurance_template_v36.json"

EXPECTED_POLICY_ID = v35.EXPECTED_POLICY_ID
EXPECTED_MODEL = v35.EXPECTED_MODEL
EXPECTED_BREADTH = v35.EXPECTED_BREADTH
EXPECTED_CAP = v35.EXPECTED_CAP
ASSURANCE_SCHEMA = "exact_ledger_data_assurance_v2"
PRICE_BASIS_MODE = "RAW_UNADJUSTED_EXECUTION_PRICES"
INITIAL_CAPITAL_VND = 1_000_000_000
LOT_SIZE = 100
MAX_SYMBOL_WEIGHT = 0.15
MAX_SECTOR_WEIGHT = 0.25
VOLATILITY_LOOKBACK = 60
VOLATILITY_FLOOR = 0.005
RISK_ON_BUDGET = 0.80
RISK_OFF_BUDGET = 0.25

V33_REQUIRED = {
    "turnover_policy_stability_v33.json",
    "fixed_cap_periods_v33.csv",
    "analysis_bundle_manifest_v33.json",
}
V32_REQUIRED = {
    "portfolio_ablation_v32.json",
    "eligible_predictions_v32.csv",
    "analysis_bundle_manifest_v32.json",
}


def _sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def _write_json(path: Path, value: object) -> None:
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, object]],
    fields: Sequence[str],
) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    Path(path).write_text(buffer.getvalue(), encoding="utf-8-sig", newline="")


def _read_csv_bytes(payload: bytes) -> list[dict[str, str]]:
    with io.StringIO(payload.decode("utf-8-sig"), newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _safe_basename(name: str) -> str:
    normalized = str(name).replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or not path.name:
        raise ValueError(f"V36_UNSAFE_ZIP_MEMBER:{name}")
    return path.name


def _load_flat_zip(path: Path) -> dict[str, tuple[str, bytes]]:
    source = Path(path).resolve()
    if not source.is_file():
        raise ValueError(f"V36_ZIP_NOT_FOUND:{source}")
    result: dict[str, tuple[str, bytes]] = {}
    with zipfile.ZipFile(source) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"V36_ZIP_CRC_ERROR:{bad}")
        for info in archive.infolist():
            if info.is_dir():
                continue
            basename = _safe_basename(info.filename)
            if basename in result:
                raise ValueError(f"V36_DUPLICATE_ZIP_BASENAME:{basename}")
            result[basename] = (info.filename, archive.read(info))
    return result


def _manifest_items(manifest: Mapping[str, object]) -> list[dict[str, object]]:
    raw = manifest.get("files")
    if isinstance(raw, list):
        return [dict(item) for item in raw if isinstance(item, Mapping)]
    if isinstance(raw, Mapping):
        return [
            {"path": name, **dict(meta)}
            for name, meta in raw.items()
            if isinstance(meta, Mapping)
        ]
    return []


def _verify_bundle_manifest(
    members: Mapping[str, tuple[str, bytes]],
    manifest_name: str,
) -> dict[str, object]:
    if manifest_name not in members:
        raise ValueError(f"V36_MANIFEST_MISSING:{manifest_name}")
    manifest_payload = members[manifest_name][1]
    manifest = json.loads(manifest_payload.decode("utf-8-sig"))
    if not isinstance(manifest, Mapping) or manifest.get("status") != "SUCCESS":
        raise ValueError(f"V36_MANIFEST_STATUS_INVALID:{manifest_name}")
    verified = 0
    for item in _manifest_items(manifest):
        basename = _safe_basename(str(item.get("path") or ""))
        if basename not in members:
            raise ValueError(f"V36_MANIFEST_MEMBER_MISSING:{basename}")
        payload = members[basename][1]
        expected_size = item.get("size_bytes", item.get("size"))
        if expected_size is not None and len(payload) != int(expected_size):
            raise ValueError(f"V36_MANIFEST_SIZE_MISMATCH:{basename}")
        if _sha_bytes(payload) != str(item.get("sha256") or ""):
            raise ValueError(f"V36_MANIFEST_HASH_MISMATCH:{basename}")
        verified += 1
    return {
        "manifest_sha256": _sha_bytes(manifest_payload),
        "manifest_entry_count": verified,
        "schema_version": manifest.get("schema_version"),
    }


def _verified_v33(path: Path, expected_sha256: str = "") -> dict[str, object]:
    source = Path(path).resolve()
    actual = _sha256(source)
    if expected_sha256 and actual != expected_sha256:
        raise ValueError(f"V36_V33_SHA256_MISMATCH:{actual}")
    members = _load_flat_zip(source)
    missing = V33_REQUIRED - set(members)
    if missing:
        raise ValueError("V36_V33_REQUIRED_MISSING:" + "|".join(sorted(missing)))
    manifest = _verify_bundle_manifest(members, "analysis_bundle_manifest_v33.json")
    report_payload = members["turnover_policy_stability_v33.json"][1]
    report = json.loads(report_payload.decode("utf-8-sig"))
    if not isinstance(report, Mapping) or report.get("status") != "SUCCESS":
        raise ValueError("V36_V33_REPORT_INVALID")
    if report.get("recommendation") != "FREEZE_C3_FIXED_CAP_3_FOR_FUTURE_PAPER_HOLDOUT_ONLY":
        raise ValueError("V36_V33_FREEZE_RECOMMENDATION_MISSING")
    period_payload = members["fixed_cap_periods_v33.csv"][1]
    rows = _read_csv_bytes(period_payload)
    selected = [
        dict(row)
        for row in rows
        if str(row.get("model") or "") == EXPECTED_MODEL
        and int(float(row.get("fixed_replacement_cap", -1) or -1)) == EXPECTED_CAP
        and str(row.get("cost_scenario") or "") == "BASE"
    ]
    selected.sort(key=lambda row: str(row.get("signal_date") or ""))
    if len(selected) != 51:
        raise ValueError(f"V36_V33_EXPECTED_51_CAP3_PERIODS:{len(selected)}")
    dates = [str(row.get("signal_date") or "") for row in selected]
    if len(set(dates)) != len(dates):
        raise ValueError("V36_V33_DUPLICATE_SIGNAL_DATE")
    for row in selected:
        symbols = [s for s in str(row.get("selected_symbols") or "").split("|") if s]
        if len(symbols) != EXPECTED_BREADTH or len(set(symbols)) != len(symbols):
            raise ValueError(f"V36_V33_SELECTED_SYMBOLS_INVALID:{row.get('signal_date')}")
    return {
        "path": str(source),
        "sha256": actual,
        "report_sha256": _sha_bytes(report_payload),
        "periods_sha256": _sha_bytes(period_payload),
        "periods": selected,
        **manifest,
    }


def _verified_v32(path: Path, expected_sha256: str = "") -> dict[str, object]:
    source = Path(path).resolve()
    actual = _sha256(source)
    if expected_sha256 and actual != expected_sha256:
        raise ValueError(f"V36_V32_SHA256_MISMATCH:{actual}")
    members = _load_flat_zip(source)
    missing = V32_REQUIRED - set(members)
    if missing:
        raise ValueError("V36_V32_REQUIRED_MISSING:" + "|".join(sorted(missing)))
    manifest = _verify_bundle_manifest(members, "analysis_bundle_manifest_v32.json")
    report_payload = members["portfolio_ablation_v32.json"][1]
    report = json.loads(report_payload.decode("utf-8-sig"))
    if not isinstance(report, Mapping) or report.get("status") != "SUCCESS":
        raise ValueError("V36_V32_REPORT_INVALID")
    prediction_payload = members["eligible_predictions_v32.csv"][1]
    predictions = _read_csv_bytes(prediction_payload)
    c3 = [dict(row) for row in predictions if str(row.get("model") or "") == EXPECTED_MODEL]
    if not c3:
        raise ValueError("V36_V32_C3_PREDICTIONS_MISSING")
    return {
        "path": str(source),
        "sha256": actual,
        "report_sha256": _sha_bytes(report_payload),
        "predictions_sha256": _sha_bytes(prediction_payload),
        "predictions": c3,
        **manifest,
    }


def rebuild_cap3_selections(
    prediction_rows: Sequence[Mapping[str, object]],
    signal_dates: Sequence[str],
) -> list[dict[str, object]]:
    """Rebuild the exact V11 selection rule used by V33."""
    wanted = set(signal_dates)
    by_day: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in prediction_rows:
        day = str(row.get("test_date") or "")
        if day in wanted:
            by_day[day].append(row)
    if set(by_day) != wanted:
        missing = sorted(wanted - set(by_day))
        raise ValueError("V36_SELECTION_DATE_COVERAGE_MISSING:" + "|".join(missing))
    previous: list[str] = []
    output: list[dict[str, object]] = []
    for index, day in enumerate(signal_dates):
        rows = sorted(
            by_day[day],
            key=lambda row: (
                int(float(row.get("rank", 10**9) or 10**9)),
                str(row.get("symbol") or ""),
            ),
        )
        ranked = [str(row.get("symbol") or "").strip().upper() for row in rows]
        ranked = [symbol for symbol in ranked if symbol]
        if len(ranked) < EXPECTED_BREADTH or len(set(ranked)) != len(ranked):
            raise ValueError(f"V36_SELECTION_CANDIDATES_INVALID:{day}")
        available = set(ranked)
        previous_available = [symbol for symbol in previous if symbol in available]
        forced_exits = [symbol for symbol in previous if symbol not in available]
        desired = ranked[:EXPECTED_BREADTH]
        if index == 0:
            selected = list(desired)
            voluntary = EXPECTED_BREADTH
        else:
            minimum_retain = max(
                0,
                min(len(previous_available), EXPECTED_BREADTH - EXPECTED_CAP),
            )
            retained = [symbol for symbol in desired if symbol in previous_available]
            rank_by_symbol = {symbol: pos for pos, symbol in enumerate(ranked, start=1)}
            if len(retained) < minimum_retain:
                for symbol in sorted(
                    previous_available,
                    key=lambda item: (rank_by_symbol[item], item),
                ):
                    if symbol not in retained:
                        retained.append(symbol)
                    if len(retained) >= minimum_retain:
                        break
            selected = list(retained)
            for symbol in ranked:
                if symbol not in selected:
                    selected.append(symbol)
                if len(selected) >= EXPECTED_BREADTH:
                    break
            selected = selected[:EXPECTED_BREADTH]
            voluntary = len(
                [symbol for symbol in selected if symbol not in previous_available]
            )
        output.append(
            {
                "signal_date": day,
                "selected_symbols": selected,
                "forced_exit_count": len(forced_exits),
                "voluntary_replacement_count": voluntary,
                "candidate_count": len(ranked),
            }
        )
        previous = selected
    return output


def selection_lineage_audit(
    v33_periods: Sequence[Mapping[str, object]],
    prediction_rows: Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, object]], bool]:
    dates = [str(row.get("signal_date") or "") for row in v33_periods]
    rebuilt = rebuild_cap3_selections(prediction_rows, dates)
    expected_by_date = {
        str(row.get("signal_date") or ""): [
            symbol
            for symbol in str(row.get("selected_symbols") or "").split("|")
            if symbol
        ]
        for row in v33_periods
    }
    rows: list[dict[str, object]] = []
    all_match = True
    for item in rebuilt:
        day = str(item["signal_date"])
        actual = list(item["selected_symbols"])
        expected = expected_by_date[day]
        exact = actual == expected
        set_match = set(actual) == set(expected)
        all_match = all_match and exact
        rows.append(
            {
                "signal_date": day,
                "expected_selected_symbols": "|".join(expected),
                "rebuilt_selected_symbols": "|".join(actual),
                "exact_order_match": exact,
                "set_match": set_match,
                "forced_exit_count": item["forced_exit_count"],
                "voluntary_replacement_count": item["voluntary_replacement_count"],
                "candidate_count": item["candidate_count"],
            }
        )
    return rows, all_match


def _connect_readonly(path: Path) -> sqlite3.Connection:
    uri = f"file:{quote(Path(path).resolve().as_posix())}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _quoted(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _invalid_reason_flags(row: Mapping[str, object]) -> list[str]:
    reasons: list[str] = []
    values: dict[str, float | None] = {}
    if row.get("day") in (None, ""):
        reasons.append("MISSING_DAY")
    if row.get("symbol") in (None, ""):
        reasons.append("MISSING_SYMBOL")
    for field in ("open", "high", "low", "close", "volume"):
        value = row.get(field)
        if value in (None, ""):
            values[field] = None
            reasons.append(f"MISSING_{field.upper()}")
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            values[field] = None
            reasons.append(f"NON_NUMERIC_{field.upper()}")
            continue
        values[field] = number
        if not math.isfinite(number):
            reasons.append(f"NON_FINITE_{field.upper()}")
    for field in ("open", "high", "low", "close"):
        value = values.get(field)
        if value is not None and value <= 0.0:
            reasons.append(f"NONPOSITIVE_{field.upper()}")
    volume = values.get("volume")
    if volume is not None and volume < 0.0:
        reasons.append("NEGATIVE_VOLUME")
    if all(values.get(field) is not None for field in ("open", "high", "close")):
        if float(values["high"]) < max(float(values["open"]), float(values["close"])):
            reasons.append("HIGH_BELOW_OPEN_OR_CLOSE")
    if all(values.get(field) is not None for field in ("open", "low", "close")):
        if float(values["low"]) > min(float(values["open"]), float(values["close"])):
            reasons.append("LOW_ABOVE_OPEN_OR_CLOSE")
    return reasons


def _invalid_category(reasons: Sequence[str]) -> str:
    values = set(reasons)
    if any(
        item.startswith("MISSING_")
        or item.startswith("NON_NUMERIC_")
        or item.startswith("NON_FINITE_")
        for item in values
    ):
        return "MISSING_OR_NON_NUMERIC"
    zero_fields = [item for item in values if item.startswith("NONPOSITIVE_")]
    range_fields = {
        "HIGH_BELOW_OPEN_OR_CLOSE",
        "LOW_ABOVE_OPEN_OR_CLOSE",
    } & values
    if len(zero_fields) >= 4:
        return "ALL_PRICE_FIELDS_NONPOSITIVE"
    if zero_fields:
        return "PARTIAL_NONPOSITIVE_PRICE"
    if "NEGATIVE_VOLUME" in values:
        return "NEGATIVE_VOLUME"
    if range_fields:
        return "OHLC_RANGE_INCONSISTENT"
    return "OTHER_INVALID_OHLCV"


def extract_invalid_ohlcv(
    sqlite_store: Path,
    resolved_columns: Mapping[str, object],
) -> list[dict[str, object]]:
    columns = {key: str(value) for key, value in resolved_columns.items() if value}
    required = {"day", "symbol", "open", "high", "low", "close", "volume"}
    if set(columns) != required:
        raise ValueError("V36_RESOLVED_OHLCV_COLUMNS_INVALID")
    q = {key: _quoted(value) for key, value in columns.items()}
    invalid_where = """
        day IS NULL OR symbol IS NULL
        OR open IS NULL OR high IS NULL OR low IS NULL
        OR close IS NULL OR volume IS NULL
        OR CAST(open AS REAL) <= 0
        OR CAST(high AS REAL) <= 0
        OR CAST(low AS REAL) <= 0
        OR CAST(close AS REAL) <= 0
        OR CAST(volume AS REAL) < 0
        OR CAST(high AS REAL) < MAX(CAST(open AS REAL), CAST(close AS REAL))
        OR CAST(low AS REAL) > MIN(CAST(open AS REAL), CAST(close AS REAL))
    """
    connection = _connect_readonly(sqlite_store)
    try:
        sql = f"""
            WITH ordered AS (
                SELECT rowid AS source_rowid,
                       {q['day']} AS day,
                       {q['symbol']} AS symbol,
                       {q['open']} AS open,
                       {q['high']} AS high,
                       {q['low']} AS low,
                       {q['close']} AS close,
                       {q['volume']} AS volume,
                       LAG({q['day']}) OVER (
                           PARTITION BY {q['symbol']} ORDER BY {q['day']}
                       ) AS previous_day,
                       LAG({q['close']}) OVER (
                           PARTITION BY {q['symbol']} ORDER BY {q['day']}
                       ) AS previous_close,
                       LEAD({q['day']}) OVER (
                           PARTITION BY {q['symbol']} ORDER BY {q['day']}
                       ) AS next_day,
                       LEAD({q['open']}) OVER (
                           PARTITION BY {q['symbol']} ORDER BY {q['day']}
                       ) AS next_open
                FROM bars
            )
            SELECT * FROM ordered
            WHERE {invalid_where}
            ORDER BY day, symbol, source_rowid
        """
        raw = [dict(row) for row in connection.execute(sql)]
    finally:
        connection.close()
    output: list[dict[str, object]] = []
    for row in raw:
        reasons = _invalid_reason_flags(row)
        day_text = str(row.get("day") or "")
        output.append(
            {
                **row,
                "year": day_text[:4] if len(day_text) >= 4 else "",
                "reason_count": len(reasons),
                "reasons": "|".join(reasons),
                "category": _invalid_category(reasons),
                "quarantine_required": True,
                "automatic_correction_allowed": False,
            }
        )
    return output


def invalid_ohlcv_summary(
    rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    counters: dict[tuple[str, str], int] = defaultdict(int)
    for row in rows:
        counters[("CATEGORY", str(row.get("category") or ""))] += 1
        counters[("SYMBOL", str(row.get("symbol") or ""))] += 1
        counters[("YEAR", str(row.get("year") or ""))] += 1
        for reason in str(row.get("reasons") or "").split("|"):
            if reason:
                counters[("REASON", reason)] += 1
    return [
        {"dimension": dimension, "value": value, "row_count": count}
        for (dimension, value), count in sorted(counters.items())
    ]


def load_regime_map(
    v22_input_zip: Path,
) -> tuple[dict[str, bool], dict[str, object]]:
    members = _load_flat_zip(v22_input_zip)
    if "feature_raw.csv" not in members:
        raise ValueError("V36_V22_FEATURE_RAW_MISSING")
    payload = members["feature_raw.csv"][1]
    rows = _read_csv_bytes(payload)
    regime_by_day: dict[str, bool] = {}
    conflicts: set[str] = set()
    for row in rows:
        day = str(
            row.get("ngay") or row.get("day") or row.get("test_date") or ""
        )[:10]
        raw = row.get("vnindex_tren_ma250", row.get("market_above_ma250"))
        if not day or raw in (None, ""):
            continue
        text = str(raw).strip().lower()
        if text in {"1", "true", "yes", "y"}:
            value = True
        elif text in {"0", "false", "no", "n"}:
            value = False
        else:
            raise ValueError(f"V36_INVALID_REGIME_VALUE:{day}:{raw}")
        if day in regime_by_day and regime_by_day[day] != value:
            conflicts.add(day)
        regime_by_day[day] = value
    if conflicts:
        raise ValueError("V36_REGIME_CONFLICT:" + "|".join(sorted(conflicts)))
    return regime_by_day, {
        "input_zip_sha256": _sha256(v22_input_zip),
        "feature_raw_sha256": _sha_bytes(payload),
        "regime_day_count": len(regime_by_day),
    }


def _read_csv_path(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _sector_at(
    rows: Sequence[Mapping[str, object]],
    symbol: str,
    day: str,
) -> str | None:
    matches: list[str] = []
    for row in rows:
        if str(row.get("symbol") or "").strip().upper() != symbol:
            continue
        start = str(row.get("effective_from") or "")
        end = str(row.get("effective_to") or "")
        if start and start <= day and (not end or day <= end):
            matches.append(str(row.get("sector") or "").strip())
    matches = [value for value in matches if value]
    return matches[0] if len(matches) == 1 else None


def audit_sector_coverage(
    path: Path | None,
    selections: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    base = v35.audit_sector_master(path)
    if not bool(base.get("valid")) or path is None:
        return {
            **base,
            "coverage_complete_for_selected_symbols": False,
            "missing_key_count": 0,
        }
    rows = _read_csv_path(path)
    missing: list[str] = []
    for selection in selections:
        day = str(selection.get("signal_date") or "")
        for symbol in selection.get("selected_symbols", []):
            if _sector_at(rows, str(symbol), day) is None:
                missing.append(f"{day}:{symbol}")
    return {
        **base,
        "coverage_complete_for_selected_symbols": not missing,
        "missing_key_count": len(missing),
        "missing_keys_sample": missing[:100],
    }


def audit_corporate_actions_strict(path: Path | None) -> dict[str, object]:
    base = v35.audit_corporate_actions(path)
    if not bool(base.get("valid")) or path is None:
        return {**base, "strict_valid": False, "unsupported_event_count": 0}
    rows = _read_csv_path(path)
    supported = {
        "CASH_DIVIDEND",
        "STOCK_DIVIDEND",
        "SPLIT",
        "REVERSE_SPLIT",
    }
    unsupported: list[str] = []
    invalid: list[str] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(rows, start=2):
        event = str(row.get("event_type") or "").strip().upper()
        event_id = str(row.get("source_event_id") or "").strip()
        if event not in supported:
            unsupported.append(f"line={index}:{event}")
        if not event_id or event_id in seen_ids:
            invalid.append(f"line={index}:source_event_id")
        seen_ids.add(event_id)
        try:
            factor = float(row.get("adjustment_factor") or 0.0)
            cash = float(row.get("cash_amount_vnd") or 0.0)
            if event in {"STOCK_DIVIDEND", "SPLIT", "REVERSE_SPLIT"} and factor <= 0.0:
                invalid.append(f"line={index}:adjustment_factor")
            if event == "CASH_DIVIDEND" and cash < 0.0:
                invalid.append(f"line={index}:cash_amount_vnd")
        except (TypeError, ValueError):
            invalid.append(f"line={index}:numeric")
    strict = not unsupported and not invalid
    return {
        **base,
        "strict_valid": strict,
        "unsupported_event_count": len(unsupported),
        "unsupported_events_sample": unsupported[:100],
        "strict_invalid_count": len(invalid),
        "strict_invalid_sample": invalid[:100],
    }


def audit_assurance_v2(
    path: Path | None,
    *,
    sqlite_audit: Mapping[str, object],
    sector: Mapping[str, object],
    actions: Mapping[str, object],
    invalid_rows_sha256: str,
) -> dict[str, object]:
    defaults = {
        "price_basis_confirmed": False,
        "point_in_time_sector_master_complete": False,
        "corporate_actions_complete": False,
        "invalid_ohlcv_quarantine_approved": False,
    }
    if path is None:
        return {
            "provided": False,
            "valid": False,
            **defaults,
            "blocker": "V36_DATA_ASSURANCE_V2_MISSING",
        }
    source = Path(path).resolve()
    if not source.is_file():
        return {
            "provided": True,
            "valid": False,
            **defaults,
            "blocker": "V36_DATA_ASSURANCE_V2_NOT_FOUND",
        }
    try:
        value = json.loads(source.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {
            "provided": True,
            "valid": False,
            **defaults,
            "blocker": "V36_DATA_ASSURANCE_V2_INVALID_JSON",
        }
    if not isinstance(value, Mapping):
        return {
            "provided": True,
            "valid": False,
            **defaults,
            "blocker": "V36_DATA_ASSURANCE_V2_NOT_OBJECT",
        }
    first = str(value.get("coverage_first_day") or "")
    last = str(value.get("coverage_last_day") or "")
    coverage_ok = (
        bool(first and last)
        and first <= str(sqlite_audit["first_day"])
        and last >= str(sqlite_audit["last_day"])
    )
    hashes = {
        "sqlite_sha256_match": str(value.get("sqlite_sha256") or "")
        == str(sqlite_audit["sha256"]),
        "sector_master_sha256_match": bool(sector.get("valid"))
        and str(value.get("sector_master_sha256") or "")
        == str(sector.get("sha256") or ""),
        "corporate_actions_sha256_match": bool(actions.get("strict_valid"))
        and str(value.get("corporate_actions_sha256") or "")
        == str(actions.get("sha256") or ""),
        "invalid_ohlcv_export_sha256_match": str(
            value.get("invalid_ohlcv_export_sha256") or ""
        )
        == invalid_rows_sha256,
    }
    flags = {
        "price_basis_confirmed": value.get("price_basis_confirmed") is True,
        "point_in_time_sector_master_complete": value.get(
            "point_in_time_sector_master_complete"
        )
        is True,
        "corporate_actions_complete": value.get("corporate_actions_complete")
        is True,
        "invalid_ohlcv_quarantine_approved": value.get(
            "invalid_ohlcv_quarantine_approved"
        )
        is True,
    }
    try:
        multiplier_value = float(value.get("price_unit_vnd_multiplier"))
    except (TypeError, ValueError):
        multiplier_value = 0.0
    try:
        dividend_tax_bps = float(value.get("cash_dividend_tax_bps"))
    except (TypeError, ValueError):
        dividend_tax_bps = -1.0
    mode_ok = str(value.get("price_basis_mode") or "") == PRICE_BASIS_MODE
    numerical_ok = (
        math.isfinite(multiplier_value)
        and multiplier_value > 0.0
        and math.isfinite(dividend_tax_bps)
        and 0.0 <= dividend_tax_bps < 10_000.0
    )
    valid = bool(
        value.get("schema_version") == ASSURANCE_SCHEMA
        and coverage_ok
        and all(hashes.values())
        and all(flags.values())
        and mode_ok
        and numerical_ok
        and sector.get("coverage_complete_for_selected_symbols") is True
        and actions.get("strict_valid") is True
    )
    return {
        "provided": True,
        "path": str(source),
        "sha256": _sha256(source),
        "schema_version": value.get("schema_version"),
        "coverage_first_day": first,
        "coverage_last_day": last,
        "coverage_contains_sqlite": coverage_ok,
        **hashes,
        **flags,
        "price_basis_mode": value.get("price_basis_mode"),
        "price_basis_mode_supported": mode_ok,
        "price_unit_vnd_multiplier": multiplier_value,
        "cash_dividend_tax_bps": dividend_tax_bps,
        "numerical_contract_valid": numerical_ok,
        "valid": valid,
        "blocker": "" if valid else "V36_DATA_ASSURANCE_V2_NOT_VERIFIED",
    }


def _trading_day_after(
    connection: sqlite3.Connection,
    day: str,
) -> str | None:
    row = connection.execute(
        "SELECT MIN(day) AS day FROM bars WHERE day > ?",
        (day,),
    ).fetchone()
    return str(row["day"]) if row and row["day"] else None


def execution_critical_keys(
    sqlite_store: Path,
    selections: Sequence[Mapping[str, object]],
    v33_periods: Sequence[Mapping[str, object]],
) -> set[tuple[str, str]]:
    period_meta = {
        str(row.get("signal_date") or ""): row for row in v33_periods
    }
    connection = _connect_readonly(sqlite_store)
    keys: set[tuple[str, str]] = set()
    previous: set[str] = set()
    try:
        for index, selection in enumerate(selections):
            signal_day = str(selection.get("signal_date") or "")
            current = {
                str(symbol) for symbol in selection.get("selected_symbols", [])
            }
            execution_day = _trading_day_after(connection, signal_day)
            if execution_day is None:
                raise ValueError(f"V36_EXECUTION_DAY_MISSING:{signal_day}")
            for symbol in previous | current:
                keys.add((execution_day, symbol))
            if index + 1 == len(selections):
                boundary = str(period_meta[signal_day].get("label_end") or "")
                final_day = _trading_day_after(connection, boundary)
                if final_day is None:
                    raise ValueError(f"V36_FINAL_EXECUTION_DAY_MISSING:{boundary}")
                for symbol in current:
                    keys.add((final_day, symbol))
            previous = current
    finally:
        connection.close()
    return keys


def _load_prices_for_symbols(
    connection: sqlite3.Connection,
    symbols: Sequence[str],
    day: str,
    field: str,
    multiplier: float,
    invalid_keys: set[tuple[str, str]] | None = None,
) -> dict[str, float]:
    if not symbols:
        return {}
    placeholders = ",".join("?" for _ in symbols)
    rows = connection.execute(
        f"SELECT symbol, {field} AS value FROM bars "
        f"WHERE day=? AND symbol IN ({placeholders})",
        (day, *symbols),
    ).fetchall()
    blocked = invalid_keys or set()
    return {
        str(row["symbol"]): float(row["value"]) * multiplier
        for row in rows
        if row["value"] is not None
        and (day, str(row["symbol"])) not in blocked
    }


def _load_close_history(
    connection: sqlite3.Connection,
    symbol: str,
    signal_date: str,
    limit: int,
    multiplier: float,
    invalid_keys: set[tuple[str, str]] | None = None,
) -> list[tuple[str, float]]:
    rows = connection.execute(
        "SELECT day, close FROM bars "
        "WHERE symbol=? AND day<=? AND close>0 "
        "ORDER BY day DESC LIMIT ?",
        (symbol, signal_date, limit * 3 + 10),
    ).fetchall()
    blocked = invalid_keys or set()
    result = [
        (str(row["day"]), float(row["close"]) * multiplier)
        for row in reversed(rows)
        if (str(row["day"]), symbol) not in blocked
    ]
    return result[-(limit + 1) :]


def _action_rows(path: Path | None) -> list[dict[str, str]]:
    return (
        _read_csv_path(path)
        if path is not None and Path(path).is_file()
        else []
    )


def _events_by_key(
    rows: Sequence[Mapping[str, object]],
) -> dict[tuple[str, str], list[Mapping[str, object]]]:
    result: dict[tuple[str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        result[
            (
                str(row.get("symbol") or "").strip().upper(),
                str(row.get("event_date") or ""),
            )
        ].append(row)
    return result


def adjusted_volatility(
    history: Sequence[tuple[str, float]],
    symbol: str,
    events: Mapping[tuple[str, str], Sequence[Mapping[str, object]]],
) -> float:
    if len(history) < 21:
        raise ValueError(f"V36_VOLATILITY_HISTORY_INSUFFICIENT:{symbol}")
    returns: list[float] = []
    for (_, previous_close), (day, close) in zip(history, history[1:]):
        adjusted_close = close
        cash = 0.0
        for event in events.get((symbol, day), []):
            event_type = str(event.get("event_type") or "").upper()
            if event_type in {"STOCK_DIVIDEND", "SPLIT", "REVERSE_SPLIT"}:
                adjusted_close *= float(event.get("adjustment_factor") or 1.0)
            elif event_type == "CASH_DIVIDEND":
                cash += float(event.get("cash_amount_vnd") or 0.0)
        value = (adjusted_close + cash) / previous_close - 1.0
        if math.isfinite(value):
            returns.append(value)
    if len(returns) < 20:
        raise ValueError(f"V36_VOLATILITY_RETURNS_INSUFFICIENT:{symbol}")
    return max(pstdev(returns[-VOLATILITY_LOOKBACK:]), VOLATILITY_FLOOR)


def constrained_inverse_vol_weights(
    symbols: Sequence[str],
    volatilities: Mapping[str, float],
    sectors: Mapping[str, str],
    budget: float,
) -> dict[str, float]:
    if not 0.0 <= budget <= 1.0:
        raise ValueError("V36_WEIGHT_BUDGET_INVALID")
    if (
        len(set(symbols)) != len(symbols)
        or any(
            symbol not in volatilities or symbol not in sectors
            for symbol in symbols
        )
    ):
        raise ValueError("V36_WEIGHT_INPUT_INVALID")
    raw = {
        symbol: 1.0 / max(float(volatilities[symbol]), VOLATILITY_FLOOR)
        for symbol in symbols
    }
    weights = {symbol: 0.0 for symbol in symbols}
    remaining = budget
    for _ in range(200):
        if remaining <= 1e-12:
            break
        sector_used: dict[str, float] = defaultdict(float)
        for symbol, weight in weights.items():
            sector_used[sectors[symbol]] += weight
        active = [
            symbol
            for symbol in symbols
            if weights[symbol] < MAX_SYMBOL_WEIGHT - 1e-12
            and sector_used[sectors[symbol]] < MAX_SECTOR_WEIGHT - 1e-12
        ]
        if not active:
            break
        total_raw = sum(raw[symbol] for symbol in active)
        proposed = {
            symbol: remaining * raw[symbol] / total_raw for symbol in active
        }
        scale = 1.0
        for symbol in active:
            if proposed[symbol] > 0:
                scale = min(
                    scale,
                    (MAX_SYMBOL_WEIGHT - weights[symbol]) / proposed[symbol],
                )
        by_sector: dict[str, float] = defaultdict(float)
        for symbol in active:
            by_sector[sectors[symbol]] += proposed[symbol]
        for sector, value in by_sector.items():
            if value > 0:
                scale = min(
                    scale,
                    (MAX_SECTOR_WEIGHT - sector_used[sector]) / value,
                )
        scale = max(0.0, min(1.0, scale))
        allocated = 0.0
        for symbol in active:
            increment = proposed[symbol] * scale
            weights[symbol] += increment
            allocated += increment
        remaining -= allocated
        if allocated <= 1e-12:
            break
    if any(weight > MAX_SYMBOL_WEIGHT + 1e-9 for weight in weights.values()):
        raise AssertionError("V36_SYMBOL_CAP_BREACH")
    sector_totals: dict[str, float] = defaultdict(float)
    for symbol, weight in weights.items():
        sector_totals[sectors[symbol]] += weight
    if any(value > MAX_SECTOR_WEIGHT + 1e-9 for value in sector_totals.values()):
        raise AssertionError("V36_SECTOR_CAP_BREACH")
    return weights


@dataclass(frozen=True)
class CostContract:
    broker_buy_fee_bps: float = 0.0
    broker_sell_fee_bps: float = 0.0
    exchange_buy_fee_bps: float = 2.7
    exchange_sell_fee_bps: float = 2.7
    sell_tax_bps: float = 10.0
    transfer_fee_vnd_per_share: float = 0.3
    base_slippage_bps: float = 5.0
    stress_slippage_bps: float = 10.0

    def slippage(self, scenario: str) -> float:
        return (
            self.base_slippage_bps
            if scenario == "BASE"
            else self.stress_slippage_bps
        )


@dataclass
class LedgerState:
    cash: float
    holdings: dict[str, int]


def _apply_actions(
    state: LedgerState,
    action_rows: Sequence[Mapping[str, object]],
    start_exclusive: str,
    end_inclusive: str,
    dividend_tax_bps: float,
) -> list[dict[str, object]]:
    applied: list[dict[str, object]] = []
    ordered = sorted(
        action_rows,
        key=lambda item: (
            str(item.get("event_date") or ""),
            str(item.get("symbol") or ""),
        ),
    )
    for row in ordered:
        day = str(row.get("event_date") or "")
        if not (start_exclusive < day <= end_inclusive):
            continue
        symbol = str(row.get("symbol") or "").strip().upper()
        quantity = state.holdings.get(symbol, 0)
        if quantity <= 0:
            continue
        event = str(row.get("event_type") or "").strip().upper()
        cash_delta = 0.0
        old_quantity = quantity
        if event == "CASH_DIVIDEND":
            gross = quantity * float(row.get("cash_amount_vnd") or 0.0)
            cash_delta = gross * (1.0 - dividend_tax_bps / 10_000.0)
            state.cash += cash_delta
        elif event in {"STOCK_DIVIDEND", "SPLIT", "REVERSE_SPLIT"}:
            factor = float(row.get("adjustment_factor") or 1.0)
            new_quantity = quantity * factor
            rounded = round(new_quantity)
            if abs(new_quantity - rounded) > 1e-9:
                raise ValueError(
                    f"V36_FRACTIONAL_CORPORATE_ACTION_QUANTITY:{day}:{symbol}"
                )
            state.holdings[symbol] = int(rounded)
        else:
            raise ValueError(
                f"V36_UNSUPPORTED_ACTION_DURING_LEDGER:{day}:{symbol}:{event}"
            )
        applied.append(
            {
                "event_date": day,
                "symbol": symbol,
                "event_type": event,
                "old_quantity": old_quantity,
                "new_quantity": state.holdings.get(symbol, old_quantity),
                "cash_delta_vnd": cash_delta,
                "source_event_id": row.get("source_event_id", ""),
            }
        )
    return applied


def _nav(state: LedgerState, prices: Mapping[str, float]) -> float:
    return state.cash + sum(
        quantity * prices[symbol]
        for symbol, quantity in state.holdings.items()
        if symbol in prices
    )


def _execute_rebalance(
    state: LedgerState,
    *,
    execution_day: str,
    target_weights: Mapping[str, float],
    open_prices: Mapping[str, float],
    cost: CostContract,
    scenario: str,
    strategy: str,
    signal_date: str,
) -> list[dict[str, object]]:
    symbols = sorted(set(state.holdings) | set(target_weights))
    if any(symbol not in open_prices for symbol in symbols):
        missing = sorted(
            symbol for symbol in symbols if symbol not in open_prices
        )
        raise ValueError("V36_EXECUTION_OPEN_MISSING:" + "|".join(missing))
    pre_nav = _nav(state, open_prices)
    target_qty = {
        symbol: int(
            math.floor(
                (pre_nav * float(target_weights.get(symbol, 0.0)))
                / (open_prices[symbol] * LOT_SIZE)
            )
        )
        * LOT_SIZE
        for symbol in symbols
    }
    trades: list[dict[str, object]] = []
    slip = cost.slippage(scenario) / 10_000.0
    for symbol in symbols:
        current = state.holdings.get(symbol, 0)
        desired = target_qty.get(symbol, 0)
        quantity = ((max(0, current - desired)) // LOT_SIZE) * LOT_SIZE
        if quantity <= 0:
            continue
        raw = open_prices[symbol]
        execution = raw * (1.0 - slip)
        gross = execution * quantity
        fee = gross * (
            cost.broker_sell_fee_bps + cost.exchange_sell_fee_bps
        ) / 10_000.0
        tax = gross * cost.sell_tax_bps / 10_000.0
        transfer = quantity * cost.transfer_fee_vnd_per_share
        net = gross - fee - tax - transfer
        state.cash += net
        state.holdings[symbol] = current - quantity
        trades.append(
            {
                "strategy": strategy,
                "scenario": scenario,
                "signal_date": signal_date,
                "execution_day": execution_day,
                "symbol": symbol,
                "side": "SELL",
                "quantity": quantity,
                "raw_open_vnd": raw,
                "execution_price_vnd": execution,
                "gross_notional_vnd": gross,
                "fee_vnd": fee,
                "tax_vnd": tax,
                "transfer_fee_vnd": transfer,
                "cash_change_vnd": net,
            }
        )
    buy_candidates: list[tuple[float, str, int]] = []
    for symbol in symbols:
        current = state.holdings.get(symbol, 0)
        desired = target_qty.get(symbol, 0)
        quantity = ((max(0, desired - current)) // LOT_SIZE) * LOT_SIZE
        if quantity > 0:
            buy_candidates.append(
                (quantity * open_prices[symbol], symbol, quantity)
            )
    for _, symbol, requested in sorted(
        buy_candidates,
        key=lambda item: (-item[0], item[1]),
    ):
        raw = open_prices[symbol]
        execution = raw * (1.0 + slip)
        fee_rate = (
            cost.broker_buy_fee_bps + cost.exchange_buy_fee_bps
        ) / 10_000.0
        lot_cash = execution * LOT_SIZE * (1.0 + fee_rate)
        affordable_lots = int(state.cash // lot_cash)
        quantity = min(requested, affordable_lots * LOT_SIZE)
        if quantity <= 0:
            continue
        gross = execution * quantity
        fee = gross * fee_rate
        cash_change = -(gross + fee)
        state.cash += cash_change
        state.holdings[symbol] = state.holdings.get(symbol, 0) + quantity
        trades.append(
            {
                "strategy": strategy,
                "scenario": scenario,
                "signal_date": signal_date,
                "execution_day": execution_day,
                "symbol": symbol,
                "side": "BUY",
                "quantity": quantity,
                "raw_open_vnd": raw,
                "execution_price_vnd": execution,
                "gross_notional_vnd": gross,
                "fee_vnd": fee,
                "tax_vnd": 0.0,
                "transfer_fee_vnd": 0.0,
                "cash_change_vnd": cash_change,
            }
        )
    return trades


def _max_drawdown(nav_values: Sequence[float]) -> float:
    peak = 0.0
    worst = 0.0
    for value in nav_values:
        peak = max(peak, value)
        if peak > 0:
            worst = min(worst, value / peak - 1.0)
    return worst


def _compound(values: Sequence[float]) -> float:
    return math.prod(1.0 + value for value in values) - 1.0


def run_exact_ledgers(
    *,
    sqlite_store: Path,
    selections: Sequence[Mapping[str, object]],
    v33_periods: Sequence[Mapping[str, object]],
    sector_master: Path,
    corporate_actions: Path,
    regime_by_day: Mapping[str, bool],
    price_multiplier: float,
    dividend_tax_bps: float,
    initial_capital_vnd: int,
    invalid_keys: set[tuple[str, str]] | None = None,
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    sectors_rows = _read_csv_path(sector_master)
    action_rows = _action_rows(corporate_actions)
    events = _events_by_key(action_rows)
    period_meta = {
        str(row.get("signal_date") or ""): row for row in v33_periods
    }
    cost = CostContract()
    all_periods: list[dict[str, object]] = []
    all_trades: list[dict[str, object]] = []
    all_holdings: list[dict[str, object]] = []
    summaries: list[dict[str, object]] = []
    connection = _connect_readonly(sqlite_store)
    try:
        strategies = (
            "FROZEN_SELECTION_FULLY_INVESTED",
            "MVP_REGIME_CASH_OVERLAY_DIAGNOSTIC",
        )
        for strategy in strategies:
            for scenario in ("BASE", "STRESS"):
                state = LedgerState(
                    cash=float(initial_capital_vnd),
                    holdings={},
                )
                previous_execution = "0000-01-01"
                nav_path = [float(initial_capital_vnd)]
                benchmark_nav = 1.0
                period_rows: list[dict[str, object]] = []
                strategy_trades: list[dict[str, object]] = []
                for index, selection in enumerate(selections):
                    signal_day = str(selection.get("signal_date") or "")
                    execution_day = _trading_day_after(connection, signal_day)
                    if execution_day is None:
                        raise ValueError(f"V36_EXECUTION_DAY_MISSING:{signal_day}")
                    _apply_actions(
                        state,
                        action_rows,
                        previous_execution,
                        execution_day,
                        dividend_tax_bps,
                    )
                    selected_symbols = list(selection.get("selected_symbols", []))
                    prices = _load_prices_for_symbols(
                        connection,
                        sorted(set(state.holdings) | set(selected_symbols)),
                        execution_day,
                        "open",
                        price_multiplier,
                        invalid_keys,
                    )
                    pre_trade_nav = _nav(state, prices)
                    vol: dict[str, float] = {}
                    sector_map: dict[str, str] = {}
                    for symbol in selected_symbols:
                        history = _load_close_history(
                            connection,
                            symbol,
                            signal_day,
                            VOLATILITY_LOOKBACK,
                            price_multiplier,
                            invalid_keys,
                        )
                        vol[symbol] = adjusted_volatility(
                            history,
                            symbol,
                            events,
                        )
                        sector = _sector_at(sectors_rows, symbol, signal_day)
                        if sector is None:
                            raise ValueError(
                                f"V36_SECTOR_NOT_UNIQUE:{signal_day}:{symbol}"
                            )
                        sector_map[symbol] = sector
                    if strategy == "FROZEN_SELECTION_FULLY_INVESTED":
                        budget = 1.0
                    else:
                        if signal_day not in regime_by_day:
                            raise ValueError(f"V36_REGIME_MISSING:{signal_day}")
                        budget = (
                            RISK_ON_BUDGET
                            if regime_by_day[signal_day]
                            else RISK_OFF_BUDGET
                        )
                    weights = constrained_inverse_vol_weights(
                        selected_symbols,
                        vol,
                        sector_map,
                        budget,
                    )
                    trades = _execute_rebalance(
                        state,
                        execution_day=execution_day,
                        target_weights=weights,
                        open_prices=prices,
                        cost=cost,
                        scenario=scenario,
                        strategy=strategy,
                        signal_date=signal_day,
                    )
                    period_trades = list(trades)
                    strategy_trades.extend(trades)
                    post_trade_prices = _load_prices_for_symbols(
                        connection,
                        list(state.holdings),
                        execution_day,
                        "open",
                        price_multiplier,
                        invalid_keys,
                    )
                    post_trade_nav = _nav(state, post_trade_prices)
                    next_boundary = (
                        str(selections[index + 1].get("signal_date") or "")
                        if index + 1 < len(selections)
                        else str(period_meta[signal_day].get("label_end") or "")
                    )
                    end_execution = _trading_day_after(connection, next_boundary)
                    if end_execution is None:
                        raise ValueError(
                            f"V36_PERIOD_END_EXECUTION_MISSING:{signal_day}:"
                            f"{next_boundary}"
                        )
                    _apply_actions(
                        state,
                        action_rows,
                        execution_day,
                        end_execution,
                        dividend_tax_bps,
                    )
                    end_prices = _load_prices_for_symbols(
                        connection,
                        list(state.holdings),
                        end_execution,
                        "open",
                        price_multiplier,
                        invalid_keys,
                    )
                    if index + 1 == len(selections):
                        liquidation = _execute_rebalance(
                            state,
                            execution_day=end_execution,
                            target_weights={},
                            open_prices=end_prices,
                            cost=cost,
                            scenario=scenario,
                            strategy=strategy,
                            signal_date=signal_day,
                        )
                        period_trades.extend(liquidation)
                        strategy_trades.extend(liquidation)
                        residual = {
                            symbol: quantity
                            for symbol, quantity in state.holdings.items()
                            if quantity > 0
                        }
                        if residual:
                            raise ValueError(
                                "V36_FINAL_ODD_LOT_RESIDUAL:"
                                + "|".join(
                                    f"{symbol}:{quantity}"
                                    for symbol, quantity in sorted(residual.items())
                                )
                            )
                        end_prices = {}
                    end_nav = _nav(state, end_prices)
                    benchmark_return = float(
                        period_meta[signal_day].get("benchmark_return") or 0.0
                    )
                    benchmark_nav *= 1.0 + benchmark_return
                    net_return = end_nav / nav_path[-1] - 1.0
                    nav_path.append(end_nav)
                    period_row = {
                        "strategy": strategy,
                        "scenario": scenario,
                        "signal_date": signal_day,
                        "execution_day": execution_day,
                        "period_end_boundary": next_boundary,
                        "period_end_execution_day": end_execution,
                        "selected_symbols": "|".join(selected_symbols),
                        "target_budget": budget,
                        "target_weight_sum": sum(weights.values()),
                        "pre_trade_nav_vnd": pre_trade_nav,
                        "post_trade_nav_vnd": post_trade_nav,
                        "period_end_nav_vnd": end_nav,
                        "period_net_return": net_return,
                        "benchmark_return": benchmark_return,
                        "net_excess_return": net_return - benchmark_return,
                        "benchmark_nav": benchmark_nav,
                        "cash_vnd": state.cash,
                        "cash_weight": state.cash / end_nav if end_nav > 0 else 0.0,
                        "trade_count": len(period_trades),
                        "buy_count": sum(
                            row["side"] == "BUY" for row in period_trades
                        ),
                        "sell_count": sum(
                            row["side"] == "SELL" for row in period_trades
                        ),
                    }
                    period_rows.append(period_row)
                    for symbol, quantity in sorted(state.holdings.items()):
                        if quantity <= 0:
                            continue
                        all_holdings.append(
                            {
                                "strategy": strategy,
                                "scenario": scenario,
                                "signal_date": signal_day,
                                "valuation_day": end_execution,
                                "symbol": symbol,
                                "quantity": quantity,
                                "price_vnd": end_prices.get(symbol, 0.0),
                                "market_value_vnd": quantity
                                * end_prices.get(symbol, 0.0),
                                "sector": _sector_at(
                                    sectors_rows,
                                    symbol,
                                    signal_day,
                                )
                                or "",
                            }
                        )
                    previous_execution = end_execution
                benchmark_returns = [
                    float(row["benchmark_return"]) for row in period_rows
                ]
                final_nav = nav_path[-1]
                total_return = final_nav / initial_capital_vnd - 1.0
                benchmark_total = _compound(benchmark_returns)
                relative = (
                    (1.0 + total_return) / (1.0 + benchmark_total) - 1.0
                )
                summaries.append(
                    {
                        "strategy": strategy,
                        "scenario": scenario,
                        "period_count": len(period_rows),
                        "first_signal_date": period_rows[0]["signal_date"],
                        "last_signal_date": period_rows[-1]["signal_date"],
                        "initial_capital_vnd": initial_capital_vnd,
                        "final_nav_vnd": final_nav,
                        "net_profit_vnd": final_nav - initial_capital_vnd,
                        "net_total_return": total_return,
                        "benchmark_total_return": benchmark_total,
                        "relative_total_return": relative,
                        "positive_net_excess_ratio": sum(
                            row["net_excess_return"] > 0 for row in period_rows
                        )
                        / len(period_rows),
                        "average_net_excess_return": fmean(
                            float(row["net_excess_return"])
                            for row in period_rows
                        ),
                        "max_drawdown": _max_drawdown(nav_path),
                        "total_trade_count": len(strategy_trades),
                        "final_cash_vnd": state.cash,
                        "exact_cash_ledger_pnl_computed": True,
                    }
                )
                all_periods.extend(period_rows)
                all_trades.extend(strategy_trades)
    finally:
        connection.close()
    return all_periods, all_trades, all_holdings, summaries


def _data_contract() -> dict[str, object]:
    return {
        "schema_version": "integrated_data_ledger_v36_contract",
        "frozen_policy": {
            "policy_id": EXPECTED_POLICY_ID,
            "model": EXPECTED_MODEL,
            "breadth": EXPECTED_BREADTH,
            "fixed_voluntary_replacement_cap": EXPECTED_CAP,
        },
        "required_price_basis_mode": PRICE_BASIS_MODE,
        "required_assurance_schema": ASSURANCE_SCHEMA,
        "execution": {
            "signal_to_execution": "NEXT_MARKET_DAY_OPEN",
            "lot_size": LOT_SIZE,
            "inverse_volatility_lookback_sessions": VOLATILITY_LOOKBACK,
            "max_symbol_weight": MAX_SYMBOL_WEIGHT,
            "max_sector_weight": MAX_SECTOR_WEIGHT,
            "base_slippage_bps_each_side": 5.0,
            "stress_slippage_bps_each_side": 10.0,
        },
        "strategies": [
            "FROZEN_SELECTION_FULLY_INVESTED",
            "MVP_REGIME_CASH_OVERLAY_DIAGNOSTIC",
        ],
        "regime_cash_overlay": {
            "risk_on_budget": RISK_ON_BUDGET,
            "risk_off_budget": RISK_OFF_BUDGET,
            "promotion_authority": False,
        },
        "permissions": {
            "historical_promotion_allowed": False,
            "research_eligible": False,
            "live_capital_approved": False,
            "automatic_live_orders_allowed": False,
        },
    }


def _write_templates(
    output_dir: Path,
    sqlite_sha: str,
    invalid_sha: str,
) -> None:
    _write_csv(
        output_dir / SECTOR_TEMPLATE_FILE,
        [],
        (
            "symbol",
            "sector",
            "effective_from",
            "effective_to",
            "source",
            "confirmed_at",
        ),
    )
    _write_csv(
        output_dir / ACTIONS_TEMPLATE_FILE,
        [],
        (
            "source_event_id",
            "symbol",
            "event_date",
            "event_type",
            "adjustment_factor",
            "cash_amount_vnd",
            "source",
            "confirmed_at",
        ),
    )
    _write_json(
        output_dir / ASSURANCE_TEMPLATE_FILE,
        {
            "schema_version": ASSURANCE_SCHEMA,
            "coverage_first_day": "2015-06-29",
            "coverage_last_day": "2026-07-31",
            "sqlite_sha256": sqlite_sha,
            "sector_master_sha256": "REPLACE_WITH_SHA256",
            "corporate_actions_sha256": "REPLACE_WITH_SHA256",
            "invalid_ohlcv_export_sha256": invalid_sha,
            "price_basis_confirmed": False,
            "price_basis_mode": PRICE_BASIS_MODE,
            "price_unit_vnd_multiplier": 1000,
            "cash_dividend_tax_bps": "REPLACE_WITH_VERIFIED_VALUE",
            "point_in_time_sector_master_complete": False,
            "corporate_actions_complete": False,
            "invalid_ohlcv_quarantine_approved": False,
            "reviewer": "",
            "reviewed_at": "",
            "evidence": [],
        },
    )


def _empty_ledger_outputs(output_dir: Path) -> None:
    _write_csv(
        output_dir / LEDGER_PERIODS_FILE,
        [],
        (
            "strategy",
            "scenario",
            "signal_date",
            "execution_day",
            "period_end_boundary",
            "period_end_execution_day",
            "selected_symbols",
            "target_budget",
            "target_weight_sum",
            "pre_trade_nav_vnd",
            "post_trade_nav_vnd",
            "period_end_nav_vnd",
            "period_net_return",
            "benchmark_return",
            "net_excess_return",
            "benchmark_nav",
            "cash_vnd",
            "cash_weight",
            "trade_count",
            "buy_count",
            "sell_count",
        ),
    )
    _write_csv(
        output_dir / LEDGER_TRADES_FILE,
        [],
        (
            "strategy",
            "scenario",
            "signal_date",
            "execution_day",
            "symbol",
            "side",
            "quantity",
            "raw_open_vnd",
            "execution_price_vnd",
            "gross_notional_vnd",
            "fee_vnd",
            "tax_vnd",
            "transfer_fee_vnd",
            "cash_change_vnd",
        ),
    )
    _write_csv(
        output_dir / LEDGER_HOLDINGS_FILE,
        [],
        (
            "strategy",
            "scenario",
            "signal_date",
            "valuation_day",
            "symbol",
            "quantity",
            "price_vnd",
            "market_value_vnd",
            "sector",
        ),
    )
    _write_csv(
        output_dir / LEDGER_SUMMARY_FILE,
        [],
        (
            "strategy",
            "scenario",
            "period_count",
            "first_signal_date",
            "last_signal_date",
            "initial_capital_vnd",
            "final_nav_vnd",
            "net_profit_vnd",
            "net_total_return",
            "benchmark_total_return",
            "relative_total_return",
            "positive_net_excess_ratio",
            "average_net_excess_return",
            "max_drawdown",
            "total_trade_count",
            "final_cash_vnd",
            "exact_cash_ledger_pnl_computed",
        ),
    )


def run_v36(
    *,
    v34_artifact_zip: Path,
    v33_artifact_zip: Path,
    v32_artifact_zip: Path,
    v22_input_zip: Path,
    sqlite_store: Path,
    output_dir: Path,
    expected_v34_sha256: str = "",
    expected_v33_sha256: str = "",
    expected_v32_sha256: str = "",
    expected_v22_sha256: str = "",
    expected_sqlite_sha256: str = "",
    sector_master: Path | None = None,
    corporate_actions: Path | None = None,
    data_assurance_report: Path | None = None,
    initial_capital_vnd: int = INITIAL_CAPITAL_VND,
) -> dict[str, object]:
    out = Path(output_dir).resolve()
    if out.exists():
        raise FileExistsError(f"V36_OUTPUT_EXISTS:{out}")
    if initial_capital_vnd <= 0:
        raise ValueError("V36_INITIAL_CAPITAL_INVALID")
    if expected_v22_sha256 and _sha256(v22_input_zip) != expected_v22_sha256:
        raise ValueError("V36_V22_SHA256_MISMATCH")
    frozen = v35._verified_v34(v34_artifact_zip, expected_v34_sha256)
    v33 = _verified_v33(v33_artifact_zip, expected_v33_sha256)
    v32 = _verified_v32(v32_artifact_zip, expected_v32_sha256)
    sqlite_audit = v35.audit_sqlite(sqlite_store, expected_sqlite_sha256)
    selection_rows, selection_match = selection_lineage_audit(
        v33["periods"],
        v32["predictions"],
    )
    selections = [
        {
            "signal_date": row["signal_date"],
            "selected_symbols": row["rebuilt_selected_symbols"].split("|"),
        }
        for row in selection_rows
    ]
    regime_map, regime_meta = load_regime_map(v22_input_zip)

    out.mkdir(parents=True)
    invalid_rows = extract_invalid_ohlcv(
        sqlite_store,
        sqlite_audit["resolved_columns"],
    )
    critical_keys = execution_critical_keys(
        sqlite_store,
        selections,
        v33["periods"],
    )
    for row in invalid_rows:
        row["execution_critical"] = (
            str(row.get("day") or ""),
            str(row.get("symbol") or ""),
        ) in critical_keys
    execution_critical_count = sum(
        bool(row["execution_critical"]) for row in invalid_rows
    )
    invalid_fields = (
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
    _write_csv(out / INVALID_ROWS_FILE, invalid_rows, invalid_fields)
    invalid_summary = invalid_ohlcv_summary(invalid_rows)
    _write_csv(
        out / INVALID_SUMMARY_FILE,
        invalid_summary,
        ("dimension", "value", "row_count"),
    )
    invalid_sha = _sha256(out / INVALID_ROWS_FILE)

    sector = audit_sector_coverage(sector_master, selections)
    actions = audit_corporate_actions_strict(corporate_actions)
    assurance = audit_assurance_v2(
        data_assurance_report,
        sqlite_audit=sqlite_audit,
        sector=sector,
        actions=actions,
        invalid_rows_sha256=invalid_sha,
    )

    gates = [
        (
            "V34_POLICY_VERIFIED",
            frozen["policy"].get("policy_id") == EXPECTED_POLICY_ID,
            "V36_V34_POLICY_INVALID",
        ),
        ("V33_CAP3_ARTIFACT_VERIFIED", True, ""),
        ("V32_ELIGIBLE_PREDICTIONS_VERIFIED", True, ""),
        (
            "V33_SELECTIONS_REBUILT_EXACTLY",
            selection_match,
            "V36_SELECTION_LINEAGE_MISMATCH",
        ),
        (
            "SQLITE_UNIQUE_DAY_SYMBOL",
            sqlite_audit["duplicate_key_count"] == 0,
            "SQLITE_DUPLICATE_DAY_SYMBOL",
        ),
        (
            "SQLITE_CONFLICTS_ZERO",
            sqlite_audit["conflict_row_count"] in (None, 0),
            "SQLITE_CONFLICTS_PRESENT",
        ),
        (
            "T1_OPEN_COVERAGE_COMPLETE",
            sqlite_audit["t1_open_coverage_ratio"] == 1.0,
            "T1_OPEN_COVERAGE_INCOMPLETE",
        ),
        (
            "INVALID_OHLCV_EXPORTED",
            len(invalid_rows) == int(sqlite_audit["invalid_ohlcv_row_count"]),
            "V36_INVALID_OHLCV_EXPORT_COUNT_MISMATCH",
        ),
        (
            "INVALID_OHLCV_EXECUTION_CRITICAL_ZERO",
            execution_critical_count == 0,
            "V36_INVALID_OHLCV_OVERLAPS_EXECUTION",
        ),
        (
            "INVALID_OHLCV_QUARANTINE_APPROVED",
            bool(assurance.get("invalid_ohlcv_quarantine_approved")),
            "V36_INVALID_OHLCV_QUARANTINE_NOT_APPROVED",
        ),
        (
            "SECTOR_MASTER_SCHEMA_VALID",
            bool(sector.get("valid")),
            str(sector.get("blocker") or "POINT_IN_TIME_SECTOR_MASTER_INVALID"),
        ),
        (
            "SECTOR_COVERAGE_COMPLETE",
            bool(sector.get("coverage_complete_for_selected_symbols")),
            "V36_SECTOR_COVERAGE_INCOMPLETE",
        ),
        (
            "CORPORATE_ACTION_SCHEMA_STRICT",
            bool(actions.get("strict_valid")),
            str(
                actions.get("blocker")
                or "V36_CORPORATE_ACTION_CONTRACT_INVALID"
            ),
        ),
        (
            "DATA_ASSURANCE_V2_VERIFIED",
            bool(assurance.get("valid")),
            str(
                assurance.get("blocker")
                or "V36_DATA_ASSURANCE_V2_NOT_VERIFIED"
            ),
        ),
        (
            "PRICE_BASIS_RAW_EXECUTION_CONFIRMED",
            bool(assurance.get("price_basis_confirmed"))
            and bool(assurance.get("price_basis_mode_supported")),
            "V36_PRICE_BASIS_NOT_CONFIRMED",
        ),
        (
            "REGIME_COVERAGE_COMPLETE",
            all(str(row["signal_date"]) in regime_map for row in selections),
            "V36_REGIME_COVERAGE_INCOMPLETE",
        ),
    ]
    gate_rows = [
        {
            "gate": name,
            "passed": bool(passed),
            "blocker": "" if passed else blocker,
        }
        for name, passed, blocker in gates
    ]
    blockers = sorted(
        {str(row["blocker"]) for row in gate_rows if row["blocker"]}
    )
    ready = not blockers

    period_rows: list[dict[str, object]] = []
    trade_rows: list[dict[str, object]] = []
    holding_rows: list[dict[str, object]] = []
    ledger_summaries: list[dict[str, object]] = []
    ledger_status = "NOT_RUN_BLOCKED"
    ledger_error = ""
    if ready:
        try:
            period_rows, trade_rows, holding_rows, ledger_summaries = (
                run_exact_ledgers(
                    sqlite_store=sqlite_store,
                    selections=selections,
                    v33_periods=v33["periods"],
                    sector_master=Path(sector_master),
                    corporate_actions=Path(corporate_actions),
                    regime_by_day=regime_map,
                    price_multiplier=float(
                        assurance["price_unit_vnd_multiplier"]
                    ),
                    dividend_tax_bps=float(
                        assurance["cash_dividend_tax_bps"]
                    ),
                    initial_capital_vnd=initial_capital_vnd,
                    invalid_keys={
                        (
                            str(row.get("day") or ""),
                            str(row.get("symbol") or ""),
                        )
                        for row in invalid_rows
                    },
                )
            )
            ledger_status = "SUCCESS"
        except Exception as exc:
            ledger_status = "FAILED_CLOSED"
            ledger_error = f"{type(exc).__name__}:{exc}"
            blockers = sorted(set(blockers) | {"V36_EXACT_LEDGER_RUNTIME_FAILED"})
            ready = False

    _write_csv(
        out / SELECTION_AUDIT_FILE,
        selection_rows,
        (
            "signal_date",
            "expected_selected_symbols",
            "rebuilt_selected_symbols",
            "exact_order_match",
            "set_match",
            "forced_exit_count",
            "voluntary_replacement_count",
            "candidate_count",
        ),
    )
    _write_csv(
        out / READINESS_GATES_FILE,
        gate_rows,
        ("gate", "passed", "blocker"),
    )
    _write_csv(
        out / BLOCKERS_FILE,
        [{"blocker": blocker} for blocker in blockers],
        ("blocker",),
    )
    if period_rows:
        _write_csv(out / LEDGER_PERIODS_FILE, period_rows, tuple(period_rows[0]))
        _write_csv(out / LEDGER_TRADES_FILE, trade_rows, tuple(trade_rows[0]))
        _write_csv(
            out / LEDGER_HOLDINGS_FILE,
            holding_rows,
            tuple(holding_rows[0]) if holding_rows else (
                "strategy",
                "scenario",
                "signal_date",
                "valuation_day",
                "symbol",
                "quantity",
                "price_vnd",
                "market_value_vnd",
                "sector",
            ),
        )
        _write_csv(
            out / LEDGER_SUMMARY_FILE,
            ledger_summaries,
            tuple(ledger_summaries[0]),
        )
    else:
        _empty_ledger_outputs(out)
    _write_json(out / DATA_CONTRACT_FILE, _data_contract())
    _write_templates(out, str(sqlite_audit["sha256"]), invalid_sha)

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "decision": (
            "LEDGER_COMPLETED" if ledger_status == "SUCCESS" else "BLOCKED"
        ),
        "recommendation": (
            "REVIEW_EXACT_LEDGER_AND_CONTINUE_FUTURE_HOLDOUT"
            if ledger_status == "SUCCESS"
            else "COMPLETE_DATA_INTEGRITY_PACK_THEN_RERUN_SAME_V36"
        ),
        "policy_id": EXPECTED_POLICY_ID,
        "frozen_policy_unchanged": True,
        "source": {
            "v34_artifact_sha256": frozen["artifact_sha256"],
            "v34_policy_sha256": frozen["policy_sha256"],
            "v33_artifact_sha256": v33["sha256"],
            "v32_artifact_sha256": v32["sha256"],
            "v22_input_sha256": regime_meta["input_zip_sha256"],
            "sqlite_sha256": sqlite_audit["sha256"],
        },
        "coverage": {
            "historical_period_count": len(selections),
            "first_signal_date": selections[0]["signal_date"],
            "last_signal_date": selections[-1]["signal_date"],
            "sqlite_first_day": sqlite_audit["first_day"],
            "sqlite_last_day": sqlite_audit["last_day"],
        },
        "data_integrity": {
            "sqlite_row_count": sqlite_audit["row_count"],
            "duplicate_key_count": sqlite_audit["duplicate_key_count"],
            "conflict_row_count": sqlite_audit["conflict_row_count"],
            "t1_open_coverage_ratio": sqlite_audit["t1_open_coverage_ratio"],
            "invalid_ohlcv_row_count": len(invalid_rows),
            "invalid_ohlcv_ratio": len(invalid_rows)
            / int(sqlite_audit["row_count"]),
            "invalid_ohlcv_execution_critical_count": execution_critical_count,
            "invalid_ohlcv_export_sha256": invalid_sha,
            "automatic_correction_performed": False,
        },
        "selection_lineage": {
            "exact_match": selection_match,
            "period_count": len(selection_rows),
        },
        "sector_master": sector,
        "corporate_actions": actions,
        "data_assurance": assurance,
        "gates": gate_rows,
        "blockers": blockers,
        "ledger_status": ledger_status,
        "ledger_error": ledger_error,
        "ledger_summaries": ledger_summaries,
        "exact_cash_ledger_pnl_computed": ledger_status == "SUCCESS",
        "portfolio_return_proxy_used_as_exact_pnl": False,
        "historical_promotion_allowed": False,
        "research_eligible": False,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
        "actionable": False,
    }
    _write_json(out / REPORT_FILE, report)
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v34-artifact-zip", type=Path, required=True)
    parser.add_argument("--v33-artifact-zip", type=Path, required=True)
    parser.add_argument("--v32-artifact-zip", type=Path, required=True)
    parser.add_argument("--v22-input-zip", type=Path, required=True)
    parser.add_argument("--sqlite-store", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-v34-sha256", default="")
    parser.add_argument("--expected-v33-sha256", default="")
    parser.add_argument("--expected-v32-sha256", default="")
    parser.add_argument("--expected-v22-sha256", default="")
    parser.add_argument("--expected-sqlite-sha256", default="")
    parser.add_argument("--sector-master", type=Path)
    parser.add_argument("--corporate-actions", type=Path)
    parser.add_argument("--data-assurance-report", type=Path)
    parser.add_argument(
        "--initial-capital-vnd",
        type=int,
        default=INITIAL_CAPITAL_VND,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = run_v36(
        v34_artifact_zip=args.v34_artifact_zip,
        v33_artifact_zip=args.v33_artifact_zip,
        v32_artifact_zip=args.v32_artifact_zip,
        v22_input_zip=args.v22_input_zip,
        sqlite_store=args.sqlite_store,
        output_dir=args.output_dir,
        expected_v34_sha256=args.expected_v34_sha256,
        expected_v33_sha256=args.expected_v33_sha256,
        expected_v32_sha256=args.expected_v32_sha256,
        expected_v22_sha256=args.expected_v22_sha256,
        expected_sqlite_sha256=args.expected_sqlite_sha256,
        sector_master=args.sector_master,
        corporate_actions=args.corporate_actions,
        data_assurance_report=args.data_assurance_report,
        initial_capital_vnd=args.initial_capital_vnd,
    )
    print(json.dumps(report, ensure_ascii=True, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
