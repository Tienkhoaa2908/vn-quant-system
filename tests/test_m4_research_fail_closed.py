from __future__ import annotations

from datetime import date
import unittest

from he_thong_dinh_luong.nghien_cuu_moc_4.mo_hinh import DuDoan, ThanhOHLCV
from he_thong_dinh_luong.nghien_cuu_moc_4.runner import (
    _research_fail_closed,
    _xac_thuc_benchmark_identity,
)
from ho_tro_m4 import cau_hinh


class TestResearchFailClosed(unittest.TestCase):
    def setUp(self) -> None:
        self.day = date(2025, 1, 31)
        self.prediction = DuDoan("f", "m", "test", self.day, "AAA", 0.6, 1, 0.1)
        self.config = cau_hinh(
            muc_dich_lan_chay="nghien_cuu",
            co_so_gia_da_xac_nhan=True,
            corporate_actions_day_du=True,
        )

    def _call(self, **overrides):
        values = {
            "config": self.config,
            "warnings": [],
            "benchmark_metadata_missing": (),
            "successful_fold_count": 1,
            "test_predictions": (self.prediction,),
            "rebalance_dates": (self.day,),
            "coverage_by_day": {self.day: (1, 1)},
        }
        values.update(overrides)
        return _research_fail_closed(**values)

    def test_benchmark_file_nhieu_ma_bi_tu_choi(self) -> None:
        rows = [
            ThanhOHLCV("VNINDEX", self.day, 10, 11, 9, 10, 100),
            ThanhOHLCV("HNXINDEX", self.day, 10, 11, 9, 10, 100),
        ]
        with self.assertRaisesRegex(ValueError, "dung mot ma VNINDEX"):
            _xac_thuc_benchmark_identity(rows, "VNINDEX")

    def test_benchmark_identity_sai_bi_tu_choi(self) -> None:
        rows = [ThanhOHLCV("HNXINDEX", self.day, 10, 11, 9, 10, 100)]
        with self.assertRaisesRegex(ValueError, "VNINDEX"):
            _xac_thuc_benchmark_identity(rows, "VNINDEX")

    def test_thieu_benchmark_metadata_pit_bi_tu_choi(self) -> None:
        with self.assertRaisesRegex(ValueError, "THIEU_BENCHMARK_METADATA_PIT"):
            self._call(benchmark_metadata_missing=(self.day,))

    def test_khong_co_fold_test_hop_le_bi_tu_choi(self) -> None:
        with self.assertRaisesRegex(ValueError, "KHONG_CO_FOLD_TEST_HOP_LE"):
            self._call(successful_fold_count=0)

    def test_khong_co_prediction_test_oos_bi_tu_choi(self) -> None:
        with self.assertRaisesRegex(ValueError, "KHONG_CO_PREDICTION_TEST_OOS"):
            self._call(test_predictions=())

    def test_khong_co_ngay_tai_can_bang_bi_tu_choi(self) -> None:
        with self.assertRaisesRegex(ValueError, "KHONG_CO_NGAY_TAI_CAN_BANG"):
            self._call(rebalance_dates=())

    def test_coverage_duoi_nguong_bi_tu_choi(self) -> None:
        config = cau_hinh(
            muc_dich_lan_chay="nghien_cuu", co_so_gia_da_xac_nhan=True,
            corporate_actions_day_du=True, ty_le_coverage_toi_thieu=0.8,
        )
        with self.assertRaisesRegex(ValueError, "COVERAGE_DUOI_NGUONG_TOI_THIEU"):
            self._call(config=config, coverage_by_day={self.day: (1, 2)})

    def test_universe_eligible_duoi_nguong_bi_tu_choi(self) -> None:
        config = cau_hinh(
            muc_dich_lan_chay="nghien_cuu", co_so_gia_da_xac_nhan=True,
            corporate_actions_day_du=True, so_ma_eligible_toi_thieu=2,
        )
        with self.assertRaisesRegex(ValueError, "UNIVERSE_ELIGIBLE_DUOI_NGUONG_TOI_THIEU"):
            self._call(config=config, coverage_by_day={self.day: (1, 1)})

    def test_technical_duoc_tiep_tuc_nhung_co_canh_bao(self) -> None:
        warnings: list[str] = []
        technical = cau_hinh(muc_dich_lan_chay="kiem_tra_ky_thuat")
        _research_fail_closed(
            config=technical, warnings=warnings, benchmark_metadata_missing=(self.day,),
            successful_fold_count=0, test_predictions=(), rebalance_dates=(),
            coverage_by_day={self.day: (0, 1)},
        )
        self.assertIn("TECHNICAL_THIEU_BENCHMARK_METADATA_PIT", warnings)
        self.assertIn("TECHNICAL_KHONG_CO_FOLD_TEST_HOP_LE", warnings)


if __name__ == "__main__":
    unittest.main()
