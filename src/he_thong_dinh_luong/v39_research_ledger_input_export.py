"""Export a compact, self-contained research-ledger input for V39 handoff.

The export is deliberately research-only. It includes the selected-symbol
surface, a warm OHLCV slice for the 78 symbols plus VNINDEX, and a mechanically
computed VNINDEX/MA250 regime table. It does not resolve sector, corporate
action, or vendor price-basis assurance and cannot approve live capital.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import sqlite3
from statistics import fmean
from typing import Mapping, Sequence

SCHEMA_VERSION = "vn_quant_v39_research_ledger_input_v1"
REPORT_FILE = "research_ledger_input_v39.json"
OHLCV_FILE = "research_ohlcv_slice_v39.csv"
SELECTION_FILE = "research_selection_surface_v39.csv"
REGIME_FILE = "research_vnindex_regime_v39.csv"
MANIFEST_FILE = "research_ledger_input_manifest_v39.json"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]], fields: Sequence[str]) -> None:
    with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _write_json(path: Path, value: object) -> None:
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _sha(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _symbols(workspace: Path) -> list[str]:
    path = workspace / "selected_symbols_v39.txt"
    values = sorted({line.strip().upper() for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()})
    if not values:
        raise ValueError("V39_RESEARCH_SELECTED_SYMBOLS_EMPTY")
    return values


def _selection_rows(workspace: Path) -> list[dict[str, str]]:
    path = workspace / "corporate_action_window_evidence_v39.csv"
    rows = _read_csv(path)
    selected = [
        {
            "signal_date": str(row.get("signal_date") or ""),
            "holding_start": str(row.get("holding_start") or ""),
            "holding_end": str(row.get("holding_end") or ""),
            "symbol": str(row.get("symbol") or "").strip().upper(),
        }
        for row in rows
    ]
    selected.sort(key=lambda row: (row["signal_date"], row["symbol"]))
    if not selected:
        raise ValueError("V39_RESEARCH_SELECTION_SURFACE_EMPTY")
    if len({(row["signal_date"], row["symbol"]) for row in selected}) != len(selected):
        raise ValueError("V39_RESEARCH_SELECTION_SURFACE_DUPLICATE")
    return selected


def _table_columns(db: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in db.execute(f"PRAGMA table_info({table})")}


def _ohlcv_rows(store: Path, symbols: Sequence[str], start: str, end: str) -> tuple[list[dict[str, object]], list[tuple[str, float]]]:
    db = sqlite3.connect(Path(store))
    try:
        columns = _table_columns(db, "bars")
        required = {"symbol", "day", "open", "high", "low", "close", "volume"}
        if not required.issubset(columns):
            raise ValueError("V39_RESEARCH_SQLITE_BARS_SCHEMA_INVALID")
        optional = [name for name in ("asset_type", "source", "source_version", "price_basis") if name in columns]
        fields = optional + ["symbol", "day", "open", "high", "low", "close", "volume"]
        placeholders = ",".join("?" for _ in symbols)
        sql = (
            f"SELECT {','.join(fields)} FROM bars "
            f"WHERE day>=? AND day<=? AND (symbol='VNINDEX' OR symbol IN ({placeholders})) "
            "ORDER BY day, symbol"
        )
        raw = db.execute(sql, (start, end, *symbols)).fetchall()
        rows: list[dict[str, object]] = []
        vnindex: list[tuple[str, float]] = []
        for values in raw:
            row = dict(zip(fields, values, strict=True))
            numeric = [row.get(name) for name in ("open", "high", "low", "close")]
            try:
                valid = all(math.isfinite(float(value)) and float(value) > 0.0 for value in numeric)
                volume = float(row.get("volume") or 0.0)
                valid = valid and math.isfinite(volume) and volume >= 0.0
            except (TypeError, ValueError):
                valid = False
            row["mechanically_valid_ohlcv"] = valid
            rows.append(row)
            if str(row.get("symbol") or "").upper() == "VNINDEX" and valid:
                vnindex.append((str(row["day"]), float(row["close"])))
        return rows, vnindex
    finally:
        db.close()


def _regime_rows(signal_dates: Sequence[str], vnindex: Sequence[tuple[str, float]]) -> list[dict[str, object]]:
    bars = sorted(vnindex)
    result: list[dict[str, object]] = []
    for signal in sorted(set(signal_dates)):
        history = [(day, close) for day, close in bars if day <= signal]
        if history:
            as_of, close = history[-1]
        else:
            as_of, close = "", 0.0
        window = [value for _, value in history[-250:]]
        ma250 = fmean(window) if len(window) == 250 else None
        result.append({
            "signal_date": signal,
            "vnindex_as_of": as_of,
            "vnindex_close": close if close > 0 else "",
            "vnindex_ma250": ma250 if ma250 is not None else "",
            "ma250_observation_count": len(window),
            "risk_on": bool(ma250 is not None and close >= ma250),
            "mechanically_complete": ma250 is not None,
        })
    return result


def export_research_ledger_input(*, workspace_dir: Path, sqlite_store: Path, output_dir: Path) -> dict[str, object]:
    workspace = Path(workspace_dir).resolve()
    store = Path(sqlite_store).resolve()
    output = Path(output_dir).resolve()
    if not workspace.is_dir():
        raise FileNotFoundError(f"V39_RESEARCH_WORKSPACE_MISSING:{workspace}")
    if not store.is_file():
        raise FileNotFoundError(f"V39_RESEARCH_SQLITE_MISSING:{store}")
    output.mkdir(parents=True, exist_ok=True)

    symbols = _symbols(workspace)
    selections = _selection_rows(workspace)
    starts = [date.fromisoformat(row["holding_start"]) for row in selections]
    ends = [date.fromisoformat(row["holding_end"]) for row in selections]
    warm_start = (min(starts) - timedelta(days=550)).isoformat()
    final_end = max(ends).isoformat()
    ohlcv, vnindex = _ohlcv_rows(store, symbols, warm_start, final_end)
    regimes = _regime_rows([row["signal_date"] for row in selections], vnindex)

    _write_csv(
        output / SELECTION_FILE,
        selections,
        ("signal_date", "holding_start", "holding_end", "symbol"),
    )
    ohlcv_fields = (
        "asset_type", "symbol", "day", "open", "high", "low", "close",
        "volume", "source", "source_version", "price_basis",
        "mechanically_valid_ohlcv",
    )
    _write_csv(output / OHLCV_FILE, ohlcv, ohlcv_fields)
    _write_csv(
        output / REGIME_FILE,
        regimes,
        (
            "signal_date", "vnindex_as_of", "vnindex_close", "vnindex_ma250",
            "ma250_observation_count", "risk_on", "mechanically_complete",
        ),
    )

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "RESEARCH_INPUT_EXPORTED",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "selected_symbol_count": len(symbols),
        "selection_row_count": len(selections),
        "signal_date_count": len({row["signal_date"] for row in selections}),
        "ohlcv_row_count": len(ohlcv),
        "valid_ohlcv_row_count": sum(row.get("mechanically_valid_ohlcv") is True for row in ohlcv),
        "vnindex_row_count": len(vnindex),
        "regime_complete_count": sum(row.get("mechanically_complete") is True for row in regimes),
        "warm_start": warm_start,
        "final_end": final_end,
        "price_basis_values": sorted({str(row.get("price_basis") or "") for row in ohlcv}),
        "research_only": True,
        "sector_point_in_time_resolved": False,
        "corporate_actions_complete": False,
        "vendor_price_basis_confirmed": False,
        "exact_cash_ledger_approved": False,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }
    _write_json(output / REPORT_FILE, report)
    files = [output / SELECTION_FILE, output / OHLCV_FILE, output / REGIME_FILE, output / REPORT_FILE]
    manifest = {
        "schema_version": "vn_quant_v39_research_ledger_input_manifest_v1",
        "files": [
            {"path": path.name, "sha256": _sha(path), "size_bytes": path.stat().st_size}
            for path in files
        ],
    }
    _write_json(output / MANIFEST_FILE, manifest)
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export V39 research-ledger input")
    parser.add_argument("--workspace-dir", required=True, type=Path)
    parser.add_argument("--sqlite-store", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = export_research_ledger_input(
        workspace_dir=args.workspace_dir,
        sqlite_store=args.sqlite_store,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
