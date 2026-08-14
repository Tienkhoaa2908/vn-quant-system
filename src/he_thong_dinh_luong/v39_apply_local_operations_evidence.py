"""Apply strictly verified local DNSE operations evidence to the V39 workspace.

Only the read-only account-sync control can be upgraded by this module. A
portfolio snapshot is not, by itself, an independent position reconciliation,
so that control remains fail-closed. No credentials, account identifiers,
orders, or live-capital permissions are written.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO, StringIO
import json
import math
from pathlib import Path
import re
import shutil
from typing import Mapping, Sequence
from zipfile import BadZipFile, ZipFile

SCHEMA_VERSION = "vn_quant_v39_apply_local_operations_evidence_v1"
COLLECTION_MANIFEST = "local_evidence_collection_v39.json"
OPS_RELATIVE_ZIP = Path("operations") / "001_dnse_portfolio_analysis.zip"
WORKSTATION_FILE = "workstation_controls_v39.json"
SOURCE_DIR = "source_documents"
EVIDENCE_FILENAME = "dnse_account_sync_evidence_v39.zip"
AUDIT_FILE = "local_operations_evidence_application_v39.json"
_MASKED_ACCOUNT_RE = re.compile(r"^\*{4,}[0-9]{4}$")


def _sha_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _read_json_bytes(data: bytes, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"V39_OPERATIONS_JSON_INVALID:{label}") from exc
    if not isinstance(value, Mapping):
        raise ValueError(f"V39_OPERATIONS_JSON_NOT_OBJECT:{label}")
    return value


def _finite_nonnegative(value: object, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"V39_OPERATIONS_NUMBER_INVALID:{label}") from exc
    if not math.isfinite(number) or number < 0.0:
        raise ValueError(f"V39_OPERATIONS_NUMBER_INVALID:{label}")
    return number


def _verify_collection_manifest(collected_dir: Path, evidence: Path) -> Mapping[str, object]:
    manifest_path = collected_dir / COLLECTION_MANIFEST
    if not manifest_path.is_file():
        raise FileNotFoundError(f"V39_COLLECTION_MANIFEST_MISSING:{manifest_path}")
    manifest = _read_json_bytes(manifest_path.read_bytes(), COLLECTION_MANIFEST)
    copied = manifest.get("copied_files")
    if manifest.get("status") != "EVIDENCE_COLLECTED" or not isinstance(copied, list):
        raise ValueError("V39_COLLECTION_MANIFEST_NOT_SUCCESS")
    expected_rel = OPS_RELATIVE_ZIP.as_posix()
    matches = [
        row for row in copied
        if isinstance(row, Mapping) and str(row.get("collected_path") or "") == expected_rel
    ]
    if len(matches) != 1:
        raise ValueError("V39_ACCOUNT_SYNC_EVIDENCE_NOT_UNIQUE")
    row = matches[0]
    data = evidence.read_bytes()
    if _sha_bytes(data) != str(row.get("sha256") or ""):
        raise ValueError("V39_ACCOUNT_SYNC_COLLECTION_HASH_MISMATCH")
    if len(data) != int(row.get("size_bytes") or -1):
        raise ValueError("V39_ACCOUNT_SYNC_COLLECTION_SIZE_MISMATCH")
    return manifest


def _verify_nested_snapshot(data: bytes) -> dict[str, object]:
    try:
        with ZipFile(BytesIO(data)) as archive:
            bad = archive.testzip()
            if bad is not None:
                raise ValueError(f"V39_ACCOUNT_SYNC_ZIP_CRC_FAILED:{bad}")
            required = {
                "manifest.json",
                "portfolio_summary.json",
                "portfolio_analysis.csv",
            }
            names = set(archive.namelist())
            missing = sorted(required - names)
            if missing:
                raise ValueError("V39_ACCOUNT_SYNC_ZIP_MEMBER_MISSING:" + ",".join(missing))
            manifest_bytes = archive.read("manifest.json")
            manifest = _read_json_bytes(manifest_bytes, "manifest.json")
            summary = _read_json_bytes(archive.read("portfolio_summary.json"), "portfolio_summary.json")
            analysis_bytes = archive.read("portfolio_analysis.csv")

            files = manifest.get("files")
            if not isinstance(files, Mapping):
                raise ValueError("V39_ACCOUNT_SYNC_NESTED_MANIFEST_FILES_INVALID")
            for name in required - {"manifest.json"}:
                row = files.get(name)
                if not isinstance(row, Mapping):
                    raise ValueError(f"V39_ACCOUNT_SYNC_NESTED_HASH_MISSING:{name}")
                payload = archive.read(name)
                if _sha_bytes(payload) != str(row.get("sha256") or ""):
                    raise ValueError(f"V39_ACCOUNT_SYNC_NESTED_HASH_MISMATCH:{name}")
                if len(payload) != int(row.get("size") or -1):
                    raise ValueError(f"V39_ACCOUNT_SYNC_NESTED_SIZE_MISMATCH:{name}")
    except BadZipFile as exc:
        raise ValueError("V39_ACCOUNT_SYNC_ZIP_INVALID") from exc

    masked = str(manifest.get("masked_account") or "")
    controls_ok = bool(
        manifest.get("status") == "SUCCESS"
        and manifest.get("read_only") is True
        and manifest.get("credentials_recorded") is False
        and manifest.get("trading_token_used") is False
        and _MASKED_ACCOUNT_RE.fullmatch(masked)
    )
    if not controls_ok:
        raise ValueError("V39_ACCOUNT_SYNC_MANIFEST_CONTROL_FAILED")
    if not (
        summary.get("status") == "PASS_SETTLED_CASH"
        and summary.get("source") == "dnse_openapi_read_only"
        and summary.get("read_only") is True
        and summary.get("trading_token_used") is False
        and str(summary.get("masked_account") or "") == masked
        and str(summary.get("as_of") or "") == str(manifest.get("as_of") or "")
    ):
        raise ValueError("V39_ACCOUNT_SYNC_SUMMARY_CONTROL_FAILED")

    try:
        text = analysis_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("V39_ACCOUNT_SYNC_ANALYSIS_ENCODING_INVALID") from exc
    rows = list(csv.DictReader(StringIO(text, newline="")))
    if int(summary.get("position_count") or -1) != len(rows):
        raise ValueError("V39_ACCOUNT_SYNC_POSITION_COUNT_MISMATCH")
    market_value = sum(
        _finite_nonnegative(row.get("market_value_vnd"), "market_value_vnd")
        for row in rows
    )
    summary_market_value = _finite_nonnegative(
        summary.get("stock_market_value_vnd"), "stock_market_value_vnd"
    )
    if abs(market_value - summary_market_value) > 1.0:
        raise ValueError("V39_ACCOUNT_SYNC_MARKET_VALUE_MISMATCH")
    for key in (
        "total_cash_vnd",
        "withdrawable_cash_vnd",
        "safe_planner_cash_vnd",
        "net_liquidation_value_vnd",
        "available_cash_vnd",
    ):
        _finite_nonnegative(summary.get(key), key)

    return {
        "as_of": str(manifest.get("as_of") or ""),
        "masked_account": masked,
        "position_count": len(rows),
        "stock_market_value_vnd": summary_market_value,
        "nested_manifest_sha256": _sha_bytes(manifest_bytes),
    }


def apply_local_operations_evidence(*, workspace_dir: Path, collected_dir: Path) -> dict[str, object]:
    workspace = Path(workspace_dir).resolve()
    collected = Path(collected_dir).resolve()
    ops_path = workspace / WORKSTATION_FILE
    evidence = collected / OPS_RELATIVE_ZIP
    if not workspace.is_dir():
        raise FileNotFoundError(f"V39_WORKSPACE_MISSING:{workspace}")
    if not ops_path.is_file():
        raise FileNotFoundError(f"V39_WORKSTATION_CONTROLS_MISSING:{ops_path}")
    if not evidence.is_file():
        raise FileNotFoundError(f"V39_ACCOUNT_SYNC_EVIDENCE_MISSING:{evidence}")

    _verify_collection_manifest(collected, evidence)
    evidence_bytes = evidence.read_bytes()
    snapshot = _verify_nested_snapshot(evidence_bytes)
    evidence_sha = _sha_bytes(evidence_bytes)

    current = _read_json_bytes(ops_path.read_bytes(), WORKSTATION_FILE)
    updated = dict(current)
    source_dir = workspace / SOURCE_DIR
    source_dir.mkdir(exist_ok=True)
    target = source_dir / EVIDENCE_FILENAME
    if target.exists() and _sha_bytes(target.read_bytes()) != evidence_sha:
        raise FileExistsError(f"V39_ACCOUNT_SYNC_EVIDENCE_CONFLICT:{target}")
    if not target.exists():
        shutil.copyfile(evidence, target)

    document_id = "dnse-read-only-account-sync-" + re.sub(
        r"[^0-9]", "", str(snapshot["as_of"])
    )[:14]
    updated.update({
        "account_sync_verified": True,
        "account_sync_evidence_document_id": document_id,
        "account_sync_evidence_filename": EVIDENCE_FILENAME,
        "account_sync_evidence_sha256": evidence_sha,
        # A broker snapshot is not an independent reconciliation against the
        # local ledger. Preserve the prior value and evidence fields.
        "position_reconciliation_verified": current.get("position_reconciliation_verified") is True,
    })
    updated.setdefault("reviewer", "")
    updated.setdefault("reviewed_at", "")

    temporary = ops_path.with_suffix(ops_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(updated, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(ops_path)

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "ACCOUNT_SYNC_APPLIED",
        "workspace_dir": str(workspace),
        "source_evidence_filename": EVIDENCE_FILENAME,
        "source_evidence_sha256": evidence_sha,
        "account_sync_verified": True,
        "position_reconciliation_verified": updated.get("position_reconciliation_verified") is True,
        "position_reconciliation_reason": "BROKER_SNAPSHOT_IS_NOT_INDEPENDENT_LEDGER_RECONCILIATION",
        "snapshot": snapshot,
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "authoritative_sector_approval_invented": False,
        "authoritative_corporate_action_approval_invented": False,
        "price_basis_approval_invented": False,
        "live_capital_approved": False,
        "automatic_live_orders_allowed": False,
    }
    (workspace / AUDIT_FILE).write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apply verified DNSE account-sync evidence to V39")
    parser.add_argument("--workspace-dir", required=True, type=Path)
    parser.add_argument("--collected-dir", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = apply_local_operations_evidence(
        workspace_dir=args.workspace_dir,
        collected_dir=args.collected_dir,
    )
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
