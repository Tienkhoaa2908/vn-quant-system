"""Lưu các sản phẩm dữ liệu theo cách không ghi đè."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping


def _chuyen_json(gia_tri: Any) -> Any:
    if isinstance(gia_tri, (datetime, date)):
        return gia_tri.isoformat()
    if hasattr(gia_tri, "isoformat"):
        return gia_tri.isoformat()
    if hasattr(gia_tri, "item"):
        return gia_tri.item()
    return str(gia_tri)


class kho_luu_tru:
    def __init__(self, thu_muc_goc: str | Path) -> None:
        self.thu_muc_goc = Path(thu_muc_goc)

    def duong_dan(self, nhom: str, ma_lan_chay: str, ten_tep: str) -> Path:
        return self.thu_muc_goc / nhom / ma_lan_chay / ten_tep

    def _ghi_bat_bien(self, duong_dan: Path, noi_dung: bytes) -> str:
        duong_dan.parent.mkdir(parents=True, exist_ok=True)
        if duong_dan.exists():
            raise FileExistsError(f"Khong duoc ghi de tep da ton tai: {duong_dan}")
        tep_tam = duong_dan.with_name(f".{duong_dan.name}.{uuid.uuid4().hex}.tmp")
        try:
            with tep_tam.open("xb") as tep:
                tep.write(noi_dung)
                tep.flush()
                os.fsync(tep.fileno())
            os.link(tep_tam, duong_dan)
        finally:
            tep_tam.unlink(missing_ok=True)
        return hashlib.sha256(noi_dung).hexdigest()

    def ghi_json(
        self, nhom: str, ma_lan_chay: str, ten_tep: str, du_lieu: Any
    ) -> tuple[Path, str]:
        duong_dan = self.duong_dan(nhom, ma_lan_chay, ten_tep)
        noi_dung = (
            json.dumps(
                du_lieu,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                default=_chuyen_json,
            )
            + "\n"
        ).encode("utf-8")
        return duong_dan, self._ghi_bat_bien(duong_dan, noi_dung)

    def ghi_csv(
        self,
        nhom: str,
        ma_lan_chay: str,
        ten_tep: str,
        cac_dong: Iterable[Mapping[str, Any]],
        cac_cot: tuple[str, ...],
    ) -> tuple[Path, str]:
        from io import StringIO

        bo_nho = StringIO(newline="")
        bo_ghi = csv.DictWriter(bo_nho, fieldnames=cac_cot, lineterminator="\n")
        bo_ghi.writeheader()
        for dong in cac_dong:
            bo_ghi.writerow({cot: dong.get(cot, "") for cot in cac_cot})
        noi_dung = bo_nho.getvalue().encode("utf-8")
        duong_dan = self.duong_dan(nhom, ma_lan_chay, ten_tep)
        return duong_dan, self._ghi_bat_bien(duong_dan, noi_dung)
