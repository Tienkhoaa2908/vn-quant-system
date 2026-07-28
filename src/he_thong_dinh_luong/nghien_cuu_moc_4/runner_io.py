"""Doc va xac thuc dau vao cuc bo cho runner Moc 4."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import hashlib
from io import StringIO
import json
from math import isfinite
from pathlib import Path
import re
from typing import Iterable, Mapping, Sequence

from .mo_hinh import (
    BanGhiPointInTime,
    BanGhiUniverse,
    STOCK_PRICE_BASIS_CHUA_XAC_NHAN,
    ThanhBenchmarkDongCua,
    ThanhCoGiaDongCua,
    ThanhGiaMoDongKhoiLuong,
    ThanhOHLCV,
)
from .phong_ve import xac_thuc_cau_truc_huu_han, xac_thuc_so_huu_han

UTC = timezone.utc
MUI_GIO_VIET_NAM = timezone(timedelta(hours=7))
GIO_TAO_TIN_HIEU = time(15, 0)

TEN_TEP_PUBLICATION_REDUCED = (
    "du_lieu_gia_mo_dong_khoi_luong.csv",
    "bao_cao_do_phu_hop_dong_rut_gon.json",
    "bao_cao_ma_bi_loai.json",
    "manifest.json",
    "sha256.txt",
)
COT_REDUCED = (
    "ma", "ngay", "gia_mo_cua", "gia_dong_cua", "khoi_luong",
    "nguon", "phien_ban", "co_so_gia", "raw_sha256",
)
_RE_VOLUME = re.compile(r"(?:0|[1-9][0-9]*)\Z")
_RE_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class _DocOHLCV:
    rows: tuple[ThanhOHLCV, ...]
    nguon: str
    phien_ban: str
    ma_loi_gia: tuple[str, ...]
    ma_loi_volume: tuple[str, ...]
    khoa_loi_gia: tuple[tuple[str, date], ...]
    khoa_loi_volume: tuple[tuple[str, date], ...]


@dataclass(frozen=True)
class _DocPublicationRutGon:
    rows: tuple[ThanhGiaMoDongKhoiLuong, ...]
    nguon: str
    phien_ban: str
    stock_price_basis: str
    candidate_union_expected_count: int
    publication_expected_symbol_count: int
    publication_observed_symbol_count: int
    publication_expected_row_count: int
    publication_observed_row_count: int
    manifest: Mapping[str, object]
    input_paths: Mapping[str, Path]


@dataclass(frozen=True)
class _DocBenchmarkDongCua:
    rows: tuple[ThanhBenchmarkDongCua, ...]
    nguon: str
    phien_ban: str
    co_so_gia: str


@dataclass(frozen=True)
class _DocPIT:
    records: tuple[BanGhiPointInTime, ...]
    event_rows: tuple[Mapping[str, object], ...]
    nguon: str
    phien_ban: str


def _read_csv(path: Path) -> tuple[list[dict[str, str]], tuple[str, ...]]:
    if not path.is_file():
        raise ValueError(f"Tep dau vao khong ton tai: {path}.")
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV khong co header: {path}.")
        rows = [dict(row) for row in reader]
        return rows, tuple(reader.fieldnames)


def _parse_date(value: object, name: str) -> date:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} khong duoc rong.")
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(f"{name} khong dung YYYY-MM-DD.") from exc


def _parse_datetime(value: object, name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} khong duoc rong.")
    try:
        result = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} khong phai ISO-8601.") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(f"{name} phai co mui gio.")
    return result


def _parse_bool(value: object, name: str) -> bool:
    if value is True or value == "true" or value == "True" or value == "1":
        return True
    if value is False or value == "false" or value == "False" or value == "0":
        return False
    raise ValueError(f"{name} phai la boolean ro rang.")


def _parse_float(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} khong phai so hop le.")
    try:
        result = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} khong phai so hop le.") from exc
    if not isfinite(result):
        raise ValueError(f"{name} phai huu han; NaN/Inf bi tu choi.")
    return result


def _parse_int(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} khong phai int hop le.")
    text = str(value).strip()
    if not text or not text.lstrip("-").isdigit():
        raise ValueError(f"{name} phai la int.")
    return int(text)


def _unique(values: Iterable[str], name: str) -> str:
    found = sorted({value for value in values if value})
    if len(found) != 1:
        raise ValueError(f"{name} phai co dung mot gia tri; nhan duoc {found}.")
    return found[0]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _doc_json_object(path: Path, name: str) -> dict[str, object]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=lambda raw: (_ for _ in ()).throw(ValueError(f"{name} chua {raw}.")),
        )
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} khong phai JSON hop le.") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{name} phai la JSON object.")
    xac_thuc_cau_truc_huu_han(value, name)
    return value


def _doc_sha256_txt(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        parts = line.split("  ", 1)
        if len(parts) != 2 or not _RE_SHA256.fullmatch(parts[0]) or not parts[1]:
            raise ValueError(f"sha256.txt sai dinh dang tai dong {number}.")
        digest, name = parts
        if name in result:
            raise ValueError("sha256.txt trung ten tep.")
        result[name] = digest
    return result


def _doc_ohlcv(path: Path) -> _DocOHLCV:
    """Doc OHLCV co phieu; loi gia/volume bi loai co kiem soat nhu hop dong cu."""
    raw_rows, fields = _read_csv(path)
    required = {
        "ma", "ngay", "gia_mo_cua", "gia_cao_nhat", "gia_thap_nhat",
        "gia_dong_cua", "khoi_luong", "nguon", "phien_ban", "co_so_gia",
    }
    missing = sorted(required - set(fields))
    if missing:
        raise ValueError(f"OHLCV thieu cot: {', '.join(missing)}.")
    rows: list[ThanhOHLCV] = []
    price_errors: set[str] = set()
    volume_errors: set[str] = set()
    price_error_keys: set[tuple[str, date]] = set()
    volume_error_keys: set[tuple[str, date]] = set()
    seen: set[tuple[str, date]] = set()
    sources: list[str] = []
    versions: list[str] = []
    for number, raw in enumerate(raw_rows, 2):
        symbol = str(raw.get("ma", "")).strip().upper()
        if not symbol:
            raise ValueError(f"Ma rong tai dong {number} cua {path.name}.")
        day = _parse_date(raw.get("ngay"), f"ngay dong {number}")
        key = (symbol, day)
        if key in seen:
            raise ValueError(f"OHLCV trung ma/ngay: {symbol}, {day}.")
        seen.add(key)
        source = str(raw.get("nguon", "")).strip()
        version = str(raw.get("phien_ban", "")).strip()
        basis = str(raw.get("co_so_gia", "")).strip()
        if not source or not version or not basis:
            raise ValueError(f"OHLCV thieu nguon/phien_ban/co_so_gia tai dong {number}.")
        sources.append(source)
        versions.append(version)
        try:
            open_price = _parse_float(raw.get("gia_mo_cua"), "gia_mo_cua")
            high = _parse_float(raw.get("gia_cao_nhat"), "gia_cao_nhat")
            low = _parse_float(raw.get("gia_thap_nhat"), "gia_thap_nhat")
            close = _parse_float(raw.get("gia_dong_cua"), "gia_dong_cua")
            if min(open_price, high, low, close) <= 0:
                raise ValueError("Gia phai duong.")
        except ValueError:
            price_errors.add(symbol)
            price_error_keys.add(key)
            continue
        try:
            volume = _parse_int(raw.get("khoi_luong"), "khoi_luong")
            if volume < 0:
                raise ValueError("khoi_luong khong duoc am.")
        except ValueError:
            volume_errors.add(symbol)
            volume_error_keys.add(key)
            continue
        try:
            item = ThanhOHLCV(
                ma=symbol, ngay=day, gia_mo_cua=open_price, gia_cao_nhat=high,
                gia_thap_nhat=low, gia_dong_cua=close, khoi_luong=volume,
                nguon=source, phien_ban=version, co_so_gia=basis,
            )
        except ValueError:
            price_errors.add(symbol)
            price_error_keys.add(key)
            continue
        rows.append(item)
    return _DocOHLCV(
        tuple(sorted(rows, key=lambda row: (row.ma, row.ngay))),
        _unique(sources, "nguon OHLCV"), _unique(versions, "phien_ban OHLCV"),
        tuple(sorted(price_errors)), tuple(sorted(volume_errors)),
        tuple(sorted(price_error_keys)), tuple(sorted(volume_error_keys)),
    )


def _doc_publication_rut_gon(
    directory: Path,
    *,
    candidate_union_expected_count: int,
) -> _DocPublicationRutGon:
    root = Path(directory)
    if not root.is_dir():
        raise ValueError(f"Thu muc publication rut gon khong ton tai: {root}.")
    names = tuple(sorted(path.name for path in root.iterdir() if path.is_file()))
    if names != tuple(sorted(TEN_TEP_PUBLICATION_REDUCED)):
        raise ValueError("Publication rut gon phai co dung nam tep canonical.")
    paths = {name: root / name for name in TEN_TEP_PUBLICATION_REDUCED}
    sha_rows = _doc_sha256_txt(paths["sha256.txt"])
    expected_sha_names = set(TEN_TEP_PUBLICATION_REDUCED) - {"sha256.txt"}
    if set(sha_rows) != expected_sha_names:
        raise ValueError("sha256.txt khong bao phu dung bon tep publication.")
    for name, expected in sha_rows.items():
        if _sha256(paths[name]) != expected:
            raise ValueError(f"SHA-256 publication khong khop: {name}.")

    manifest = _doc_json_object(paths["manifest.json"], "publication.manifest")
    coverage = _doc_json_object(paths["bao_cao_do_phu_hop_dong_rut_gon.json"], "publication.coverage")
    excluded = _doc_json_object(paths["bao_cao_ma_bi_loai.json"], "publication.excluded")
    contract = manifest.get("hop_dong")
    if not isinstance(contract, Mapping):
        raise ValueError("Publication manifest thieu hop_dong.")
    if tuple(contract.get("cot", ())) != COT_REDUCED:
        raise ValueError("Publication manifest co schema reduced khong dung canonical.")
    if contract.get("co_so_gia") != STOCK_PRICE_BASIS_CHUA_XAC_NHAN:
        raise ValueError("Publication stock price basis phai bang CHUA_XAC_NHAN.")
    if contract.get("high_low_trong_san_pham") is not False:
        raise ValueError("Publication reduced khong duoc chua high/low.")
    if contract.get("chi_dung_kiem_tra_ky_thuat") is not True:
        raise ValueError("Publication reduced phai chi dung kiem tra ky thuat.")
    product_hashes = manifest.get("san_pham_sha256")
    if not isinstance(product_hashes, Mapping):
        raise ValueError("Publication manifest thieu san_pham_sha256.")
    for name in TEN_TEP_PUBLICATION_REDUCED[:3]:
        if product_hashes.get(name) != _sha256(paths[name]):
            raise ValueError(f"Manifest publication bam sai tep {name}.")
    if excluded.get("so_ma_bi_loai") != 0:
        raise ValueError("Ho so candidate union hien tai khong cho phep ma bi loai.")

    raw_manifest = manifest.get("raw")
    if not isinstance(raw_manifest, list):
        raise ValueError("Publication manifest.raw phai la list.")
    publication_expected_symbol_count = len(raw_manifest)
    tong_ma = coverage.get("tong_ma")
    so_ma_dat = coverage.get("so_ma_dat")
    expected_rows = coverage.get("tong_so_dong")
    for value, name in (
        (tong_ma, "coverage.tong_ma"),
        (so_ma_dat, "coverage.so_ma_dat"),
        (expected_rows, "coverage.tong_so_dong"),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"{name} phai la int khong am.")
    if not (
        candidate_union_expected_count
        == publication_expected_symbol_count
        == tong_ma
        == so_ma_dat
    ):
        raise ValueError("So ma du kien giua run profile va publication khong khop.")

    raw_rows, fields = _read_csv(paths["du_lieu_gia_mo_dong_khoi_luong.csv"])
    if fields != COT_REDUCED:
        raise ValueError("CSV reduced sai schema hoac thu tu cot canonical.")
    if not raw_rows:
        raise ValueError("CSV reduced rong.")
    rows: list[ThanhGiaMoDongKhoiLuong] = []
    seen: set[tuple[str, date]] = set()
    original_keys: list[tuple[str, date]] = []
    sources: list[str] = []
    versions: list[str] = []
    bases: list[str] = []
    for number, raw in enumerate(raw_rows, 2):
        symbol = str(raw.get("ma", "")).strip().upper()
        day = _parse_date(raw.get("ngay"), f"reduced.ngay dong {number}")
        key = (symbol, day)
        if not symbol:
            raise ValueError(f"Ma reduced rong tai dong {number}.")
        if key in seen:
            raise ValueError(f"Reduced trung ma/ngay: {symbol}, {day}.")
        seen.add(key)
        original_keys.append(key)
        volume_text = str(raw.get("khoi_luong", "")).strip()
        if not _RE_VOLUME.fullmatch(volume_text):
            raise ValueError(f"khoi_luong reduced phai la so nguyen thap phan khong am tai dong {number}.")
        source = str(raw.get("nguon", "")).strip()
        version = str(raw.get("phien_ban", "")).strip()
        basis = str(raw.get("co_so_gia", "")).strip()
        item = ThanhGiaMoDongKhoiLuong(
            ma=symbol,
            ngay=day,
            gia_mo_cua=_parse_float(raw.get("gia_mo_cua"), "gia_mo_cua reduced"),
            gia_dong_cua=_parse_float(raw.get("gia_dong_cua"), "gia_dong_cua reduced"),
            khoi_luong=int(volume_text),
            nguon=source,
            phien_ban=version,
            co_so_gia=basis,
            raw_sha256=str(raw.get("raw_sha256", "")).strip(),
        )
        rows.append(item)
        sources.append(source)
        versions.append(version)
        bases.append(basis)
    if original_keys != sorted(original_keys):
        raise ValueError("CSV reduced phai sap xep nghiem ngat theo ma,ngay.")
    observed_symbols = len({row.ma for row in rows})
    if observed_symbols != candidate_union_expected_count:
        raise ValueError("So ma quan sat reduced khong khop run profile.")
    if len(rows) != expected_rows:
        raise ValueError("So dong quan sat reduced khong khop publication manifest/coverage.")
    return _DocPublicationRutGon(
        rows=tuple(rows),
        nguon=_unique(sources, "nguon reduced"),
        phien_ban=_unique(versions, "phien_ban reduced"),
        stock_price_basis=_unique(bases, "stock_price_basis reduced"),
        candidate_union_expected_count=candidate_union_expected_count,
        publication_expected_symbol_count=publication_expected_symbol_count,
        publication_observed_symbol_count=observed_symbols,
        publication_expected_row_count=expected_rows,
        publication_observed_row_count=len(rows),
        manifest=manifest,
        input_paths=paths,
    )


def _xac_thuc_benchmark_identity(rows: Sequence[ThanhCoGiaDongCua], expected_symbol: str) -> str:
    symbols = sorted({row.ma for row in rows})
    if symbols != [expected_symbol]:
        raise ValueError(f"Benchmark file phai co dung mot ma {expected_symbol}; nhan duoc {symbols}.")
    return symbols[0]


def _doc_benchmark_dong_cua(path: Path, *, expected_symbol: str) -> _DocBenchmarkDongCua:
    """Doc benchmark canonical close-only va fail closed tren schema/identity."""
    raw_rows, fields = _read_csv(path)
    expected_fields = ("ma", "ngay", "gia_dong_cua", "nguon", "phien_ban", "co_so_gia")
    if fields != expected_fields:
        missing = sorted(set(expected_fields) - set(fields))
        extra = sorted(set(fields) - set(expected_fields))
        details: list[str] = []
        if missing:
            details.append("thieu cot: " + ", ".join(missing))
        if extra:
            details.append("cot ngoai hop dong: " + ", ".join(extra))
        if not missing and not extra:
            details.append("thu tu cot khong dung schema canonical")
        raise ValueError("Benchmark close-only sai schema: " + "; ".join(details) + ".")
    if not raw_rows:
        raise ValueError("Benchmark close-only rong.")
    rows: list[ThanhBenchmarkDongCua] = []
    seen: set[tuple[str, date]] = set()
    sources: list[str] = []
    versions: list[str] = []
    bases: list[str] = []
    for number, raw in enumerate(raw_rows, 2):
        symbol = str(raw.get("ma", "")).strip().upper()
        if not symbol:
            raise ValueError(f"Ma benchmark rong tai dong {number}.")
        day = _parse_date(raw.get("ngay"), f"benchmark.ngay dong {number}")
        key = (symbol, day)
        if key in seen:
            raise ValueError(f"Benchmark trung ma/ngay: {symbol}, {day}.")
        seen.add(key)
        source = str(raw.get("nguon", "")).strip()
        version = str(raw.get("phien_ban", "")).strip()
        basis = str(raw.get("co_so_gia", "")).strip()
        item = ThanhBenchmarkDongCua(
            ma=symbol, ngay=day,
            gia_dong_cua=_parse_float(raw.get("gia_dong_cua"), "gia_dong_cua benchmark"),
            nguon=source, phien_ban=version, co_so_gia=basis,
        )
        rows.append(item)
        sources.append(source)
        versions.append(version)
        bases.append(basis)
    ordered = tuple(sorted(rows, key=lambda row: (row.ma, row.ngay)))
    _xac_thuc_benchmark_identity(ordered, expected_symbol)
    return _DocBenchmarkDongCua(
        rows=ordered,
        nguon=_unique(sources, "nguon benchmark"),
        phien_ban=_unique(versions, "phien_ban benchmark"),
        co_so_gia=_unique(bases, "co_so_gia benchmark"),
    )


def _doc_calendar(path: Path) -> tuple[date, ...]:
    rows, fields = _read_csv(path)
    if "ngay" not in fields:
        raise ValueError("Lich benchmark thieu cot ngay.")
    days = tuple(_parse_date(row.get("ngay"), "lich_benchmark.ngay") for row in rows)
    if not days:
        raise ValueError("Lich benchmark rong.")
    if len(days) != len(set(days)):
        raise ValueError("Lich benchmark trung ngay.")
    if tuple(sorted(days)) != days:
        raise ValueError("Lich benchmark phai sap xep tang dan.")
    return days


def _doc_universe(path: Path) -> tuple[tuple[BanGhiUniverse, ...], str, str]:
    rows, fields = _read_csv(path)
    required = {"ngay_hieu_luc", "ma", "thuoc_universe", "nguon", "phien_ban", "thoi_diem_cong_bo"}
    missing = sorted(required - set(fields))
    if missing:
        raise ValueError(f"Universe thieu cot: {', '.join(missing)}.")
    result: list[BanGhiUniverse] = []
    for number, row in enumerate(rows, 2):
        result.append(BanGhiUniverse(
            ngay_hieu_luc=_parse_date(row.get("ngay_hieu_luc"), f"universe.ngay_hieu_luc dong {number}"),
            ma=str(row.get("ma", "")).strip().upper(),
            thuoc_universe=_parse_bool(row.get("thuoc_universe"), "thuoc_universe"),
            nguon=str(row.get("nguon", "")).strip(),
            phien_ban=str(row.get("phien_ban", "")).strip(),
            thoi_diem_cong_bo=_parse_datetime(row.get("thoi_diem_cong_bo"), "thoi_diem_cong_bo"),
        ))
    if not result:
        raise ValueError("Universe rong.")
    return tuple(result), _unique((x.nguon for x in result), "nguon universe"), _unique((x.phien_ban for x in result), "phien_ban universe")


def _doc_pit(path: Path) -> _DocPIT:
    rows, fields = _read_csv(path)
    if not rows:
        return _DocPIT((), (), "khong_co_su_kien", "0")
    required = {"loai_du_lieu", "khoa_ban_ghi", "ngay_hieu_luc", "nguon", "phien_ban", "thoi_diem_cong_bo"}
    missing = sorted(required - set(fields))
    if missing:
        raise ValueError(f"Metadata PIT thieu cot: {', '.join(missing)}.")
    records: list[BanGhiPointInTime] = []
    events: list[Mapping[str, object]] = []
    for number, row in enumerate(rows, 2):
        data_text = str(row.get("du_lieu_json", "") or "{}").strip()
        try:
            data = json.loads(data_text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"du_lieu_json sai tai dong {number}.") from exc
        if not isinstance(data, dict):
            raise ValueError("du_lieu_json phai la object.")
        xac_thuc_cau_truc_huu_han(data, f"metadata_pit[{number}]")
        record = BanGhiPointInTime(
            loai_du_lieu=str(row.get("loai_du_lieu", "")).strip(),
            khoa_ban_ghi=str(row.get("khoa_ban_ghi", "")).strip(),
            ngay_hieu_luc=_parse_date(row.get("ngay_hieu_luc"), "metadata_pit.ngay_hieu_luc"),
            nguon=str(row.get("nguon", "")).strip(),
            phien_ban=str(row.get("phien_ban", "")).strip(),
            thoi_diem_cong_bo=_parse_datetime(row.get("thoi_diem_cong_bo"), "metadata_pit.thoi_diem_cong_bo"),
            du_lieu=data,
        )
        records.append(record)
        if record.loai_du_lieu == "corporate_action":
            events.append(data)
    keys = [record.khoa() for record in records]
    if len(keys) != len(set(keys)):
        raise ValueError("Trung ban ghi metadata PIT/corporate action.")
    return _DocPIT(
        tuple(records), tuple(events),
        _unique((x.nguon for x in records), "nguon metadata PIT"),
        _unique((x.phien_ban for x in records), "phien_ban metadata PIT"),
    )


def _signal_time(day: date) -> datetime:
    return datetime.combine(day, GIO_TAO_TIN_HIEU, tzinfo=MUI_GIO_VIET_NAM)


def _json_ready(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    if isinstance(value, float):
        xac_thuc_so_huu_han(value, "json")
    return value


def _json_text(value: object) -> str:
    return json.dumps(_json_ready(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"


def _csv_text(fieldnames: Sequence[str], rows: Iterable[Mapping[str, object]]) -> str:
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="raise", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        normalized = {}
        for name in fieldnames:
            value = row.get(name)
            if isinstance(value, bool):
                normalized[name] = "true" if value else "false"
            elif isinstance(value, (date, datetime)):
                normalized[name] = value.isoformat()
            elif value is None:
                normalized[name] = ""
            elif isinstance(value, float):
                xac_thuc_so_huu_han(value, f"csv.{name}")
                normalized[name] = format(value, ".17g")
            else:
                normalized[name] = value
        writer.writerow(normalized)
    return stream.getvalue()
