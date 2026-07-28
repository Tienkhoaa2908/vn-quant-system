"""Dieu phoi tai OHLCV VN100 hang loat, co tiep tuc va kiem tra hash.

Mo-dun nay chi dieu phoi mo-dun du lieu Moc 1 hien co. Du lieu that phai nam
ngoai kho ma; kiem thu phai truyen nguon gia va khong goi mang.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from .du_lieu_thi_truong.nguon_vnstock import nguon_vnstock
from .du_lieu_thi_truong.quy_trinh import chay_quy_trinh, lam_sach_loi
from .du_lieu_thi_truong.tham_so_vnstock import SO_NEN_MAC_DINH, so_nguyen_duong


class NguonCoTheTai(Protocol):
    ten_nguon: str
    phien_ban: str

    def lay_du_lieu(self, ma: str, ngay_bat_dau: str, ngay_ket_thuc: str) -> Any:
        """Lay mot bang du lieu nguon."""


@dataclass(frozen=True)
class CauHinhTaiVN100:
    danh_sach_ma: Path
    ngay_bat_dau: str
    ngay_ket_thuc: str
    ngay_kiem_tra: date
    thu_muc_du_lieu: Path
    ma_lan_chay: str
    so_nen: int = SO_NEN_MAC_DINH
    so_lan_thu_toi_da: int = 3
    yeu_cau_moi_phut: int = 18
    tiep_tuc: bool = True

    def __post_init__(self) -> None:
        if self.ngay_bat_dau > self.ngay_ket_thuc:
            raise ValueError("ngay_bat_dau phai khong sau ngay_ket_thuc")
        if self.ngay_ket_thuc > self.ngay_kiem_tra.isoformat():
            raise ValueError("ngay_ket_thuc khong duoc sau ngay_kiem_tra")
        if self.so_nen <= 0 or self.so_lan_thu_toi_da <= 0:
            raise ValueError("so_nen va so_lan_thu_toi_da phai duong")
        if self.yeu_cau_moi_phut <= 0:
            raise ValueError("yeu_cau_moi_phut phai duong")
        if not self.ma_lan_chay.strip():
            raise ValueError("ma_lan_chay khong duoc rong")


class NguonGioiHanTocDo:
    """Boc nguon de gioi han moi lan goi, ke ca lan thu lai."""

    def __init__(
        self,
        nguon: NguonCoTheTai,
        *,
        yeu_cau_moi_phut: int,
        ham_dong_ho: Callable[[], float] = time.monotonic,
        ham_cho: Callable[[float], None] = time.sleep,
    ) -> None:
        if yeu_cau_moi_phut <= 0:
            raise ValueError("yeu_cau_moi_phut phai duong")
        self._nguon = nguon
        self.ten_nguon = nguon.ten_nguon
        self.phien_ban = nguon.phien_ban
        self._khoang_cach = 60.0 / float(yeu_cau_moi_phut)
        self._ham_dong_ho = ham_dong_ho
        self._ham_cho = ham_cho
        self._lan_goi_truoc: float | None = None

    def lay_du_lieu(self, ma: str, ngay_bat_dau: str, ngay_ket_thuc: str) -> Any:
        bay_gio = self._ham_dong_ho()
        if self._lan_goi_truoc is not None:
            con_lai = self._khoang_cach - (bay_gio - self._lan_goi_truoc)
            if con_lai > 0:
                self._ham_cho(con_lai)
                bay_gio = self._ham_dong_ho()
        self._lan_goi_truoc = bay_gio
        return self._nguon.lay_du_lieu(ma, ngay_bat_dau, ngay_ket_thuc)


def _sha256(duong_dan: Path) -> str:
    ma_bam = hashlib.sha256()
    with duong_dan.open("rb") as tep:
        for khoi in iter(lambda: tep.read(1024 * 1024), b""):
            ma_bam.update(khoi)
    return ma_bam.hexdigest()


def _ghi_json_nguyen_tu(duong_dan: Path, noi_dung: Mapping[str, Any]) -> None:
    duong_dan.parent.mkdir(parents=True, exist_ok=True)
    tep_tam = duong_dan.with_name(f".{duong_dan.name}.{uuid.uuid4().hex}.tmp")
    try:
        with tep_tam.open("w", encoding="utf-8", newline="\n") as tep:
            json.dump(noi_dung, tep, ensure_ascii=False, indent=2, sort_keys=True)
            tep.write("\n")
            tep.flush()
            os.fsync(tep.fileno())
        os.replace(tep_tam, duong_dan)
    finally:
        if tep_tam.exists():
            tep_tam.unlink()


def doc_danh_sach_ma(duong_dan: Path) -> tuple[str, ...]:
    with duong_dan.open(encoding="utf-8-sig", newline="") as tep:
        bo_doc = csv.DictReader(tep)
        if bo_doc.fieldnames is None or "ma" not in bo_doc.fieldnames:
            raise ValueError("CSV danh sach ma phai co cot 'ma'")
        cac_ma = tuple(
            dict.fromkeys(
                str(dong.get("ma", "")).strip().upper()
                for dong in bo_doc
                if str(dong.get("ma", "")).strip()
            )
        )
    if not cac_ma:
        raise ValueError("CSV danh sach ma khong co ma hop le")
    return cac_ma


def _doc_checkpoint(duong_dan: Path) -> dict[str, Any]:
    if not duong_dan.exists():
        return {"schema_version": "1.0", "trang_thai_tung_ma": {}}
    noi_dung = json.loads(duong_dan.read_text(encoding="utf-8"))
    if not isinstance(noi_dung, dict):
        raise ValueError("checkpoint phai la JSON object")
    noi_dung.setdefault("schema_version", "1.0")
    noi_dung.setdefault("trang_thai_tung_ma", {})
    if not isinstance(noi_dung["trang_thai_tung_ma"], dict):
        raise ValueError("checkpoint.trang_thai_tung_ma phai la object")
    return noi_dung


def _hash_checkpoint_hop_le(muc: Mapping[str, Any]) -> bool:
    if muc.get("trang_thai") != "thanh_cong":
        return False
    duong_dan = muc.get("duong_dan_tho")
    ma_sha256 = muc.get("ma_sha256")
    if not duong_dan or not ma_sha256:
        return False
    tep = Path(str(duong_dan))
    return tep.is_file() and _sha256(tep) == str(ma_sha256)


def _ghi_loi_jsonl(duong_dan: Path, noi_dung: Mapping[str, Any]) -> None:
    duong_dan.parent.mkdir(parents=True, exist_ok=True)
    with duong_dan.open("a", encoding="utf-8", newline="\n") as tep:
        tep.write(json.dumps(noi_dung, ensure_ascii=False, sort_keys=True) + "\n")
        tep.flush()
        os.fsync(tep.fileno())


def chay_tai_hang_loat(
    cau_hinh: CauHinhTaiVN100,
    *,
    ham_tao_nguon: Callable[[int], NguonCoTheTai] = lambda so_nen: nguon_vnstock(
        so_nen=so_nen
    ),
    ham_chay_quy_trinh: Callable[..., Any] = chay_quy_trinh,
    ham_dong_ho: Callable[[], float] = time.monotonic,
    ham_cho: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Tai doc lap theo ma; loi mot ma khong chan cac ma con lai."""

    cac_ma = doc_danh_sach_ma(cau_hinh.danh_sach_ma)
    thu_muc_dieu_phoi = (
        cau_hinh.thu_muc_du_lieu / "dieu_phoi_vn100" / cau_hinh.ma_lan_chay
    )
    checkpoint_path = thu_muc_dieu_phoi / "checkpoint.json"
    error_path = thu_muc_dieu_phoi / "loi_tung_ma.jsonl"
    summary_path = thu_muc_dieu_phoi / "tong_hop.json"
    checkpoint = _doc_checkpoint(checkpoint_path)
    checkpoint.update(
        {
            "schema_version": "1.0",
            "ma_lan_chay": cau_hinh.ma_lan_chay,
            "ngay_bat_dau": cau_hinh.ngay_bat_dau,
            "ngay_ket_thuc": cau_hinh.ngay_ket_thuc,
            "danh_sach_ma_sha256": _sha256(cau_hinh.danh_sach_ma),
            "nguon_yeu_cau": "vnstock_kbs",
            "phien_ban_yeu_cau": "4.0.4",
            "cap_nhat_luc": datetime.now(timezone.utc).isoformat(),
        }
    )
    trang_thai_tung_ma: dict[str, Any] = checkpoint["trang_thai_tung_ma"]

    nguon = NguonGioiHanTocDo(
        ham_tao_nguon(cau_hinh.so_nen),
        yeu_cau_moi_phut=cau_hinh.yeu_cau_moi_phut,
        ham_dong_ho=ham_dong_ho,
        ham_cho=ham_cho,
    )
    bo_qua = 0
    thanh_cong = 0
    that_bai = 0

    for ma in cac_ma:
        muc_cu = trang_thai_tung_ma.get(ma, {})
        if (
            cau_hinh.tiep_tuc
            and isinstance(muc_cu, Mapping)
            and _hash_checkpoint_hop_le(muc_cu)
        ):
            bo_qua += 1
            continue

        lan_tai = int(muc_cu.get("lan_tai", 0)) + 1 if isinstance(muc_cu, Mapping) else 1
        thoi_diem_bat_dau = datetime.now(timezone.utc).isoformat()
        try:
            ket_qua = ham_chay_quy_trinh(
                nguon,
                (ma,),
                cau_hinh.ngay_bat_dau,
                cau_hinh.ngay_ket_thuc,
                cau_hinh.thu_muc_du_lieu,
                cau_hinh.ngay_kiem_tra,
                so_lan_thu_toi_da=cau_hinh.so_lan_thu_toi_da,
                ham_cho=ham_cho,
                ma_lan_chay=f"{cau_hinh.ma_lan_chay}_{ma}_{lan_tai:03d}",
                cau_hinh_lan_chay={
                    "loai_lan_chay": "vn100_hang_loat",
                    "ma_lan_chay_cha": cau_hinh.ma_lan_chay,
                    "so_nen_yeu_cau": cau_hinh.so_nen,
                    "yeu_cau_moi_phut": cau_hinh.yeu_cau_moi_phut,
                },
            )
            trang_thai = ket_qua.trang_thai_tung_ma[0]
            muc = trang_thai.thanh_tu_dien()
            if trang_thai.trang_thai != "thanh_cong":
                raise RuntimeError(trang_thai.loi or f"Tai {ma} that bai")
            if not trang_thai.duong_dan_tho or not trang_thai.ma_sha256:
                raise RuntimeError(f"Tai {ma} thanh cong nhung thieu duong dan/hash raw")
            ma_bam_thuc_te = _sha256(Path(trang_thai.duong_dan_tho))
            if ma_bam_thuc_te != trang_thai.ma_sha256:
                raise RuntimeError(
                    f"Hash raw {ma} khong khop: "
                    f"{ma_bam_thuc_te} != {trang_thai.ma_sha256}"
                )
            muc.update(
                {
                    "trang_thai": "thanh_cong",
                    "lan_tai": lan_tai,
                    "ma_sha256_da_kiem_tra_lai": ma_bam_thuc_te,
                    "thoi_diem_bat_dau": thoi_diem_bat_dau,
                    "thoi_diem_ket_thuc": datetime.now(timezone.utc).isoformat(),
                }
            )
            trang_thai_tung_ma[ma] = muc
            thanh_cong += 1
        except Exception as exc:
            noi_dung_loi = lam_sach_loi(exc)
            muc = {
                "ma": ma,
                "trang_thai": "that_bai",
                "lan_tai": lan_tai,
                "thoi_diem_bat_dau": thoi_diem_bat_dau,
                "thoi_diem_ket_thuc": datetime.now(timezone.utc).isoformat(),
                "loi": noi_dung_loi,
            }
            trang_thai_tung_ma[ma] = muc
            _ghi_loi_jsonl(error_path, muc)
            that_bai += 1
        finally:
            checkpoint["cap_nhat_luc"] = datetime.now(timezone.utc).isoformat()
            _ghi_json_nguyen_tu(checkpoint_path, checkpoint)

    tong_hop = {
        "schema_version": "1.0",
        "ma_lan_chay": cau_hinh.ma_lan_chay,
        "nguon": nguon.ten_nguon,
        "phien_ban": nguon.phien_ban,
        "tong_so_ma": len(cac_ma),
        "tai_thanh_cong_trong_lan_nay": thanh_cong,
        "that_bai_trong_lan_nay": that_bai,
        "bo_qua_do_hash_checkpoint_hop_le": bo_qua,
        "so_ma_checkpoint_thanh_cong": sum(
            1
            for muc in trang_thai_tung_ma.values()
            if isinstance(muc, Mapping) and _hash_checkpoint_hop_le(muc)
        ),
        "checkpoint": str(checkpoint_path),
        "nhat_ky_loi": str(error_path),
        "ket_thuc_luc": datetime.now(timezone.utc).isoformat(),
    }
    _ghi_json_nguyen_tu(summary_path, tong_hop)
    return tong_hop


