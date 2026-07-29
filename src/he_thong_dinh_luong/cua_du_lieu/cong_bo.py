"""Cong bo candidate nguyen tu va auditor doc lap khong goi builder."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Mapping

from .hop_dong import LoiHopDong, thanh_primitive


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            thanh_primitive(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _fsync_file(path: Path) -> None:
    # Windows can reject fsync on a read-only descriptor. Open the existing file
    # without truncation but with write capability on both supported platforms.
    with path.open("r+b") as handle:
        os.fsync(handle.fileno())


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cong_bo_candidate(
    output_parent: Path,
    run_id: str,
    products: Mapping[str, Any],
    *,
    git_commit: str,
    research_eligible: bool = False,
) -> Path:
    if not run_id.strip() or len(git_commit) != 40:
        raise LoiHopDong("run_id/git_commit khong hop le")
    if research_eligible:
        raise LoiHopDong("foundation package khong duoc research_eligible")
    destination = output_parent / run_id
    if destination.exists():
        raise FileExistsError(destination)
    output_parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{run_id}.", dir=output_parent))
    try:
        manifest_products: list[dict[str, object]] = []
        for filename in sorted(products):
            if Path(filename).name != filename or filename == "manifest.json":
                raise LoiHopDong("ten product khong hop le")
            path = staging / filename
            data = _json_bytes(products[filename])
            path.write_bytes(data)
            _fsync_file(path)
            manifest_products.append(
                {
                    "filename": filename,
                    "byte_size": len(data),
                    "sha256": sha256(data).hexdigest(),
                }
            )
        manifest = {
            "contract": "data_gate_foundation_v1",
            "git_commit": git_commit,
            "products": manifest_products,
            "research_eligible": False,
            "run_id": run_id,
        }
        manifest_path = staging / "manifest.json"
        manifest_path.write_bytes(_json_bytes(manifest))
        _fsync_file(manifest_path)
        os.replace(staging, destination)
        return destination
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


@dataclass(frozen=True, slots=True)
class KetQuaKiemToan:
    passed: bool
    errors: tuple[str, ...]
    manifest_sha256: str | None


def kiem_toan_cong_bo_doc_lap(directory: Path) -> KetQuaKiemToan:
    errors: list[str] = []
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        return KetQuaKiemToan(False, ("MISSING_MANIFEST",), None)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return KetQuaKiemToan(
            False,
            ("INVALID_MANIFEST",),
            _hash_file(manifest_path),
        )
    if manifest.get("research_eligible") is not False:
        errors.append("FOUNDATION_RESEARCH_ELIGIBLE_INVALID")
    products = manifest.get("products")
    if not isinstance(products, list):
        errors.append("INVALID_PRODUCT_LIST")
        products = []
    filenames = [p.get("filename") for p in products if isinstance(p, dict)]
    if filenames != sorted(filenames) or len(filenames) != len(set(filenames)):
        errors.append("NONDETERMINISTIC_PRODUCT_ORDER")
    expected_files = {"manifest.json"}
    for item in products:
        if not isinstance(item, dict):
            errors.append("INVALID_PRODUCT_ROW")
            continue
        filename = item.get("filename")
        if not isinstance(filename, str):
            errors.append("INVALID_PRODUCT_FILENAME")
            continue
        expected_files.add(filename)
        path = directory / filename
        if not path.is_file():
            errors.append(f"MISSING_PRODUCT:{filename}")
            continue
        if path.stat().st_size != item.get("byte_size"):
            errors.append(f"SIZE_MISMATCH:{filename}")
        if _hash_file(path) != item.get("sha256"):
            errors.append(f"HASH_MISMATCH:{filename}")
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            errors.append(f"INVALID_JSON:{filename}")
    actual_files = {p.name for p in directory.iterdir() if p.is_file()}
    if actual_files != expected_files:
        errors.append("UNDECLARED_OR_MISSING_FILES")
    return KetQuaKiemToan(
        not errors,
        tuple(sorted(errors)),
        _hash_file(manifest_path),
    )
