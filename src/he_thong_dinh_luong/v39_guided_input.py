"""Preflight and plain-language guidance for the persistent V39 workspace."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Sequence

GUIDE_FILE = "BAT_DAU_O_DAY_V39.txt"
COMPACT_FILES = (
    "sector_intervals_import_v39.csv",
    "corporate_action_coverage_import_v39.csv",
    "price_basis_coverage_import_v39.csv",
)
EVENT_FILE = "corporate_action_events_v39.csv"
CONTRACT_FILE = "execution_contract_evidence_v39.json"
OPS_FILE = "workstation_controls_v39.json"
SOURCE_DIR = "source_documents"


def _csv_rows(path: Path) -> int:
    if not path.is_file():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return sum(1 for _ in csv.DictReader(stream))


def _json_object(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    return dict(value) if isinstance(value, dict) else {}


def _source_files(root: Path) -> list[str]:
    source = root / SOURCE_DIR
    if not source.is_dir():
        return []
    return sorted(
        path.relative_to(source).as_posix()
        for path in source.rglob("*")
        if path.is_file() and not path.name.startswith("PUT_")
    )


def _write_guide(root: Path) -> Path:
    guide = root / GUIDE_FILE
    guide.write_text(
        "V39 - BAT DAU O DAY\n"
        "=====================\n\n"
        "Code khong the tu tao du lieu co tham quyen. Viec duy nhat can con nguoi lam la:\n\n"
        "1. Lay tai lieu nguon chinh thuc ve:\n"
        "   - phan nganh theo thoi diem;\n"
        "   - corporate actions;\n"
        "   - price basis/don vi gia va thue co tuc tien mat;\n"
        "   - account sync va position reconciliation (phai mask thong tin nhay cam).\n\n"
        "2. Keo cac file nguon vao thu muc source_documents.\n\n"
        "3. Dien cac file compact trong cung thu muc nay:\n"
        "   - sector_intervals_import_v39.csv\n"
        "   - corporate_action_coverage_import_v39.csv\n"
        "   - corporate_action_events_v39.csv\n"
        "   - price_basis_coverage_import_v39.csv\n"
        "   - execution_contract_evidence_v39.json\n"
        "   - workstation_controls_v39.json\n\n"
        "Khong biet cach dien: upload tai lieu nguon cho AI de AI tao cac file compact.\n"
        "Khong dat API key, password, bearer token hoac private key trong thu muc.\n\n"
        "Sau khi da co tai lieu/du lieu, chay lai duy nhat lenh Git Bash:\n"
        "bash scripts/run_v39_and_make_upload_zip_gitbash.sh\n\n"
        "Neu du lieu du, script se chay exact ledger va tao 1 file UPLOAD_THIS_v39-*.zip.\n",
        encoding="utf-8",
    )
    return guide


def inspect_workspace(workspace_dir: Path) -> dict[str, object]:
    root = Path(workspace_dir).resolve()
    if not root.is_dir():
        return {
            "status": "WORKSPACE_MISSING",
            "workspace_dir": str(root),
            "guide_file": None,
            "compact_rows": {},
            "source_document_count": 0,
            "event_rows": 0,
            "execution_contract_verified": False,
            "account_sync_verified": False,
            "position_reconciliation_verified": False,
        }

    guide = _write_guide(root)
    compact_rows = {name: _csv_rows(root / name) for name in COMPACT_FILES}
    event_rows = _csv_rows(root / EVENT_FILE)
    sources = _source_files(root)
    contract = _json_object(root / CONTRACT_FILE)
    ops = _json_object(root / OPS_FILE)
    no_input = (
        sum(compact_rows.values()) == 0
        and event_rows == 0
        and not sources
        and contract.get("verified") is not True
        and ops.get("account_sync_verified") is not True
        and ops.get("position_reconciliation_verified") is not True
    )
    return {
        "status": "INPUT_EMPTY" if no_input else "INPUT_PRESENT",
        "workspace_dir": str(root),
        "guide_file": str(guide),
        "compact_rows": compact_rows,
        "source_document_count": len(sources),
        "source_documents": sources,
        "event_rows": event_rows,
        "execution_contract_verified": contract.get("verified") is True,
        "account_sync_verified": ops.get("account_sync_verified") is True,
        "position_reconciliation_verified": ops.get("position_reconciliation_verified") is True,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect V39 input readiness")
    parser.add_argument("--workspace-dir", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    print(json.dumps(inspect_workspace(args.workspace_dir), ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
