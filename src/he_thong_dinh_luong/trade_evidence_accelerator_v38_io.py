"""I/O and bundle-verification helpers for V38."""
from __future__ import annotations

import csv
from hashlib import sha256
import io
import json
from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence
import zipfile


def sha256_file(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_basename(name: str) -> str:
    normalized = str(name).replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or not path.name:
        raise ValueError(f"V38_UNSAFE_ZIP_MEMBER:{name}")
    return path.name


def read_csv_bytes(payload: bytes) -> list[dict[str, str]]:
    with io.StringIO(payload.decode("utf-8-sig"), newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def write_csv(path: Path, rows: Sequence[Mapping[str, object]], fields: Sequence[str]) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    Path(path).write_text(buffer.getvalue(), encoding="utf-8-sig", newline="")


def write_json(path: Path, value: object) -> None:
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def load_verified_bundle(
    path: Path,
    *,
    manifest_name: str,
    report_name: str,
    expected_sha256: str = "",
) -> dict[str, object]:
    source = Path(path).resolve()
    if not source.is_file():
        raise ValueError(f"V38_ARTIFACT_NOT_FOUND:{source}")
    actual = sha256_file(source)
    if expected_sha256 and actual != expected_sha256:
        raise ValueError(f"V38_ARTIFACT_SHA256_MISMATCH:{actual}")
    members: dict[str, bytes] = {}
    with zipfile.ZipFile(source) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"V38_ZIP_CRC_ERROR:{bad}")
        for info in archive.infolist():
            if info.is_dir():
                continue
            basename = safe_basename(info.filename)
            if basename in members:
                raise ValueError(f"V38_DUPLICATE_MEMBER:{basename}")
            members[basename] = archive.read(info)
    for required in (manifest_name, report_name):
        if required not in members:
            raise ValueError(f"V38_REQUIRED_MEMBER_MISSING:{required}")
    manifest = json.loads(members[manifest_name].decode("utf-8-sig"))
    if manifest.get("status") != "SUCCESS":
        raise ValueError(f"V38_MANIFEST_NOT_SUCCESS:{manifest_name}")
    verified = 0
    for item in manifest.get("files", []):
        basename = safe_basename(str(item.get("path") or ""))
        payload = members.get(basename)
        if payload is None:
            raise ValueError(f"V38_MANIFEST_MEMBER_MISSING:{basename}")
        if len(payload) != int(item.get("size_bytes", -1)):
            raise ValueError(f"V38_MANIFEST_SIZE_MISMATCH:{basename}")
        if sha256(payload).hexdigest() != str(item.get("sha256") or ""):
            raise ValueError(f"V38_MANIFEST_HASH_MISMATCH:{basename}")
        verified += 1
    report = json.loads(members[report_name].decode("utf-8-sig"))
    if report.get("status") != "SUCCESS":
        raise ValueError(f"V38_REPORT_NOT_SUCCESS:{report_name}")
    return {
        "path": str(source),
        "sha256": actual,
        "members": members,
        "report": report,
        "manifest_entry_count": verified,
    }
