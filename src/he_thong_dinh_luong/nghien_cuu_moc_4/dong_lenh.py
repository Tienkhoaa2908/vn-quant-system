"""CLI ngoai tuyen cho runner dau-cuoi Moc 4."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from .mo_hinh import CauHinhMoc4
from .runner import chay_nghien_cuu_moc_4


def tao_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m he_thong_dinh_luong.nghien_cuu_moc_4")
    parser.add_argument("--kiem-tra-cau-hinh", type=Path)
    parser.add_argument("--cau-hinh", type=Path)
    parser.add_argument("--ohlcv", type=Path)
    parser.add_argument("--thu-muc-publication-gia-rut-gon", type=Path)
    parser.add_argument("--benchmark", type=Path)
    parser.add_argument("--lich-benchmark", type=Path)
    parser.add_argument("--universe", type=Path)
    parser.add_argument("--corporate-actions", type=Path)
    parser.add_argument("--thu-muc-dau-ra", type=Path)
    parser.add_argument("--ma-lan-chay")
    parser.add_argument("--git-commit")
    return parser


def _doc_config(path: Path) -> tuple[CauHinhMoc4, dict[str, object]]:
    data = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f"Cau hinh chua {x}.")),
    )
    if not isinstance(data, dict):
        raise ValueError("Cau hinh phai la object.")
    m4 = data.get("moc_4", data)
    if not isinstance(m4, dict):
        raise ValueError("moc_4 phai la object.")
    mapping = dict(m4)
    mapping["thu_muc_dau_ra"] = str(mapping.get("thu_muc_dau_ra", "."))
    return CauHinhMoc4.tu_mapping(mapping), data


def main(argv: Sequence[str] | None = None) -> int:
    parser = tao_parser()
    args = parser.parse_args(argv)
    if args.kiem_tra_cau_hinh is not None:
        if any(value is not None for value in (
            args.cau_hinh, args.ohlcv, args.thu_muc_publication_gia_rut_gon,
            args.benchmark, args.lich_benchmark, args.universe,
            args.corporate_actions, args.thu_muc_dau_ra,
            args.ma_lan_chay, args.git_commit,
        )):
            raise ValueError("Che do kiem tra cau hinh khong duoc tron voi che do chay.")
        config, _ = _doc_config(args.kiem_tra_cau_hinh)
        print(json.dumps({
            "hop_le": True,
            "muc_dich_lan_chay": config.muc_dich_lan_chay,
            "price_contract": config.price_contract,
            "universe_contract": config.universe_contract,
            "canh_bao": list(config.canh_bao_muc_dich()),
        }, ensure_ascii=False, sort_keys=True))
        return 0

    common_required = {
        "cau_hinh": args.cau_hinh,
        "benchmark": args.benchmark,
        "lich_benchmark": args.lich_benchmark,
        "corporate_actions": args.corporate_actions,
        "thu_muc_dau_ra": args.thu_muc_dau_ra,
        "ma_lan_chay": args.ma_lan_chay,
        "git_commit": args.git_commit,
    }
    missing = sorted(name for name, value in common_required.items() if value is None)
    if missing:
        parser.error("Thieu tham so chay: " + ", ".join(missing))
    try:
        config, _ = _doc_config(args.cau_hinh)
        if config.la_reduced:
            if args.thu_muc_publication_gia_rut_gon is None:
                parser.error("Reduced mode thieu thu_muc_publication_gia_rut_gon")
            if args.ohlcv is not None or args.universe is not None:
                parser.error("Reduced mode cam ohlcv/universe; khong tu nhan dang schema")
        else:
            if args.ohlcv is None or args.universe is None:
                parser.error("strict_ohlcv thieu ohlcv/universe")
            if args.thu_muc_publication_gia_rut_gon is not None:
                parser.error("strict_ohlcv cam publication reduced")
        result = chay_nghien_cuu_moc_4(
            duong_dan_cau_hinh=args.cau_hinh,
            duong_dan_ohlcv=args.ohlcv,
            thu_muc_publication_gia_rut_gon=args.thu_muc_publication_gia_rut_gon,
            duong_dan_benchmark=args.benchmark,
            duong_dan_lich_benchmark=args.lich_benchmark,
            duong_dan_universe=args.universe,
            duong_dan_corporate_actions=args.corporate_actions,
            thu_muc_dau_ra=args.thu_muc_dau_ra,
            ma_lan_chay=args.ma_lan_chay,
            git_commit=args.git_commit,
        )
    except SystemExit:
        raise
    except Exception as exc:
        print(json.dumps({"hop_le": False, "loi": str(exc)}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps({
        "hop_le": True,
        "thu_muc_san_pham": str(result.thu_muc_san_pham),
        "so_fold": result.so_fold,
        "so_fold_thanh_cong": result.so_fold_thanh_cong,
        "so_du_doan_test_logistic": result.so_du_doan_test_logistic,
        "so_du_doan_test_baseline": result.so_du_doan_test_baseline,
        "canh_bao": list(result.canh_bao),
    }, ensure_ascii=False, sort_keys=True))
    return 0
