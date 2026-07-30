"""Cap nhat EOD KBS/VCI va chay forward prediction sau phien."""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from hashlib import sha256
from io import StringIO
import json
from math import isfinite
from pathlib import Path, PurePosixPath
import time
from types import SimpleNamespace
from typing import Callable, Iterable, Mapping, Protocol, Sequence
from zoneinfo import ZoneInfo
from zipfile import ZIP_DEFLATED, ZipFile

SCHEMA_VERSION = "eod_daily_quant_v1"
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
VNSTOCK_VERSION = "4.0.4"
PUB_FILES = (
    "du_lieu_gia_mo_dong_khoi_luong.csv",
    "bao_cao_do_phu_hop_dong_rut_gon.json",
    "bao_cao_ma_bi_loai.json",
    "manifest.json",
    "sha256.txt",
)
PUB_FIELDS = (
    "ma", "ngay", "gia_mo_cua", "gia_dong_cua", "khoi_luong",
    "nguon", "phien_ban", "co_so_gia", "raw_sha256",
)
FEATURE_PREFIX = (
    "ngay", "ma", "hop_le", "ly_do", "eligible", "ly_do_eligibility",
    "gtgd_tb_20_eligibility", "T1", "open_t1_hop_le",
)
PREDICTION_REQUIRED = {
    "manifest.json", "cau_hinh.json", "feature_raw.csv", "nhan.csv",
    "chi_so_mo_hinh.json",
}


@dataclass(frozen=True)
class EodRow:
    symbol: str
    day: date
    open: float
    close: float
    volume: int
    source: str
    version: str
    high: float | None = None
    low: float | None = None

    def __post_init__(self) -> None:
        if not self.symbol or self.symbol != self.symbol.upper():
            raise ValueError("EOD_SYMBOL_INVALID")
        for name in ("open", "close"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"EOD_{name.upper()}_INVALID")
            if not isfinite(float(value)) or float(value) <= 0:
                raise ValueError(f"EOD_{name.upper()}_NON_POSITIVE")
        if isinstance(self.volume, bool) or not isinstance(self.volume, int) or self.volume < 0:
            raise ValueError("EOD_VOLUME_INVALID")
        if not self.source or not self.version:
            raise ValueError("EOD_PROVENANCE_MISSING")

    def payload(self) -> dict[str, object]:
        return {
            "symbol": self.symbol, "day": self.day.isoformat(),
            "open": self.open, "high": self.high, "low": self.low,
            "close": self.close, "volume": self.volume,
            "source": self.source, "version": self.version,
        }


class Source(Protocol):
    name: str
    version: str

    def fetch(
        self, symbol: str, start: date, end: date, *, is_index: bool = False
    ) -> Sequence[EodRow]: ...


def _sha_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _sha_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _csv_bytes(rows: Sequence[Mapping[str, object]], fields: Sequence[str]) -> bytes:
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    return output.getvalue().encode("utf-8")


