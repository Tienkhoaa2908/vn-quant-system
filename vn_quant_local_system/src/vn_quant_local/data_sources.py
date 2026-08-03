"""Nguồn dữ liệu local: DNSE credentials, incremental sync và CSV thủ công.

Credentials chỉ được lưu trong ``data/state`` của workstation, không commit lên
Git và không bao giờ trả API secret về trình duyệt sau khi lưu.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from hashlib import sha256
import importlib
from importlib import metadata, util
import io
import json
import math
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from typing import Mapping

from .core import SYSTEM_ROOT, paths, state_db, utc_now

EXPECTED_DNSE_SDK_VERSION = "0.5.0"
SECRET_PATH = SYSTEM_ROOT / "data" / "state" / "dnse_credentials.json"
MANUAL_IMPORT_DIR = SYSTEM_ROOT / "data" / "market" / "manual_imports"
MAX_MANUAL_ROWS = 50_000
MAX_MANUAL_BYTES = 15 * 1024 * 1024


def _mask(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    if len(text) <= 8:
        return "•" * len(text)
    return f"{text[:4]}{'•' * min(len(text) - 8, 12)}{text[-4:]}"


def sdk_status() -> dict[str, object]:
    installed = util.find_spec("dnse") is not None
    version = ""
    if installed:
        try:
            version = metadata.version("dnse")
        except metadata.PackageNotFoundError:
            installed = False
    return {
        "installed": installed,
        "version": version or None,
        "expected_version": EXPECTED_DNSE_SDK_VERSION,
        "version_ok": installed and version == EXPECTED_DNSE_SDK_VERSION,
        "install_command": (
            f'"{sys.executable}" -m pip install dnse=={EXPECTED_DNSE_SDK_VERSION}'
        ),
    }


def _read_local_credentials(secret_path: Path = SECRET_PATH) -> dict[str, str]:
    path = Path(secret_path)
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError("DNSE_LOCAL_CREDENTIAL_FILE_INVALID")
    return {
        "api_key": str(value.get("api_key") or "").strip(),
        "api_secret": str(value.get("api_secret") or "").strip(),
        "saved_at": str(value.get("saved_at") or ""),
    }


def _effective_credentials(secret_path: Path = SECRET_PATH) -> tuple[dict[str, str], str]:
    local = _read_local_credentials(secret_path)
    if local.get("api_key") and local.get("api_secret"):
        return local, "LOCAL_FILE"
    env = {
        "api_key": os.environ.get("DNSE_API_KEY", "").strip(),
        "api_secret": os.environ.get("DNSE_API_SECRET", "").strip(),
        "saved_at": "",
    }
    if env["api_key"] and env["api_secret"]:
        return env, "ENVIRONMENT"
    return {}, "NONE"


def credential_status(secret_path: Path = SECRET_PATH) -> dict[str, object]:
    credentials, source = _effective_credentials(secret_path)
    return {
        "configured": bool(credentials.get("api_key") and credentials.get("api_secret")),
        "source": source,
        "api_key_masked": _mask(credentials.get("api_key", "")),
        "saved_at": credentials.get("saved_at") or None,
        "secret_path": str(Path(secret_path)),
        "secret_is_returned_to_browser": False,
        "sdk": sdk_status(),
    }


def save_credentials(
    api_key: str,
    api_secret: str,
    *,
    secret_path: Path = SECRET_PATH,
) -> dict[str, object]:
    key = str(api_key or "").strip()
    secret = str(api_secret or "").strip()
    if not key or not secret:
        raise ValueError("DNSE_CREDENTIALS_MISSING")
    if len(key) > 4096 or len(secret) > 4096:
        raise ValueError("DNSE_CREDENTIALS_TOO_LONG")
    path = Path(secret_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "api_key": key,
        "api_secret": secret,
        "saved_at": utc_now(),
        "storage": "LOCAL_WORKSTATION_ONLY",
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass
    os.replace(temporary, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return credential_status(path)


def clear_credentials(*, secret_path: Path = SECRET_PATH) -> dict[str, object]:
    Path(secret_path).unlink(missing_ok=True)
    return credential_status(secret_path)


def install_dnse_sdk() -> dict[str, object]:
    before = sdk_status()
    if before["version_ok"]:
        return {"status": "ALREADY_READY", "sdk": before}
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-input",
            f"dnse=={EXPECTED_DNSE_SDK_VERSION}",
        ],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip()[-3000:]
        raise RuntimeError(f"DNSE_SDK_INSTALL_FAILED:{tail}")
    importlib.invalidate_caches()
    after = sdk_status()
    if not after["version_ok"]:
        raise RuntimeError(f"DNSE_SDK_INSTALL_INCOMPLETE:{after}")
    return {
        "status": "SUCCESS",
        "sdk": after,
        "output_tail": (completed.stdout or "").strip()[-1500:],
    }


def _source_from_saved_credentials():
    credentials, source_name = _effective_credentials()
    if not credentials:
        raise ValueError("DNSE_CREDENTIALS_MISSING")
    sdk = sdk_status()
    if not sdk["installed"]:
        raise RuntimeError("DNSE_SDK_NOT_INSTALLED:0.5.0")
    if not sdk["version_ok"]:
        raise RuntimeError(
            f"DNSE_SDK_VERSION_MISMATCH:{sdk.get('version')}!={EXPECTED_DNSE_SDK_VERSION}"
        )
    from he_thong_dinh_luong.nguon_dnse import DnseRestSource

    return (
        DnseRestSource(credentials["api_key"], credentials["api_secret"]),
        source_name,
    )


def test_dnse_connection() -> dict[str, object]:
    source, credential_source = _source_from_saved_credentials()
    end = datetime.now().astimezone().date()
    start = end - timedelta(days=21)
    try:
        rows = tuple(source.fetch("VNINDEX", start, end, is_index=True))
    finally:
        source.close()
    if not rows:
        raise ValueError("DNSE_CONNECTION_OK_BUT_NO_VNINDEX_ROWS")
    latest = rows[-1]
    return {
        "status": "SUCCESS",
        "credential_source": credential_source,
        "row_count": len(rows),
        "latest_day": latest.day.isoformat(),
        "latest_close": latest.close,
        "sdk": sdk_status(),
    }


def sync_incremental_market_data_local(
    *,
    end: date | None = None,
    lookback_days: int = 14,
) -> dict[str, object]:
    p = paths()
    if not p.market_db.is_file():
        raise FileNotFoundError("Chưa bootstrap market database local")
    db = sqlite3.connect(p.market_db)
    try:
        symbols = [
            str(row[0])
            for row in db.execute(
                "SELECT DISTINCT symbol FROM bars "
                "WHERE upper(asset_type)='STOCK' ORDER BY symbol"
            ).fetchall()
        ]
        last_day_raw = db.execute("SELECT MAX(day) FROM bars").fetchone()[0]
    finally:
        db.close()
    if not symbols or not last_day_raw:
        raise ValueError("Local market store không có dữ liệu STOCK")

    from he_thong_dinh_luong.dnse_historical_store_v20 import sync_historical_store

    source, credential_source = _source_from_saved_credentials()
    last_day = date.fromisoformat(str(last_day_raw))
    final_end = end or datetime.now().astimezone().date()
    start = min(last_day + timedelta(days=1), final_end)
    start = min(start, final_end) - timedelta(days=max(lookback_days, 0))
    try:
        result = sync_historical_store(
            store_path=p.market_db,
            symbols=symbols,
            start=start,
            end=final_end,
            include_vnindex=True,
            force_refresh=False,
            source=source,
        )
    finally:
        source.close()
    result = dict(result)
    result["credential_source"] = credential_source
    with state_db() as state:
        state.execute(
            "INSERT INTO metadata(key,value,updated_at) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET "
            "value=excluded.value,updated_at=excluded.updated_at",
            ("last_market_sync", json.dumps(result, sort_keys=True), utc_now()),
        )
    return result


def _pick(row: Mapping[str, object], *names: str) -> str:
    lowered = {str(key).strip().lower(): value for key, value in row.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return ""


def _positive_float(raw: str, field: str) -> float:
    try:
        value = float(raw.replace(",", ""))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"MANUAL_CSV_INVALID_NUMBER:{field}:{raw}") from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"MANUAL_CSV_NON_POSITIVE:{field}:{raw}")
    return value


def parse_manual_csv(
    content: str,
    *,
    price_unit: str = "THOUSAND_VND",
) -> list[dict[str, object]]:
    if len(content.encode("utf-8")) > MAX_MANUAL_BYTES:
        raise ValueError("MANUAL_CSV_TOO_LARGE")
    unit = str(price_unit or "").strip().upper()
    if unit not in {"THOUSAND_VND", "VND"}:
        raise ValueError("MANUAL_CSV_PRICE_UNIT_INVALID")
    reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff"), newline=""))
    if not reader.fieldnames:
        raise ValueError("MANUAL_CSV_HEADER_MISSING")
    result: list[dict[str, object]] = []
    seen: set[tuple[str, str, date]] = set()
    for line_number, source_row in enumerate(reader, start=2):
        if not any(str(value or "").strip() for value in source_row.values()):
            continue
        symbol = _pick(source_row, "symbol", "ma").upper()
        raw_day = _pick(source_row, "day", "date", "ngay")
        raw_asset = _pick(source_row, "asset_type", "loai_tai_san").upper()
        asset_type = raw_asset or ("INDEX" if symbol in {"VNINDEX", "VN-INDEX", "VN_INDEX"} else "STOCK")
        if asset_type not in {"STOCK", "INDEX"}:
            raise ValueError(f"MANUAL_CSV_ASSET_TYPE_INVALID:line={line_number}")
        if not symbol or not symbol.replace(".", "").replace("_", "").isalnum():
            raise ValueError(f"MANUAL_CSV_SYMBOL_INVALID:line={line_number}")
        try:
            day = date.fromisoformat(raw_day[:10])
        except ValueError as exc:
            raise ValueError(f"MANUAL_CSV_DAY_INVALID:line={line_number}:{raw_day}") from exc
        open_price = _positive_float(_pick(source_row, "open", "gia_mo_cua"), "open")
        high = _positive_float(_pick(source_row, "high", "gia_cao_nhat"), "high")
        low = _positive_float(_pick(source_row, "low", "gia_thap_nhat"), "low")
        close = _positive_float(_pick(source_row, "close", "gia_dong_cua"), "close")
        raw_volume = _pick(source_row, "volume", "khoi_luong")
        try:
            volume_value = float(raw_volume.replace(",", ""))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"MANUAL_CSV_VOLUME_INVALID:line={line_number}") from exc
        if volume_value < 0 or not volume_value.is_integer():
            raise ValueError(f"MANUAL_CSV_VOLUME_INVALID:line={line_number}")
        volume = int(volume_value)
        if high < max(open_price, close, low) or low > min(open_price, close, high):
            raise ValueError(f"MANUAL_CSV_OHLC_INVALID:line={line_number}")
        if asset_type == "STOCK" and unit == "VND":
            open_price /= 1000.0
            high /= 1000.0
            low /= 1000.0
            close /= 1000.0
        key = (asset_type, symbol, day)
        if key in seen:
            raise ValueError(f"MANUAL_CSV_DUPLICATE_KEY:{asset_type}:{symbol}:{day}")
        seen.add(key)
        result.append(
            {
                "asset_type": asset_type,
                "symbol": symbol,
                "day": day,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        )
        if len(result) > MAX_MANUAL_ROWS:
            raise ValueError("MANUAL_CSV_TOO_MANY_ROWS")
    if not result:
        raise ValueError("MANUAL_CSV_EMPTY")
    result.sort(key=lambda row: (str(row["asset_type"]), str(row["symbol"]), row["day"]))
    return result


def _normalized_hash(row: Mapping[str, object]) -> str:
    normalized = (
        row["symbol"],
        row["day"].isoformat(),
        row["open"],
        row["high"],
        row["low"],
        row["close"],
        row["volume"],
    )
    payload = (
        json.dumps(
            normalized,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def import_manual_csv(
    content: str,
    *,
    filename: str = "manual_ohlcv.csv",
    price_unit: str = "THOUSAND_VND",
) -> dict[str, object]:
    rows = parse_manual_csv(content, price_unit=price_unit)
    p = paths()
    if not p.market_db.is_file():
        raise FileNotFoundError("Chưa bootstrap market database local")
    fetched_at = utc_now()
    safe_name = "".join(
        character if character.isalnum() or character in {"-", "_", "."} else "_"
        for character in Path(filename or "manual_ohlcv.csv").name
    )
    archive_name = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{safe_name}"
    MANUAL_IMPORT_DIR.mkdir(parents=True, exist_ok=True)

    db = sqlite3.connect(p.market_db)
    db.row_factory = sqlite3.Row
    conflicts: list[tuple[dict[str, object], sqlite3.Row]] = []
    identical = 0
    inserts: list[dict[str, object]] = []
    try:
        for row in rows:
            current = db.execute(
                "SELECT * FROM bars WHERE asset_type=? AND symbol=? AND day=?",
                (row["asset_type"], row["symbol"], row["day"].isoformat()),
            ).fetchone()
            if current is None:
                inserts.append(row)
                continue
            incoming = tuple(float(row[name]) for name in ("open", "high", "low", "close")) + (int(row["volume"]),)
            stored = tuple(float(current[name]) for name in ("open", "high", "low", "close")) + (int(current["volume"]),)
            if incoming == stored:
                identical += 1
            else:
                conflicts.append((row, current))
        if conflicts:
            with db:
                for row, current in conflicts:
                    db.execute(
                        """
                        INSERT INTO conflicts(
                            asset_type,symbol,day,existing_json,incoming_json,detected_at
                        ) VALUES (?,?,?,?,?,?)
                        """,
                        (
                            row["asset_type"],
                            row["symbol"],
                            row["day"].isoformat(),
                            json.dumps({name: current[name] for name in ("open", "high", "low", "close", "volume")}, sort_keys=True),
                            json.dumps({name: row[name] for name in ("open", "high", "low", "close", "volume")}, sort_keys=True, default=str),
                            fetched_at,
                        ),
                    )
            first = conflicts[0][0]
            raise ValueError(
                f"MANUAL_CSV_HISTORICAL_CONFLICT:{first['asset_type']}:{first['symbol']}:{first['day']}"
            )
        with db:
            for row in inserts:
                db.execute(
                    "INSERT INTO bars VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        row["asset_type"],
                        row["symbol"],
                        row["day"].isoformat(),
                        row["open"],
                        row["high"],
                        row["low"],
                        row["close"],
                        row["volume"],
                        "manual_csv",
                        "v1",
                        "CHUA_XAC_NHAN",
                        _normalized_hash(row),
                        fetched_at,
                    ),
                )
                db.execute(
                    """
                    INSERT INTO fetched_ranges(
                        asset_type,symbol,start_day,end_day,fetched_at,
                        returned_rows,source,source_version
                    ) VALUES (?,?,?,?,?,?,?,?)
                    """,
                    (
                        row["asset_type"],
                        row["symbol"],
                        row["day"].isoformat(),
                        row["day"].isoformat(),
                        fetched_at,
                        1,
                        "manual_csv",
                        "v1",
                    ),
                )
    finally:
        db.close()

    archive_path = MANUAL_IMPORT_DIR / archive_name
    archive_path.write_text(content, encoding="utf-8")
    report = {
        "status": "SUCCESS",
        "input_row_count": len(rows),
        "inserted_row_count": len(inserts),
        "existing_identical_row_count": identical,
        "conflict_count": 0,
        "price_unit": price_unit,
        "archive_path": str(archive_path),
        "archive_sha256": sha256(archive_path.read_bytes()).hexdigest(),
        "latest_day": max(row["day"] for row in rows).isoformat(),
        "source": "manual_csv",
    }
    with state_db() as state:
        state.execute(
            "INSERT INTO metadata(key,value,updated_at) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET "
            "value=excluded.value,updated_at=excluded.updated_at",
            ("last_manual_market_import", json.dumps(report, sort_keys=True), utc_now()),
        )
    return report
