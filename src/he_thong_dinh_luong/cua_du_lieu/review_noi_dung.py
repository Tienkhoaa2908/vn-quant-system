"""Trich xuat va lap bang chung review noi dung PDF theo lo, fail-closed."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Callable, Sequence
import unicodedata
from zipfile import ZIP_DEFLATED, ZipFile

from .hop_dong import LoiHopDong

SCHEMA_VERSION = "content_review_batch_v1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ROW_RE = re.compile(
    r"^\s*(?P<row>\d{1,3})\s+"
    r"(?P<symbol>[A-Z][A-Z0-9]{2,4})\s+"
    r"(?P<company>.+?)\s+"
    r"(?P<shares>\d[\d,.]*)\s+"
    r"(?P<free_float>\d+(?:[.,]\d+)?)%\s+"
    r"(?P<cap>\d+(?:[.,]\d+)?)%"
)
_DATE_RE = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_text(value: str) -> str:
    value = value.replace("Đ", "D").replace("đ", "d")
    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return re.sub(r"[^A-Z0-9]+", " ", without_marks.upper()).strip()


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_marker_groups(groups: object, source_id: str) -> list[list[str]]:
    if not isinstance(groups, list) or not groups:
        raise LoiHopDong(f"{source_id}: required_marker_groups rong")
    result: list[list[str]] = []
    for group in groups:
        if not isinstance(group, list) or not group:
            raise LoiHopDong(f"{source_id}: marker group rong")
        cleaned = [str(item).strip() for item in group]
        if any(not item for item in cleaned):
            raise LoiHopDong(f"{source_id}: marker rong")
        result.append(cleaned)
    return result


def tai_manifest_review(path: Path) -> dict[str, object]:
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise LoiHopDong("manifest review phai la object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise LoiHopDong("manifest review sai schema_version")
    documents = payload.get("documents")
    if not isinstance(documents, list) or not documents:
        raise LoiHopDong("manifest review thieu documents")

    ids: set[str] = set()
    normalized: list[dict[str, object]] = []
    for raw in documents:
        if not isinstance(raw, dict):
            raise LoiHopDong("document review phai la object")
        source_id = str(raw.get("source_document_id", "")).strip()
        if not source_id or source_id in ids:
            raise LoiHopDong("source_document_id rong hoac trung")
        ids.add(source_id)

        expected_sha = str(raw.get("expected_sha256", "")).strip()
        if not _SHA256_RE.fullmatch(expected_sha):
            raise LoiHopDong(f"{source_id}: expected_sha256 khong hop le")
        expected_size = raw.get("expected_byte_size")
        if not isinstance(expected_size, int) or expected_size <= 0:
            raise LoiHopDong(f"{source_id}: expected_byte_size khong hop le")

        document_type = str(raw.get("document_type", "")).strip()
        if document_type not in {"RULEBOOK", "PERIODIC_FULL_LIST"}:
            raise LoiHopDong(f"{source_id}: document_type khong ho tro")

        expected_pages = raw.get("expected_page_count")
        if expected_pages is not None and (
            not isinstance(expected_pages, int) or expected_pages <= 0
        ):
            raise LoiHopDong(f"{source_id}: expected_page_count khong hop le")

        item = dict(raw)
        item["source_document_id"] = source_id
        item["expected_sha256"] = expected_sha
        item["expected_byte_size"] = expected_size
        item["document_type"] = document_type
        item["required"] = bool(raw.get("required", True))
        item["required_marker_groups"] = _validate_marker_groups(
            raw.get("required_marker_groups"), source_id
        )

        if document_type == "PERIODIC_FULL_LIST":
            page_indexes = raw.get("vn100_page_indexes")
            if (
                not isinstance(page_indexes, list)
                or not page_indexes
                or any(not isinstance(x, int) or x < 0 for x in page_indexes)
                or page_indexes != sorted(set(page_indexes))
            ):
                raise LoiHopDong(f"{source_id}: vn100_page_indexes khong hop le")
            expected_count = raw.get("expected_member_count")
            if not isinstance(expected_count, int) or expected_count <= 0:
                raise LoiHopDong(f"{source_id}: expected_member_count khong hop le")
            item["vn100_page_indexes"] = page_indexes
            item["expected_member_count"] = expected_count

        normalized.append(item)

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": str(payload.get("run_id", "")).strip(),
        "documents": normalized,
    }


def _default_reader_factory(path: Path) -> object:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise LoiHopDong(
            "PYPDF_NOT_INSTALLED: chay bang uv run --with pypdf==5.9.0"
        ) from exc
    reader = PdfReader(str(path), strict=False)
    if getattr(reader, "is_encrypted", False):
        try:
            decrypted = reader.decrypt("")
        except Exception as exc:  # pragma: no cover - depends on external PDF
            raise LoiHopDong("PDF_ENCRYPTED") from exc
        if not decrypted:
            raise LoiHopDong("PDF_ENCRYPTED")
    return reader


def _extract_pages(reader: object) -> list[str]:
    pages = getattr(reader, "pages", None)
    if pages is None:
        raise LoiHopDong("PDF_READER_MISSING_PAGES")
    result: list[str] = []
    for page in pages:
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            raise LoiHopDong("PDF_TEXT_EXTRACTION_FAILED") from exc
        result.append(text.replace("\r\n", "\n").replace("\r", "\n"))
    return result


def _check_markers(
    canonical_document: str, groups: list[list[str]]
) -> tuple[bool, list[dict[str, object]]]:
    details: list[dict[str, object]] = []
    passed = True
    for alternatives in groups:
        normalized = [_canonical_text(value) for value in alternatives]
        matched = [value for value in normalized if value and value in canonical_document]
        group_passed = bool(matched)
        passed = passed and group_passed
        details.append(
            {
                "alternatives": alternatives,
                "matched": matched,
                "passed": group_passed,
            }
        )
    return passed, details


def _parse_percent(value: str) -> str:
    return value.replace(",", ".")


def _parse_shares(value: str) -> int:
    return int(value.replace(",", "").replace(".", ""))


def _extract_rows_from_page(text: str, page_index: int) -> list[dict[str, object]]:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    rows: list[dict[str, object]] = []
    for index, line in enumerate(lines):
        if not line:
            continue
        match = None
        candidate = line
        for lookahead in range(0, 4):
            if lookahead:
                next_index = index + lookahead
                if next_index >= len(lines):
                    break
                candidate = f"{candidate} {lines[next_index]}".strip()
            match = _ROW_RE.match(candidate)
            if match:
                break
        if not match:
            continue
        row_number = int(match.group("row"))
        rows.append(
            {
                "row_number": row_number,
                "raw_symbol": match.group("symbol"),
                "company_name": match.group("company").strip(),
                "shares_for_index": _parse_shares(match.group("shares")),
                "free_float_pct": _parse_percent(match.group("free_float")),
                "capitalization_cap_pct": _parse_percent(match.group("cap")),
                "source_locator": f"pdf_page_index={page_index};page_number={page_index + 1}",
            }
        )
    return rows


def _extract_vn100_rows(
    pages: list[str], page_indexes: list[int], expected_count: int
) -> tuple[list[dict[str, object]], list[str]]:
    errors: list[str] = []
    by_row: dict[int, dict[str, object]] = {}
    symbols: dict[str, int] = {}

    for page_index in page_indexes:
        if page_index >= len(pages):
            errors.append(f"VN100_PAGE_OUT_OF_RANGE:{page_index}")
            continue
        for row in _extract_rows_from_page(pages[page_index], page_index):
            row_number = int(row["row_number"])
            if row_number < 1 or row_number > expected_count:
                continue
            existing = by_row.get(row_number)
            if existing is not None and existing != row:
                errors.append(f"VN100_ROW_CONFLICT:{row_number}")
                continue
            symbol = str(row["raw_symbol"])
            prior_row = symbols.get(symbol)
            if prior_row is not None and prior_row != row_number:
                errors.append(f"VN100_SYMBOL_DUPLICATE:{symbol}")
                continue
            by_row[row_number] = row
            symbols[symbol] = row_number

    expected_rows = set(range(1, expected_count + 1))
    missing = sorted(expected_rows - set(by_row))
    if missing:
        errors.append(
            "VN100_ROW_SEQUENCE_INCOMPLETE:" + ",".join(str(value) for value in missing)
        )
    if len(by_row) != expected_count:
        errors.append(
            f"VN100_ROW_COUNT_MISMATCH:expected={expected_count};observed={len(by_row)}"
        )
    return [by_row[key] for key in sorted(by_row)], sorted(set(errors))


def _registry_by_id(run_root: Path) -> dict[str, dict[str, object]]:
    path = run_root / "evidence" / "source_document_registry_candidate.json"
    if not path.is_file():
        raise LoiHopDong("ACQUISITION_REGISTRY_MISSING")
    payload = _load_json(path)
    if not isinstance(payload, list):
        raise LoiHopDong("ACQUISITION_REGISTRY_INVALID")
    result: dict[str, dict[str, object]] = {}
    for row in payload:
        if not isinstance(row, dict):
            raise LoiHopDong("ACQUISITION_REGISTRY_INVALID_ROW")
        source_id = str(row.get("source_document_id", "")).strip()
        if not source_id or source_id in result:
            raise LoiHopDong("ACQUISITION_REGISTRY_DUPLICATE_ID")
        result[source_id] = row
    return result


def _review_document(
    run_root: Path,
    contract: dict[str, object],
    registry: dict[str, dict[str, object]],
    reader_factory: Callable[[Path], object],
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    source_id = str(contract["source_document_id"])
    raw_path = (
        run_root
        / "documents"
        / source_id
        / "raw"
        / source_id
        / "original.bin"
    )
    base_result: dict[str, object] = {
        "source_document_id": source_id,
        "document_type": contract["document_type"],
        "required": contract["required"],
        "status": "FAILED",
        "errors": [],
        "content_reviewed": False,
        "chain_verified": False,
        "canonical_eligible": False,
    }
    errors: list[str] = []

    registry_row = registry.get(source_id)
    if registry_row is None:
        errors.append("ACQUISITION_REGISTRY_DOCUMENT_MISSING")
    else:
        if registry_row.get("sha256") != contract["expected_sha256"]:
            errors.append("ACQUISITION_REGISTRY_SHA_MISMATCH")
        if registry_row.get("byte_size") != contract["expected_byte_size"]:
            errors.append("ACQUISITION_REGISTRY_SIZE_MISMATCH")
        if registry_row.get("canonical_eligible") is True:
            errors.append("UNEXPECTED_CANONICAL_FLAG")
        if registry_row.get("content_reviewed") is True:
            errors.append("UNEXPECTED_CONTENT_REVIEWED_FLAG")

    if not raw_path.is_file():
        errors.append("RAW_FILE_MISSING")
        base_result["errors"] = sorted(set(errors))
        return base_result, [], []

    observed_size = raw_path.stat().st_size
    observed_sha = _hash_file(raw_path)
    base_result["observed_byte_size"] = observed_size
    base_result["observed_sha256"] = observed_sha
    if observed_size != contract["expected_byte_size"]:
        errors.append("RAW_SIZE_MISMATCH")
    if observed_sha != contract["expected_sha256"]:
        errors.append("RAW_SHA256_MISMATCH")
    if errors:
        base_result["errors"] = sorted(set(errors))
        return base_result, [], []

    try:
        reader = reader_factory(raw_path)
        pages = _extract_pages(reader)
    except Exception as exc:
        base_result["errors"] = [f"PDF_READ_ERROR:{type(exc).__name__}:{exc}"]
        return base_result, [], []

    page_fingerprints = [
        {
            "source_document_id": source_id,
            "page_index": index,
            "page_number": index + 1,
            "char_count": len(text),
            "text_sha256": sha256(text.encode("utf-8")).hexdigest(),
        }
        for index, text in enumerate(pages)
    ]
    base_result["page_count"] = len(pages)
    base_result["nonempty_page_count"] = sum(bool(text.strip()) for text in pages)

    expected_pages = contract.get("expected_page_count")
    if expected_pages is not None and len(pages) != expected_pages:
        errors.append(
            f"PDF_PAGE_COUNT_MISMATCH:expected={expected_pages};observed={len(pages)}"
        )

    canonical_document = _canonical_text("\n".join(pages))
    markers_passed, marker_details = _check_markers(
        canonical_document, contract["required_marker_groups"]  # type: ignore[arg-type]
    )
    base_result["marker_groups"] = marker_details
    if not markers_passed:
        errors.append("REQUIRED_MARKER_MISSING")

    candidates: list[dict[str, object]] = []
    if contract["document_type"] == "PERIODIC_FULL_LIST":
        page_indexes = contract["vn100_page_indexes"]  # type: ignore[assignment]
        expected_count = int(contract["expected_member_count"])
        rows, row_errors = _extract_vn100_rows(
            pages, page_indexes, expected_count  # type: ignore[arg-type]
        )
        errors.extend(row_errors)
        selected_text = "\n".join(
            pages[index]
            for index in page_indexes  # type: ignore[union-attr]
            if index < len(pages)
        )
        candidate = {
            "source_document_id": source_id,
            "contract_version": "pit_membership_interval_v2",
            "index_name": "VN100",
            "expected_member_count": expected_count,
            "observed_member_count": len(rows),
            "period_label": contract.get("period_label"),
            "effective_from_candidate": contract.get("effective_from_candidate"),
            "effective_to_candidate": contract.get("effective_to_candidate"),
            "dates_observed": sorted(set(_DATE_RE.findall(selected_text))),
            "rows": rows,
            "is_fixture": False,
            "content_reviewed": False,
            "chain_verified": False,
            "canonical_candidate": False,
            "research_eligible": False,
        }
        candidates.append(candidate)

    base_result["errors"] = sorted(set(errors))
    base_result["status"] = "REVIEW_READY" if not errors else "NEEDS_REVIEW"
    return base_result, page_fingerprints, candidates


def thuc_hien_review_noi_dung_theo_lo(
    run_root: Path,
    manifest_path: Path,
    output_dir: Path,
    *,
    reader_factory: Callable[[Path], object] | None = None,
    review_time: datetime | None = None,
) -> dict[str, object]:
    if output_dir.exists():
        raise FileExistsError(output_dir)
    if not run_root.is_dir():
        raise FileNotFoundError(run_root)
    manifest = tai_manifest_review(manifest_path)
    registry = _registry_by_id(run_root)
    reader_factory = reader_factory or _default_reader_factory
    review_time = review_time or datetime.now(timezone.utc)
    if review_time.tzinfo is None or review_time.utcoffset() is None:
        raise LoiHopDong("review_time phai co mui gio")

    evidence_dir = output_dir / "evidence"
    evidence_dir.mkdir(parents=True)

    results: list[dict[str, object]] = []
    page_fingerprints: list[dict[str, object]] = []
    candidates: list[dict[str, object]] = []
    for contract in manifest["documents"]:  # type: ignore[index]
        result, fingerprints, document_candidates = _review_document(
            run_root,
            contract,  # type: ignore[arg-type]
            registry,
            reader_factory,
        )
        results.append(result)
        page_fingerprints.extend(fingerprints)
        candidates.extend(document_candidates)

    required_failures = sum(
        bool(result["required"]) and result["status"] != "REVIEW_READY"
        for result in results
    )
    ready_count = sum(result["status"] == "REVIEW_READY" for result in results)
    if required_failures == 0:
        batch_status = "READY_FOR_MANUAL_REVIEW"
    elif ready_count:
        batch_status = "PARTIAL"
    else:
        batch_status = "FAILED"

    summary = {
        "schema_version": SCHEMA_VERSION,
        "run_id": manifest["run_id"],
        "reviewed_at": review_time.isoformat(),
        "document_count": len(results),
        "review_ready_count": ready_count,
        "required_failure_count": required_failures,
        "batch_status": batch_status,
        "content_reviewed": False,
        "chain_verified": False,
        "canonical_eligible": False,
        "research_eligible": False,
    }
    _write_json(evidence_dir / "manifest_copy.json", manifest)
    _write_json(evidence_dir / "document_review_results.json", results)
    _write_json(evidence_dir / "page_text_fingerprints.json", page_fingerprints)
    _write_json(evidence_dir / "vn100_membership_candidates.json", candidates)
    _write_json(evidence_dir / "batch_summary.json", summary)

    hashes = {
        path.name: _hash_file(path)
        for path in sorted(evidence_dir.iterdir())
        if path.is_file()
    }
    _write_json(evidence_dir / "evidence_hashes.json", hashes)

    zip_path = output_dir / "content_review_metadata_evidence.zip"
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(evidence_dir.iterdir()):
            if path.is_file():
                archive.write(path, arcname=f"evidence/{path.name}")

    result = dict(summary)
    result["output_dir"] = str(output_dir)
    result["evidence_zip"] = str(zip_path)
    result["evidence_zip_sha256"] = _hash_file(zip_path)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Review noi dung PDF acquisition theo lo; chi tao candidate va "
            "khong tu dong canonical."
        )
    )
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = thuc_hien_review_noi_dung_theo_lo(
        args.run_root,
        args.manifest,
        args.output_dir,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["batch_status"] == "READY_FOR_MANUAL_REVIEW" else 2


if __name__ == "__main__":
    raise SystemExit(main())