def _read_csv(path: Path) -> tuple[list[dict[str, str]], tuple[str, ...]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV_HEADER_MISSING:{path}")
        return [dict(row) for row in reader], tuple(reader.fieldnames)


def _safe_zip(names: Iterable[str]) -> None:
    for name in names:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name:
            raise ValueError(f"ZIP_UNSAFE_PATH:{name}")


def _format_number(value: float) -> str:
    value = float(value)
    return str(int(value)) if value.is_integer() else format(value, ".15g")


class VnstockSource:
    """Adapter co dinh nguon KBS/VCI, co rate limit va retry."""

    def __init__(
        self,
        provider: str,
        *,
        market_factory: Callable[[], object] | None = None,
        version_reader: Callable[[str], str] | None = None,
        requests_per_minute: int = 18,
        max_attempts: int = 3,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        provider = provider.strip().lower()
        if provider not in {"kbs", "vci"}:
            raise ValueError("VNSTOCK_SOURCE_UNSUPPORTED")
        if requests_per_minute <= 0 or max_attempts <= 0:
            raise ValueError("VNSTOCK_RATE_OR_RETRY_INVALID")
        self.provider = provider
        self.name = f"vnstock_{provider}"
        self._market_factory = market_factory
        self._rpm = requests_per_minute
        self._attempts = max_attempts
        self._sleep = sleeper
        self._clock = clock
        self._last: float | None = None
        if version_reader is None:
            from importlib import metadata
            version_reader = metadata.version
        self.version = version_reader("vnstock")
        if self.version != VNSTOCK_VERSION:
            raise RuntimeError(
                f"VNSTOCK_VERSION_MISMATCH:{self.version}!={VNSTOCK_VERSION}"
            )

    def _market(self) -> object:
        if self._market_factory is not None:
            return self._market_factory()
        try:
            from vnstock import Market
        except ImportError as exc:
            raise RuntimeError(f"VNSTOCK_NOT_INSTALLED:{VNSTOCK_VERSION}") from exc
        return Market()

    @staticmethod
    def _day(value: object) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value).strip().split("T")[0].split(" ")[0])

    def _request(self, symbol: str, start: date, end: date, is_index: bool) -> object:
        last: Exception | None = None
        for attempt in range(self._attempts):
            if self._last is not None:
                wait = 60.0 / self._rpm - (self._clock() - self._last)
                if wait > 0:
                    self._sleep(wait)
            try:
                market = self._market()
                reader = (
                    market.index(symbol=symbol)
                    if is_index else market.equity(symbol=symbol)
                )
                self._last = self._clock()
                return reader.ohlcv(
                    start=start.isoformat(), end=end.isoformat(),
                    interval="1D", source=self.provider, count=5000,
                )
            except Exception as exc:
                last = exc
                if attempt + 1 < self._attempts:
                    self._sleep(float(2 ** attempt))
        assert last is not None
        raise RuntimeError(
            f"VNSTOCK_FETCH_FAILED:{self.provider}:{symbol}:{last}"
        ) from last

    def fetch(
        self, symbol: str, start: date, end: date, *, is_index: bool = False
    ) -> Sequence[EodRow]:
        symbol = symbol.strip().upper()
        frame = self._request(symbol, start, end, is_index)
        if frame is None or bool(getattr(frame, "empty", False)):
            return ()
        required = {"time", "open", "close", "volume"}
        missing = sorted(required - {str(column) for column in frame.columns})
        if missing:
            raise ValueError(f"VNSTOCK_COLUMNS_MISSING:{missing}")
        result = []
        for raw in frame.to_dict(orient="records"):
            volume = float(raw["volume"])
            if not volume.is_integer():
                raise ValueError("VNSTOCK_VOLUME_NOT_INTEGER")
            result.append(EodRow(
                symbol=symbol, day=self._day(raw["time"]),
                open=float(raw["open"]), close=float(raw["close"]),
                volume=int(volume), source=self.name, version=self.version,
                high=float(raw["high"]) if raw.get("high") is not None else None,
                low=float(raw["low"]) if raw.get("low") is not None else None,
            ))
        keys = [(row.symbol, row.day) for row in result]
        if len(keys) != len(set(keys)):
            raise ValueError(f"VNSTOCK_DUPLICATE_DAY:{symbol}")
        return tuple(sorted(result, key=lambda row: row.day))


def _valid_publication(directory: Path) -> tuple[date, int] | None:
    paths = {name: directory / name for name in PUB_FILES}
    if not all(path.is_file() for path in paths.values()):
        return None
    try:
        manifest = json.loads(paths["manifest.json"].read_text(encoding="utf-8"))
        hashes = manifest.get("san_pham_sha256")
        if not isinstance(hashes, dict):
            return None
        for name in PUB_FILES[:3]:
            if hashes.get(name) != _sha_file(paths[name]):
                return None
        rows, fields = _read_csv(paths[PUB_FILES[0]])
        if fields != PUB_FIELDS or not rows:
            return None
        return max(date.fromisoformat(row["ngay"]) for row in rows), len(rows)
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return None


def discover_publication(root: Path) -> Path:
    candidates = []
    for manifest in Path(root).rglob("manifest.json"):
        valid = _valid_publication(manifest.parent)
        if valid is not None:
            candidates.append((*valid, str(manifest.parent), manifest.parent))
    if not candidates:
        raise ValueError("BASE_PUBLICATION_NOT_FOUND")
    return max(candidates)[-1]


