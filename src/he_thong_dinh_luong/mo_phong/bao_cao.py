"""Cong bo san pham Moc 3 theo cach bat bien va co rollback."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from io import StringIO
from pathlib import Path
from typing import Any, Iterable, Mapping
from uuid import uuid4

from .chi_so import tinh_chi_so
from .mo_hinh import ket_qua_mo_phong

CAC_COT_LENH = (
    "ma_lenh", "ngay_tin_hieu", "ngay_thuc_thi", "ma", "chieu",
    "so_luong_yeu_cau", "so_luong", "so_luong_bi_giam", "ly_do_giam",
    "loai_lenh", "trang_thai", "ly_do_tu_choi_hoac_het_han",
)
CAC_COT_KHOP_LENH = (
    "ma_lenh", "ma", "ngay_khop", "chieu", "so_luong_yeu_cau", "so_luong",
    "so_luong_bi_giam", "ly_do_giam", "gia_mo_cua", "gia_khop",
    "gia_tri_giao_dich", "phi", "thue", "chi_phi_truot_gia",
)
CAC_COT_VI_THE = (
    "ngay", "ma", "so_luong", "gia_von", "gia_dong_cua",
    "gia_tri_thi_truong", "lai_lo_chua_thuc_hien",
)
CAC_COT_SO_CAI = (
    "ngay", "tien_mat_dau_ngay", "dong_tien_su_kien", "co_tuc_tien_mat",
    "co_tuc_tien_mat_luy_ke", "tien_mua", "tien_ban", "phi", "phi_mua",
    "phi_ban", "phi_mua_luy_ke", "phi_ban_luy_ke", "thue", "thue_ban",
    "thue_ban_luy_ke", "chi_phi_truot_gia", "lai_lo_da_thuc_hien",
    "lai_lo_da_thuc_hien_luy_ke", "lai_lo_chua_thuc_hien",
    "tien_mat_cuoi_ngay", "gia_tri_vi_the", "nav", "chenh_lech_doi_soat",
)
CAC_COT_NAV = ("ngay", "nav", "loi_nhuan_phien", "tien_mat", "ty_trong_tien_mat")
TEN_TEP_THANH_CONG = (
    "cau_hinh.json", "lenh.csv", "khop_lenh.csv", "vi_the.csv", "so_cai.csv",
    "nav.csv", "chi_so.json", "bao_cao.json", "manifest.json",
)


def lam_sach_loi(loi: BaseException) -> str:
    noi_dung = str(loi)
    for mau in (
        r"vnstock_[A-Za-z0-9_-]+",
        r"(?i)(api[_ -]?key|token|secret|password)\s*[:=]\s*[^\s,;]+",
        r"(?i)bearer\s+[A-Za-z0-9._~-]+",
    ):
        noi_dung = re.sub(mau, "[DA_AN]", noi_dung)
    return noi_dung[:2000]


def _chuyen(gia_tri: Any) -> Any:
    if isinstance(gia_tri, Decimal):
        return format(gia_tri, "f")
    if isinstance(gia_tri, (date, datetime)):
        return gia_tri.isoformat()
    if is_dataclass(gia_tri):
        return {khoa: _chuyen(muc) for khoa, muc in asdict(gia_tri).items()}
    if isinstance(gia_tri, Mapping):
        return {str(khoa): _chuyen(muc) for khoa, muc in gia_tri.items()}
    if isinstance(gia_tri, (list, tuple)):
        return [_chuyen(muc) for muc in gia_tri]
    return gia_tri


def _noi_dung_json(du_lieu: object) -> bytes:
    return (json.dumps(_chuyen(du_lieu), ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _noi_dung_csv(cac_dong: Iterable[object], cac_cot: tuple[str, ...]) -> bytes:
    bo_nho = StringIO(newline="")
    bo_ghi = csv.DictWriter(bo_nho, fieldnames=cac_cot, lineterminator="\n")
    bo_ghi.writeheader()
    for muc in cac_dong:
        dong = asdict(muc) if is_dataclass(muc) else dict(muc)  # type: ignore[arg-type]
        bo_ghi.writerow({cot: _chuyen(dong.get(cot)) if dong.get(cot) is not None else "" for cot in cac_cot})
    return bo_nho.getvalue().encode("utf-8")


def _ghi_va_fsync(duong_dan: Path, noi_dung: bytes) -> None:
    with duong_dan.open("xb") as tep:
        tep.write(noi_dung)
        tep.flush()
        os.fsync(tep.fileno())


def ma_bam_tep(duong_dan: str | Path) -> str:
    bo_bam = hashlib.sha256()
    with Path(duong_dan).open("rb") as tep:
        for khoi in iter(lambda: tep.read(1024 * 1024), b""):
            bo_bam.update(khoi)
    return bo_bam.hexdigest()


def tao_noi_dung_san_pham(
    ket_qua: ket_qua_mo_phong,
    *,
    ma_lan_chay: str,
    thoi_diem_chay_utc: str,
    git_commit: str,
    python_version: str,
    uv_version: str | None,
    nguon_du_lieu: Mapping[str, object],
    sha256_dau_vao: Mapping[str, str],
    gioi_han: Iterable[str],
) -> dict[str, bytes]:
    chi_so = tinh_chi_so(ket_qua)
    don_vi = {
        "don_vi_gia": ket_qua.cau_hinh.don_vi_gia,
        "don_vi_tien": ket_qua.cau_hinh.don_vi_tien,
        "quan_he": "gia va tien dung cung don vi; gia_tri = gia * so_luong",
    }
    quy_uoc_ke_toan = {
        "gia_von": "gia khop binh quan, da gom truot gia, khong gom phi mua",
        "realized_pnl": "(gia_khop_ban - gia_von_binh_quan) * so_luong_ban, truoc phi ban va thue",
        "unrealized_pnl": "(gia_dong_cua - gia_von_binh_quan) * so_luong_con_lai",
        "doi_soat": "NAV = von_dau + realized + unrealized + co_tuc - phi_mua - phi_ban - thue_ban",
        "truot_gia": "da nam trong gia_khop, chi cong bo rieng va khong tru lan hai",
    }
    bao_cao = {
        "trang_thai": "thanh_cong",
        "ma_lan_chay": ma_lan_chay,
        "thoi_diem_chay_utc": thoi_diem_chay_utc,
        "git_commit": git_commit,
        "python_version": python_version,
        "uv_version": uv_version,
        "cau_hinh": ket_qua.cau_hinh.thanh_tu_dien(),
        "don_vi": don_vi,
        "quy_uoc_ke_toan": quy_uoc_ke_toan,
        "nguon_du_lieu": dict(nguon_du_lieu),
        "sha256_dau_vao": dict(sorted(sha256_dau_vao.items())),
        "co_so_gia": ket_qua.cau_hinh.co_so_gia,
        "canh_bao": chi_so["canh_bao"],
        "gioi_han": sorted(set(gioi_han)),
        "so_dong": {
            "lenh": len(ket_qua.lenh),
            "khop_lenh": len(ket_qua.khop_lenh),
            "vi_the": len(ket_qua.vi_the_hang_ngay),
            "so_cai": len(ket_qua.so_cai),
            "nav": len(ket_qua.nav),
            "su_kien_da_ap_dung": len(ket_qua.su_kien_da_ap_dung),
        },
        "chi_so_tom_tat": chi_so,
        "su_kien_doanh_nghiep_da_ap_dung": ket_qua.su_kien_da_ap_dung,
    }
    noi_dung: dict[str, bytes] = {
        "cau_hinh.json": _noi_dung_json(ket_qua.cau_hinh.thanh_tu_dien()),
        "lenh.csv": _noi_dung_csv(ket_qua.lenh, CAC_COT_LENH),
        "khop_lenh.csv": _noi_dung_csv(ket_qua.khop_lenh, CAC_COT_KHOP_LENH),
        "vi_the.csv": _noi_dung_csv(ket_qua.vi_the_hang_ngay, CAC_COT_VI_THE),
        "so_cai.csv": _noi_dung_csv(ket_qua.so_cai, CAC_COT_SO_CAI),
        "nav.csv": _noi_dung_csv(ket_qua.nav, CAC_COT_NAV),
        "chi_so.json": _noi_dung_json(chi_so),
        "bao_cao.json": _noi_dung_json(bao_cao),
    }
    bam = {ten: hashlib.sha256(du_lieu).hexdigest() for ten, du_lieu in sorted(noi_dung.items())}
    manifest = {
        "ma_lan_chay": ma_lan_chay,
        "thoi_diem_chay_utc": thoi_diem_chay_utc,
        "git_commit": git_commit,
        "co_so_gia": ket_qua.cau_hinh.co_so_gia,
        "don_vi": don_vi,
        "sha256_san_pham": bam,
        "sha256_dau_vao": dict(sorted(sha256_dau_vao.items())),
        "san_pham": list(TEN_TEP_THANH_CONG),
    }
    noi_dung["manifest.json"] = _noi_dung_json(manifest)
    return noi_dung


def cong_bo_san_pham(thu_muc_dau_ra: str | Path, noi_dung: Mapping[str, bytes]) -> Path:
    dich = Path(thu_muc_dau_ra)
    if dich.exists():
        raise FileExistsError(f"Thu muc dau ra da ton tai: {dich}")
    dich.parent.mkdir(parents=True, exist_ok=True)
    tam = dich.parent / f".{dich.name}.{uuid4().hex}.tmp"
    tam.mkdir()
    try:
        if set(noi_dung) != set(TEN_TEP_THANH_CONG):
            raise ValueError("Tap san pham thanh cong khong dung dac ta Moc 3.")
        for ten in TEN_TEP_THANH_CONG:
            _ghi_va_fsync(tam / ten, noi_dung[ten])
        os.rename(tam, dich)
    except BaseException:
        shutil.rmtree(tam, ignore_errors=True)
        raise
    return dich


def cong_bo_bao_cao_loi(thu_muc_dau_ra: str | Path, loi: BaseException, *, thoi_diem_chay_utc: str | None = None) -> Path | None:
    dich = Path(thu_muc_dau_ra)
    if dich.exists():
        return None
    dich.parent.mkdir(parents=True, exist_ok=True)
    tam = dich.parent / f".{dich.name}.{uuid4().hex}.loi.tmp"
    tam.mkdir()
    try:
        noi_dung = _noi_dung_json({
            "trang_thai": "that_bai",
            "thoi_diem_chay_utc": thoi_diem_chay_utc or datetime.now(timezone.utc).isoformat(),
            "loi": lam_sach_loi(loi),
        })
        _ghi_va_fsync(tam / "bao_cao_loi.json", noi_dung)
        os.rename(tam, dich)
    except BaseException:
        shutil.rmtree(tam, ignore_errors=True)
        return None
    return dich
