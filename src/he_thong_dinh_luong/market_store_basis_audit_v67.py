"""V67 read-only audit for market-store price-basis seams.

This module never mutates the SQLite market store and never trains a model.
It inspects consecutive-session price discontinuities together with bar
``fetched_at`` provenance, source revisions, conflicts, fetched ranges and sync
runs.  The purpose is to determine whether the store may contain mixed price
bases across fetch batches before C3 is allowed to use the history.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import closing
from datetime import date
import json
from pathlib import Path
import sqlite3
from typing import Mapping, Sequence

SCHEMA_VERSION = "market_store_basis_audit_v67"
GAP_THRESHOLDS = (0.18, 0.25, 0.40)
SENSITIVE = ("secret", "password", "token", "api_key", "apikey", "credential")


def _q(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _schema(db: sqlite3.Connection) -> dict[str, list[str]]:
    tables = [
        str(r[0]) for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        if not str(r[0]).startswith("sqlite_")
    ]
    return {
        table: [str(r[1]) for r in db.execute(f"PRAGMA table_info({_q(table)})")]
        for table in tables
    }


def _parse_day(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _redact(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(k): ("[REDACTED]" if any(t in str(k).lower() for t in SENSITIVE) else _redact(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def _parse_json(value: object) -> object:
    if value is None:
        return None
    try:
        return _redact(json.loads(str(value)))
    except (json.JSONDecodeError, TypeError, ValueError):
        text = str(value)
        return text if len(text) <= 2000 else text[:2000] + "...[truncated]"


def _load_bars(db: sqlite3.Connection) -> tuple[tuple[date, ...], dict[str, list[dict[str, object]]]]:
    schema = _schema(db)
    if "bars" not in schema:
        raise ValueError("V67_BARS_TABLE_MISSING")
    cols = {c.lower(): c for c in schema["bars"]}
    required = {"asset_type", "symbol", "day", "open", "close"}
    if not required.issubset(cols):
        raise ValueError("V67_BARS_REQUIRED_COLUMNS_MISSING")
    optional = ["high", "low", "volume", "source", "source_version", "price_basis", "normalized_sha256", "fetched_at"]
    selected = [cols[k] for k in ["asset_type", "symbol", "day", "open", "close"]]
    selected += [cols[k] for k in optional if k in cols]
    sql = f"SELECT {','.join(_q(c) for c in selected)} FROM bars ORDER BY {_q(cols['day'])},{_q(cols['symbol'])}"
    keys = ["asset_type", "symbol", "day", "open", "close"] + [k for k in optional if k in cols]

    index_days: list[date] = []
    by_symbol: dict[str, list[dict[str, object]]] = defaultdict(list)
    for raw in db.execute(sql):
        row = dict(zip(keys, raw))
        symbol = str(row.get("symbol") or "").strip().upper()
        day = _parse_day(row.get("day"))
        if not symbol or day is None:
            continue
        row["symbol"] = symbol
        row["day"] = day.isoformat()
        asset = str(row.get("asset_type") or "").upper()
        if asset == "INDEX" and symbol in {"VNINDEX", "VN-INDEX", "VN_INDEX"}:
            index_days.append(day)
            continue
        if asset != "STOCK":
            continue
        try:
            if float(row["open"]) <= 0 or float(row["close"]) <= 0:
                continue
        except (TypeError, ValueError):
            continue
        by_symbol[symbol].append(row)
    calendar = tuple(sorted(set(index_days)))
    if not calendar:
        raise ValueError("V67_VNINDEX_CALENDAR_MISSING")
    return calendar, by_symbol


def _gap_events(
    calendar: Sequence[date], by_symbol: Mapping[str, Sequence[Mapping[str, object]]]
) -> list[dict[str, object]]:
    pos = {d: i for i, d in enumerate(calendar)}
    events: list[dict[str, object]] = []
    for symbol, rows in sorted(by_symbol.items()):
        for prev, cur in zip(rows, rows[1:]):
            pday = _parse_day(prev.get("day"))
            day = _parse_day(cur.get("day"))
            if pday is None or day is None or pos.get(day, -99) - pos.get(pday, -99) != 1:
                continue
            try:
                prev_close = float(prev["close"])
                open_price = float(cur["open"])
            except (TypeError, ValueError, KeyError):
                continue
            gap = open_price / prev_close - 1.0
            abs_gap = abs(gap)
            if abs_gap < GAP_THRESHOLDS[0]:
                continue
            events.append({
                "symbol": symbol,
                "prev_day": pday.isoformat(),
                "day": day.isoformat(),
                "prev_close": prev_close,
                "open": open_price,
                "open_gap": gap,
                "abs_open_gap": abs_gap,
                "thresholds": [f"{t:.2f}" for t in GAP_THRESHOLDS if abs_gap >= t],
                "prev_fetched_at": prev.get("fetched_at"),
                "fetched_at": cur.get("fetched_at"),
                "different_fetch_timestamp": bool(prev.get("fetched_at") != cur.get("fetched_at")),
                "prev_price_basis": prev.get("price_basis"),
                "price_basis": cur.get("price_basis"),
                "prev_source_version": prev.get("source_version"),
                "source_version": cur.get("source_version"),
            })
    events.sort(key=lambda r: (-float(r["abs_open_gap"]), str(r["symbol"]), str(r["day"])))
    return events


def _contexts(events: Sequence[Mapping[str, object]], by_symbol: Mapping[str, Sequence[Mapping[str, object]]], radius: int = 4) -> list[dict[str, object]]:
    by_key = {(str(e["symbol"]), str(e["day"])): e for e in events}
    out: list[dict[str, object]] = []
    for symbol, rows in sorted(by_symbol.items()):
        day_to_i = {str(row["day"]): i for i, row in enumerate(rows)}
        for (sym, day), event in by_key.items():
            if sym != symbol or day not in day_to_i:
                continue
            i = day_to_i[day]
            for j in range(max(0, i-radius), min(len(rows), i+radius+1)):
                row = dict(rows[j])
                row["event_day"] = day
                row["event_abs_open_gap"] = event["abs_open_gap"]
                row["relative_row"] = j - i
                out.append(row)
    out.sort(key=lambda r: (str(r["symbol"]), str(r["event_day"]), int(r["relative_row"])))
    return out


def _table_count(db: sqlite3.Connection, table: str) -> int:
    return int(db.execute(f"SELECT COUNT(*) FROM {_q(table)}").fetchone()[0])


def _revision_rows(db: sqlite3.Connection, events: Sequence[Mapping[str, object]], schema: Mapping[str, Sequence[str]]) -> list[dict[str, object]]:
    table = "market_source_revisions_v49"
    if table not in schema:
        return []
    cols = {c.lower(): c for c in schema[table]}
    if not {"symbol", "day", "old_json", "new_json"}.issubset(cols):
        return []
    wanted = {(str(e["symbol"]), str(e["day"])) for e in events} | {(str(e["symbol"]), str(e["prev_day"])) for e in events}
    selected = [c for c in ["id","asset_type","symbol","day","old_json","new_json","detected_at","policy"] if c in cols]
    sql = f"SELECT {','.join(_q(cols[c]) for c in selected)} FROM {_q(table)} ORDER BY {_q(cols.get('id', selected[0]))}"
    out = []
    for raw in db.execute(sql):
        row = dict(zip(selected, raw))
        key = (str(row.get("symbol") or "").upper(), str(row.get("day") or "")[:10])
        if key not in wanted:
            continue
        if "old_json" in row: row["old_json"] = _parse_json(row["old_json"])
        if "new_json" in row: row["new_json"] = _parse_json(row["new_json"])
        out.append(row)
    return out


def _conflict_rows(db: sqlite3.Connection, events: Sequence[Mapping[str, object]], schema: Mapping[str, Sequence[str]]) -> list[dict[str, object]]:
    table = "conflicts"
    if table not in schema:
        return []
    cols = {c.lower(): c for c in schema[table]}
    if not {"symbol", "day"}.issubset(cols):
        return []
    wanted = {(str(e["symbol"]), str(e["day"])) for e in events} | {(str(e["symbol"]), str(e["prev_day"])) for e in events}
    selected = [c for c in ["id","asset_type","symbol","day","existing_json","incoming_json","detected_at"] if c in cols]
    sql = f"SELECT {','.join(_q(cols[c]) for c in selected)} FROM {_q(table)} ORDER BY {_q(cols.get('id', selected[0]))}"
    out = []
    for raw in db.execute(sql):
        row = dict(zip(selected, raw))
        key = (str(row.get("symbol") or "").upper(), str(row.get("day") or "")[:10])
        if key not in wanted:
            continue
        for field in ("existing_json","incoming_json"):
            if field in row: row[field] = _parse_json(row[field])
        out.append(row)
    return out


def _range_rows(db: sqlite3.Connection, events: Sequence[Mapping[str, object]], schema: Mapping[str, Sequence[str]]) -> list[dict[str, object]]:
    table = "fetched_ranges"
    if table not in schema:
        return []
    cols = {c.lower(): c for c in schema[table]}
    if not {"symbol","start_day","end_day"}.issubset(cols):
        return []
    symbols = {str(e["symbol"]) for e in events}
    selected = [c for c in ["id","asset_type","symbol","start_day","end_day","fetched_at","returned_rows","source","source_version"] if c in cols]
    sql = f"SELECT {','.join(_q(cols[c]) for c in selected)} FROM {_q(table)} ORDER BY {_q(cols.get('id', selected[0]))}"
    out=[]
    for raw in db.execute(sql):
        row=dict(zip(selected,raw))
        if str(row.get("symbol") or "").upper() in symbols:
            out.append(row)
    return out


def _sync_rows(db: sqlite3.Connection, schema: Mapping[str, Sequence[str]], limit: int = 100) -> list[dict[str, object]]:
    table = "market_sync_runs_v49"
    if table not in schema:
        return []
    cols={c.lower():c for c in schema[table]}
    selected=[c for c in ["run_id","started_at","requested_start","requested_end","expected_final_session","latest_index_day","latest_stock_day","source_freshness","details_json"] if c in cols]
    if not selected:
        return []
    order = cols.get("started_at") or cols.get("run_id") or selected[0]
    sql=f"SELECT {','.join(_q(cols[c]) for c in selected)} FROM {_q(table)} ORDER BY {_q(order)} DESC LIMIT {int(limit)}"
    out=[]
    for raw in db.execute(sql):
        row=dict(zip(selected,raw))
        if "details_json" in row:
            row["details_json"]=_parse_json(row["details_json"])
        out.append(row)
    return out


def build_report(store: Path) -> dict[str, object]:
    uri = store.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        schema = _schema(db)
        calendar, by_symbol = _load_bars(db)
        events = _gap_events(calendar, by_symbol)
        contexts = _contexts(events, by_symbol)
        revisions = _revision_rows(db, events, schema)
        conflicts = _conflict_rows(db, events, schema)
        ranges = _range_rows(db, events, schema)
        syncs = _sync_rows(db, schema)
        table_counts = {t: _table_count(db,t) for t in ("bars","conflicts","fetched_ranges","market_source_revisions_v49","market_sync_runs_v49") if t in schema}

    revision_keys = {(str(r.get("symbol") or "").upper(), str(r.get("day") or "")[:10]) for r in revisions}
    conflict_keys = {(str(r.get("symbol") or "").upper(), str(r.get("day") or "")[:10]) for r in conflicts}
    for event in events:
        keys={(str(event["symbol"]),str(event["day"])),(str(event["symbol"]),str(event["prev_day"]))}
        event["revision_overlap"] = bool(keys & revision_keys)
        event["conflict_overlap"] = bool(keys & conflict_keys)
        event["mixed_basis_seam_candidate"] = bool(
            float(event["abs_open_gap"]) >= 0.25 and (
                event["different_fetch_timestamp"] or event["revision_overlap"] or event["conflict_overlap"]
            )
        )

    counts={f"{t:.2f}": sum(float(e["abs_open_gap"]) >= t for e in events) for t in GAP_THRESHOLDS}
    seam=[e for e in events if e["mixed_basis_seam_candidate"]]
    symbol_counts=Counter(str(e["symbol"]) for e in events)
    return {
        "schema_version": SCHEMA_VERSION,
        "research_only": True,
        "model_training_run": False,
        "network_used": False,
        "store_mutated": False,
        "table_counts": table_counts,
        "vnindex_session_count": len(calendar),
        "stock_symbol_count": len(by_symbol),
        "gap_event_count_by_threshold": counts,
        "gap_symbol_count": len(symbol_counts),
        "top_gap_symbols": [{"symbol":s,"event_count":c} for s,c in symbol_counts.most_common(30)],
        "different_fetch_timestamp_gap_count": sum(bool(e["different_fetch_timestamp"]) for e in events),
        "revision_overlap_gap_count": sum(bool(e["revision_overlap"]) for e in events),
        "conflict_overlap_gap_count": sum(bool(e["conflict_overlap"]) for e in events),
        "mixed_basis_seam_candidate_count": len(seam),
        "mixed_basis_seam_candidates": seam,
        "gap_events": events,
        "gap_context_rows": contexts,
        "revision_rows_near_gaps": revisions,
        "conflict_rows_near_gaps": conflicts,
        "fetched_ranges_for_gap_symbols": ranges,
        "recent_sync_runs": syncs,
        "research_gate": {
            "price_basis_gate_closed": False,
            "c3_training_authorized": False,
            "rule": "This audit is diagnostic only. Mixed-basis evidence must be resolved or the history rebuilt on one explicit basis before C3 training.",
        },
    }


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    import csv
    path.parent.mkdir(parents=True, exist_ok=True)
    fields=sorted({str(k) for row in rows for k in row.keys()})
    with path.open("w",encoding="utf-8",newline="") as h:
        w=csv.DictWriter(h,fieldnames=fields)
        w.writeheader()
        for row in rows:
            cooked={}
            for k in fields:
                v=row.get(k)
                if isinstance(v,(dict,list)):
                    v=json.dumps(v,ensure_ascii=False,sort_keys=True)
                cooked[k]=v
            w.writerow(cooked)


def main(argv: Sequence[str] | None = None) -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--store",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args(argv)
    report=build_report(args.store)
    out=args.output_dir
    out.mkdir(parents=True,exist_ok=True)
    (out/"v67_market_store_basis_audit.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"
    )
    _write_csv(out/"v67_gap_events_with_provenance.csv",report["gap_events"])
    _write_csv(out/"v67_gap_context_rows.csv",report["gap_context_rows"])
    _write_csv(out/"v67_revision_rows_near_gaps.csv",report["revision_rows_near_gaps"])
    _write_csv(out/"v67_conflict_rows_near_gaps.csv",report["conflict_rows_near_gaps"])
    _write_csv(out/"v67_fetched_ranges_for_gap_symbols.csv",report["fetched_ranges_for_gap_symbols"])
    print(json.dumps({
        "schema_version":SCHEMA_VERSION,
        "gap_event_count_by_threshold":report["gap_event_count_by_threshold"],
        "different_fetch_timestamp_gap_count":report["different_fetch_timestamp_gap_count"],
        "revision_overlap_gap_count":report["revision_overlap_gap_count"],
        "conflict_overlap_gap_count":report["conflict_overlap_gap_count"],
        "mixed_basis_seam_candidate_count":report["mixed_basis_seam_candidate_count"],
        "c3_training_authorized":False,
    },sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
