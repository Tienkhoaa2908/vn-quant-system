"""One-shot external reference-data resolution for the frozen V39 surface.

This module replaces repeated local discovery. It archives public/official
source pages, uses Vnstock only as a candidate locator, builds research-only
sector/corporate-action diagnostics, and reports whether the strict V39 gate can
be closed. It never invents point-in-time coverage or live-capital approval.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
from io import StringIO
import json
import math
from pathlib import Path
import re
import sqlite3
import time
from typing import Any, Iterable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import Request, urlopen

SCHEMA_VERSION = "vn_quant_v39_one_shot_external_resolution_v1"
REPORT_FILE = "one_shot_external_resolution_v39.json"
SECTOR_FILE = "research_sector_static_v39.csv"
EVENT_FILE = "research_corporate_action_candidates_v39.csv"
PRICE_FILE = "research_price_basis_diagnostic_v39.json"
SOURCE_MANIFEST_FILE = "external_source_manifest_v39.json"
NETWORK_LOG_FILE = "external_network_log_v39.csv"

OFFICIAL_DOCS = {
    "dnse_ohlc_docs": "https://hdsd.dnse.com.vn/san-pham-dich-vu/api-giao-dich/iii.-market-data/3.-api-lay-du-lieu-gia-chung-khoan",
    "dnse_instruments_docs": "https://hdsd.dnse.com.vn/san-pham-dich-vu/api-giao-dich/iii.-market-data/2.-api-lay-thong-tin-chung-khoan",
    "vsdc_rights_rule": "https://vsd.vn/vi/ad/170306",
}
ALLOWED_OFFICIAL_HOSTS = ("vsd.vn", "www.vsd.vn", "hnx.vn", "www.hnx.vn", "hsx.vn", "www.hsx.vn", "dnse.com.vn", "hdsd.dnse.com.vn")
EVENT_WORDS = {
    "cash": "CASH_DIVIDEND",
    "tiền": "CASH_DIVIDEND",
    "stock dividend": "STOCK_DIVIDEND",
    "cổ phiếu": "STOCK_DIVIDEND",
    "split": "SPLIT",
    "chia tách": "SPLIT",
    "thưởng": "STOCK_DIVIDEND",
}
DATE_RE = re.compile(r"\b(20\d{2})[-/.](0?[1-9]|1[0-2])[-/.](0?[1-9]|[12]\d|3[01])\b|\b(0?[1-9]|[12]\d|3[01])[-/.](0?[1-9]|1[0-2])[-/.](20\d{2})\b")


def _sha_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _sha_file(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]], fields: Sequence[str]) -> None:
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    Path(path).write_text(output.getvalue(), encoding="utf-8-sig", newline="")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _normalize_date(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = text[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return ""


def _first_value(row: Mapping[str, object], tokens: Sequence[str]) -> object:
    for key, value in row.items():
        normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
        if any(token in normalized for token in tokens):
            if str(value or "").strip():
                return value
    return ""


def _records(value: object) -> list[dict[str, object]]:
    if value is None:
        return []
    if isinstance(value, list):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    if isinstance(value, Mapping):
        return [dict(value)]
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            raw = to_dict(orient="records")
        except TypeError:
            raw = to_dict()
        if isinstance(raw, list):
            return [dict(row) for row in raw if isinstance(row, Mapping)]
    return []


class _TextLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._href = ""
        self._link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            self._href = dict(attrs).get("href") or ""
            self._link_text = []

    def handle_data(self, data: str) -> None:
        cleaned = " ".join(data.split())
        if cleaned:
            self.text.append(cleaned)
            if self._href:
                self._link_text.append(cleaned)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href:
            self.links.append((self._href, " ".join(self._link_text)))
            self._href = ""
            self._link_text = []


def html_text_and_links(payload: bytes) -> tuple[str, list[tuple[str, str]]]:
    parser = _TextLinkParser()
    text = payload.decode("utf-8", errors="replace")
    parser.feed(text)
    return " ".join(parser.text), parser.links


def extract_official_search_links(payload: bytes) -> list[str]:
    """Extract only official-domain result links from a DuckDuckGo HTML page."""
    _, links = html_text_and_links(payload)
    result: list[str] = []
    for href, _ in links:
        candidate = unescape(href)
        parsed = urlparse(candidate)
        if parsed.netloc.endswith("duckduckgo.com"):
            candidate = unquote(parse_qs(parsed.query).get("uddg", [""])[0])
            parsed = urlparse(candidate)
        host = parsed.netloc.lower()
        if candidate.startswith("https://") and any(host == allowed or host.endswith("." + allowed) for allowed in ALLOWED_OFFICIAL_HOSTS):
            if candidate not in result:
                result.append(candidate)
    return result


@dataclass(frozen=True)
class FetchRecord:
    label: str
    url: str
    status: str
    http_status: int
    cache_file: str
    sha256: str
    size_bytes: int
    error: str


class CachedFetcher:
    def __init__(self, cache_dir: Path, *, delay_seconds: float = 0.35, timeout_seconds: float = 25.0) -> None:
        self.cache_dir = Path(cache_dir).resolve()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.delay_seconds = max(0.0, float(delay_seconds))
        self.timeout_seconds = max(1.0, float(timeout_seconds))
        self.records: list[FetchRecord] = []
        self._last_request = 0.0

    def fetch(self, label: str, url: str) -> bytes | None:
        key = sha256(url.encode("utf-8")).hexdigest()
        extension = ".html" if "html" in url or not Path(urlparse(url).path).suffix else Path(urlparse(url).path).suffix[:12]
        target = self.cache_dir / f"{label[:40]}_{key[:16]}{extension}"
        if target.is_file():
            payload = target.read_bytes()
            self.records.append(FetchRecord(label, url, "CACHE_HIT", 200, target.name, _sha_bytes(payload), len(payload), ""))
            return payload
        wait = self.delay_seconds - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        request = Request(url, headers={"User-Agent": "Mozilla/5.0 vn-quant-system-v39 research audit"})
        try:
            self._last_request = time.monotonic()
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = response.read()
                status = int(getattr(response, "status", 200) or 200)
            target.write_bytes(payload)
            self.records.append(FetchRecord(label, url, "SUCCESS", status, target.name, _sha_bytes(payload), len(payload), ""))
            return payload
        except HTTPError as exc:
            self.records.append(FetchRecord(label, url, "HTTP_ERROR", int(exc.code), "", "", 0, str(exc)))
        except (URLError, TimeoutError, OSError) as exc:
            self.records.append(FetchRecord(label, url, "NETWORK_ERROR", 0, "", "", 0, type(exc).__name__))
        return None


def _selected_symbols(workspace: Path) -> list[str]:
    path = workspace / "selected_symbols_v39.txt"
    if not path.is_file():
        raise FileNotFoundError(f"V39_SELECTED_SYMBOLS_MISSING:{path}")
    symbols = sorted({line.strip().upper() for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()})
    if not symbols:
        raise ValueError("V39_SELECTED_SYMBOLS_EMPTY")
    return symbols


def _required_windows(workspace: Path) -> list[dict[str, str]]:
    path = workspace / "corporate_action_window_evidence_v39.csv"
    if not path.is_file():
        raise FileNotFoundError(f"V39_WINDOWS_MISSING:{path}")
    return _read_csv(path)


def _event_inside_any_window(symbol: str, event_day: str, windows: Sequence[Mapping[str, str]]) -> bool:
    if not event_day:
        return False
    day = date.fromisoformat(event_day)
    for row in windows:
        if str(row.get("symbol") or "").strip().upper() != symbol:
            continue
        try:
            start = date.fromisoformat(str(row.get("holding_start") or ""))
            end = date.fromisoformat(str(row.get("holding_end") or ""))
        except ValueError:
            continue
        if start < day <= end:
            return True
    return False


def _classify_event(row: Mapping[str, object]) -> str:
    text = " ".join(str(value or "") for value in row.values()).lower()
    for token, event_type in EVENT_WORDS.items():
        if token in text:
            return event_type
    return "OTHER_OR_UNKNOWN"


def load_vnstock_candidates(symbols: Sequence[str], windows: Sequence[Mapping[str, str]], *, use_vnstock: bool) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    if not use_vnstock:
        return [], [], {"enabled": False, "status": "SKIPPED"}
    try:
        from vnstock import Reference  # type: ignore
    except Exception as exc:
        return [], [], {"enabled": True, "status": "IMPORT_FAILED", "error": type(exc).__name__}

    sectors: list[dict[str, object]] = []
    events: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    try:
        reference = Reference()
        equity = getattr(reference, "equity", None)
        industry_data = equity.list_by_industry() if equity is not None and callable(getattr(equity, "list_by_industry", None)) else None
        for row in _records(industry_data):
            symbol = str(_first_value(row, ("symbol", "ticker", "stockcode", "mack")) or "").strip().upper()
            if symbol not in symbols:
                continue
            sector = str(_first_value(row, ("industryname", "industry", "sector", "nganh")) or "").strip()
            if sector:
                sectors.append({
                    "symbol": symbol,
                    "sector": sector,
                    "as_of": datetime.now(timezone.utc).date().isoformat(),
                    "source": "vnstock_4_0_4_candidate_locator",
                    "point_in_time_verified": False,
                    "authoritative": False,
                })
    except Exception as exc:
        errors.append({"scope": "industry", "error": type(exc).__name__})

    for symbol in symbols:
        try:
            company = Reference().company(symbol=symbol)
            getter = getattr(company, "events", None)
            raw = getter() if callable(getter) else None
            for index, row in enumerate(_records(raw), start=1):
                event_day = _normalize_date(_first_value(row, ("exdate", "recorddate", "eventdate", "date", "ngay")))
                event_type = _classify_event(row)
                events.append({
                    "candidate_id": f"vnstock-{symbol}-{index}",
                    "symbol": symbol,
                    "event_date": event_day,
                    "event_type": event_type,
                    "inside_required_window": _event_inside_any_window(symbol, event_day, windows),
                    "raw_json": json.dumps(row, ensure_ascii=False, sort_keys=True, default=str),
                    "candidate_source": "vnstock_4_0_4",
                    "official_source_url": "",
                    "official_source_sha256": "",
                    "strict_verified": False,
                })
        except Exception as exc:
            errors.append({"scope": symbol, "error": type(exc).__name__})
    return sectors, events, {"enabled": True, "status": "COMPLETED_WITH_ERRORS" if errors else "SUCCESS", "errors": errors}


def _search_official_pages(fetcher: CachedFetcher, symbol: str) -> list[tuple[str, bytes]]:
    query = quote_plus(f'site:vsd.vn OR site:hnx.vn "{symbol}" cổ tức ngày GDKHQ')
    search_url = f"https://html.duckduckgo.com/html/?q={query}"
    payload = fetcher.fetch(f"search_{symbol}", search_url)
    if payload is None:
        return []
    result: list[tuple[str, bytes]] = []
    for index, url in enumerate(extract_official_search_links(payload)[:3], start=1):
        official = fetcher.fetch(f"official_{symbol}_{index}", url)
        if official is not None:
            result.append((url, official))
    return result


def enrich_events_with_official_pages(events: list[dict[str, object]], symbols: Sequence[str], fetcher: CachedFetcher) -> dict[str, object]:
    by_symbol: dict[str, list[dict[str, object]]] = {}
    for row in events:
        by_symbol.setdefault(str(row.get("symbol") or ""), []).append(row)
    official_hits = 0
    searched = 0
    for symbol in symbols:
        relevant = [row for row in by_symbol.get(symbol, []) if row.get("inside_required_window") is True]
        if not relevant:
            continue
        searched += 1
        pages = _search_official_pages(fetcher, symbol)
        for url, payload in pages:
            text, _ = html_text_and_links(payload)
            normalized = text.lower()
            if symbol.lower() not in normalized:
                continue
            page_dates = {_normalize_date(match.group(0)) for match in DATE_RE.finditer(text)}
            page_dates.discard("")
            for row in relevant:
                event_day = str(row.get("event_date") or "")
                if event_day and event_day in page_dates:
                    row["official_source_url"] = url
                    row["official_source_sha256"] = _sha_bytes(payload)
                    row["official_page_date_match"] = True
                    official_hits += 1
                    break
    return {"symbols_searched": searched, "official_event_date_matches": official_hits}


def _previous_trading_day(db: sqlite3.Connection, symbol: str, event_day: str) -> tuple[str, float] | None:
    row = db.execute(
        "SELECT day, close FROM bars WHERE asset_type='STOCK' AND symbol=? AND day<? AND close>0 ORDER BY day DESC LIMIT 1",
        (symbol, event_day),
    ).fetchone()
    return (str(row[0]), float(row[1])) if row else None


def _next_trading_day(db: sqlite3.Connection, symbol: str, event_day: str) -> tuple[str, float] | None:
    row = db.execute(
        "SELECT day, open FROM bars WHERE asset_type='STOCK' AND symbol=? AND day>=? AND open>0 ORDER BY day ASC LIMIT 1",
        (symbol, event_day),
    ).fetchone()
    return (str(row[0]), float(row[1])) if row else None


def empirical_price_basis(sqlite_store: Path, events: Sequence[Mapping[str, object]]) -> dict[str, object]:
    db = sqlite3.connect(Path(sqlite_store))
    try:
        basis_rows = db.execute("SELECT price_basis, COUNT(*) FROM bars GROUP BY price_basis ORDER BY price_basis").fetchall()
        observations: list[dict[str, object]] = []
        for event in events:
            if event.get("inside_required_window") is not True:
                continue
            symbol = str(event.get("symbol") or "")
            event_day = str(event.get("event_date") or "")
            if not symbol or not event_day:
                continue
            before = _previous_trading_day(db, symbol, event_day)
            after = _next_trading_day(db, symbol, event_day)
            if before and after:
                observations.append({
                    "symbol": symbol,
                    "event_date": event_day,
                    "event_type": event.get("event_type"),
                    "previous_day": before[0],
                    "previous_close": before[1],
                    "next_day": after[0],
                    "next_open": after[1],
                    "open_to_previous_close_ratio": after[1] / before[1],
                    "official_date_match": event.get("official_page_date_match") is True,
                })
        official_count = sum(row["official_date_match"] is True for row in observations)
        return {
            "sqlite_price_basis_values": [{"price_basis": row[0], "row_count": int(row[1])} for row in basis_rows],
            "event_observation_count": len(observations),
            "officially_date_matched_observation_count": official_count,
            "observations": observations,
            "strict_price_basis_confirmed": False,
            "reason": "EMPIRICAL_JUMPS_CANNOT_BY_THEMSELVES_PROVE_VENDOR_ADJUSTMENT_SEMANTICS",
        }
    finally:
        db.close()


def _workspace_ops(workspace: Path) -> dict[str, object]:
    path = workspace / "workstation_controls_v39.json"
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    return dict(value) if isinstance(value, Mapping) else {}


def resolve_external_references(*, workspace_dir: Path, sqlite_store: Path, output_dir: Path, cache_dir: Path, use_vnstock: bool, max_official_symbols: int = 78) -> dict[str, object]:
    workspace = Path(workspace_dir).resolve()
    output = Path(output_dir).resolve()
    cache = Path(cache_dir).resolve()
    if output.exists():
        raise FileExistsError(f"V39_EXTERNAL_OUTPUT_EXISTS:{output}")
    output.mkdir(parents=True)
    source_dir = output / "source_documents"
    source_dir.mkdir()
    fetcher = CachedFetcher(source_dir)

    symbols = _selected_symbols(workspace)
    windows = _required_windows(workspace)
    for label, url in OFFICIAL_DOCS.items():
        fetcher.fetch(label, url)

    sectors, events, vnstock_audit = load_vnstock_candidates(symbols, windows, use_vnstock=use_vnstock)
    relevant_symbols = sorted({str(row.get("symbol") or "") for row in events if row.get("inside_required_window") is True})
    official_audit = enrich_events_with_official_pages(events, relevant_symbols[:max_official_symbols], fetcher)
    price_diagnostic = empirical_price_basis(sqlite_store, events)

    _write_csv(output / SECTOR_FILE, sectors, ("symbol", "sector", "as_of", "source", "point_in_time_verified", "authoritative"))
    _write_csv(
        output / EVENT_FILE,
        events,
        ("candidate_id", "symbol", "event_date", "event_type", "inside_required_window", "candidate_source", "official_source_url", "official_source_sha256", "official_page_date_match", "strict_verified", "raw_json"),
    )
    _write_json(output / PRICE_FILE, price_diagnostic)

    source_manifest = {
        "schema_version": "v39_external_source_manifest_v1",
        "files": [
            {
                "path": path.relative_to(output).as_posix(),
                "sha256": _sha_file(path),
                "size_bytes": path.stat().st_size,
            }
            for path in sorted(source_dir.glob("*")) if path.is_file()
        ],
    }
    _write_json(output / SOURCE_MANIFEST_FILE, source_manifest)
    _write_csv(
        output / NETWORK_LOG_FILE,
        [record.__dict__ for record in fetcher.records],
        ("label", "url", "status", "http_status", "cache_file", "sha256", "size_bytes", "error"),
    )

    ops = _workspace_ops(workspace)
    strict_blockers = []
    if not sectors or any(row.get("point_in_time_verified") is not True for row in sectors) or len({str(row.get("symbol")) for row in sectors}) < len(symbols):
        strict_blockers.append("POINT_IN_TIME_SECTOR_HISTORY_NOT_ESTABLISHED")
    strict_events = [row for row in events if row.get("strict_verified") is True]
    if not strict_events or official_audit["official_event_date_matches"] < len([row for row in events if row.get("inside_required_window") is True]):
        strict_blockers.append("COMPLETE_OFFICIAL_CORPORATE_ACTION_INVENTORY_NOT_ESTABLISHED")
    if price_diagnostic.get("strict_price_basis_confirmed") is not True:
        strict_blockers.append("DNSE_PRICE_BASIS_CONTRACT_NOT_CONFIRMED")
    if ops.get("account_sync_verified") is not True:
        strict_blockers.append("ACCOUNT_SYNC_NOT_VERIFIED")
    if ops.get("position_reconciliation_verified") is not True:
        strict_blockers.append("POSITION_RECONCILIATION_PENDING_EXACT_LEDGER")

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "STRICT_READY" if not strict_blockers else "STRICT_BLOCKED_EXTERNAL_DATA",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "selected_symbol_count": len(symbols),
        "required_window_count": len(windows),
        "research_sector_symbol_count": len({str(row.get("symbol")) for row in sectors}),
        "research_event_candidate_count": len(events),
        "research_relevant_event_candidate_count": sum(row.get("inside_required_window") is True for row in events),
        "official_event_date_match_count": official_audit["official_event_date_matches"],
        "official_source_download_count": len(source_manifest["files"]),
        "vnstock_audit": vnstock_audit,
        "official_audit": official_audit,
        "operations": {
            "account_sync_verified": ops.get("account_sync_verified") is True,
            "position_reconciliation_verified": ops.get("position_reconciliation_verified") is True,
        },
        "strict_blockers": strict_blockers,
        "strict_workspace_mutated": False,
        "vnstock_is_candidate_locator_only": True,
        "static_sector_is_not_point_in_time": True,
        "empirical_price_diagnostic_is_not_vendor_contract": True,
        "authoritative_approval_invented": False,
        "exact_cash_ledger_allowed": not strict_blockers,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
        "final_next_action": (
            "RUN_EXISTING_V39_TO_V36_EXACT_PIPELINE"
            if not strict_blockers
            else "ACQUIRE_LICENSED_POINT_IN_TIME_REFERENCE_DATA_OR_REVISE_STRICT_RESEARCH_CONTRACT"
        ),
    }
    _write_json(output / REPORT_FILE, report)
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="One-shot external resolution for V39")
    parser.add_argument("--workspace-dir", required=True, type=Path)
    parser.add_argument("--sqlite-store", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--cache-dir", required=True, type=Path)
    parser.add_argument("--use-vnstock", action="store_true")
    parser.add_argument("--max-official-symbols", type=int, default=78)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = resolve_external_references(
        workspace_dir=args.workspace_dir,
        sqlite_store=args.sqlite_store,
        output_dir=args.output_dir,
        cache_dir=args.cache_dir,
        use_vnstock=args.use_vnstock,
        max_official_symbols=args.max_official_symbols,
    )
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
