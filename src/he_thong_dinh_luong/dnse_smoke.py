"""Smoke doc HPG va VNINDEX tu DNSE, khong chay pipeline va khong ghi credential."""
from __future__ import annotations

import argparse
from datetime import date, timedelta
from hashlib import sha256
import json
from pathlib import Path
from typing import Sequence
from zipfile import ZIP_DEFLATED, ZipFile

from .eod_hang_ngay_cli import DnseRestSource


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def run(*, output_dir: Path, start: date, end: date) -> dict[str, object]:
    destination = Path(output_dir)
    if destination.exists():
        raise FileExistsError("OUTPUT_DIR_EXISTS")
    if start > end:
        raise ValueError("DNSE_DATE_RANGE_INVALID")
    destination.mkdir(parents=True)

    source = DnseRestSource.from_env()
    try:
        hpg = tuple(source.fetch("HPG", start, end))
        vnindex = tuple(source.fetch("VNINDEX", start, end, is_index=True))
    finally:
        source.close()

    evidence = {
        "schema_version": "dnse_market_data_smoke_v1",
        "status": "SUCCESS",
        "source": source.name,
        "sdk_version": source.version,
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "credentials_recorded": False,
        "pipeline_called": False,
        "normalization_applied": False,
        "responses": {
            "HPG": {
                "type": "STOCK",
                "row_count": len(hpg),
                "rows": [row.payload() for row in hpg],
            },
            "VNINDEX": {
                "type": "INDEX",
                "row_count": len(vnindex),
                "rows": [row.payload() for row in vnindex],
            },
        },
    }
    evidence_path = destination / "dnse_smoke_evidence.json"
    evidence_path.write_bytes(_json_bytes(evidence))
    digest = sha256(evidence_path.read_bytes()).hexdigest()
    hash_path = destination / "sha256.txt"
    hash_path.write_text(f"{digest}  dnse_smoke_evidence.json\n", encoding="utf-8")
    zip_path = destination / "dnse_smoke_evidence.zip"
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.write(evidence_path, arcname=evidence_path.name)
        archive.write(hash_path, arcname=hash_path.name)

    return {
        "status": "SUCCESS",
        "source": source.name,
        "sdk_version": source.version,
        "hpg_rows": len(hpg),
        "vnindex_rows": len(vnindex),
        "evidence_zip": str(zip_path),
        "evidence_sha256": sha256(zip_path.read_bytes()).hexdigest(),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m he_thong_dinh_luong.dnse_smoke"
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--end", type=date.fromisoformat, default=date.today())
    parser.add_argument("--start", type=date.fromisoformat)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    start = args.start or args.end - timedelta(days=10)
    try:
        result = run(output_dir=args.output_dir, start=start, end=args.end)
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
