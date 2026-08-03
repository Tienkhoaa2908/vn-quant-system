"""Collect the small, high-value local evidence files identified by V39 discovery.

This module never treats discovery as authoritative approval. It only copies a
narrow allow-list of candidate files into an upload-safe staging directory so a
reviewer can inspect their actual contents. Canonical V22/SQLite payloads,
credentials and arbitrary user files are deliberately excluded.
"""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
from typing import Mapping, Sequence

SCHEMA_VERSION = "vn_quant_v39_local_evidence_collection_v1"
MANIFEST_FILE = "local_evidence_collection_v39.json"
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024

_ALLOWED_BASENAMES = {
    # Corporate-action inventory and its extraction audit.
    "corporate_action_inventory.csv",
    "corporate_action_inventory.json",
    "corporate_action_inventory.md",
    "corporate_actions_metadata.csv",
    # Price-basis and source/provenance audits.
    "price_basis_audit.csv",
    "price_basis_audit.json",
    "benchmark_ohlc_semantics_audit.json",
    "benchmark_ohlc_semantics_audit.md",
    "benchmark_ohlc_evidence_manifest.json",
    "structured_external_probe_summary.json",
    "raw_coverage_summary.json",
    "raw_coverage_summary.md",
    "execution_provenance.json",
    "input_sha256.txt",
    "cau_hinh.json",
    # Read-only DNSE operations evidence.
    "dnse_portfolio_analysis.zip",
    "manifest.json",
    "portfolio_analysis.csv",
    "portfolio_summary.json",
}

_REQUIRED_PARENT_MARKERS = (
    "04_corporate_action_audit",
    "05_price_basis_audit",
    "benchmark_semantics",
    "m4_tier_a_exec_",
    "dnse-portfolio-live",
)

_FORBIDDEN_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    "credentials.json",
    "client_secret.json",
    "secrets.json",
    "id_rsa",
    "id_ed25519",
}
_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)authorization\s*:\s*bearer\s+[^\s]+"),
    re.compile(
        r"(?i)(?:api[_ -]?secret|secret[_ -]?key|access[_ -]?token|"
        r"refresh[_ -]?token|password)\s*[:=]\s*[\"']?[^\s\"']{8,}"
    ),
)


def _sha(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_rows(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _looks_sensitive(path: Path) -> str | None:
    if path.name.lower() in _FORBIDDEN_NAMES:
        return "FORBIDDEN_FILENAME"
    if path.stat().st_size > 8 * 1024 * 1024:
        return None
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (UnicodeDecodeError, OSError):
        return None
    for pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            return "LIKELY_SECRET_CONTENT"
    return None


def _snapshot_key(path: Path) -> str | None:
    parts = [part for part in path.parts if re.fullmatch(r"20\d{6}_\d{6}", part)]
    return max(parts) if parts else None


def _eligible_path(path: Path) -> bool:
    lower = str(path).replace("/", "\\").lower()
    return (
        path.name.lower() in _ALLOWED_BASENAMES
        and any(marker.lower() in lower for marker in _REQUIRED_PARENT_MARKERS)
    )


def _select(rows: Sequence[Mapping[str, str]]) -> list[tuple[Path, set[str]]]:
    grouped: dict[Path, set[str]] = {}
    for row in rows:
        raw = str(row.get("path") or "").strip()
        if not raw:
            continue
        path = Path(raw)
        if not path.is_file() or not _eligible_path(path):
            continue
        grouped.setdefault(path, set()).add(str(row.get("category") or "UNKNOWN"))

    # Keep only the latest DNSE read-only snapshot. Historical research evidence
    # is retained because its files may cover different dates/symbols.
    snapshot_keys = {
        path: _snapshot_key(path)
        for path in grouped
        if "dnse-portfolio-live" in str(path).lower()
    }
    latest_snapshot = max((value for value in snapshot_keys.values() if value), default=None)
    selected: list[tuple[Path, set[str]]] = []
    for path, categories in grouped.items():
        key = snapshot_keys.get(path)
        if key is not None and key != latest_snapshot:
            continue
        selected.append((path, categories))
    return sorted(selected, key=lambda item: str(item[0]).lower())


def collect_local_evidence(
    *,
    candidates_csv: Path,
    output_dir: Path,
    max_file_bytes: int = MAX_FILE_BYTES,
    max_total_bytes: int = MAX_TOTAL_BYTES,
) -> dict[str, object]:
    source = Path(candidates_csv).resolve()
    destination = Path(output_dir).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"V39_CANDIDATES_MISSING:{source}")
    if destination.exists():
        raise FileExistsError(f"V39_COLLECTION_OUTPUT_EXISTS:{destination}")
    if max_file_bytes <= 0 or max_total_bytes <= 0:
        raise ValueError("V39_COLLECTION_SIZE_LIMIT_INVALID")

    selected = _select(_read_rows(source))
    destination.mkdir(parents=True)
    copied: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []
    total = 0
    for index, (path, categories) in enumerate(selected, start=1):
        size = path.stat().st_size
        if size > max_file_bytes:
            skipped.append({"path": str(path), "reason": "FILE_TOO_LARGE", "size_bytes": size})
            continue
        if total + size > max_total_bytes:
            skipped.append({"path": str(path), "reason": "TOTAL_LIMIT", "size_bytes": size})
            continue
        sensitive = _looks_sensitive(path)
        if sensitive:
            skipped.append({"path": str(path), "reason": sensitive, "size_bytes": size})
            continue

        bucket = "operations" if "dnse-portfolio-live" in str(path).lower() else "research"
        target = destination / bucket / f"{index:03d}_{path.name}"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        digest = _sha(target)
        copied.append({
            "source_path": str(path),
            "collected_path": target.relative_to(destination).as_posix(),
            "categories": sorted(categories),
            "sha256": digest,
            "size_bytes": size,
            "authoritative_verified": False,
        })
        total += size

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "EVIDENCE_COLLECTED" if copied else "NO_ELIGIBLE_EVIDENCE",
        "candidate_csv": str(source),
        "output_dir": str(destination),
        "selected_candidate_count": len(selected),
        "copied_file_count": len(copied),
        "copied_total_bytes": total,
        "copied_files": copied,
        "skipped_files": skipped,
        "authoritative_approval_invented": False,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }
    (destination / MANIFEST_FILE).write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect prioritized V39 local evidence")
    parser.add_argument("--candidates-csv", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = collect_local_evidence(
        candidates_csv=args.candidates_csv,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
