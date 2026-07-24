"""Giao dien dong lenh cho trinh kiem tra du lieu."""

from __future__ import annotations

import argparse
import json
from datetime import date

from .kiem_tra_du_lieu import kiem_tra_tep


def tao_bo_phan_tich() -> argparse.ArgumentParser:
    bo_phan_tich = argparse.ArgumentParser(description="Kiem tra chat luong du lieu gia ngay.")
    bo_phan_tich.add_argument("tep_csv", help="Duong dan den tep CSV can kiem tra.")
    bo_phan_tich.add_argument(
        "--ngay_kiem_tra",
        required=True,
        help="Ngay gioi han du lieu theo dinh dang YYYY-MM-DD.",
    )
    return bo_phan_tich


def chay() -> int:
    tham_so = tao_bo_phan_tich().parse_args()
    try:
        ngay_kiem_tra = date.fromisoformat(tham_so.ngay_kiem_tra)
        bao_cao = kiem_tra_tep(tham_so.tep_csv, ngay_kiem_tra)
    except (OSError, ValueError) as exc:
        print(json.dumps({"hop_le": False, "loi_he_thong": str(exc)}, ensure_ascii=False))
        return 1

    print(json.dumps(bao_cao.thanh_tu_dien(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if bao_cao.hop_le else 2


if __name__ == "__main__":
    raise SystemExit(chay())
