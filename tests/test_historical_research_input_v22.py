from __future__ import annotations

import csv
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZIP_DEFLATED, ZipFile

from he_thong_dinh_luong.dnse_historical_store_v20 import (
    DnseHistoricalStore,
    FetchRange,
)
from he_thong_dinh_luong.eod_hang_ngay import EodRow
from he_thong_dinh_luong.historical_research_input_v22 import (
    OUTPUT_ZIP,
    build_historical_research_input,
)
from he_thong_dinh_luong.nghien_cuu_moc_4.dac_trung import (
    FEATURE_ORDER_REDUCED_OPEN_CLOSE_VOLUME_V1,
)
from he_thong_dinh_luong.nghien_cuu_moc_4.du_doan_tien_phuong_contract import (
    REQUIRED_INPUT_FILES,
    _load_rows,
    _load_verified_input,
)

UTC = timezone.utc


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _csv_bytes(fields: tuple[str, ...]) -> bytes:
    output = StringIO(newline="")
    csv.DictWriter(output, fieldnames=list(fields), lineterminator="\n").writeheader()
    return output.getvalue().encode("utf-8-sig")


def _business_days(start: date, count: int) -> list[date]:
    result: list[date] = []
    cursor = start
    while len(result) < count:
        if cursor.weekday() < 5:
            result.append(cursor)
        cursor += timedelta(days=1)
    return result


def _bars(symbol: str, days: list[date], base: float) -> tuple[EodRow, ...]:
    rows = []
    for index, day in enumerate(days):
        close = base + index * 0.02
        rows.append(
            EodRow(
                symbol=symbol,
                day=day,
                open=close - 0.01,
                high=close + 0.03,
                low=close - 0.03,
                close=close,
                volume=1_000_000 + index,
                source="dnse_openapi",
                version="0.5.0",
            )
        )
    return tuple(rows)


def _template(path: Path) -> None:
    config = {
        "moc_4": {
            "feature_order": list(FEATURE_ORDER_REDUCED_OPEN_CLOSE_VOLUME_V1),
            "feature_bat_buoc": list(FEATURE_ORDER_REDUCED_OPEN_CLOSE_VOLUME_V1),
            "label_horizon": 20,
            "nguong_gtgd_tb_toi_thieu": 0.0,
            "muc_dich_lan_chay": "kiem_tra_ky_thuat",
            "price_contract": "reduced_open_close_volume_v1",
            "universe_contract": "technical_candidate_union_v1",
            "stock_price_basis": "CHUA_XAC_NHAN",
            "stock_price_basis_confirmed": False,
            "corporate_actions_day_du": False,
            "candidate_union_name": "old",
            "candidate_union_expected_count": 1,
            "candidate_union_is_point_in_time": False,
            "benchmark_price_basis_confirmed": False,
        }
    }
    blobs = {
        "cau_hinh.json": _json_bytes(config),
        "feature_raw.csv": _csv_bytes(
            (
                "ngay",
                "ma",
                "hop_le",
                "ly_do",
                "eligible",
                "ly_do_eligibility",
                "gtgd_tb_20_eligibility",
                "T1",
                "open_t1_hop_le",
            )
            + FEATURE_ORDER_REDUCED_OPEN_CLOSE_VOLUME_V1
        ),
        "nhan.csv": _csv_bytes(
            (
                "ngay",
                "ma",
                "T_H",
                "ngay_ket_thuc_nhan",
                "loi_nhuan_co_phieu",
                "loi_nhuan_benchmark",
                "loi_nhuan_tuong_doi",
                "nhan",
                "ly_do_nhan_rong",
            )
        ),
        "chi_so_mo_hinh.json": _json_bytes({"status": "template"}),
    }
    manifest = {
        "schema_version": "template",
        "files": {
            name: {"sha256": sha256(payload).hexdigest(), "size": len(payload)}
            for name, payload in blobs.items()
        },
    }
    blobs["manifest.json"] = _json_bytes(manifest)
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        for name, payload in blobs.items():
            archive.writestr(name, payload)


class TestHistoricalResearchInputV22(unittest.TestCase):
    def test_rebuilds_feature_and_label_history_from_store(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store_path = root / "dnse.sqlite3"
            store = DnseHistoricalStore(store_path)
            days = _business_days(date(2020, 1, 2), 430)
            window = FetchRange(days[0], days[-1])
            fetched_at = datetime(2026, 8, 1, tzinfo=UTC).isoformat()
            for asset_type, symbol, base in (
                ("INDEX", "VNINDEX", 900.0),
                ("STOCK", "AAA", 10.0),
                ("STOCK", "BBB", 20.0),
            ):
                store.apply(
                    asset_type,
                    symbol,
                    window,
                    _bars(symbol, days, base),
                    fetched_at=fetched_at,
                    source_name="dnse_openapi",
                    source_version="0.5.0",
                )

            template = root / "template.zip"
            _template(template)
            output = root / "output"
            result = build_historical_research_input(
                store_path=store_path,
                template_input_zip=template,
                output_dir=output,
                evaluation_months=72,
                minimum_train_months=60,
                minimum_outer_test_periods=48,
            )

            self.assertEqual(result["status"], "SUCCESS")
            self.assertEqual(result["stock_symbol_count"], 2)
            self.assertEqual(result["technical_validation_only"], True)
            self.assertEqual(result["research_eligible"], False)
            self.assertGreater(result["data_summary"]["complete_feature_row_count"], 0)
            self.assertGreater(result["data_summary"]["labeled_row_count"], 0)
            self.assertEqual(
                result["extended_history_preflight"]["status"],
                "INSUFFICIENT_HISTORY",
            )

            output_zip = output / OUTPUT_ZIP
            blobs, manifest, _ = _load_verified_input(output_zip)
            self.assertEqual(set(blobs), REQUIRED_INPUT_FILES)
            self.assertEqual(manifest["schema_version"], "historical_research_input_v22")
            self.assertEqual(manifest["candidate_union_is_point_in_time"], False)
            history, forward, forward_day = _load_rows(blobs)
            self.assertTrue(history)
            self.assertEqual({row.ma for row in forward}, {"AAA", "BBB"})
            self.assertEqual(
                forward_day.isoformat(),
                result["data_summary"]["last_monthly_signal_date"],
            )
            sibling = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(sibling["status"], "SUCCESS")
            self.assertEqual(sibling["research_eligible"], False)


if __name__ == "__main__":
    unittest.main()
