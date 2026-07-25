"""CLI ngoai tuyen cho viec xac thuc cau hinh fixture Moc 4."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .mo_hinh import CauHinhMoc4


def tao_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m he_thong_dinh_luong.nghien_cuu_moc_4")
    parser.add_argument("--kiem-tra-cau-hinh", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = tao_parser().parse_args(argv)
    data = json.loads(args.kiem_tra_cau_hinh.read_text(encoding="utf-8"))
    config = CauHinhMoc4.tu_mapping(data)
    print(json.dumps({
        "hop_le": True,
        "muc_dich_lan_chay": config.muc_dich_lan_chay,
        "canh_bao": list(config.canh_bao_muc_dich()),
    }, ensure_ascii=False, sort_keys=True))
    return 0
