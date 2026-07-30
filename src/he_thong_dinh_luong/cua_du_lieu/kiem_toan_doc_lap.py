"""Kiểm toán độc lập candidate VN100 bằng PDF engine và parser tọa độ tách biệt."""

from __future__ import annotations

import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import shutil
from typing import Any, Callable, Iterable
import unicodedata
from zipfile import ZIP_DEFLATED, ZipFile

from .hop_dong import LoiHopDong

SCHEMA_VERSION = "independent_audit_batch_v1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9]{2,4}$")
_INTEGER_RE = re.compile(r"^\d{1,3}$")
_NUMBER_RE = re.compile(r"^\d[\d.,]*$")
_PERCENT_RE = re.compile(r"^\d+(?:[.,]\d+)?%$")
_REQUIRED_REVIEW_FILES = {
    "evidence/batch_summary.json",
    "evidence/document_review_results.json",
    "evidence/evidence_hashes.json",
    "evidence/manifest_copy.json",
    "evidence/page_text_fingerprints.json",
    "evidence/vn100_membership_candidates.json",
}


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_bytes(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _canonical_text(value: str) -> str:
    value = value.replace("Đ", "D").replace("đ", "d")
    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return re.sub(r"[^A-Z0-9]+", " ", without_marks.upper()).strip()


def _canonical_decimal(value: object) -> str:
    raw = str(value).strip().replace(",", ".")
    try:
        parsed = Decimal(raw)
    except InvalidOperation as exc:
        raise LoiHopDong(f"DECIMAL_INVALID:{value}") from exc
    if not parsed.is_finite():
        raise LoiHopDong(f"DECIMAL_INVALID:{value}")
    normalized = format(parsed.normalize(), "f")
    return "0" if normalized in {"-0", ""} else normalized


def _safe_zip_names(names: Iterable[str]) -> None:
    for name in names:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name:
            raise LoiHopDong(f"REVIEW_ZIP_UNSAFE_PATH:{name}")


def tai_manifest_audit(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise LoiHopDong("AUDIT_MANIFEST_NOT_OBJECT")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise LoiHopDong("AUDIT_MANIFEST_SCHEMA_MISMATCH")
    review_sha = str(payload.get("expected_review_zip_sha256", "")).strip()
    if not _SHA256_RE.fullmatch(review_sha):
        raise LoiHopDong("AUDIT_MANIFEST_REVIEW_SHA_INVALID")
    documents = payload.get("documents")
    if not isinstance(documents, list) or not documents:
        raise LoiHopDong("AUDIT_MANIFEST_DOCUMENTS_EMPTY")

    ids: set[str] = set()
    normalized: list[dict[str, object]] = []
    for raw in documents:
        if not isinstance(raw, dict):
            raise LoiHopDong("AUDIT_MANIFEST_DOCUMENT_NOT_OBJECT")
        source_id = str(raw.get("source_document_id", "")).strip()
        if not source_id or source_id in ids:
            raise LoiHopDong("AUDIT_MANIFEST_SOURCE_ID_INVALID")
        ids.add(source_id)
        expected_sha = str(raw.get("expected_sha256", "")).strip()
        expected_size = raw.get("expected_byte_size")
        expected_pages = raw.get("expected_page_count")
        document_type = str(raw.get("document_type", "")).strip()
        if not _SHA256_RE.fullmatch(expected_sha):
            raise LoiHopDong(f"{source_id}:EXPECTED_SHA_INVALID")
        if not isinstance(expected_size, int) or expected_size <= 0:
            raise LoiHopDong(f"{source_id}:EXPECTED_SIZE_INVALID")
        if not isinstance(expected_pages, int) or expected_pages <= 0:
            raise LoiHopDong(f"{source_id}:EXPECTED_PAGE_COUNT_INVALID")
        if document_type not in {"RULEBOOK", "PERIODIC_FULL_LIST"}:
            raise LoiHopDong(f"{source_id}:DOCUMENT_TYPE_INVALID")
        groups = raw.get("required_marker_groups")
        if not isinstance(groups, list) or not groups:
            raise LoiHopDong(f"{source_id}:MARKER_GROUPS_EMPTY")
        clean_groups: list[list[str]] = []
        for group in groups:
            if not isinstance(group, list) or not group:
                raise LoiHopDong(f"{source_id}:MARKER_GROUP_EMPTY")
            cleaned = [str(item).strip() for item in group]
            if any(not item for item in cleaned):
                raise LoiHopDong(f"{source_id}:MARKER_EMPTY")
            clean_groups.append(cleaned)

        item = dict(raw)
        item.update(
            {
                "source_document_id": source_id,
                "expected_sha256": expected_sha,
                "expected_byte_size": expected_size,
                "expected_page_count": expected_pages,
                "document_type": document_type,
                "required": bool(raw.get("required", True)),
                "required_marker_groups": clean_groups,
            }
        )
        if document_type == "PERIODIC_FULL_LIST":
            indexes = raw.get("vn100_page_indexes")
            count = raw.get("expected_member_count")
            if (
                not isinstance(indexes, list)
                or not indexes
                or any(not isinstance(value, int) or value < 0 for value in indexes)
                or indexes != sorted(set(indexes))
            ):
                raise LoiHopDong(f"{source_id}:PAGE_INDEXES_INVALID")
            if not isinstance(count, int) or count <= 0:
                raise LoiHopDong(f"{source_id}:EXPECTED_MEMBER_COUNT_INVALID")
            item["vn100_page_indexes"] = indexes
            item["expected_member_count"] = count
        normalized.append(item)

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": str(payload.get("run_id", "")).strip(),
        "expected_review_zip_sha256": review_sha,
        "documents": normalized,
    }


def _load_review_evidence(
    zip_path: Path, expected_sha: str
) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    if not zip_path.is_file():
        raise LoiHopDong("REVIEW_EVIDENCE_ZIP_MISSING")
    observed_sha = _hash_file(zip_path)
    if observed_sha != expected_sha:
        raise LoiHopDong(
            "REVIEW_EVIDENCE_ZIP_SHA_MISMATCH:"
            f"expected={expected_sha};observed={observed_sha}"
        )
    with ZipFile(zip_path) as archive:
        names = archive.namelist()
        _safe_zip_names(names)
        if set(names) != _REQUIRED_REVIEW_FILES:
            missing = sorted(_REQUIRED_REVIEW_FILES - set(names))
            extra = sorted(set(names) - _REQUIRED_REVIEW_FILES)
            raise LoiHopDong(
                f"REVIEW_EVIDENCE_FILE_SET_MISMATCH:missing={missing};extra={extra}"
            )
        blobs = {name: archive.read(name) for name in names}

    hashes = json.loads(blobs["evidence/evidence_hashes.json"])
    if not isinstance(hashes, dict):
        raise LoiHopDong("REVIEW_EVIDENCE_HASHES_INVALID")
    for basename, expected in hashes.items():
        member = f"evidence/{basename}"
        if member not in blobs:
            raise LoiHopDong(f"REVIEW_EVIDENCE_HASH_TARGET_MISSING:{basename}")
        if _hash_bytes(blobs[member]) != expected:
            raise LoiHopDong(f"REVIEW_EVIDENCE_INTERNAL_HASH_MISMATCH:{basename}")

    summary = json.loads(blobs["evidence/batch_summary.json"])
    if not isinstance(summary, dict):
        raise LoiHopDong("REVIEW_SUMMARY_INVALID")
    if summary.get("batch_status") != "READY_FOR_MANUAL_REVIEW":
        raise LoiHopDong("REVIEW_BATCH_NOT_READY")
    for flag in (
        "content_reviewed",
        "chain_verified",
        "canonical_eligible",
        "research_eligible",
    ):
        if summary.get(flag) is not False:
            raise LoiHopDong(f"REVIEW_SUMMARY_UNSAFE_FLAG:{flag}")

    candidates = json.loads(blobs["evidence/vn100_membership_candidates.json"])
    if not isinstance(candidates, list):
        raise LoiHopDong("REVIEW_CANDIDATES_INVALID")
    by_id: dict[str, dict[str, object]] = {}
    for item in candidates:
        if not isinstance(item, dict):
            raise LoiHopDong("REVIEW_CANDIDATE_NOT_OBJECT")
        source_id = str(item.get("source_document_id", "")).strip()
        if not source_id or source_id in by_id:
            raise LoiHopDong("REVIEW_CANDIDATE_SOURCE_ID_INVALID")
        for flag in (
            "content_reviewed",
            "chain_verified",
            "canonical_candidate",
            "research_eligible",
        ):
            if item.get(flag) is not False:
                raise LoiHopDong(f"{source_id}:REVIEW_CANDIDATE_UNSAFE_FLAG:{flag}")
        by_id[source_id] = item
    return summary, by_id


def _default_pdf_factory(path: Path) -> object:
    try:
        import pdfplumber
    except ImportError as exc:
        raise LoiHopDong(
            "PDFPLUMBER_NOT_INSTALLED: "
            "chay bang uv run --with pdfplumber==0.11.10"
        ) from exc
    return pdfplumber.open(path)


def _page_text(page: object) -> str:
    try:
        value = page.extract_text(x_tolerance=1.5, y_tolerance=3) or ""
    except Exception as exc:
        raise LoiHopDong("INDEPENDENT_TEXT_EXTRACTION_FAILED") from exc
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _page_words(page: object) -> list[dict[str, object]]:
    try:
        words = page.extract_words(
            x_tolerance=1.5,
            y_tolerance=3,
            keep_blank_chars=False,
            use_text_flow=False,
        )
    except Exception as exc:
        raise LoiHopDong("INDEPENDENT_WORD_EXTRACTION_FAILED") from exc
    if not isinstance(words, list):
        raise LoiHopDong("INDEPENDENT_WORDS_INVALID")
    result: list[dict[str, object]] = []
    for word in words:
        if not isinstance(word, dict):
            continue
        text = str(word.get("text", "")).strip()
        if not text:
            continue
        try:
            top = float(word["top"])
            x0 = float(word["x0"])
        except (KeyError, TypeError, ValueError) as exc:
            raise LoiHopDong("INDEPENDENT_WORD_COORDINATE_INVALID") from exc
        result.append({"text": text, "top": top, "x0": x0})
    return result


def _group_visual_lines(
    words: list[dict[str, object]], tolerance: float = 3.0
) -> list[list[str]]:
    ordered = sorted(words, key=lambda item: (float(item["top"]), float(item["x0"])))
    lines: list[dict[str, object]] = []
    for word in ordered:
        top = float(word["top"])
        target = None
        for line in reversed(lines[-3:]):
            if abs(top - float(line["top"])) <= tolerance:
                target = line
                break
        if target is None:
            target = {"top": top, "words": []}
            lines.append(target)
        target["words"].append(word)
    result: list[list[str]] = []
    for line in lines:
        sorted_words = sorted(line["words"], key=lambda item: float(item["x0"]))
        result.append([str(item["text"]) for item in sorted_words])
    return result


def _starts_row(tokens: list[str], expected_count: int) -> bool:
    if len(tokens) < 2 or not _INTEGER_RE.fullmatch(tokens[0]):
        return False
    row_number = int(tokens[0])
    return 1 <= row_number <= expected_count and bool(_SYMBOL_RE.fullmatch(tokens[1]))


def _parse_row_block(tokens: list[str], page_index: int) -> dict[str, object] | None:
    if len(tokens) < 6:
        return None
    pct_positions = [
        index for index, token in enumerate(tokens) if _PERCENT_RE.fullmatch(token)
    ]
    if len(pct_positions) < 2:
        return None
    free_index, cap_index = pct_positions[-2], pct_positions[-1]
    share_index = None
    for index in range(free_index - 1, 1, -1):
        if _NUMBER_RE.fullmatch(tokens[index]):
            share_index = index
            break
    if share_index is None or not tokens[2:share_index]:
        return None
    return {
        "row_number": int(tokens[0]),
        "raw_symbol": tokens[1],
        "company_name": " ".join(tokens[2:share_index]).strip(),
        "shares_for_index": int(
            tokens[share_index].replace(",", "").replace(".", "")
        ),
        "free_float_pct": _canonical_decimal(tokens[free_index][:-1]),
        "capitalization_cap_pct": _canonical_decimal(tokens[cap_index][:-1]),
        "source_locator": f"pdf_page_index={page_index};page_number={page_index + 1}",
    }


def _extract_independent_rows(
    pages: list[object], page_indexes: list[int], expected_count: int
) -> tuple[list[dict[str, object]], list[str], list[dict[str, object]]]:
    errors: list[str] = []
    rows_by_number: dict[int, dict[str, object]] = {}
    diagnostics: list[dict[str, object]] = []
    for page_index in page_indexes:
        if page_index >= len(pages):
            errors.append(f"AUDIT_PAGE_OUT_OF_RANGE:{page_index}")
            continue
        lines = _group_visual_lines(_page_words(pages[page_index]))
        blocks: list[list[str]] = []
        current: list[str] | None = None
        for line in lines:
            if _starts_row(line, expected_count):
                if current is not None:
                    blocks.append(current)
                current = list(line)
            elif current is not None:
                current.extend(line)
        if current is not None:
            blocks.append(current)

        parsed_on_page = 0
        for block in blocks:
            row = _parse_row_block(block, page_index)
            if row is None:
                continue
            row_number = int(row["row_number"])
            existing = rows_by_number.get(row_number)
            if existing is not None and existing != row:
                errors.append(f"AUDIT_ROW_CONFLICT:{row_number}")
                continue
            rows_by_number[row_number] = row
            parsed_on_page += 1
        diagnostics.append(
            {
                "page_index": page_index,
                "visual_line_count": len(lines),
                "row_block_count": len(blocks),
                "parsed_row_count": parsed_on_page,
                "word_stream_sha256": _hash_bytes(
                    "\n".join(" ".join(line) for line in lines).encode("utf-8")
                ),
            }
        )

    expected = set(range(1, expected_count + 1))
    missing = sorted(expected - set(rows_by_number))
    if missing:
        errors.append("AUDIT_ROW_SEQUENCE_INCOMPLETE:" + ",".join(map(str, missing)))
    symbols: dict[str, int] = {}
    for row_number, row in rows_by_number.items():
        symbol = str(row["raw_symbol"])
        if symbol in symbols and symbols[symbol] != row_number:
            errors.append(f"AUDIT_SYMBOL_DUPLICATE:{symbol}")
        symbols[symbol] = row_number
    if len(rows_by_number) != expected_count:
        errors.append(
            "AUDIT_ROW_COUNT_MISMATCH:"
            f"expected={expected_count};observed={len(rows_by_number)}"
        )
    return (
        [rows_by_number[key] for key in sorted(rows_by_number)],
        sorted(set(errors)),
        diagnostics,
    )


def _normalize_candidate_row(row: dict[str, object]) -> dict[str, object]:
    return {
        "row_number": int(row["row_number"]),
        "raw_symbol": str(row["raw_symbol"]).strip(),
        "company_name": _canonical_text(str(row["company_name"])),
        "shares_for_index": int(row["shares_for_index"]),
        "free_float_pct": _canonical_decimal(row["free_float_pct"]),
        "capitalization_cap_pct": _canonical_decimal(
            row["capitalization_cap_pct"]
        ),
        "source_locator": str(row["source_locator"]).strip(),
    }


def _compare_rows(
    source_id: str,
    independent_rows: list[dict[str, object]],
    candidate: dict[str, object],
) -> list[dict[str, object]]:
    raw_candidate_rows = candidate.get("rows")
    if not isinstance(raw_candidate_rows, list):
        return [{"source_document_id": source_id, "error": "CANDIDATE_ROWS_INVALID"}]
    candidate_by_number: dict[int, dict[str, object]] = {}
    discrepancies: list[dict[str, object]] = []
    for raw in raw_candidate_rows:
        if not isinstance(raw, dict):
            discrepancies.append(
                {"source_document_id": source_id, "error": "CANDIDATE_ROW_NOT_OBJECT"}
            )
            continue
        normalized = _normalize_candidate_row(raw)
        row_number = int(normalized["row_number"])
        if row_number in candidate_by_number:
            discrepancies.append(
                {
                    "source_document_id": source_id,
                    "row_number": row_number,
                    "error": "CANDIDATE_ROW_DUPLICATE",
                }
            )
        candidate_by_number[row_number] = normalized

    independent_by_number = {
        int(row["row_number"]): {
            **row,
            "company_name": _canonical_text(str(row["company_name"])),
        }
        for row in independent_rows
    }
    fields = (
        "raw_symbol",
        "company_name",
        "shares_for_index",
        "free_float_pct",
        "capitalization_cap_pct",
        "source_locator",
    )
    for row_number in sorted(set(candidate_by_number) | set(independent_by_number)):
        candidate_row = candidate_by_number.get(row_number)
        audit_row = independent_by_number.get(row_number)
        if candidate_row is None or audit_row is None:
            discrepancies.append(
                {
                    "source_document_id": source_id,
                    "row_number": row_number,
                    "error": "ROW_MISSING_ONE_SIDE",
                    "candidate_present": candidate_row is not None,
                    "independent_present": audit_row is not None,
                }
            )
            continue
        for field in fields:
            if candidate_row[field] != audit_row[field]:
                discrepancies.append(
                    {
                        "source_document_id": source_id,
                        "row_number": row_number,
                        "field": field,
                        "candidate": candidate_row[field],
                        "independent": audit_row[field],
                        "error": "FIELD_MISMATCH",
                    }
                )
    return discrepancies


def _marker_result(
    text: str, groups: list[list[str]]
) -> tuple[bool, list[dict[str, object]]]:
    canonical = _canonical_text(text)
    details: list[dict[str, object]] = []
    passed = True
    for alternatives in groups:
        matches = [
            value
            for value in alternatives
            if _canonical_text(value) and _canonical_text(value) in canonical
        ]
        group_passed = bool(matches)
        passed = passed and group_passed
        details.append(
            {"alternatives": alternatives, "matched": matches, "passed": group_passed}
        )
    return passed, details


def _audit_document(
    run_root: Path,
    contract: dict[str, object],
    candidates: dict[str, dict[str, object]],
    pdf_factory: Callable[[Path], object],
) -> tuple[
    dict[str, object],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    source_id = str(contract["source_document_id"])
    raw_path = (
        run_root
        / "documents"
        / source_id
        / "raw"
        / source_id
        / "original.bin"
    )
    errors: list[str] = []
    result: dict[str, object] = {
        "source_document_id": source_id,
        "document_type": contract["document_type"],
        "required": contract["required"],
        "status": "FAILED",
        "errors": errors,
        "content_reviewed": False,
        "chain_verified": False,
        "canonical_eligible": False,
        "research_eligible": False,
        "interval_dates_audited": False,
    }
    if not raw_path.is_file():
        errors.append("RAW_FILE_MISSING")
        return result, [], [], []

    observed_size = raw_path.stat().st_size
    observed_sha = _hash_file(raw_path)
    result["observed_byte_size"] = observed_size
    result["observed_sha256"] = observed_sha
    if observed_size != contract["expected_byte_size"]:
        errors.append("RAW_SIZE_MISMATCH")
    if observed_sha != contract["expected_sha256"]:
        errors.append("RAW_SHA256_MISMATCH")
    if errors:
        return result, [], [], []

    try:
        resource = pdf_factory(raw_path)
        manager = resource if hasattr(resource, "__enter__") else nullcontext(resource)
        with manager as pdf:
            pages = list(getattr(pdf, "pages", []))
            result["page_count"] = len(pages)
            if len(pages) != contract["expected_page_count"]:
                errors.append(
                    "PDF_PAGE_COUNT_MISMATCH:"
                    f"expected={contract['expected_page_count']};observed={len(pages)}"
                )
            texts = [_page_text(page) for page in pages]
            marker_ok, marker_details = _marker_result(
                "\n".join(texts), contract["required_marker_groups"]
            )
            result["marker_groups"] = marker_details
            if not marker_ok:
                errors.append("REQUIRED_MARKER_MISSING")

            independent_rows: list[dict[str, object]] = []
            discrepancies: list[dict[str, object]] = []
            diagnostics: list[dict[str, object]] = []
            if contract["document_type"] == "PERIODIC_FULL_LIST":
                candidate = candidates.get(source_id)
                if candidate is None:
                    errors.append("REVIEW_CANDIDATE_MISSING")
                else:
                    independent_rows, parse_errors, diagnostics = (
                        _extract_independent_rows(
                            pages,
                            contract["vn100_page_indexes"],
                            contract["expected_member_count"],
                        )
                    )
                    errors.extend(parse_errors)
                    discrepancies = _compare_rows(
                        source_id, independent_rows, candidate
                    )
                    if discrepancies:
                        errors.append(
                            f"CANDIDATE_COMPARISON_MISMATCH:{len(discrepancies)}"
                        )
                    result["independent_member_count"] = len(independent_rows)
                    result["candidate_member_count"] = candidate.get(
                        "observed_member_count"
                    )
            result["errors"] = sorted(set(errors))
            result["status"] = "AUDIT_MATCHED" if not errors else "AUDIT_MISMATCH"
            return result, independent_rows, discrepancies, diagnostics
    except LoiHopDong as exc:
        errors.append(str(exc))
    except Exception as exc:  # pragma: no cover - external parser behavior
        errors.append(f"PDF_AUDIT_ERROR:{type(exc).__name__}:{exc}")
    result["errors"] = sorted(set(errors))
    return result, [], [], []


def chay_audit_doc_lap(
    run_root: Path,
    review_evidence_zip: Path,
    manifest_path: Path,
    output_dir: Path,
    pdf_factory: Callable[[Path], object] = _default_pdf_factory,
) -> dict[str, object]:
    if output_dir.exists():
        raise LoiHopDong("AUDIT_OUTPUT_ALREADY_EXISTS")
    manifest = tai_manifest_audit(manifest_path)
    review_summary, candidates = _load_review_evidence(
        review_evidence_zip, str(manifest["expected_review_zip_sha256"])
    )

    temp_dir = output_dir.with_name(output_dir.name + ".tmp")
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    evidence_dir = temp_dir / "evidence"
    evidence_dir.mkdir(parents=True)

    results: list[dict[str, object]] = []
    independent_sets: list[dict[str, object]] = []
    discrepancies: list[dict[str, object]] = []
    diagnostics: list[dict[str, object]] = []
    for contract in manifest["documents"]:
        result, rows, doc_discrepancies, doc_diagnostics = _audit_document(
            run_root, contract, candidates, pdf_factory
        )
        results.append(result)
        if rows:
            independent_sets.append(
                {
                    "source_document_id": contract["source_document_id"],
                    "period_label": contract.get("period_label"),
                    "expected_member_count": contract.get("expected_member_count"),
                    "observed_member_count": len(rows),
                    "rows": rows,
                    "content_reviewed": False,
                    "chain_verified": False,
                    "canonical_eligible": False,
                    "research_eligible": False,
                    "interval_dates_audited": False,
                }
            )
        discrepancies.extend(doc_discrepancies)
        diagnostics.extend(
            {
                "source_document_id": contract["source_document_id"],
                **row,
            }
            for row in doc_diagnostics
        )

    required_failures = sum(
        1
        for result in results
        if result["required"] and result["status"] != "AUDIT_MATCHED"
    )
    matched_count = sum(result["status"] == "AUDIT_MATCHED" for result in results)
    if required_failures:
        batch_status = "INDEPENDENT_AUDIT_FAILED"
    elif matched_count == len(results):
        batch_status = "INDEPENDENT_AUDIT_PASSED"
    else:
        batch_status = "INDEPENDENT_AUDIT_PARTIAL"

    summary = {
        "schema_version": SCHEMA_VERSION,
        "run_id": manifest["run_id"],
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "batch_status": batch_status,
        "document_count": len(results),
        "matched_count": matched_count,
        "required_failure_count": required_failures,
        "discrepancy_count": len(discrepancies),
        "review_evidence_zip_sha256": manifest["expected_review_zip_sha256"],
        "review_batch_status": review_summary.get("batch_status"),
        "content_reviewed": False,
        "chain_verified": False,
        "canonical_eligible": False,
        "research_eligible": False,
        "interval_dates_audited": False,
    }
    files = {
        "manifest_copy.json": manifest,
        "audit_results.json": results,
        "independent_membership_rows.json": independent_sets,
        "discrepancies.json": discrepancies,
        "word_stream_fingerprints.json": diagnostics,
        "batch_summary.json": summary,
    }
    for name, value in files.items():
        _write_json(evidence_dir / name, value)
    hashes = {name: _hash_file(evidence_dir / name) for name in sorted(files)}
    _write_json(evidence_dir / "evidence_hashes.json", hashes)

    zip_path = temp_dir / "independent_audit_metadata_evidence.zip"
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for path in sorted(evidence_dir.glob("*.json")):
            archive.write(path, f"evidence/{path.name}")
    with ZipFile(zip_path) as archive:
        bad = [
            name
            for name in archive.namelist()
            if "original.bin" in name.lower()
            or name.lower().endswith(".pdf")
            or "full_text" in name.lower()
        ]
        if bad:
            raise LoiHopDong(f"AUDIT_ZIP_CONTAINS_FORBIDDEN_CONTENT:{bad}")

    temp_dir.rename(output_dir)
    final_zip = output_dir / "independent_audit_metadata_evidence.zip"
    return {
        **summary,
        "output_dir": str(output_dir),
        "evidence_zip": str(final_zip),
        "evidence_zip_sha256": _hash_file(final_zip),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--review-evidence-zip", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    result = chay_audit_doc_lap(
        args.run_root,
        args.review_evidence_zip,
        args.manifest,
        args.output_dir,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
