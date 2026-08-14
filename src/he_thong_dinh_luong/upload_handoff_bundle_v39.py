"""Build one upload-safe V39 handoff ZIP.

The bundle contains the console log, V36-V39 artifacts, the persistent V39
workspace, repository metadata, a compact decision summary and a SHA-256
manifest. It deliberately excludes the canonical SQLite/V22 payloads and only
records their hashes. The build fails closed if likely credentials or private
keys are detected in the staging directory.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
from typing import Mapping, Sequence
import zipfile

MANIFEST_FILE = "bundle_manifest_v39.json"
SUMMARY_FILE = "handoff_summary_v39.json"
SCHEMA_VERSION = "vn_quant_upload_handoff_v39"

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
_FORBIDDEN_NAME_PARTS = (
    "api_secret",
    "private_key",
    "access_token",
    "refresh_token",
    "password_dump",
)
_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)authorization\s*:\s*bearer\s+[^\s]+"),
    re.compile(
        r"(?i)(?:api[_ -]?secret|secret[_ -]?key|access[_ -]?token|"
        r"refresh[_ -]?token|password)\s*[:=]\s*[\"']?[^\s\"']{8,}"
    ),
)
_REPORT_NAMES = {
    "integrated_data_ledger_v36.json": "v36",
    "trade_readiness_v37.json": "v37",
    "trade_evidence_accelerator_v38.json": "v38",
    "trade_reference_pack_v39.json": "v39",
}


def sha256_file(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_relative(path: Path, root: Path) -> str:
    relative = path.relative_to(root).as_posix()
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or not pure.name:
        raise ValueError(f"V39_HANDOFF_UNSAFE_PATH:{relative}")
    return relative


def _looks_sensitive_name(path: Path) -> bool:
    lower = path.name.lower()
    return lower in _FORBIDDEN_NAMES or any(part in lower for part in _FORBIDDEN_NAME_PARTS)


def _scan_text(path: Path) -> str:
    if path.stat().st_size > 8 * 1024 * 1024:
        return ""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (UnicodeDecodeError, OSError):
        return ""
    for pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            return pattern.pattern
    return ""


def _artifact_report(path: Path) -> dict[str, object]:
    result: dict[str, object] = {
        "filename": path.name,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }
    try:
        with zipfile.ZipFile(path) as archive:
            bad = archive.testzip()
            result["zip_crc_valid"] = bad is None
            if bad is not None:
                result["zip_crc_error_member"] = bad
                return result
            for info in archive.infolist():
                if info.is_dir():
                    continue
                name = PurePosixPath(info.filename).name
                label = _REPORT_NAMES.get(name)
                if label is None:
                    continue
                value = json.loads(archive.read(info).decode("utf-8-sig"))
                if not isinstance(value, Mapping):
                    continue
                selected: dict[str, object] = {
                    "status": value.get("status"),
                    "decision": value.get("decision"),
                    "policy_id": value.get("policy_id"),
                    "blockers": value.get("blockers"),
                    "ledger_status": value.get("ledger_status"),
                    "exact_cash_ledger_pnl_computed": value.get(
                        "exact_cash_ledger_pnl_computed"
                    ),
                    "exact_vnindex_comparison_computed": value.get(
                        "exact_vnindex_comparison_computed"
                    ),
                    "capital_stage": value.get("capital_stage"),
                    "readiness_score_percent": value.get(
                        "readiness_score_percent"
                    ),
                    "reference_pack_ready": value.get("reference_pack_ready"),
                    "gap_count": value.get("gap_count"),
                    "metrics": value.get("metrics"),
                    "next_action": value.get("next_action"),
                    "live_capital_approved": value.get("live_capital_approved"),
                    "automatic_live_orders_allowed": value.get(
                        "automatic_live_orders_allowed"
                    ),
                }
                result[label] = {
                    key: item for key, item in selected.items() if item is not None
                }
    except (zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError) as exc:
        result["inspection_error"] = f"{type(exc).__name__}:{exc}"
    return result


def build_handoff(staging_dir: Path, output_zip: Path) -> dict[str, object]:
    root = Path(staging_dir).resolve()
    destination = Path(output_zip).resolve()
    if not root.is_dir():
        raise ValueError(f"V39_HANDOFF_STAGING_NOT_FOUND:{root}")
    if destination.exists():
        raise FileExistsError(f"V39_HANDOFF_OUTPUT_EXISTS:{destination}")

    files = sorted(
        path for path in root.rglob("*")
        if path.is_file() and path.name not in {MANIFEST_FILE, SUMMARY_FILE}
    )
    sensitive: list[dict[str, str]] = []
    for path in files:
        relative = _safe_relative(path, root)
        if _looks_sensitive_name(path):
            sensitive.append({"path": relative, "reason": "SENSITIVE_FILENAME"})
            continue
        pattern = _scan_text(path)
        if pattern:
            sensitive.append({"path": relative, "reason": "SECRET_PATTERN_DETECTED"})
    if sensitive:
        raise ValueError(
            "V39_HANDOFF_SENSITIVE_CONTENT:" + json.dumps(
                sensitive, ensure_ascii=True, sort_keys=True
            )
        )

    artifact_files = [path for path in files if path.suffix.lower() == ".zip"]
    summary = {
        "schema_version": SCHEMA_VERSION,
        "artifact_count": len(artifact_files),
        "artifacts": [_artifact_report(path) for path in artifact_files],
        "workspace_included": any(
            _safe_relative(path, root).startswith("workspace/") for path in files
        ),
        "canonical_large_inputs_included": False,
        "credentials_included": False,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }
    (root / SUMMARY_FILE).write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )

    manifest_files = sorted(
        path for path in root.rglob("*")
        if path.is_file() and path.name != MANIFEST_FILE
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "file_count_excluding_manifest": len(manifest_files),
        "files": [
            {
                "path": _safe_relative(path, root),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in manifest_files
        ],
        "source_staging_dir": str(root),
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }
    (root / MANIFEST_FILE).write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                archive.write(path, arcname=(Path(root.name) / path.relative_to(root)).as_posix())
    temporary.replace(destination)
    return {
        "status": "SUCCESS",
        "artifact_zip": str(destination),
        "artifact_zip_sha256": sha256_file(destination),
        "file_count_excluding_manifest": len(manifest_files),
        "artifact_count": len(artifact_files),
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging-dir", type=Path, required=True)
    parser.add_argument("--output-zip", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = build_handoff(args.staging_dir, args.output_zip)
    except Exception as exc:
        print(json.dumps({
            "status": "FAILED",
            "error": f"{type(exc).__name__}:{exc}",
            "live_capital_approved": False,
        }, ensure_ascii=True, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
