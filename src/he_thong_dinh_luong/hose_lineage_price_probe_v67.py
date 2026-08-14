"""V67 official-HOSE lineage + local price-basis probe.

Research/data-readiness only. No order placement, no model training and no
market-store mutation.

The probe combines two evidence lanes:

1) an official HOSE listing-list fetch to identify which local symbols are
   currently listed on HOSE and the official effective listing date;
2) an offline discontinuity audit on the 11-year local OHLCV store to detect
   corporate-action-like price resets that would make raw prices unsafe for C3
   momentum/high-52-week features.

The official listing-list date is NOT automatically treated as first trading
date. Transfer cases can have a gap between listing effectiveness and first
HOSE trading session, so those cases remain provisional until first-trade
evidence is confirmed.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import closing
from dataclasses import dataclass
from datetime import date
import hashlib
import http.cookiejar
import json
from pathlib import Path
import sqlite3
from typing import Mapping, Sequence
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

SCHEMA_VERSION = "hose_lineage_price_probe_v67"
HSX_SYMBOL_LIST_URL = "https://www.hsx.vn/Modules/Listed/Web/SymbolList"
HSX_LANGUAGE_URL = "https://www.hsx.vn/Common/ChangeLanguage/9e054dac-a75b-423f-95f6-54d3f73d4e53"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
PRICE_GAP_THRESHOLDS = (0.18, 0.25, 0.40)


@dataclass(frozen=True)
class LocalSymbol:
    symbol: str
    first_day: date
    last_day: date
    rows: int


def _parse_iso(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _parse_hsx_date(value: object) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    for sep in ("/", "-", "."):
        parts = text.split(sep)
        if len(parts) == 3:
            try:
                a, b, c = (int(x) for x in parts)
            except ValueError:
                continue
            if c >= 1900:
                try:
                    return date(c, b, a)
                except ValueError:
                    return None
    return _parse_iso(text)


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _schema(db: sqlite3.Connection) -> dict[str, list[str]]:
    tables = [
        str(row[0])
        for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        if not str(row[0]).startswith("sqlite_")
    ]
    return {
        table: [str(row[1]) for row in db.execute(f"PRAGMA table_info({_quote(table)})")]
        for table in tables
    }


def load_local_store(store: Path) -> tuple[list[LocalSymbol], tuple[date, ...], dict[str, list[tuple[date, float, float]]]]:
    with closing(sqlite3.connect(store)) as db:
        schema = _schema(db)
        if "bars" not in schema:
            raise ValueError("V67_BARS_TABLE_MISSING")
        cols = {str(c).strip().lower(): c for c in schema["bars"]}
        required = {"symbol", "day", "open", "close"}
        if not required.issubset(cols):
            raise ValueError("V67_BARS_REQUIRED_COLUMNS_MISSING")
        asset_col = cols.get("asset_type")
        symbol_col = cols["symbol"]
        day_col = cols["day"]
        open_col = cols["open"]
        close_col = cols["close"]

        index_days: list[date] = []
        by_symbol: dict[str, list[tuple[date, float, float]]] = defaultdict(list)

        select = [symbol_col, day_col, open_col, close_col]
        if asset_col:
            select.append(asset_col)
        sql = f"SELECT {','.join(_quote(x) for x in select)} FROM bars ORDER BY {_quote(day_col)},{_quote(symbol_col)}"
        for row in db.execute(sql):
            symbol = str(row[0] or "").strip().upper()
            day = _parse_iso(row[1])
            if not symbol or day is None:
                continue
            try:
                open_price = float(row[2])
                close_price = float(row[3])
            except (TypeError, ValueError):
                continue
            asset = str(row[4] or "").strip().upper() if asset_col else ""
            is_index = asset == "INDEX" or symbol in {"VNINDEX", "VN-INDEX", "VN_INDEX"}
            if is_index:
                if symbol in {"VNINDEX", "VN-INDEX", "VN_INDEX"}:
                    index_days.append(day)
                continue
            if open_price > 0 and close_price > 0:
                by_symbol[symbol].append((day, open_price, close_price))

    calendar = tuple(sorted(set(index_days)))
    if not calendar:
        raise ValueError("V67_VNINDEX_CALENDAR_MISSING")
    local_symbols = [
        LocalSymbol(symbol, rows[0][0], rows[-1][0], len(rows))
        for symbol, rows in sorted(by_symbol.items())
        if rows
    ]
    return local_symbols, calendar, by_symbol


def fetch_hsx_current_listing(*, timeout: float = 30.0) -> dict[str, object]:
    params = {
        "pageFieldName1": "Code",
        "pageFieldValue1": "",
        "pageFieldValue2": "",
        "pageFieldOperator2": "",
        "pageFieldOperator3": "",
        "pageFieldValue4": "",
        "pageFieldOperator4": "",
        "pageFieldOperator1": "eq",
        "pageFieldName2": "Sectors",
        "pageFieldName3": "Sector",
        "pageFieldValue3": "00000000-0000-0000-0000-000000000000",
        "pageFieldName4": "StartWith",
        "pageCriteriaLength": "4",
        "_search": "false",
        "rows": "2000",
        "page": "1",
        "sidx": "id",
        "sord": "desc",
    }
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.hsx.vn/vi/quan-ly-niem-yet/co-phieu",
    }
    jar = http.cookiejar.CookieJar()
    opener = build_opener(HTTPCookieProcessor(jar))

    language_error = None
    try:
        opener.open(Request(HSX_LANGUAGE_URL, headers={"User-Agent": USER_AGENT}), timeout=timeout).close()
    except Exception as exc:
        language_error = f"{type(exc).__name__}: {exc}"

    url = HSX_SYMBOL_LIST_URL + "?" + urlencode(params)
    request = Request(url, headers=headers)
    with opener.open(request, timeout=timeout) as response:
        body = response.read()
        status = int(getattr(response, "status", 200) or 200)
        content_type = str(response.headers.get("Content-Type", ""))
    payload = json.loads(body.decode("utf-8-sig"))
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("V67_HSX_SYMBOL_LIST_ROWS_MISSING")

    parsed: list[dict[str, object]] = []
    for item in rows:
        cell = item.get("cell") if isinstance(item, dict) else None
        if not isinstance(cell, list) or len(cell) < 8:
            continue
        symbol = str(cell[1] or "").strip().upper()
        if not symbol:
            continue
        listing_day = _parse_hsx_date(cell[7])
        parsed.append(
            {
                "id": cell[0],
                "symbol": symbol,
                "isin": str(cell[2] or "").strip(),
                "figi": str(cell[3] or "").strip(),
                "name": str(cell[4] or "").strip(),
                "listing_effective_date": listing_day.isoformat() if listing_day else None,
                "listing_effective_date_raw": str(cell[7] or "").strip(),
            }
        )
    parsed.sort(key=lambda row: str(row["symbol"]))
    return {
        "source": "HOSE_OFFICIAL_LEGACY_SYMBOL_LIST",
        "url": HSX_SYMBOL_LIST_URL,
        "http_status": status,
        "content_type": content_type,
        "response_sha256": hashlib.sha256(body).hexdigest(),
        "language_change_error": language_error,
        "raw_row_count": len(rows),
        "parsed_row_count": len(parsed),
        "rows": parsed,
    }


def _calendar_positions(calendar: Sequence[date]) -> dict[date, int]:
    return {day: idx for idx, day in enumerate(calendar)}


def infer_transfer_candidate(
    *,
    listing_effective_day: date,
    rows: Sequence[tuple[date, float, float]],
    calendar_positions: Mapping[date, int],
) -> dict[str, object]:
    if not rows:
        return {"candidate_first_hose_trade_day": None, "classification": "NO_LOCAL_ROWS"}
    first_day = rows[0][0]
    if first_day >= listing_effective_day:
        return {
            "candidate_first_hose_trade_day": first_day.isoformat(),
            "classification": "LOCAL_HISTORY_STARTS_ON_OR_AFTER_HOSE_EFFECTIVE_DATE",
            "needs_official_first_trade_confirmation": False,
        }

    after = [(idx, row) for idx, row in enumerate(rows) if row[0] >= listing_effective_day]
    for idx, row in after:
        if idx == 0:
            continue
        prev_day = rows[idx - 1][0]
        day = row[0]
        prev_pos = calendar_positions.get(prev_day)
        pos = calendar_positions.get(day)
        if prev_pos is None or pos is None:
            continue
        missing_market_sessions = pos - prev_pos - 1
        if missing_market_sessions >= 2:
            return {
                "candidate_first_hose_trade_day": day.isoformat(),
                "previous_local_trade_day": prev_day.isoformat(),
                "missing_vnindex_sessions_before_candidate": missing_market_sessions,
                "classification": "TRANSFER_GAP_HEURISTIC",
                "needs_official_first_trade_confirmation": True,
            }
    return {
        "candidate_first_hose_trade_day": None,
        "classification": "PRE_HOSE_LOCAL_HISTORY_WITHOUT_CLEAR_TRANSFER_GAP",
        "needs_official_first_trade_confirmation": True,
    }


def audit_price_gaps(
    *,
    by_symbol: Mapping[str, Sequence[tuple[date, float, float]]],
    calendar: Sequence[date],
) -> dict[str, object]:
    positions = _calendar_positions(calendar)
    events: list[dict[str, object]] = []
    counts = {str(t): 0 for t in PRICE_GAP_THRESHOLDS}
    symbol_counts: dict[str, int] = defaultdict(int)

    for symbol, rows in sorted(by_symbol.items()):
        for prev, current in zip(rows, rows[1:]):
            prev_day, _, prev_close = prev
            day, open_price, _ = current
            prev_pos = positions.get(prev_day)
            pos = positions.get(day)
            if prev_pos is None or pos is None or pos - prev_pos != 1 or prev_close <= 0:
                continue
            gap = open_price / prev_close - 1.0
            absolute = abs(gap)
            triggered = [threshold for threshold in PRICE_GAP_THRESHOLDS if absolute >= threshold]
            if not triggered:
                continue
            for threshold in triggered:
                counts[str(threshold)] += 1
            symbol_counts[symbol] += 1
            events.append(
                {
                    "symbol": symbol,
                    "prev_day": prev_day.isoformat(),
                    "day": day.isoformat(),
                    "prev_close": prev_close,
                    "open": open_price,
                    "open_gap": gap,
                    "abs_open_gap": absolute,
                    "strongest_threshold": max(triggered),
                }
            )
    events.sort(key=lambda row: (-float(row["abs_open_gap"]), str(row["symbol"]), str(row["day"])))
    top_symbols = sorted(symbol_counts.items(), key=lambda item: (-item[1], item[0]))
    return {
        "method": "CONSECUTIVE_VNINDEX_SESSION_OPEN_VS_PREVIOUS_CLOSE",
        "thresholds": list(PRICE_GAP_THRESHOLDS),
        "event_count_by_threshold": counts,
        "symbols_with_ge18pct_event_count": len(symbol_counts),
        "top_symbols_by_ge18pct_event_count": [
            {"symbol": symbol, "event_count": count} for symbol, count in top_symbols[:30]
        ],
        "events": events[:500],
        "interpretation_guardrail": (
            "Large consecutive-session gaps are evidence of price resets/special sessions, "
            "not a complete corporate-action adjustment factor. They can reject an assumption "
            "of fully adjusted data but cannot by themselves construct an adjusted series."
        ),
    }


def build_report(store: Path, *, allow_network: bool = True, timeout: float = 30.0) -> dict[str, object]:
    local_symbols, calendar, by_symbol = load_local_store(store)
    hsx: dict[str, object]
    network_error = None
    if allow_network:
        try:
            hsx = fetch_hsx_current_listing(timeout=timeout)
        except Exception as exc:
            network_error = f"{type(exc).__name__}: {exc}"
            hsx = {"rows": [], "parsed_row_count": 0}
    else:
        hsx = {"rows": [], "parsed_row_count": 0}
        network_error = "NETWORK_DISABLED_BY_ARGUMENT"

    hsx_by_symbol = {
        str(row["symbol"]): row
        for row in hsx.get("rows", [])
        if isinstance(row, dict) and row.get("symbol")
    }
    positions = _calendar_positions(calendar)

    symbol_rows: list[dict[str, object]] = []
    unmatched: list[str] = []
    pre_hose_history: list[str] = []
    needs_first_trade_confirmation: list[str] = []

    for item in local_symbols:
        official = hsx_by_symbol.get(item.symbol)
        row: dict[str, object] = {
            "symbol": item.symbol,
            "local_first_day": item.first_day.isoformat(),
            "local_last_day": item.last_day.isoformat(),
            "local_row_count": item.rows,
            "in_current_hsx_symbol_list": official is not None,
            "official_listing_effective_date": None,
            "has_local_history_before_hose_effective_date": None,
            "candidate_first_hose_trade_day": None,
            "lineage_classification": "NOT_IN_CURRENT_HSX_LIST_NEEDS_HISTORY",
            "pit_accepted_for_research": False,
        }
        if official is None:
            unmatched.append(item.symbol)
            symbol_rows.append(row)
            continue

        listing_day = _parse_iso(official.get("listing_effective_date"))
        row["official_listing_effective_date"] = official.get("listing_effective_date")
        if listing_day is None:
            row["lineage_classification"] = "CURRENT_HSX_ROW_WITHOUT_PARSEABLE_LISTING_DATE"
            symbol_rows.append(row)
            continue

        has_pre = item.first_day < listing_day
        row["has_local_history_before_hose_effective_date"] = has_pre
        if has_pre:
            pre_hose_history.append(item.symbol)
        inferred = infer_transfer_candidate(
            listing_effective_day=listing_day,
            rows=by_symbol[item.symbol],
            calendar_positions=positions,
        )
        row["candidate_first_hose_trade_day"] = inferred.get("candidate_first_hose_trade_day")
        row["lineage_classification"] = inferred.get("classification")
        row["needs_official_first_trade_confirmation"] = bool(
            inferred.get("needs_official_first_trade_confirmation", False)
        )
        if row["needs_official_first_trade_confirmation"]:
            needs_first_trade_confirmation.append(item.symbol)
        row["pit_accepted_for_research"] = bool(
            official is not None
            and listing_day is not None
            and not row["needs_official_first_trade_confirmation"]
        )
        symbol_rows.append(row)

    gap_audit = audit_price_gaps(by_symbol=by_symbol, calendar=calendar)
    report = {
        "schema_version": SCHEMA_VERSION,
        "research_only": True,
        "model_training_run": False,
        "store_mutated": False,
        "network_allowed": allow_network,
        "network_error": network_error,
        "local_store": {
            "stock_symbol_count": len(local_symbols),
            "first_market_day": calendar[0].isoformat(),
            "last_market_day": calendar[-1].isoformat(),
            "vnindex_session_count": len(calendar),
        },
        "hsx_official": {k: v for k, v in hsx.items() if k != "rows"},
        "lineage_summary": {
            "local_stock_symbol_count": len(local_symbols),
            "matched_current_hsx_count": sum(1 for row in symbol_rows if row["in_current_hsx_symbol_list"]),
            "unmatched_current_hsx_count": len(unmatched),
            "unmatched_current_hsx_symbols": unmatched,
            "symbols_with_local_history_before_hose_effective_date_count": len(pre_hose_history),
            "symbols_with_local_history_before_hose_effective_date": pre_hose_history,
            "symbols_needing_official_first_trade_confirmation_count": len(needs_first_trade_confirmation),
            "symbols_needing_official_first_trade_confirmation": needs_first_trade_confirmation,
            "all_symbols_pit_accepted": bool(symbol_rows) and all(bool(row["pit_accepted_for_research"]) for row in symbol_rows),
        },
        "symbol_lineage_rows": symbol_rows,
        "price_gap_audit": gap_audit,
        "research_gate": {
            "hose_pit_gate_closed": bool(symbol_rows) and all(bool(row["pit_accepted_for_research"]) for row in symbol_rows),
            "price_basis_gate_closed": False,
            "price_basis_gate_rule": (
                "CHUA_XAC_NHAN remains blocked until official source semantics or corporate-action "
                "cross-check establishes adjusted/raw treatment. Gap audit is diagnostic evidence only."
            ),
            "c3_training_authorized": False,
        },
    }
    return report


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    seen = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(str(key))
    import csv
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--no-network", action="store_true")
    args = parser.parse_args(argv)

    report = build_report(args.store, allow_network=not args.no_network, timeout=args.timeout)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "v67_hose_lineage_price_probe.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_csv(args.output_dir / "v67_symbol_lineage_probe.csv", report["symbol_lineage_rows"])
    _write_csv(args.output_dir / "v67_price_gap_events.csv", report["price_gap_audit"]["events"])

    print(json.dumps(
        {
            "schema_version": SCHEMA_VERSION,
            "network_error": report["network_error"],
            "matched_current_hsx_count": report["lineage_summary"]["matched_current_hsx_count"],
            "unmatched_current_hsx_count": report["lineage_summary"]["unmatched_current_hsx_count"],
            "needs_first_trade_confirmation_count": report["lineage_summary"]["symbols_needing_official_first_trade_confirmation_count"],
            "ge18pct_gap_event_count": report["price_gap_audit"]["event_count_by_threshold"]["0.18"],
            "hose_pit_gate_closed": report["research_gate"]["hose_pit_gate_closed"],
            "price_basis_gate_closed": report["research_gate"]["price_basis_gate_closed"],
            "c3_training_authorized": report["research_gate"]["c3_training_authorized"],
        },
        ensure_ascii=False,
        sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