def _load_prediction_zip(path: Path) -> tuple[dict[str, bytes], dict[str, object]]:
    with ZipFile(path) as archive:
        names = archive.namelist()
        _safe_zip(names)
        missing = sorted(PREDICTION_REQUIRED - set(names))
        if missing:
            raise ValueError(f"PREDICTION_INPUT_MISSING:{missing}")
        blobs = {name: archive.read(name) for name in names}
    manifest = json.loads(blobs["manifest.json"])
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise ValueError("PREDICTION_MANIFEST_INVALID")
    for name in PREDICTION_REQUIRED - {"manifest.json"}:
        record = files.get(name)
        if not isinstance(record, dict):
            raise ValueError(f"PREDICTION_MANIFEST_RECORD_MISSING:{name}")
        if record.get("sha256") != _sha_bytes(blobs[name]):
            raise ValueError(f"PREDICTION_INPUT_SHA_MISMATCH:{name}")
        if record.get("size") != len(blobs[name]):
            raise ValueError(f"PREDICTION_INPUT_SIZE_MISMATCH:{name}")
    return blobs, manifest


def _by_day(rows: Sequence[EodRow]) -> dict[date, EodRow]:
    return {row.day: row for row in rows}


def _crosscheck(
    left: EodRow, right: EodRow, price_bps: float, volume_ratio: float
) -> tuple[str, ...]:
    if left.symbol != right.symbol or left.day != right.day:
        return ("IDENTITY_MISMATCH",)
    reasons = []
    tolerance = price_bps / 10_000.0
    for name in ("open", "close"):
        a, b = float(getattr(left, name)), float(getattr(right, name))
        if abs(a - b) / max(abs(a), abs(b), 1e-12) > tolerance:
            reasons.append(f"{name.upper()}_MISMATCH")
    a, b = float(left.volume), float(right.volume)
    if abs(a - b) / max(abs(a), abs(b), 1.0) > volume_ratio:
        reasons.append("VOLUME_MISMATCH")
    return tuple(sorted(reasons))


def _merge_rows(
    base: Sequence[Mapping[str, str]], accepted: Sequence[EodRow]
) -> list[dict[str, str]]:
    merged = {(row["ma"].upper(), row["ngay"]): dict(row) for row in base}
    for row in accepted:
        key = (row.symbol, row.day.isoformat())
        new = {
            "ma": row.symbol, "ngay": row.day.isoformat(),
            "gia_mo_cua": _format_number(row.open),
            "gia_dong_cua": _format_number(row.close),
            "khoi_luong": str(row.volume), "nguon": row.source,
            "phien_ban": row.version, "co_so_gia": "CHUA_XAC_NHAN",
            "raw_sha256": _sha_bytes(_json_bytes(row.payload())),
        }
        old = merged.get(key)
        if old is not None:
            old_core = tuple(old[field] for field in (
                "gia_mo_cua", "gia_dong_cua", "khoi_luong"
            ))
            new_core = tuple(new[field] for field in (
                "gia_mo_cua", "gia_dong_cua", "khoi_luong"
            ))
            if old_core != new_core:
                raise ValueError(f"HISTORICAL_REVISION_CONFLICT:{key}")
        merged[key] = new
    return [merged[key] for key in sorted(merged)]


