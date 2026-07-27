from __future__ import annotations

import sys
from pathlib import Path


CANONICAL_BRANCH = "m4-dac_trung-xep-hang-hoc_may-sach-final-v2"
EXPECTED_HEAD = "e2c866db1fdb0b143a94a53a4ec26ee8b1e2c81e"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def replace_once(path: Path, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one match, got {count}: {old[:120]!r}")
    write(path, text.replace(old, new, 1))


def insert_before_once(path: Path, marker: str, insertion: str) -> None:
    text = read(path)
    count = text.count(marker)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one marker, got {count}: {marker[:120]!r}")
    write(path, text.replace(marker, insertion + marker, 1))


def append_once(path: Path, marker: str, section: str) -> None:
    text = read(path)
    if marker in text:
        raise RuntimeError(f"{path}: marker already exists: {marker}")
    suffix = "" if text.endswith("\n") else "\n"
    write(path, text + suffix + "\n" + section.rstrip() + "\n")


def patch_mo_hinh(root: Path) -> None:
    path = root / "src/he_thong_dinh_luong/nghien_cuu_moc_4/mo_hinh.py"
    replace_once(path, "from typing import Any, Mapping, Sequence", "from typing import Any, Mapping, Protocol, Sequence")
    replace_once(
        path,
        'VAI_TRO_DU_DOAN_HOP_LE = {"validation", "test"}\n',
        'VAI_TRO_DU_DOAN_HOP_LE = {"validation", "test"}\n'
        'BENCHMARK_CONTRACT = "close_only"\n'
        'CANH_BAO_BENCHMARK_CLOSE_ONLY = "BENCHMARK_CLOSE_ONLY"\n'
        'CANH_BAO_BENCHMARK_SEMANTICS = "BENCHMARK_OHLC_SEMANTICS_CHUA_XAC_NHAN"\n\n\n'
        'class ThanhCoGiaDongCua(Protocol):\n'
        '    """Giao dien toi thieu cho feature/label chi doc gia dong cua."""\n\n'
        '    ma: str\n'
        '    ngay: date\n'
        '    gia_dong_cua: float\n',
    )
    replace_once(
        path,
        '        if self.co_so_gia == "gia_khong_dieu_chinh" and not self.corporate_actions_day_du:\n'
        '            warnings.append("CORPORATE_ACTIONS_CHUA_DAY_DU")\n'
        '        return tuple(warnings)\n',
        '        if self.co_so_gia == "gia_khong_dieu_chinh" and not self.corporate_actions_day_du:\n'
        '            warnings.append("CORPORATE_ACTIONS_CHUA_DAY_DU")\n'
        '        warnings.extend((CANH_BAO_BENCHMARK_CLOSE_ONLY, CANH_BAO_BENCHMARK_SEMANTICS))\n'
        '        return tuple(warnings)\n',
    )
    insert_before_once(
        path,
        "\n\n@dataclass(frozen=True)\nclass BanGhiUniverse:",
        "\n\n@dataclass(frozen=True)\n"
        "class ThanhBenchmarkDongCua:\n"
        "    \"\"\"Thanh benchmark canonical khong mang OHLC/volume chua xac nhan.\"\"\"\n\n"
        "    ma: str\n"
        "    ngay: date\n"
        "    gia_dong_cua: float\n"
        "    nguon: str\n"
        "    phien_ban: str\n"
        "    co_so_gia: str\n\n"
        "    def __post_init__(self) -> None:\n"
        "        if not isinstance(self.ma, str) or not self.ma or self.ma != self.ma.upper():\n"
        "            raise ValueError(\"ma benchmark phai la chu hoa khong rong.\")\n"
        "        if not isinstance(self.ngay, date):\n"
        "            raise TypeError(\"ngay benchmark phai la date.\")\n"
        "        close = xac_thuc_so_huu_han(self.gia_dong_cua, \"gia_dong_cua benchmark\")\n"
        "        if close <= 0.0:\n"
        "            raise ValueError(\"gia_dong_cua benchmark phai la so duong.\")\n"
        "        for ten in (\"nguon\", \"phien_ban\", \"co_so_gia\"):\n"
        "            value = getattr(self, ten)\n"
        "            if not isinstance(value, str) or not value.strip():\n"
        "                raise ValueError(f\"Benchmark thieu {ten}.\")\n",
    )


def patch_runner_io(root: Path) -> None:
    path = root / "src/he_thong_dinh_luong/nghien_cuu_moc_4/runner_io.py"
    replace_once(
        path,
        "    MauMoHinh,\n    ThanhOHLCV,\n    xac_thuc_co_so_gia_va_su_kien,\n",
        "    MauMoHinh,\n    ThanhBenchmarkDongCua,\n    ThanhCoGiaDongCua,\n    ThanhOHLCV,\n    xac_thuc_co_so_gia_va_su_kien,\n",
    )
    insert_before_once(
        path,
        "\n\n@dataclass(frozen=True)\nclass _DocPIT:",
        "\n\n@dataclass(frozen=True)\n"
        "class _DocBenchmarkDongCua:\n"
        "    rows: tuple[ThanhBenchmarkDongCua, ...]\n"
        "    nguon: str\n"
        "    phien_ban: str\n"
        "    co_so_gia: str\n",
    )
    replace_once(
        path,
        "def _doc_ohlcv(path: Path, *, benchmark: bool = False) -> _DocOHLCV:\n"
        "    \"\"\"Doc OHLCV theo policy B: stock loi bi loai co kiem soat; benchmark fail closed.\"\"\"\n",
        "def _doc_ohlcv(path: Path) -> _DocOHLCV:\n"
        "    \"\"\"Doc OHLCV co phieu; loi gia/volume bi loai co kiem soat nhu hop dong cu.\"\"\"\n",
    )
    for old in (
        "            if benchmark:\n                raise ValueError(f\"OHLCV benchmark loi gia tai {symbol}, {day}: {exc}\") from exc\n",
        "            if benchmark:\n                raise ValueError(f\"OHLCV benchmark loi volume tai {symbol}, {day}: {exc}\") from exc\n",
        "            if benchmark:\n                raise ValueError(f\"OHLCV benchmark loi gia tai {symbol}, {day}: {exc}\") from exc\n",
        "    if benchmark and not rows:\n        raise ValueError(\"Benchmark khong co bar hop le.\")\n",
    ):
        text = read(path)
        if old not in text:
            raise RuntimeError(f"{path}: benchmark fallback snippet not found: {old!r}")
        write(path, text.replace(old, "", 1))
    replace_once(
        path,
        "def _xac_thuc_benchmark_identity(rows: Sequence[ThanhOHLCV], expected_symbol: str) -> str:",
        "def _xac_thuc_benchmark_identity(rows: Sequence[ThanhCoGiaDongCua], expected_symbol: str) -> str:",
    )
    insert_before_once(
        path,
        "\n\ndef _doc_calendar(path: Path) -> tuple[date, ...]:",
        "\n\ndef _doc_benchmark_dong_cua(\n"
        "    path: Path,\n"
        "    *,\n"
        "    expected_symbol: str,\n"
        ") -> _DocBenchmarkDongCua:\n"
        "    \"\"\"Doc benchmark canonical close-only va fail closed tren schema/identity.\"\"\"\n"
        "    raw_rows, fields = _read_csv(path)\n"
        "    expected_fields = (\n"
        "        \"ma\", \"ngay\", \"gia_dong_cua\", \"nguon\", \"phien_ban\", \"co_so_gia\",\n"
        "    )\n"
        "    if fields != expected_fields:\n"
        "        missing = sorted(set(expected_fields) - set(fields))\n"
        "        extra = sorted(set(fields) - set(expected_fields))\n"
        "        details: list[str] = []\n"
        "        if missing:\n"
        "            details.append(\"thieu cot: \" + \", \".join(missing))\n"
        "        if extra:\n"
        "            details.append(\"cot ngoai hop dong: \" + \", \".join(extra))\n"
        "        if not missing and not extra:\n"
        "            details.append(\"thu tu cot khong dung schema canonical\")\n"
        "        raise ValueError(\"Benchmark close-only sai schema: \" + \"; \".join(details) + \".\")\n"
        "    if not raw_rows:\n"
        "        raise ValueError(\"Benchmark close-only rong.\")\n"
        "    rows: list[ThanhBenchmarkDongCua] = []\n"
        "    seen: set[tuple[str, date]] = set()\n"
        "    sources: list[str] = []\n"
        "    versions: list[str] = []\n"
        "    bases: list[str] = []\n"
        "    for number, raw in enumerate(raw_rows, 2):\n"
        "        symbol = str(raw.get(\"ma\", \"\")).strip().upper()\n"
        "        if not symbol:\n"
        "            raise ValueError(f\"Ma benchmark rong tai dong {number}.\")\n"
        "        day = _parse_date(raw.get(\"ngay\"), f\"benchmark.ngay dong {number}\")\n"
        "        key = (symbol, day)\n"
        "        if key in seen:\n"
        "            raise ValueError(f\"Benchmark trung ma/ngay: {symbol}, {day}.\")\n"
        "        seen.add(key)\n"
        "        source = str(raw.get(\"nguon\", \"\")).strip()\n"
        "        version = str(raw.get(\"phien_ban\", \"\")).strip()\n"
        "        basis = str(raw.get(\"co_so_gia\", \"\")).strip()\n"
        "        item = ThanhBenchmarkDongCua(\n"
        "            ma=symbol, ngay=day,\n"
        "            gia_dong_cua=_parse_float(raw.get(\"gia_dong_cua\"), \"gia_dong_cua benchmark\"),\n"
        "            nguon=source, phien_ban=version, co_so_gia=basis,\n"
        "        )\n"
        "        rows.append(item)\n"
        "        sources.append(source)\n"
        "        versions.append(version)\n"
        "        bases.append(basis)\n"
        "    ordered = tuple(sorted(rows, key=lambda row: (row.ma, row.ngay)))\n"
        "    _xac_thuc_benchmark_identity(ordered, expected_symbol)\n"
        "    return _DocBenchmarkDongCua(\n"
        "        rows=ordered,\n"
        "        nguon=_unique(sources, \"nguon benchmark\"),\n"
        "        phien_ban=_unique(versions, \"phien_ban benchmark\"),\n"
        "        co_so_gia=_unique(bases, \"co_so_gia benchmark\"),\n"
        "    )\n",
    )


def patch_dac_trung(root: Path) -> None:
    path = root / "src/he_thong_dinh_luong/nghien_cuu_moc_4/dac_trung.py"
    replace_once(path, "from typing import Iterable, Sequence", "from typing import Iterable, Sequence, TypeVar")
    replace_once(path, "from .mo_hinh import DongFeature, ThanhOHLCV", "from .mo_hinh import DongFeature, ThanhCoGiaDongCua, ThanhOHLCV")
    replace_once(path, ")\n\n\ndef _lich_chinh_thuc", ")\n\n_BAR_DONG_CUA = TypeVar(\"_BAR_DONG_CUA\", bound=ThanhCoGiaDongCua)\n\n\ndef _lich_chinh_thuc")
    replace_once(path, "def _validate_bars(rows: Sequence[ThanhOHLCV]) -> None:", "def _validate_bars(rows: Sequence[ThanhCoGiaDongCua]) -> None:")
    replace_once(path, "def _bars_exact(mapping: dict[date, ThanhOHLCV], dates: Sequence[date]) -> list[ThanhOHLCV] | None:", "def _bars_exact(mapping: dict[date, _BAR_DONG_CUA], dates: Sequence[date]) -> list[_BAR_DONG_CUA] | None:")
    replace_once(path, "    benchmark_map: dict[date, ThanhOHLCV],", "    benchmark_map: dict[date, ThanhCoGiaDongCua],")
    replace_once(path, "    du_lieu_benchmark: Iterable[ThanhOHLCV],", "    du_lieu_benchmark: Iterable[ThanhCoGiaDongCua],")


def patch_nhan(root: Path) -> None:
    path = root / "src/he_thong_dinh_luong/nghien_cuu_moc_4/nhan.py"
    replace_once(path, "from .mo_hinh import DongNhan, ThanhOHLCV", "from .mo_hinh import DongNhan, ThanhCoGiaDongCua, ThanhOHLCV")
    replace_once(path, "    du_lieu_benchmark: Iterable[ThanhOHLCV],", "    du_lieu_benchmark: Iterable[ThanhCoGiaDongCua],")


def patch_runner(root: Path) -> None:
    path = root / "src/he_thong_dinh_luong/nghien_cuu_moc_4/runner.py"
    replace_once(path, "    BanGhiPointInTime,\n    BanGhiUniverse,\n    CauHinhMoc4,", "    BENCHMARK_CONTRACT,\n    BanGhiPointInTime,\n    BanGhiUniverse,\n    CauHinhMoc4,")
    replace_once(path, "    _DocOHLCV, _DocPIT, _read_csv, _parse_date, _parse_datetime, _parse_bool, _parse_float, _parse_int, _unique, _doc_ohlcv, _xac_thuc_benchmark_identity, _doc_calendar, _doc_universe, _doc_pit, _signal_time, _json_ready, _json_text, _csv_text,", "    _DocBenchmarkDongCua, _DocOHLCV, _DocPIT, _read_csv, _parse_date, _parse_datetime, _parse_bool, _parse_float, _parse_int, _unique, _doc_ohlcv, _doc_benchmark_dong_cua, _doc_calendar, _doc_universe, _doc_pit, _signal_time, _json_ready, _json_text, _csv_text,")
    replace_once(path, "    stock_doc = _doc_ohlcv(paths[\"ohlcv\"])\n    benchmark_doc = _doc_ohlcv(paths[\"benchmark\"], benchmark=True)\n", "    stock_doc = _doc_ohlcv(paths[\"ohlcv\"])\n    benchmark_doc = _doc_benchmark_dong_cua(\n        paths[\"benchmark\"], expected_symbol=config.benchmark,\n    )\n")
    replace_once(path, "    _xac_thuc_benchmark_identity(benchmark_doc.rows, config.benchmark)\n    if any(row.co_so_gia != config.co_so_gia for row in [*stock_doc.rows, *benchmark_doc.rows]):\n        raise ValueError(\"Co so gia OHLCV/benchmark khong khop cau hinh.\")\n", "    if (\n        any(row.co_so_gia != config.co_so_gia for row in stock_doc.rows)\n        or benchmark_doc.co_so_gia != config.co_so_gia\n    ):\n        raise ValueError(\"Co so gia OHLCV/benchmark khong khop cau hinh.\")\n")
    replace_once(path, "    limitations = [\n        \"TIER_A_TIER_B_CHUA_CHAY\",\n        \"NGUON_DU_LIEU_THAT_CHUA_DUOC_PHE_DUYET\",\n        \"KHONG_DUOC_TUYEN_BO_HIEU_QUA_CHIEN_LUOC\",\n        \"KHONG_LIGHTGBM_KHONG_SSI_KHONG_MOC_5\",\n    ]\n", "    limitations = [\n        \"TIER_A_TIER_B_CHUA_CHAY\",\n        \"NGUON_DU_LIEU_THAT_CHUA_DUOC_PHE_DUYET\",\n        \"BENCHMARK_EXACT_OFFICIAL_OHLC_CHUA_CO\",\n        \"BENCHMARK_RAW_SOURCE_GIU_BAT_BIEN\",\n        \"KHONG_CORRECTION_OVERLAY\",\n        \"KHONG_DUOC_TUYEN_BO_HIEU_QUA_CHIEN_LUOC\",\n        \"KHONG_LIGHTGBM_KHONG_SSI_KHONG_MOC_5\",\n    ]\n")
    replace_once(path, "    report = {\n        \"ma_lan_chay\": ma_lan_chay, \"so_fold\": len(folds),\n", "    report = {\n        \"ma_lan_chay\": ma_lan_chay,\n        \"benchmark_contract\": BENCHMARK_CONTRACT,\n        \"benchmark_policy\": {\n            \"features_va_labels_chi_dung_close\": True,\n            \"open_high_low_volume_duoc_dung\": False,\n            \"correction_overlay\": False,\n            \"raw_source_giu_bat_bien\": True,\n            \"exact_official_ohlc_da_co\": False,\n            \"chi_kiem_tra_ky_thuat\": True,\n        },\n        \"so_fold\": len(folds),\n")
    replace_once(path, "        \"python_version\": platform.python_version(), \"uv_version\": _uv_version(),\n        \"scikit_learn_version\": sklearn.__version__,\n", "        \"python_version\": platform.python_version(), \"uv_version\": _uv_version(),\n        \"scikit_learn_version\": sklearn.__version__,\n        \"benchmark_contract\": BENCHMARK_CONTRACT,\n        \"benchmark_policy\": {\n            \"features_va_labels_chi_dung_close\": True,\n            \"open_high_low_volume_duoc_dung\": False,\n            \"correction_overlay\": False,\n            \"raw_source_giu_bat_bien\": True,\n            \"exact_official_ohlc_da_co\": False,\n            \"chi_kiem_tra_ky_thuat\": True,\n        },\n")
    replace_once(path, "            \"tan_suat\": \"cuoi_thang\", \"lich\": \"benchmark_chinh_thuc\",\n", "            \"tan_suat\": \"cuoi_thang\", \"lich\": \"benchmark_chinh_thuc\",\n            \"benchmark\": \"chi_dung_gia_dong_cua\",\n")
    replace_once(path, '        "cau_hinh_label": {"horizon": config.label_horizon, "lich": "benchmark_chinh_thuc"},\n', '        "cau_hinh_label": {\n            "horizon": config.label_horizon, "lich": "benchmark_chinh_thuc",\n            "benchmark": "chi_dung_gia_dong_cua",\n        },\n')


def patch_init(root: Path) -> None:
    path = root / "src/he_thong_dinh_luong/nghien_cuu_moc_4/__init__.py"
    replace_once(path, "from .mo_hinh import BanGhiPointInTime, CauHinhMoc4, xac_thuc_co_so_gia_va_su_kien", "from .mo_hinh import (\n    BENCHMARK_CONTRACT,\n    BanGhiPointInTime,\n    CauHinhMoc4,\n    ThanhBenchmarkDongCua,\n    ThanhCoGiaDongCua,\n    xac_thuc_co_so_gia_va_su_kien,\n)")
    replace_once(path, '    "BanGhiPointInTime", "CauHinhMoc4", "FEATURE_ORDER_MAC_DINH", "KetQuaNghienCuuMoc4",\n', '    "BENCHMARK_CONTRACT", "BanGhiPointInTime", "CauHinhMoc4", "FEATURE_ORDER_MAC_DINH",\n    "KetQuaNghienCuuMoc4", "ThanhBenchmarkDongCua", "ThanhCoGiaDongCua",\n')


def patch_runner_fixture(root: Path) -> None:
    path = root / "tests/ho_tro_m4_runner.py"
    replace_once(path, "    fields = [\n", "    stock_fields = [\n")
    replace_once(path, "    write_csv(stock, fields, stock_rows)\n", "    write_csv(stock, stock_fields, stock_rows)\n")
    replace_once(path, "    benchmark_rows: list[dict[str, object]] = []\n", "    benchmark_fields = [\n        \"ma\", \"ngay\", \"gia_dong_cua\", \"nguon\", \"phien_ban\", \"co_so_gia\",\n    ]\n    benchmark_rows: list[dict[str, object]] = []\n")
    replace_once(path, "        benchmark_rows.append({\n            \"ma\": \"VNINDEX\", \"ngay\": day.isoformat(),\n            \"gia_mo_cua\": f\"{close - 0.3:.8f}\", \"gia_cao_nhat\": f\"{close + 1.0:.8f}\",\n            \"gia_thap_nhat\": f\"{close - 1.0:.8f}\", \"gia_dong_cua\": f\"{close:.8f}\",\n            \"khoi_luong\": 1000000 + index, \"nguon\": \"fixture_benchmark\",\n            \"phien_ban\": \"v1\", \"co_so_gia\": \"gia_dieu_chinh\",\n        })\n", "        benchmark_rows.append({\n            \"ma\": \"VNINDEX\", \"ngay\": day.isoformat(),\n            \"gia_dong_cua\": f\"{close:.8f}\", \"nguon\": \"fixture_benchmark\",\n            \"phien_ban\": \"v1\", \"co_so_gia\": \"gia_dieu_chinh\",\n        })\n")
    replace_once(path, "    write_csv(benchmark, fields, benchmark_rows)\n", "    write_csv(benchmark, benchmark_fields, benchmark_rows)\n")


def write_tests(root: Path) -> None:
    path = root / "tests/test_m4_benchmark_close_only.py"
    if path.exists():
        raise RuntimeError(f"Test file already exists: {path}")
    content = r'''from __future__ import annotations

import csv
from dataclasses import replace
from datetime import date, datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from he_thong_dinh_luong.nghien_cuu_moc_4.baseline import du_doan_baseline_test, metric_baseline_test, xep_hang_baseline_test
from he_thong_dinh_luong.nghien_cuu_moc_4.dac_trung import phien_cuoi_thang, tao_feature_cuoi_thang
from he_thong_dinh_luong.nghien_cuu_moc_4.mo_hinh import BENCHMARK_CONTRACT, ThanhBenchmarkDongCua, ThanhOHLCV
from he_thong_dinh_luong.nghien_cuu_moc_4.nhan import tao_nhan
from he_thong_dinh_luong.nghien_cuu_moc_4.runner import chay_nghien_cuu_moc_4
from he_thong_dinh_luong.nghien_cuu_moc_4.runner_core import _samples
from he_thong_dinh_luong.nghien_cuu_moc_4.runner_io import _doc_benchmark_dong_cua, _xac_thuc_benchmark_identity
from ho_tro_m4 import bars, weekdays
from ho_tro_m4_runner import tao_fixture_runner, write_csv

GIT_SHA = "e" * 40
FIXED_TIME = datetime(2026, 7, 27, 0, 0, tzinfo=timezone.utc)
BENCHMARK_FIELDS = ["ma", "ngay", "gia_dong_cua", "nguon", "phien_ban", "co_so_gia"]


def benchmark_close_rows(dates: list[date], *, base: float = 1000.0) -> list[ThanhBenchmarkDongCua]:
    return [ThanhBenchmarkDongCua("VNINDEX", day, base + 0.2 * index, "fixture_benchmark", "v1", "gia_dieu_chinh") for index, day in enumerate(dates)]


def benchmark_ohlcv_rows(dates: list[date], *, high_pad: float, low_pad: float, open_offset: float, volume_offset: int) -> list[ThanhOHLCV]:
    result: list[ThanhOHLCV] = []
    for index, day in enumerate(dates):
        close = 1000.0 + 0.2 * index
        result.append(ThanhOHLCV("VNINDEX", day, close + open_offset, max(close + high_pad, close + open_offset), min(close - low_pad, close + open_offset), close, 1_000_000 + volume_offset + index, "legacy_fixture", "v1", "gia_dieu_chinh"))
    return result


class TestKieuVaParserBenchmarkCloseOnly(unittest.TestCase):
    def test_stock_van_tu_choi_high_nho_hon_close(self):
        with self.assertRaises(ValueError):
            ThanhOHLCV("AAA", date(2026, 1, 2), 10.0, 10.5, 9.0, 11.0, 100)

    def test_stock_van_tu_choi_low_lon_hon_close(self):
        with self.assertRaises(ValueError):
            ThanhOHLCV("AAA", date(2026, 1, 2), 10.0, 12.0, 11.0, 10.5, 100)

    def test_benchmark_chap_nhan_ba_close_anomaly(self):
        for day, close in ((date(2021, 2, 17), 1155.78), (date(2021, 12, 10), 1463.54), (date(2023, 5, 15), 1065.71)):
            with self.subTest(day=day):
                self.assertEqual(ThanhBenchmarkDongCua("VNINDEX", day, close, "kbs", "4.0.4", "gia_khong_dieu_chinh").gia_dong_cua, close)

    def test_parser_chap_nhan_ba_ngay_anomaly_close_only(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "benchmark.csv"
            write_csv(path, BENCHMARK_FIELDS, [
                {"ma": "VNINDEX", "ngay": "2021-02-17", "gia_dong_cua": 1155.78, "nguon": "kbs", "phien_ban": "4.0.4", "co_so_gia": "gia_khong_dieu_chinh"},
                {"ma": "VNINDEX", "ngay": "2021-12-10", "gia_dong_cua": 1463.54, "nguon": "kbs", "phien_ban": "4.0.4", "co_so_gia": "gia_khong_dieu_chinh"},
                {"ma": "VNINDEX", "ngay": "2023-05-15", "gia_dong_cua": 1065.71, "nguon": "kbs", "phien_ban": "4.0.4", "co_so_gia": "gia_khong_dieu_chinh"},
            ])
            parsed = _doc_benchmark_dong_cua(path, expected_symbol="VNINDEX")
            self.assertEqual([row.gia_dong_cua for row in parsed.rows], [1155.78, 1463.54, 1065.71])

    def test_close_nan_bi_tu_choi(self):
        with self.assertRaises(ValueError):
            ThanhBenchmarkDongCua("VNINDEX", date(2026, 1, 2), float("nan"), "kbs", "4.0.4", "x")

    def test_close_inf_bi_tu_choi(self):
        with self.assertRaises(ValueError):
            ThanhBenchmarkDongCua("VNINDEX", date(2026, 1, 2), float("inf"), "kbs", "4.0.4", "x")

    def test_close_khong_duong_bi_tu_choi(self):
        for value in (0.0, -1.0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ThanhBenchmarkDongCua("VNINDEX", date(2026, 1, 2), value, "kbs", "4.0.4", "x")

    def test_duplicate_ngay_bi_tu_choi(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "benchmark.csv"
            row = {"ma": "VNINDEX", "ngay": "2023-05-15", "gia_dong_cua": 1065.71, "nguon": "kbs", "phien_ban": "4.0.4", "co_so_gia": "x"}
            write_csv(path, BENCHMARK_FIELDS, [row, dict(row)])
            with self.assertRaisesRegex(ValueError, "trung ma/ngay"):
                _doc_benchmark_dong_cua(path, expected_symbol="VNINDEX")

    def test_sai_identity_benchmark_bi_tu_choi(self):
        rows = [ThanhBenchmarkDongCua("HNXINDEX", date(2026, 1, 2), 100.0, "x", "1", "x")]
        with self.assertRaisesRegex(ValueError, "VNINDEX"):
            _xac_thuc_benchmark_identity(rows, "VNINDEX")

    def test_thieu_metadata_bi_tu_choi(self):
        with self.assertRaises(ValueError):
            ThanhBenchmarkDongCua("VNINDEX", date(2026, 1, 2), 100.0, "", "1", "x")

    def test_extra_ohlcv_volume_column_bi_tu_choi(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "benchmark.csv"
            fields = [*BENCHMARK_FIELDS, "gia_mo_cua", "gia_cao_nhat", "gia_thap_nhat", "khoi_luong"]
            write_csv(path, fields, [{"ma": "VNINDEX", "ngay": "2023-05-15", "gia_dong_cua": 1065.71, "nguon": "kbs", "phien_ban": "4.0.4", "co_so_gia": "x", "gia_mo_cua": 1074.82, "gia_cao_nhat": 1076.32, "gia_thap_nhat": 1067.15, "khoi_luong": 791524900}])
            with self.assertRaisesRegex(ValueError, "cot ngoai hop dong"):
                _doc_benchmark_dong_cua(path, expected_symbol="VNINDEX")


class TestCongThucBenchmarkChiDungClose(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dates = weekdays(date(2023, 1, 2), 340)
        cls.stock = [*bars("AAA", cls.dates, base=80.0, step=0.17), *bars("BBB", cls.dates, base=120.0, step=0.09)]
        cls.close_only = benchmark_close_rows(cls.dates)
        cls.legacy_a = benchmark_ohlcv_rows(cls.dates, high_pad=1.0, low_pad=1.0, open_offset=-0.2, volume_offset=0)
        cls.legacy_b = benchmark_ohlcv_rows(cls.dates, high_pad=8.0, low_pad=6.0, open_offset=3.0, volume_offset=9_000_000)
        cls.signal_dates = phien_cuoi_thang(cls.dates)

    def test_feature_close_only_giong_implementation_ohlcv_hop_le(self):
        self.assertEqual(tao_feature_cuoi_thang(self.stock, self.close_only, lich_benchmark=self.dates, feature_bat_buoc=("vnindex_momentum_60",)), tao_feature_cuoi_thang(self.stock, self.legacy_a, lich_benchmark=self.dates, feature_bat_buoc=("vnindex_momentum_60",)))

    def test_label_close_only_giong_implementation_ohlcv_hop_le(self):
        self.assertEqual(tao_nhan(self.stock, self.close_only, cac_ngay_tin_hieu=self.signal_dates, label_horizon=20, lich_benchmark=self.dates), tao_nhan(self.stock, self.legacy_a, cac_ngay_tin_hieu=self.signal_dates, label_horizon=20, lich_benchmark=self.dates))

    def test_metamorphic_ohlv_benchmark_khong_doi_feature_label_prediction_ranking_metric(self):
        features_a = tao_feature_cuoi_thang(self.stock, self.legacy_a, lich_benchmark=self.dates, feature_bat_buoc=("dong_luong_12_1",))
        features_b = tao_feature_cuoi_thang(self.stock, self.legacy_b, lich_benchmark=self.dates, feature_bat_buoc=("dong_luong_12_1",))
        labels_a = tao_nhan(self.stock, self.legacy_a, cac_ngay_tin_hieu=self.signal_dates, label_horizon=20, lich_benchmark=self.dates)
        labels_b = tao_nhan(self.stock, self.legacy_b, cac_ngay_tin_hieu=self.signal_dates, label_horizon=20, lich_benchmark=self.dates)
        self.assertEqual(features_a, features_b)
        self.assertEqual(labels_a, labels_b)
        eligible = {(row.ngay, row.ma) for row in features_a if row.hop_le}
        samples_a, momentum_a = _samples(features_a, labels_a, eligible, ("dong_luong_12_1",))
        samples_b, momentum_b = _samples(features_b, labels_b, eligible, ("dong_luong_12_1",))
        self.assertEqual(samples_a, samples_b)
        predictions_a = du_doan_baseline_test(fold="fold_close", samples=samples_a, momentum_theo_khoa=momentum_a)
        predictions_b = du_doan_baseline_test(fold="fold_close", samples=samples_b, momentum_theo_khoa=momentum_b)
        self.assertEqual(predictions_a, predictions_b)
        self.assertEqual(xep_hang_baseline_test(predictions_a, top_k=1), xep_hang_baseline_test(predictions_b, top_k=1))
        self.assertEqual(metric_baseline_test(predictions_a), metric_baseline_test(predictions_b))

    def test_thay_high_low_co_phieu_van_doi_bien_do(self):
        target = self.signal_dates[-1]
        stock_wide = [replace(row, gia_cao_nhat=row.gia_dong_cua + 5.0, gia_thap_nhat=row.gia_dong_cua - 5.0) if row.ma == "AAA" and row.ngay == target else row for row in self.stock]
        normal = tao_feature_cuoi_thang(self.stock, self.close_only, lich_benchmark=self.dates, feature_bat_buoc=("bien_do_cao_thap_chuan_hoa",))
        wide = tao_feature_cuoi_thang(stock_wide, self.close_only, lich_benchmark=self.dates, feature_bat_buoc=("bien_do_cao_thap_chuan_hoa",))
        normal_map = {(row.ngay, row.ma): row for row in normal}
        wide_map = {(row.ngay, row.ma): row for row in wide}
        self.assertNotEqual(normal_map[(target, "AAA")].gia_tri["bien_do_cao_thap_chuan_hoa"], wide_map[(target, "AAA")].gia_tri["bien_do_cao_thap_chuan_hoa"])


class TestRunnerBenchmarkCloseOnly(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        fixture = cls.root / "fixture"
        fixture.mkdir()
        cls.paths = tao_fixture_runner(fixture)
        cls.result = chay_nghien_cuu_moc_4(duong_dan_cau_hinh=cls.paths["cau_hinh"], duong_dan_ohlcv=cls.paths["ohlcv"], duong_dan_benchmark=cls.paths["benchmark"], duong_dan_lich_benchmark=cls.paths["lich_benchmark"], duong_dan_universe=cls.paths["universe"], duong_dan_corporate_actions=cls.paths["corporate_actions"], thu_muc_dau_ra=cls.root / "out", ma_lan_chay="close-only", git_commit=GIT_SHA, thoi_diem_utc=FIXED_TIME)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_manifest_report_co_contract_va_hai_warning(self):
        report = json.loads((self.result.thu_muc_san_pham / "bao_cao.json").read_text(encoding="utf-8"))
        manifest = json.loads((self.result.thu_muc_san_pham / "manifest.json").read_text(encoding="utf-8"))
        for payload in (report, manifest["metadata"]):
            self.assertEqual(payload["benchmark_contract"], BENCHMARK_CONTRACT)
            self.assertTrue(payload["benchmark_policy"]["features_va_labels_chi_dung_close"])
            self.assertFalse(payload["benchmark_policy"]["open_high_low_volume_duoc_dung"])
            self.assertFalse(payload["benchmark_policy"]["correction_overlay"])
            self.assertTrue(payload["benchmark_policy"]["raw_source_giu_bat_bien"])
            self.assertFalse(payload["benchmark_policy"]["exact_official_ohlc_da_co"])
            self.assertIn("BENCHMARK_CLOSE_ONLY", payload["canh_bao"])
            self.assertIn("BENCHMARK_OHLC_SEMANTICS_CHUA_XAC_NHAN", payload["canh_bao"])

    def test_runner_end_to_end_nhan_benchmark_close_only(self):
        with self.paths["benchmark"].open(newline="", encoding="utf-8") as handle:
            self.assertEqual(next(csv.reader(handle)), BENCHMARK_FIELDS)
        self.assertGreater(self.result.so_fold, 0)
        self.assertGreater(self.result.so_fold_thanh_cong, 0)

    def test_runner_tu_choi_full_ohlcv_o_vi_tri_benchmark_canonical(self):
        fixture_root = self.root / "full-ohlcv"
        fixture_root.mkdir()
        paths = tao_fixture_runner(fixture_root)
        full = fixture_root / "benchmark_full.csv"
        fields = ["ma", "ngay", "gia_mo_cua", "gia_cao_nhat", "gia_thap_nhat", "gia_dong_cua", "khoi_luong", "nguon", "phien_ban", "co_so_gia"]
        write_csv(full, fields, [{"ma": "VNINDEX", "ngay": "2024-01-02", "gia_mo_cua": 999.0, "gia_cao_nhat": 1001.0, "gia_thap_nhat": 998.0, "gia_dong_cua": 1000.0, "khoi_luong": 1_000_000, "nguon": "legacy", "phien_ban": "1", "co_so_gia": "gia_dieu_chinh"}])
        with self.assertRaisesRegex(ValueError, "sai schema"):
            chay_nghien_cuu_moc_4(duong_dan_cau_hinh=paths["cau_hinh"], duong_dan_ohlcv=paths["ohlcv"], duong_dan_benchmark=full, duong_dan_lich_benchmark=paths["lich_benchmark"], duong_dan_universe=paths["universe"], duong_dan_corporate_actions=paths["corporate_actions"], thu_muc_dau_ra=self.root / "reject", ma_lan_chay="reject-full", git_commit=GIT_SHA, thoi_diem_utc=FIXED_TIME)


if __name__ == "__main__":
    unittest.main()
'''
    path.parent.mkdir(parents=True, exist_ok=True)
    write(path, content)


def patch_docs(root: Path) -> None:
    append_once(root / "DECISIONS.md", "## QD-0061: Benchmark Moc 4 chi dung gia dong cua", """## QD-0061: Benchmark Moc 4 chi dung gia dong cua

Audit Tier A Giai doan 2A cua run `m4_tier_a_20260727T081753Z_e2c866db` ket luan `D.OFFICIAL_VALUES_UNAVAILABLE`, `SEMANTICS_DEFINITION_NOT_FOUND` va khoa quyet dinh `CLOSE_ONLY_BENCHMARK_CONTRACT`. Raw VNINDEX KBS `vnstock==4.0.4` co SHA-256 `a6ec1ab2d13cf620116ac5688c2cfd5e632a1bab72e3c1bde98df00a73ac616f` cung ho so audit duoc giu bat bien; khong co correction overlay, replacement value, ep max/min, loai phien hay noi suy.

`ThanhOHLCV` cua co phieu tiep tuc giu invariant OHLCV strict. Benchmark dung kieu `ThanhBenchmarkDongCua` va CSV canonical gom dung `ma,ngay,gia_dong_cua,nguon,phien_ban,co_so_gia`; khong mang open/high/low/volume. Feature va label benchmark chi duoc doc `gia_dong_cua`. Manifest va bao cao phai cong bo `benchmark_contract=close_only`, canh bao `BENCHMARK_CLOSE_ONLY` va `BENCHMARK_OHLC_SEMANTICS_CHUA_XAC_NHAN`, khong tuyen bo co so gia co phieu da duoc xac nhan.

PR canonical la #16 tren nhanh `m4-dac_trung-xep-hang-hoc_may-sach-final-v2`. G2A da hoan tat; vong hien tai chi sua contract close-only va kiem thu ky thuat. CI #347 chi la baseline cua head truoc QD-0061. Tier A pipeline, normalization, Tier B va Moc 5 chua chay.""")
    common = """## Cap nhat QD-0061: contract benchmark close-only

PR canonical hien tai la #16 tren nhanh `m4-dac_trung-xep-hang-hoc_may-sach-final-v2`. Giai doan 2A da hoan tat voi `D.OFFICIAL_VALUES_UNAVAILABLE`, `SEMANTICS_DEFINITION_NOT_FOUND` va `CLOSE_ONLY_BENCHMARK_CONTRACT`; cac tham chieu PR #14/CI cu o phan lich su khong phai trang thai current-head. CI #347 chi la baseline cua head cu truoc patch nay.

Co phieu tiep tuc dung `ThanhOHLCV` strict. Benchmark dung `ThanhBenchmarkDongCua` va schema CSV dung sau cot `ma,ngay,gia_dong_cua,nguon,phien_ban,co_so_gia`; open/high/low/volume benchmark khong duoc dua vao canonical input, sua, suy dien hoac dung trong feature/label. Raw KBS va ho so audit run `m4_tier_a_20260727T081753Z_e2c866db` giu bat bien; khong co correction overlay hay replacement values. Manifest/bao cao cong bo `benchmark_contract=close_only`, hai canh bao bat buoc va gioi han chi kiem tra ky thuat. Exact official OHLC van chua co; dieu nay khong xac nhan co so gia co phieu. Normalization, Tier A pipeline, Tier B va Moc 5 chua chay."""
    for relative in ("README.md", "tai_lieu/dac_ta_moc_4.md", "tai_lieu/kien_truc_moc_4.md", "tai_lieu_dieu_phoi/trang_thai_du_an.md", "tai_lieu_dieu_phoi/cong_viec_hien_tai.md", "tai_lieu_dieu_phoi/ban_giao_doan_chat.md", "tai_lieu_dieu_phoi/ke_hoach_tong_the.md"):
        append_once(root / relative, "## Cap nhat QD-0061: contract benchmark close-only", common)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: agent_patch_m4_close_only.py <repo-root>")
    root = Path(sys.argv[1]).resolve()
    if not (root / ".git").exists():
        raise SystemExit(f"Not a git worktree: {root}")
    patch_mo_hinh(root)
    patch_runner_io(root)
    patch_dac_trung(root)
    patch_nhan(root)
    patch_runner(root)
    patch_init(root)
    patch_runner_fixture(root)
    write_tests(root)
    patch_docs(root)
    print("PATCH_M4_BENCHMARK_CLOSE_ONLY_APPLIED")
    print(f"canonical_branch={CANONICAL_BRANCH}")
    print(f"expected_parent={EXPECTED_HEAD}")


if __name__ == "__main__":
    main()
