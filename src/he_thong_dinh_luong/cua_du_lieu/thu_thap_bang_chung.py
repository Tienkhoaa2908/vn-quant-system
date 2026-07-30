"""Workstation acquisition kit. CI chi dung file cuc bo, khong goi mang."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
from typing import Any, Sequence
from zipfile import ZIP_DEFLATED, ZipFile

from .hop_dong import (
    CapNguon,
    LoiHopDong,
    TaiLieuNguon,
    TrangThaiQuyen,
    bat_buoc_sha256,
    thanh_primitive,
)

BATCH_SCHEMA = "data_evidence_batch_v1"


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _safe_leaf(value: str, field: str) -> str:
    stripped = value.strip()
    if not stripped or Path(stripped).name != stripped or stripped in {".", ".."}:
        raise LoiHopDong(f"{field} khong phai ten file an toan")
    return stripped


def _require_timezone(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise LoiHopDong(f"{field} phai co mui gio")


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
    _require_timezone(acquisition_time, "acquisition_time")
    if rights_status == TrangThaiQuyen.DO_NOT_STORE:
        raise LoiHopDong("DO_NOT_STORE khong duoc copy raw")
    source_document_id = _safe_leaf(source_document_id, "source_document_id")
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
    _write_json(raw_dir / "acquisition_metadata.json", metadata)
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
        _write_json(evidence_dir / filename, value)
    product_hashes = {
        path.name: _hash_file(path)
        for path in sorted(evidence_dir.iterdir())
        if path.is_file()
    }
    _write_json(evidence_dir / "evidence_hashes.json", product_hashes)
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
        "source_document_id": source_document_id,
    }


def _load_batch_manifest(manifest_file: Path) -> dict[str, Any]:
    try:
        payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LoiHopDong("BATCH_MANIFEST_INVALID_JSON") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != BATCH_SCHEMA:
        raise LoiHopDong("BATCH_MANIFEST_WRONG_SCHEMA")
    if not isinstance(payload.get("run_id"), str) or not payload["run_id"].strip():
        raise LoiHopDong("BATCH_MANIFEST_RUN_ID_INVALID")
    documents = payload.get("documents")
    if not isinstance(documents, list) or not documents:
        raise LoiHopDong("BATCH_MANIFEST_DOCUMENTS_EMPTY")

    seen_ids: set[str] = set()
    seen_files: set[str] = set()
    required_fields = {
        "source_document_id",
        "filename",
        "publisher",
        "document_type",
        "observed_url",
        "rights_status",
        "source_tier",
        "locator",
    }
    for index, row in enumerate(documents, start=1):
        if not isinstance(row, dict) or not required_fields.issubset(row):
            raise LoiHopDong(f"BATCH_MANIFEST_ROW_INVALID:{index}")
        source_id = _safe_leaf(str(row["source_document_id"]), "source_document_id")
        filename = _safe_leaf(str(row["filename"]), "filename")
        if source_id in seen_ids:
            raise LoiHopDong("BATCH_MANIFEST_DUPLICATE_SOURCE_ID")
        if filename in seen_files:
            raise LoiHopDong("BATCH_MANIFEST_DUPLICATE_FILENAME")
        seen_ids.add(source_id)
        seen_files.add(filename)
        try:
            CapNguon(str(row["source_tier"]))
            TrangThaiQuyen(str(row["rights_status"]))
        except ValueError as exc:
            raise LoiHopDong(f"BATCH_MANIFEST_ENUM_INVALID:{source_id}") from exc
        for field in ("publisher", "document_type", "observed_url", "locator"):
            if not isinstance(row[field], str) or not row[field].strip():
                raise LoiHopDong(f"BATCH_MANIFEST_FIELD_EMPTY:{source_id}:{field}")
        expected_sha = row.get("expected_sha256")
        if expected_sha is not None:
            if not isinstance(expected_sha, str):
                raise LoiHopDong(f"BATCH_EXPECTED_SHA_INVALID:{source_id}")
            bat_buoc_sha256(expected_sha, "expected_sha256")
        required = row.get("required", True)
        if not isinstance(required, bool):
            raise LoiHopDong(f"BATCH_REQUIRED_INVALID:{source_id}")
    return payload


def _batch_status(results: list[dict[str, object]]) -> str:
    acquired = sum(row["status"] == "ACQUIRED" for row in results)
    required_failed = any(
        bool(row["required"]) and row["status"] != "ACQUIRED" for row in results
    )
    if acquired == 0:
        return "FAILED"
    if required_failed:
        return "PARTIAL"
    return "COMPLETE"


def tao_goi_bang_chung_theo_lo(
    manifest_file: Path,
    download_dir: Path,
    output_dir: Path,
    *,
    acquisition_time: datetime | None = None,
) -> dict[str, object]:
    """Nhap nhieu file browser trong mot lan va tao evidence package tong hop."""
    if output_dir.exists():
        raise FileExistsError(output_dir)
    if not download_dir.is_dir():
        raise NotADirectoryError(download_dir)
    acquisition_time = acquisition_time or datetime.now(timezone.utc)
    _require_timezone(acquisition_time, "acquisition_time")
    manifest = _load_batch_manifest(manifest_file)
    output_dir.mkdir(parents=True)
    documents_root = output_dir / "documents"
    evidence_dir = output_dir / "evidence"
    documents_root.mkdir()
    evidence_dir.mkdir()

    results: list[dict[str, object]] = []
    registry: list[dict[str, object]] = []
    for row in sorted(manifest["documents"], key=lambda item: item["source_document_id"]):
        source_id = str(row["source_document_id"])
        filename = str(row["filename"])
        source_file = download_dir / filename
        required = bool(row.get("required", True))
        result_row: dict[str, object] = {
            "filename": filename,
            "required": required,
            "source_document_id": source_id,
            "status": "PENDING",
        }
        rights_status = TrangThaiQuyen(str(row["rights_status"]))
        if rights_status == TrangThaiQuyen.DO_NOT_STORE:
            result_row["status"] = "BLOCKED_DO_NOT_STORE"
        elif not source_file.is_file():
            result_row["status"] = "MISSING_FILE"
        else:
            actual_sha = _hash_file(source_file)
            result_row["observed_byte_size"] = source_file.stat().st_size
            result_row["observed_sha256"] = actual_sha
            expected_sha = row.get("expected_sha256")
            if expected_sha is not None and actual_sha != expected_sha:
                result_row["status"] = "HASH_MISMATCH"
                result_row["expected_sha256"] = expected_sha
            else:
                document_output = documents_root / source_id
                acquired = tao_goi_bang_chung_tu_file(
                    source_file,
                    document_output,
                    source_document_id=source_id,
                    publisher=str(row["publisher"]),
                    document_type=str(row["document_type"]),
                    observed_url=str(row["observed_url"]),
                    rights_status=rights_status,
                    source_tier=CapNguon(str(row["source_tier"])),
                    locator=str(row["locator"]),
                    acquisition_time=acquisition_time,
                )
                result_row.update(acquired)
                result_row["status"] = "ACQUIRED"
                registry_path = (
                    document_output
                    / "evidence"
                    / "source_document_registry_candidate.json"
                )
                registry.append(json.loads(registry_path.read_text(encoding="utf-8")))
        if row.get("source_page_url") is not None:
            result_row["source_page_url"] = row["source_page_url"]
        if row.get("notes") is not None:
            result_row["notes"] = row["notes"]
        results.append(result_row)

    status = _batch_status(results)
    summary = {
        "acquired_count": sum(row["status"] == "ACQUIRED" for row in results),
        "batch_status": status,
        "document_count": len(results),
        "missing_count": sum(row["status"] == "MISSING_FILE" for row in results),
        "required_failure_count": sum(
            bool(row["required"]) and row["status"] != "ACQUIRED"
            for row in results
        ),
        "run_id": manifest["run_id"],
        "schema_version": BATCH_SCHEMA,
    }
    products: dict[str, Any] = {
        "acquisition_results.json": results,
        "batch_manifest_copy.json": manifest,
        "batch_summary.json": summary,
        "source_document_registry_candidate.json": registry,
    }
    for filename, value in products.items():
        _write_json(evidence_dir / filename, value)

    product_hashes = {
        path.name: _hash_file(path)
        for path in sorted(evidence_dir.iterdir())
        if path.is_file()
    }
    _write_json(evidence_dir / "evidence_hashes.json", product_hashes)

    zip_path = output_dir / "batch_metadata_evidence.zip"
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(evidence_dir.iterdir()):
            if path.is_file():
                archive.write(path, arcname=f"batch/{path.name}")
        for document_dir in sorted(documents_root.iterdir()):
            per_evidence = document_dir / "evidence"
            if not per_evidence.is_dir():
                continue
            for path in sorted(per_evidence.iterdir()):
                if path.is_file():
                    archive.write(
                        path,
                        arcname=f"documents/{document_dir.name}/{path.name}",
                    )

    return {
        **summary,
        "evidence_zip": str(zip_path),
        "evidence_zip_sha256": _hash_file(zip_path),
        "output_dir": str(output_dir),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Thu thap raw byte tu file browser da tai; khong goi mang."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--file", type=Path)
    mode.add_argument("--manifest", type=Path)
    parser.add_argument("--download-dir", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--source-document-id")
    parser.add_argument("--publisher")
    parser.add_argument("--document-type")
    parser.add_argument("--observed-url")
    parser.add_argument("--locator")
    parser.add_argument(
        "--rights-status",
        choices=[x.value for x in TrangThaiQuyen],
    )
    parser.add_argument(
        "--source-tier",
        choices=[x.value for x in CapNguon],
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.manifest is not None:
        if args.download_dir is None:
            parser.error("--manifest bat buoc --download-dir")
        result = tao_goi_bang_chung_theo_lo(
            args.manifest,
            args.download_dir,
            args.output_dir,
        )
    else:
        single_fields = {
            "--source-document-id": args.source_document_id,
            "--publisher": args.publisher,
            "--document-type": args.document_type,
            "--observed-url": args.observed_url,
            "--locator": args.locator,
            "--rights-status": args.rights_status,
            "--source-tier": args.source_tier,
        }
        missing = [name for name, value in single_fields.items() if value is None]
        if missing:
            parser.error("--file thieu " + ", ".join(missing))
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
