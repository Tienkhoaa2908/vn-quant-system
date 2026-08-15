from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

SCHEMA_VERSION = "sqlite_market_bars_fingerprint_v79"


def _jsonable(value):
    if isinstance(value, bytes):
        return {"__bytes_hex__": value.hex()}
    return value


def fingerprint_bars(store: Path) -> dict[str, object]:
    path = Path(store).resolve()
    uri = path.as_uri() + "?mode=ro"
    digest = hashlib.sha256()
    row_count = 0
    first_day: str | None = None
    last_day: str | None = None

    with sqlite3.connect(uri, uri=True) as db:
        db.execute("BEGIN")
        columns = [str(row[1]) for row in db.execute('PRAGMA table_info("bars")')]
        if not columns:
            raise ValueError("V79_BARS_TABLE_MISSING")
        lower = {column.lower(): column for column in columns}
        required = {"asset_type", "symbol", "day"}
        if not required <= set(lower):
            raise ValueError("V79_BARS_KEY_COLUMNS_MISSING")

        digest.update(json.dumps(columns, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        quote = lambda text: '"' + text.replace('"', '""') + '"'
        select_columns = ",".join(quote(column) for column in columns)
        order = ",".join(
            [quote(lower["asset_type"]), quote(lower["symbol"]), quote(lower["day"]), "rowid"]
        )
        day_index = columns.index(lower["day"])
        for row in db.execute(f'SELECT {select_columns} FROM "bars" ORDER BY {order}'):
            payload = [_jsonable(value) for value in row]
            digest.update(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
            )
            digest.update(b"\n")
            row_count += 1
            raw_day = row[day_index]
            if raw_day is not None:
                day = str(raw_day)[:10]
                first_day = day if first_day is None or day < first_day else first_day
                last_day = day if last_day is None or day > last_day else last_day
        db.rollback()

    return {
        "schema_version": SCHEMA_VERSION,
        "bars_sha256": digest.hexdigest(),
        "bars_row_count": row_count,
        "bars_first_day": first_day,
        "bars_last_day": last_day,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(fingerprint_bars(args.store), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
