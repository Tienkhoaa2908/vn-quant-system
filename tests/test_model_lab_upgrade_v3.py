from __future__ import annotations

import unittest

from he_thong_dinh_luong.dnse_account_contract_v3 import (
    account_options,
    select_stock_account,
)
from he_thong_dinh_luong.model_lab_upgrade_v3 import conservative_online_weights


class _AccountModel:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def model_dump(self, *, by_alias: bool = False) -> dict[str, object]:
        del by_alias
        return dict(self.payload)


class ModelLabUpgradeV3Tests(unittest.TestCase):
    def test_ensemble_khong_chia_trong_so_cho_model_am(self) -> None:
        weights = conservative_online_weights(
            {
                "momentum_baseline": (-0.03, -0.02, -0.01, -0.04, -0.02, -0.01),
                "ridge_ranker": (0.01, 0.03, 0.02, -0.01, 0.04, 0.02),
                "lightgbm_ranker": (-0.02, 0.01, -0.03, -0.01, 0.00, -0.02),
            },
            ("momentum_baseline", "ridge_ranker", "lightgbm_ranker"),
        )
        self.assertEqual(set(weights), {"ridge_ranker"})
        self.assertAlmostEqual(sum(weights.values()), 1.0)

    def test_ensemble_thieu_bang_chung_chi_fallback_momentum(self) -> None:
        weights = conservative_online_weights(
            {
                "momentum_baseline": (-0.01, -0.02),
                "ridge_ranker": (0.02, 0.01),
            },
            ("ridge_ranker", "momentum_baseline"),
        )
        self.assertEqual(weights, {"momentum_baseline": 1.0})


class DnseAccountContractV3Tests(unittest.TestCase):
    def test_doc_dung_account_type_name_va_derivative_account(self) -> None:
        options = account_options([
            _AccountModel({
                "id": "00010001",
                "accountTypeName": "Tài khoản cơ sở",
                "derivativeAccount": False,
            }),
            {
                "id": "00010002",
                "accountTypeName": "Tài khoản phái sinh",
                "derivativeAccount": True,
            },
        ])
        self.assertEqual(options[0]["account_no"], "00010001")
        self.assertEqual(options[0]["account_type"], "Tài khoản cơ sở")
        self.assertFalse(options[0]["is_derivative"])
        self.assertTrue(options[1]["is_derivative"])
        self.assertNotIn("00010001", str(options[0]["display_label"]))

    def test_mac_dinh_chon_tai_khoan_co_so(self) -> None:
        selected = select_stock_account([
            {"id": "D01", "accountTypeName": "DERIVATIVE", "derivativeAccount": True},
            {"id": "S01", "accountTypeName": "STOCK", "derivativeAccount": False},
        ])
        self.assertEqual(selected["account_no"], "S01")

    def test_chan_tai_khoan_phai_sinh_duoc_chon_ro(self) -> None:
        with self.assertRaisesRegex(ValueError, "DNSE_DERIVATIVE_ACCOUNT_NOT_SUPPORTED"):
            select_stock_account([
                {"id": "D01", "accountTypeName": "DERIVATIVE", "derivativeAccount": True},
            ], "D01")


if __name__ == "__main__":
    unittest.main()