def _write_publication(
    destination: Path, rows: Sequence[Mapping[str, str]], base: Path, run_id: str
) -> None:
    symbols = sorted({str(row["ma"]).upper() for row in rows})
    by_symbol = {symbol: [] for symbol in symbols}
    for row in rows:
        by_symbol[str(row["ma"]).upper()].append(row)
    states, raw = {}, []
    for symbol in symbols:
        items = sorted(by_symbol[symbol], key=lambda row: row["ngay"])
        states[symbol] = {
            "ma": symbol, "trang_thai": "DAT", "so_dong": len(items),
            "ngay_dau": items[0]["ngay"], "ngay_cuoi": items[-1]["ngay"],
            "nguon": items[-1]["nguon"], "phien_ban": items[-1]["phien_ban"],
            "raw_sha256": items[-1]["raw_sha256"],
        }
        raw.append({"ma": symbol, "trang_thai": "DAT"})
    warnings = [
        "HIGH_LOW_SEMANTICS_CHUA_XAC_NHAN",
        "PRICE_BASIS_CHUA_XAC_NHAN",
        "CORPORATE_ACTIONS_CHUA_DAY_DU",
        "CHI_DUNG_CHO_KIEM_TRA_KY_THUAT",
    ]
    csv_payload = _csv_bytes(rows, PUB_FIELDS)
    coverage_payload = _json_bytes({
        "schema_version": "1.0", "ma_lan_chay": run_id,
        "hop_dong": "GIA_MO_CUA_DONG_CUA_KHOI_LUONG_KY_THUAT_MOC_4",
        "tong_ma": len(symbols), "so_ma_dat": len(symbols),
        "so_ma_bi_loai": 0, "tong_so_dong": len(rows),
        "canh_bao_bat_buoc": warnings, "trang_thai_tung_ma": states,
    })
    excluded_payload = _json_bytes({
        "schema_version": "1.0", "ma_lan_chay": run_id,
        "so_ma_bi_loai": 0, "ma_bi_loai": {},
    })
    hashes = {
        PUB_FILES[0]: _sha_bytes(csv_payload),
        PUB_FILES[1]: _sha_bytes(coverage_payload),
        PUB_FILES[2]: _sha_bytes(excluded_payload),
    }
    manifest_payload = _json_bytes({
        "schema_version": "1.0", "ma_lan_chay": run_id,
        "hop_dong": {
            "ten": "GIA_MO_CUA_DONG_CUA_KHOI_LUONG_KY_THUAT_MOC_4",
            "cot": list(PUB_FIELDS), "co_so_gia": "CHUA_XAC_NHAN",
            "high_low_trong_san_pham": False,
            "chi_dung_kiem_tra_ky_thuat": True,
        },
        "dau_vao": {
            "base_publication": str(base),
            "base_manifest_sha256": _sha_file(base / "manifest.json"),
        },
        "raw": raw, "san_pham_sha256": hashes,
        "canh_bao_bat_buoc": warnings,
        "sha256_txt_khong_tu_bam_chinh_no": True,
        "eod_daily_schema_version": SCHEMA_VERSION,
    })
    all_hashes = dict(hashes)
    all_hashes["manifest.json"] = _sha_bytes(manifest_payload)
    sha_payload = "".join(
        f"{digest}  {name}\n" for name, digest in sorted(all_hashes.items())
    ).encode()
    if destination.exists():
        raise FileExistsError(f"OUTPUT_EXISTS:{destination}")
    destination.mkdir(parents=True)
    payloads = (
        csv_payload, coverage_payload, excluded_payload, manifest_payload, sha_payload
    )
    for name, payload in zip(PUB_FILES, payloads, strict=True):
        (destination / name).write_bytes(payload)


