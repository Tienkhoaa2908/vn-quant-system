"""Workstation acquisition kit. CI chi dung mode --file, khong goi mang."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
from typing import Sequence
from zipfile import ZIP_DEFLATED, ZipFile

from .hop_dong import (
    CapNguon,
    LoiHopDong,
    TaiLieuNguon,
    TrangThaiQuyen,
    thanh_primitive,
)


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tao_goi_bang_chung_tu_file(
    source_file: Path,
    output_dir: Path,
    *,
    source_document_id: str,
    publisher: str,
    document_type: str,
    observed_url: str,
    rights_status: TrangThaiQuyen,
    source_tier: CapNguon,
    locator: str,
    acquisition_time: datetime | None = None,
) -> dict[str, object]:
    if not source_file.is_file():
        raise FileNotFoundError(source_file)
    acquisition_time = acquisition_time or datetime.now(timezone.utc)
    if acquisition_time.tzinfo is None or acquisition_time.utcoffset() is None:
        raise LoiHopDong("acquisition_time phai co mui gio")
    if rights_status == TrangThaiQuyen.DO_NOT_STORE:
        raise LoiHopDong("DO_NOT_STORE khong duoc copy raw")
    run_root = output_dir
    raw_dir = run_root / "raw" / source_document_id
    evidence_dir = run_root / "evidence"
    if run_root.exists():
        raise FileExistsError(run_root)
    raw_dir.mkdir(parents=True)
    evidence_dir.mkdir(parents=True)
    raw_path = raw_dir / "original.bin"
    shutil.copyfile(source_file, raw_path)
    hash_first = _hash_file(raw_path)
    hash_second = _hash_file(raw_path)
    if hash_first != hash_second:
        raise LoiHopDong("DOUBLE_HASH_MISMATCH")
    byte_size = raw_path.stat().st_size
    source = TaiLieuNguon(
        source_document_id=source_document_id,
        publisher=publisher,
        source_tier=source_tier,
        document_type=document_type,
        observed_url=observed_url,
        acquired_at=acquisition_time,
        rights_status=rights_status,
        sha256=hash_first,
        byte_size=byte_size,
        content_reviewed=False,
        chain_verified=False,
        canonical_eligible=False,
        is_fixture=False,
    )
    source.kiem_tra()
    metadata = {
        "access_method": "USER_SUPPLIED_FILE",
        "collection_timestamp": acquisition_time.isoformat(),
        "locator": locator,
        "original_filename": source_file.name,
        "raw_storage": str(raw_path),
        "source": thanh_primitive(source),
    }
    (raw_dir / "acquisition_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    (raw_dir / "sha256.txt").write_text(
        f"{hash_first}  original.bin\n{hash_second}  original.bin\n",
        encoding="utf-8",
    )
    verification = {
        "byte_size": byte_size,
        "hash_first": hash_first,
        "hash_match": True,
        "hash_second": hash_second,
        "source_document_id": source_document_id,
    }
    products = {
        "acquisition_manifest.json": metadata,
        "hash_verification.json": verification,
        "source_document_registry_candidate.json": thanh_primitive(source),
    }
    for filename, value in products.items():
        (evidence_dir / filename).write_text(
            json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
    product_hashes = {
        path.name: _hash_file(path)
        for path in sorted(evidence_dir.iterdir())
        if path.is_file()
    }
    (evidence_dir / "evidence_hashes.json").write_text(
        json.dumps(product_hashes, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    zip_path = run_root / "metadata_evidence.zip"
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(evidence_dir.iterdir()):
            if path.is_file():
                archive.write(path, arcname=path.name)
    return {
        "byte_size": byte_size,
        "evidence_zip": str(zip_path),
        "hash_first": hash_first,
        "hash_match": True,
        "hash_second": hash_second,
        "raw_path": str(raw_path),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Thu thap raw byte tu file browser da tai; khong goi mang."
    )
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--source-document-id", required=True)
    parser.add_argument("--publisher", required=True)
    parser.add_argument("--document-type", required=True)
    parser.add_argument("--observed-url", required=True)
    parser.add_argument("--locator", required=True)
    parser.add_argument(
        "--rights-status",
        required=True,
        choices=[x.value for x in TrangThaiQuyen],
    )
    parser.add_argument(
        "--source-tier",
        required=True,
        choices=[x.value for x in CapNguon],
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = tao_goi_bang_chung_tu_file(
        args.file,
        args.output_dir,
        source_document_id=args.source_document_id,
        publisher=args.publisher,
        document_type=args.document_type,
        observed_url=args.observed_url,
        rights_status=TrangThaiQuyen(args.rights_status),
        source_tier=CapNguon(args.source_tier),
        locator=args.locator,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
