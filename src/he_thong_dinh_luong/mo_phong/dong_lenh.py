"""Giao dien dong lenh cho bo may mo phong Moc 3."""
from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .bao_cao import (
    cong_bo_bao_cao_loi,
    cong_bo_san_pham,
    lam_sach_loi,
    ma_bam_tep,
    tao_noi_dung_san_pham,
)
from .engine import chay_mo_phong
from .mo_hinh import cau_hinh_mo_phong, chuan_hoa_gia, chuan_hoa_su_kien, chuan_hoa_ty_trong


def _doc_csv(duong_dan: Path) -> list[dict[str, str]]:
    with duong_dan.open("r", encoding="utf-8", newline="") as tep:
        bo_doc = csv.DictReader(tep)
        if bo_doc.fieldnames is None:
            raise ValueError(f"Tep CSV khong co tieu de: {duong_dan}")
        return [dict(dong) for dong in bo_doc]


def _doc_json(duong_dan: Path) -> object:
    return json.loads(duong_dan.read_text(encoding="utf-8"))


def _git_commit() -> str:
    bien = os.environ.get("GITHUB_SHA")
    if bien:
        return bien
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "khong_xac_dinh"


def _uv_version() -> str | None:
    try:
        return subprocess.run(["uv", "--version"], check=True, capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def tao_bo_phan_tich() -> argparse.ArgumentParser:
    bo = argparse.ArgumentParser(description="Mo phong giao dich va backtest Moc 3.")
    bo.add_argument("--duong_co_so", required=True)
    bo.add_argument("--ty_trong_muc_tieu", required=True)
    bo.add_argument("--cau_hinh", required=True)
    bo.add_argument("--su_kien_doanh_nghiep")
    bo.add_argument("--thu_muc_dau_ra", required=True)
    bo.add_argument("--ma_lan_chay")
    bo.add_argument("--git_commit")
    return bo


def main(argv: list[str] | None = None) -> int:
    tham_so = tao_bo_phan_tich().parse_args(argv)
    dau_ra = Path(tham_so.thu_muc_dau_ra)
    thoi_diem = datetime.now(timezone.utc).isoformat()
    try:
        tep_gia = Path(tham_so.duong_co_so)
        tep_ty_trong = Path(tham_so.ty_trong_muc_tieu)
        tep_cau_hinh = Path(tham_so.cau_hinh)
        tep_su_kien = Path(tham_so.su_kien_doanh_nghiep) if tham_so.su_kien_doanh_nghiep else None
        cau_hinh_raw = _doc_json(tep_cau_hinh)
        if not isinstance(cau_hinh_raw, dict):
            raise ValueError("cau_hinh.json phai la mot doi tuong JSON.")
        cau_hinh = cau_hinh_mo_phong.tu_mapping(cau_hinh_raw)
        gia = chuan_hoa_gia(_doc_csv(tep_gia))
        ty_trong = chuan_hoa_ty_trong(_doc_csv(tep_ty_trong))
        su_kien = chuan_hoa_su_kien(_doc_csv(tep_su_kien) if tep_su_kien else (), co_so_gia=cau_hinh.co_so_gia)
        ket_qua = chay_mo_phong(gia, ty_trong, cau_hinh, su_kien)
        ma_lan_chay = tham_so.ma_lan_chay or f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}_{uuid4().hex[:8]}"
        sha_dau_vao = {
            "duong_co_so": ma_bam_tep(tep_gia),
            "ty_trong_muc_tieu": ma_bam_tep(tep_ty_trong),
            "cau_hinh": ma_bam_tep(tep_cau_hinh),
        }
        if tep_su_kien:
            sha_dau_vao["su_kien_doanh_nghiep"] = ma_bam_tep(tep_su_kien)
        nguon = {
            "duong_co_so": str(tep_gia),
            "ty_trong_muc_tieu": str(tep_ty_trong),
            "cau_hinh": str(tep_cau_hinh),
            "su_kien_doanh_nghiep": str(tep_su_kien) if tep_su_kien else None,
        }
        gioi_han = (
            "Khong mo phong market partial fill hoac participation rate; giam khoi luong truoc khop la dinh co theo suc mua.",
            "Khong ket noi SSI, khong doc tai khoan va khong gui lenh.",
            "Baseline Moc 3 chi dung de kiem tra engine, khong phai chien luoc san xuat.",
            "Nguon lich su thanh vien that chua duoc phe duyet.",
        )
        noi_dung = tao_noi_dung_san_pham(
            ket_qua,
            ma_lan_chay=ma_lan_chay,
            thoi_diem_chay_utc=thoi_diem,
            git_commit=tham_so.git_commit or _git_commit(),
            python_version=platform.python_version(),
            uv_version=_uv_version(),
            nguon_du_lieu=nguon,
            sha256_dau_vao=sha_dau_vao,
            gioi_han=gioi_han,
        )
        cong_bo_san_pham(dau_ra, noi_dung)
        print(json.dumps({"trang_thai": "thanh_cong", "ma_lan_chay": ma_lan_chay, "thu_muc_dau_ra": str(dau_ra)}, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, AssertionError, json.JSONDecodeError) as exc:
        cong_bo_bao_cao_loi(dau_ra, exc, thoi_diem_chay_utc=thoi_diem)
        print(json.dumps({"trang_thai": "that_bai", "loi": lam_sach_loi(exc)}, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