def _feature_rows(
    publication: Sequence[Mapping[str, str]],
    benchmark: Sequence[EodRow],
    session: date,
    config_blob: bytes,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    from he_thong_dinh_luong.nghien_cuu_moc_4.dac_trung import (
        FEATURE_ORDER_REDUCED_OPEN_CLOSE_VOLUME_V1,
        _feature_calendar_aligned,
    )
    config = json.loads(config_blob)
    m4 = config.get("moc_4", config)
    order = tuple(m4["feature_order"])
    if order != FEATURE_ORDER_REDUCED_OPEN_CLOSE_VOLUME_V1:
        raise ValueError("EOD_FEATURE_ORDER_INVALID")
    threshold = float(m4.get("nguong_gtgd_tb_toi_thieu", 0.0))
    calendar = tuple(sorted(row.day for row in benchmark if row.day <= session))
    benchmark_map = {
        row.day: SimpleNamespace(ma="VNINDEX", ngay=row.day, gia_dong_cua=row.close)
        for row in benchmark if row.day <= session
    }
    stock_maps: dict[str, dict[date, object]] = {}
    for raw in publication:
        day = date.fromisoformat(str(raw["ngay"]))
        if day > session:
            continue
        symbol = str(raw["ma"]).upper()
        stock_maps.setdefault(symbol, {})[day] = SimpleNamespace(
            ma=symbol, ngay=day, gia_mo_cua=float(raw["gia_mo_cua"]),
            gia_dong_cua=float(raw["gia_dong_cua"]),
            khoi_luong=int(raw["khoi_luong"]), nguon=str(raw["nguon"]),
            phien_ban=str(raw["phien_ban"]), co_so_gia=str(raw["co_so_gia"]),
        )
    output, omitted = [], {}
    for symbol in sorted(stock_maps):
        values, reasons = _feature_calendar_aligned(
            symbol=symbol, T=session, calendar=calendar,
            stock_map=stock_maps[symbol], benchmark_map=benchmark_map,
            feature_order=order,
        )
        if any(values.get(name) is None for name in order):
            omitted[symbol] = list(reasons)
            continue
        liquidity = float(values["gtgd_tb_20"])
        eligible = bool(values["gia_tren_ma250"]) and liquidity >= threshold
        row: dict[str, object] = {
            "ngay": session.isoformat(), "ma": symbol, "hop_le": "true",
            "ly_do": "", "eligible": str(eligible).lower(),
            "ly_do_eligibility": "" if eligible else "khong_dat_ma250_hoac_thanh_khoan",
            "gtgd_tb_20_eligibility": format(liquidity, ".15g"),
            "T1": "", "open_t1_hop_le": "false",
        }
        for name in order:
            value = values[name]
            row[name] = str(value).lower() if isinstance(value, bool) else format(float(value), ".15g")
        output.append(row)
    return output, omitted


def _daily_input(
    source_zip: Path, destination: Path, feature_rows: Sequence[Mapping[str, object]],
    session: date,
) -> None:
    blobs, manifest = _load_prediction_zip(source_zip)
    text = blobs["feature_raw.csv"].decode("utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("FEATURE_HEADER_MISSING")
    fields = tuple(reader.fieldnames)
    if fields[:len(FEATURE_PREFIX)] != FEATURE_PREFIX:
        raise ValueError("FEATURE_HEADER_INVALID")
    kept = []
    for row in reader:
        day = date.fromisoformat(row["ngay"])
        if (day.year, day.month) != (session.year, session.month):
            kept.append(dict(row))
    combined = kept + [
        {field: str(row.get(field, "")) for field in fields}
        for row in feature_rows
    ]
    combined.sort(key=lambda row: (row["ngay"], row["ma"]))
    payload = _csv_bytes(combined, fields)
    blobs["feature_raw.csv"] = payload
    manifest["files"]["feature_raw.csv"] = {
        "sha256": _sha_bytes(payload), "size": len(payload),
    }
    manifest["eod_daily_schema_version"] = SCHEMA_VERSION
    blobs["manifest.json"] = _json_bytes(manifest)
    with ZipFile(destination, "w", compression=ZIP_DEFLATED) as archive:
        for name in sorted(blobs):
            archive.writestr(name, blobs[name])


def _paper_rows(path: Path) -> list[dict[str, str]]:
    rows, _ = _read_csv(path)
    return [{
        "signal_date": row.get("signal_date", ""),
        "symbol": row.get("symbol", ""),
        "champion_model": row.get("champion_model", ""),
        "rank": row.get("champion_rank", ""),
        "target_weight_pct": row.get("technical_weight_pct", ""),
        "status": "PENDING_NEXT_SESSION",
    } for row in rows if row.get("selected_top_k", "").lower() == "true"]


def run(
    *,
    data_root: Path,
    output_dir: Path,
    target_date: date | None = None,
    prediction_input: Path | None = None,
    primary: Source | None = None,
    secondary: Source | None = None,
    min_coverage: float = 0.95,
    price_tolerance_bps: float = 10.0,
    volume_tolerance_ratio: float = 0.05,
    now: datetime | None = None,
    forward_runner: Callable[..., Mapping[str, object]] | None = None,
) -> dict[str, object]:
    if not 0 < min_coverage <= 1:
        raise ValueError("MIN_COVERAGE_INVALID")
    current = now or datetime.now(VN_TZ)
    if current.tzinfo is None:
        raise ValueError("NOW_MUST_BE_TIMEZONE_AWARE")
    today = current.astimezone(VN_TZ).date()
    target = target_date or today
    if target == today and current.astimezone(VN_TZ).hour < 18:
        raise ValueError("MARKET_NOT_FINAL_BEFORE_18H_VN")
    root, destination = Path(data_root), Path(output_dir)
    if destination.exists():
        raise FileExistsError("OUTPUT_DIR_EXISTS")
    source_zip = prediction_input or root / "prediction_input.zip"
    if not source_zip.is_file():
        raise ValueError("PREDICTION_INPUT_NOT_FOUND")
    base = discover_publication(root)
    base_rows, fields = _read_csv(base / PUB_FILES[0])
    if fields != PUB_FIELDS:
        raise ValueError("BASE_PUBLICATION_SCHEMA_INVALID")
    symbols = sorted({row["ma"].upper() for row in base_rows})
    latest_local = max(date.fromisoformat(row["ngay"]) for row in base_rows)
    primary = primary or VnstockSource("kbs")
    secondary = secondary or VnstockSource("vci")
    benchmark_start = target - timedelta(days=650)
    p_benchmark = tuple(primary.fetch("VNINDEX", benchmark_start, target, is_index=True))
    s_benchmark = tuple(secondary.fetch("VNINDEX", benchmark_start, target, is_index=True))
    common = set(_by_day(p_benchmark)) & set(_by_day(s_benchmark))
    sessions = [day for day in common if day <= target]
    if not sessions:
        raise ValueError("BENCHMARK_COMMON_SESSION_NOT_FOUND")
    session = max(sessions)
    if target == today and target.weekday() < 5 and session < target:
        raise ValueError(f"EOD_NOT_PUBLISHED:{session}")
    overlap = latest_local - timedelta(days=10)
    accepted, results, raw_kbs, raw_vci = [], [], {}, {}
    for symbol in symbols:
        try:
            p_rows = tuple(primary.fetch(symbol, overlap, target))
            s_rows = tuple(secondary.fetch(symbol, overlap, target))
            raw_kbs[symbol] = [row.payload() for row in p_rows]
            raw_vci[symbol] = [row.payload() for row in s_rows]
            p, s = _by_day(p_rows).get(session), _by_day(s_rows).get(session)
            if p is None or s is None:
                results.append({"symbol": symbol, "status": "MISSING_SESSION"})
                continue
            reasons = _crosscheck(
                p, s, price_tolerance_bps, volume_tolerance_ratio
            )
            if reasons:
                results.append({
                    "symbol": symbol, "status": "MISMATCH",
                    "reasons": list(reasons),
                })
                continue
            accepted.append(p)
            results.append({"symbol": symbol, "status": "ACCEPTED"})
        except Exception as exc:
            results.append({
                "symbol": symbol, "status": "SOURCE_ERROR",
                "reasons": [f"{type(exc).__name__}:{exc}"],
            })
    coverage = len(accepted) / len(symbols)
    destination.mkdir(parents=True)
    raw_dir = destination / "raw"
    raw_dir.mkdir()
    (raw_dir / "kbs.json").write_bytes(_json_bytes({
        "source": primary.name, "version": primary.version,
        "session": session.isoformat(), "rows": raw_kbs,
    }))
    (raw_dir / "vci.json").write_bytes(_json_bytes({
        "source": secondary.name, "version": secondary.version,
        "session": session.isoformat(), "rows": raw_vci,
    }))
    quality = {
        "schema_version": SCHEMA_VERSION,
        "status": "FINAL" if coverage >= min_coverage else "NOT_FINAL",
        "target_date": target.isoformat(), "session_date": session.isoformat(),
        "base_publication": str(base),
        "symbol_count": len(symbols), "accepted_count": len(accepted),
        "coverage": coverage, "minimum_coverage": min_coverage,
        "price_tolerance_bps": price_tolerance_bps,
        "volume_tolerance_ratio": volume_tolerance_ratio,
        "results": results,
        "raw_sha256": {
            "kbs.json": _sha_file(raw_dir / "kbs.json"),
            "vci.json": _sha_file(raw_dir / "vci.json"),
        },
    }
    quality_path = destination / "data_quality_report.json"
    quality_path.write_bytes(_json_bytes(quality))
    if coverage < min_coverage:
        raise ValueError(f"EOD_DATA_NOT_FINAL:{coverage:.6f}")
    merged = _merge_rows(base_rows, accepted)
    publication_dir = destination / "updated_publication"
    _write_publication(publication_dir, merged, base, f"eod_{session}")
    p_map, s_map = _by_day(p_benchmark), _by_day(s_benchmark)
    benchmark = []
    for day in sorted(common):
        reasons = _crosscheck(
            p_map[day], s_map[day], price_tolerance_bps,
            max(volume_tolerance_ratio, 0.20),
        )
        if not [reason for reason in reasons if reason != "VOLUME_MISMATCH"]:
            benchmark.append(p_map[day])
    if session not in {row.day for row in benchmark}:
        raise ValueError("BENCHMARK_SESSION_CROSSCHECK_FAILED")
    blobs, _ = _load_prediction_zip(source_zip)
    features, omitted = _feature_rows(
        merged, benchmark, session, blobs["cau_hinh.json"]
    )
    if len(features) / len(symbols) < min_coverage:
        raise ValueError(f"FEATURE_COVERAGE_NOT_FINAL:{len(features)}")
    daily_input = destination / "daily_prediction_input.zip"
    _daily_input(source_zip, daily_input, features, session)
    if forward_runner is None:
        from he_thong_dinh_luong.nghien_cuu_moc_4.du_doan_tien_phuong import (
            run_forward_prediction,
        )
        forward_runner = run_forward_prediction
    prediction_dir = destination / "prediction"
    forward = dict(forward_runner(
        input_zip=daily_input, output_dir=prediction_dir,
        top_k=10, validation_months=12, seed=20260730,
    ))
    latest = prediction_dir / "latest_prediction.csv"
    comparison = prediction_dir / "model_comparison.json"
    paper_fields = (
        "signal_date", "symbol", "champion_model", "rank",
        "target_weight_pct", "status",
    )
    paper = destination / "paper_portfolio.csv"
    paper.write_bytes(_csv_bytes(_paper_rows(latest), paper_fields))
    summary = destination / "daily_prediction_summary.txt"
    summary.write_text("\n".join([
        "Data status: FINAL",
        f"Session date: {session}",
        f"Prediction for: next trading session after {session}",
        f"Data coverage: {len(accepted)}/{len(symbols)} ({coverage:.2%})",
        f"Feature coverage: {len(features)}/{len(symbols)}",
        f"Champion model: {forward.get('champion_model')}",
        f"Market regime: {forward.get('market_regime')}",
        f"Technical capital budget: {forward.get('capital_budget_pct')}%",
        f"Top 10: {', '.join(forward.get('top_symbols', []))}",
        "Research eligible: false",
        "Use: technical ranking and paper trading only.",
        "",
    ]), encoding="utf-8")
    final_files = {
        "data_quality_report.json": quality_path,
        "daily_prediction_summary.txt": summary,
        "latest_prediction.csv": latest,
        "model_comparison.json": comparison,
        "paper_portfolio.csv": paper,
        "prediction_manifest.json": prediction_dir / "manifest.json",
    }
    manifest_path = destination / "manifest.json"
    manifest_path.write_bytes(_json_bytes({
        "schema_version": SCHEMA_VERSION, "status": "SUCCESS",
        "session_date": session.isoformat(),
        "daily_prediction_input_sha256": _sha_file(daily_input),
        "technical_validation_only": True, "research_eligible": False,
        "raw_excluded_from_zip": True, "feature_omitted": omitted,
        "files": {
            name: {"sha256": _sha_file(path), "size": path.stat().st_size}
            for name, path in final_files.items()
        },
    }))
    final_files["manifest.json"] = manifest_path
    output_zip = destination / "daily_quant_output.zip"
    with ZipFile(output_zip, "w", compression=ZIP_DEFLATED) as archive:
        for name, path in sorted(final_files.items()):
            archive.write(path, arcname=name)
    return {
        "status": "SUCCESS", "session_date": session.isoformat(),
        "coverage": coverage, "feature_count": len(features),
        "champion_model": forward.get("champion_model"),
        "top_symbols": forward.get("top_symbols", []),
        "output_zip": str(output_zip),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m he_thong_dinh_luong.eod_hang_ngay"
    )
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--prediction-input", type=Path)
    parser.add_argument("--target-date", type=date.fromisoformat)
    parser.add_argument("--min-coverage", type=float, default=0.95)
    parser.add_argument("--price-tolerance-bps", type=float, default=10.0)
    parser.add_argument("--volume-tolerance-ratio", type=float, default=0.05)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run(
            data_root=args.data_root, output_dir=args.output_dir,
            prediction_input=args.prediction_input,
            target_date=args.target_date, min_coverage=args.min_coverage,
            price_tolerance_bps=args.price_tolerance_bps,
            volume_tolerance_ratio=args.volume_tolerance_ratio,
        )
    except Exception as exc:
        print(json.dumps({
            "status": "FAILED",
            "error": f"{type(exc).__name__}:{exc}",
        }, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
