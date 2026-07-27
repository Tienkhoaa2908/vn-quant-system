from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: agent_patch_m4_close_only_fix1.py <repo-root>")
    path = Path(sys.argv[1]).resolve() / "src/he_thong_dinh_luong/nghien_cuu_moc_4/runner.py"
    text = path.read_text(encoding="utf-8")
    old = "_doc_ohlcv, _doc_benchmark_dong_cua, _doc_calendar"
    new = "_doc_ohlcv, _doc_benchmark_dong_cua, _xac_thuc_benchmark_identity, _doc_calendar"
    if text.count(old) != 1:
        raise RuntimeError(f"compatibility import marker count={text.count(old)}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
    print("PATCH_M4_CLOSE_ONLY_FIX1_APPLIED")


if __name__ == "__main__":
    main()