def tao_bo_phan_tich() -> argparse.ArgumentParser:
    bo = argparse.ArgumentParser(
        description="Tai OHLCV cho hop ma VN100 bang vnstock 4.0.4/KBS.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    bo.add_argument("--danh-sach-ma", type=Path, required=True)
    bo.add_argument("--ngay-bat-dau", required=True)
    bo.add_argument("--ngay-ket-thuc", required=True)
    bo.add_argument("--ngay-kiem-tra")
    bo.add_argument("--thu-muc-du-lieu", type=Path, required=True)
    bo.add_argument("--ma-lan-chay")
    bo.add_argument("--so-nen", type=so_nguyen_duong, default=SO_NEN_MAC_DINH)
    bo.add_argument("--so-lan-thu-toi-da", type=so_nguyen_duong, default=3)
    bo.add_argument("--yeu-cau-moi-phut", type=so_nguyen_duong, default=18)
    bo.add_argument("--khong-tiep-tuc", action="store_true")
    return bo


def chay() -> int:
    tham_so = tao_bo_phan_tich().parse_args()
    ngay_kiem_tra = (
        date.fromisoformat(tham_so.ngay_kiem_tra)
        if tham_so.ngay_kiem_tra
        else date.today()
    )
    ma_lan_chay = tham_so.ma_lan_chay or (
        "vn100_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    cau_hinh = CauHinhTaiVN100(
        danh_sach_ma=tham_so.danh_sach_ma,
        ngay_bat_dau=date.fromisoformat(tham_so.ngay_bat_dau).isoformat(),
        ngay_ket_thuc=date.fromisoformat(tham_so.ngay_ket_thuc).isoformat(),
        ngay_kiem_tra=ngay_kiem_tra,
        thu_muc_du_lieu=tham_so.thu_muc_du_lieu,
        ma_lan_chay=ma_lan_chay,
        so_nen=tham_so.so_nen,
        so_lan_thu_toi_da=tham_so.so_lan_thu_toi_da,
        yeu_cau_moi_phut=tham_so.yeu_cau_moi_phut,
        tiep_tuc=not tham_so.khong_tiep_tuc,
    )
    ket_qua = chay_tai_hang_loat(cau_hinh)
    print(json.dumps(ket_qua, ensure_ascii=False, indent=2, sort_keys=True))
    return 2 if ket_qua["that_bai_trong_lan_nay"] else 0


if __name__ == "__main__":
    raise SystemExit(chay())
