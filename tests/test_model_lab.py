from __future__ import annotations

import csv
from datetime import date, timedelta
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from he_thong_dinh_luong.model_lab_core import (
    BacktestConfig,
    Outcome,
    backtest_top_k,
    build_walk_forward_folds,
    candidate_gate,
    ensemble_scores,
    online_ensemble_weights,
)
from he_thong_dinh_luong.model_lab_runner import run_model_lab
from he_thong_dinh_luong.nghien_cuu_moc_4.du_doan_tien_phuong_contract import (
    REGIME_FEATURES,
    STOCK_RANK_FEATURES,
    Row,
)


def _csv_bytes(rows, fields):
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _input_zip(path: Path, months: int = 44) -> None:
    feature_order = list(STOCK_RANK_FEATURES) + list(REGIME_FEATURES)
    feature_fields = [
        "ngay", "ma", "hop_le", "ly_do", "eligible", "ly_do_eligibility",
        "gtgd_tb_20_eligibility", "T1", "open_t1_hop_le", *feature_order,
    ]
    label_fields = [
        "ngay", "ma", "T_H", "ngay_ket_thuc_nhan", "loi_nhuan_co_phieu",
        "loi_nhuan_benchmark", "loi_nhuan_tuong_doi", "nhan", "ly_do_nhan_rong",
    ]
    feature_rows = []
    label_rows = []
    symbols = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]
    start = date(2021, 1, 31)
    history_days = []
    for month in range(months):
        current = start + timedelta(days=30 * month)
        history_days.append(current)
        for index, symbol in enumerate(symbols):
            strength = float(index) / 10.0 + month / 1000.0
            values = {name: strength + offset / 1000.0 for offset, name in enumerate(STOCK_RANK_FEATURES)}
            values["dong_luong_12_1"] = strength
            values.update({
                "gia_tren_ma250": "true",
                "vnindex_tren_ma250": "true",
                "vnindex_momentum_60": "0.05",
                "vnindex_bien_dong_20": "0.02",
                "vnindex_bien_dong_60": "0.03",
            })
            feature_rows.append({
                "ngay": current.isoformat(), "ma": symbol, "hop_le": "true", "ly_do": "",
                "eligible": "true", "ly_do_eligibility": "", "gtgd_tb_20_eligibility": "1",
                "T1": (current + timedelta(days=1)).isoformat(), "open_t1_hop_le": "true", **values,
            })
            relative = (index - 2.5) / 100.0
            label_end = current + timedelta(days=20)
            label_rows.append({
                "ngay": current.isoformat(), "ma": symbol, "T_H": label_end.isoformat(),
                "ngay_ket_thuc_nhan": label_end.isoformat(),
                "loi_nhuan_co_phieu": str(0.01 + relative),
                "loi_nhuan_benchmark": "0.01",
                "loi_nhuan_tuong_doi": str(relative),
                "nhan": "1" if relative > 0 else "0", "ly_do_nhan_rong": "",
            })
    forward = history_days[-1] + timedelta(days=30)
    for index, symbol in enumerate(symbols):
        strength = float(index) / 10.0
        values = {name: strength + offset / 1000.0 for offset, name in enumerate(STOCK_RANK_FEATURES)}
        values["dong_luong_12_1"] = strength
        values.update({
            "gia_tren_ma250": "true", "vnindex_tren_ma250": "true",
            "vnindex_momentum_60": "0.05", "vnindex_bien_dong_20": "0.02",
            "vnindex_bien_dong_60": "0.03",
        })
        feature_rows.append({
            "ngay": forward.isoformat(), "ma": symbol, "hop_le": "true", "ly_do": "",
            "eligible": "false", "ly_do_eligibility": "thieu_open_t1",
            "gtgd_tb_20_eligibility": "1", "T1": "", "open_t1_hop_le": "false", **values,
        })
    blobs = {
        "cau_hinh.json": json.dumps({"moc_4": {"feature_order": feature_order}}, sort_keys=True).encode(),
        "feature_raw.csv": _csv_bytes(feature_rows, feature_fields),
        "nhan.csv": _csv_bytes(label_rows, label_fields),
        "chi_so_mo_hinh.json": b"{}\n",
    }
    manifest = {
        "manifest_schema_version": "m4_manifest_v2",
        "files": {name: {"sha256": sha256(payload).hexdigest(), "size": len(payload)} for name, payload in blobs.items()},
    }
    with ZipFile(path, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        for name, payload in blobs.items():
            archive.writestr(name, payload)


class ModelLabCoreTests(unittest.TestCase):
    def test_walk_forward_purges_unfinished_labels(self):
        rows = []
        start = date(2020, 1, 31)
        for month in range(40):
            day = start + timedelta(days=30 * month)
            rows.append(Row(day, "AAA", {}, 0.01, day + timedelta(days=20)))
        folds = build_walk_forward_folds(
            rows, evaluation_months=8, minimum_train_months=12, inner_validation_months=3,
        )
        self.assertTrue(folds)
        for fold in folds:
            self.assertTrue(all(row.ngay < fold.test_day for row in fold.train_rows))
            self.assertTrue(all(row.label_end < fold.test_day for row in fold.train_rows))
            self.assertTrue(all(row.label_end < fold.test_day for row in fold.validation_rows))
            self.assertTrue(all(row.ngay == fold.test_day for row in fold.test_rows))

    def test_online_ensemble_uses_prior_history_and_normalizes(self):
        weights = online_ensemble_weights(
            {"a": [0.1, 0.1, 0.1], "b": [-0.1, -0.1, -0.1]}, ["a", "b"]
        )
        self.assertAlmostEqual(sum(weights.values()), 1.0)
        self.assertGreater(weights["a"], weights["b"])
        scores = ensemble_scores({"a": [1, 2, 3], "b": [3, 2, 1]}, weights)
        self.assertEqual(len(scores), 3)

    def test_backtest_applies_entry_and_turnover_costs(self):
        day1, day2 = date(2025, 1, 31), date(2025, 2, 28)
        rows = [
            Row(day1, "AAA", {}, 0.02, day1 + timedelta(days=20)),
            Row(day1, "BBB", {}, 0.01, day1 + timedelta(days=20)),
            Row(day2, "AAA", {}, 0.02, day2 + timedelta(days=20)),
            Row(day2, "CCC", {}, 0.03, day2 + timedelta(days=20)),
        ]
        outcomes = {
            (row.ngay, row.ma): Outcome(row.ngay, row.ma, row.label_end, 0.03, 0.01, 0.02)
            for row in rows
        }
        metrics, periods, nav = backtest_top_k(
            model="x", rows=rows, scores=[2, 1, 1, 2], outcomes=outcomes,
            config=BacktestConfig(top_k=1, buy_fee_bps=10, sell_fee_bps=10, sell_tax_bps=100, slippage_bps=10),
        )
        self.assertEqual(len(periods), 2)
        self.assertEqual(len(nav), 2)
        self.assertGreater(periods[0]["estimated_cost_rate"], 0)
        self.assertGreater(periods[1]["estimated_cost_rate"], periods[0]["estimated_cost_rate"])
        self.assertLess(metrics["total_return"], metrics["gross_total_return"])

    def test_gate_fails_negative_candidate(self):
        gate = candidate_gate(
            {"mean_rank_ic": -0.01, "positive_rank_ic_ratio": 0.4},
            {"period_count": 24, "average_net_excess_return": -0.01, "relative_total_return": -0.1, "sharpe": -0.2, "mean_turnover": 0.2, "max_drawdown": -0.1},
            {"mean_rank_ic": 0.0},
            {"average_net_excess_return": 0.0, "max_drawdown": -0.1},
        )
        self.assertFalse(all(gate.values()))
        self.assertFalse(gate["rank_ic_positive"])


class ModelLabRunnerTests(unittest.TestCase):
    def test_end_to_end_with_fake_challenger_publishes_safe_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_zip = root / "input.zip"
            output = root / "output"
            _input_zip(input_zip)

            def fake_ranker(_train, _validation, test, _seed):
                return [float(row.features["dong_luong_12_1"]) for row in test]

            result = run_model_lab(
                input_zip=input_zip,
                output_dir=output,
                models=("momentum_baseline", "ridge_ranker", "online_rank_ensemble_v1"),
                evaluation_months=18,
                minimum_train_months=12,
                inner_validation_months=3,
                top_k=2,
                predictor_overrides={"ridge_ranker": fake_ranker},
            )
            self.assertEqual(result["status"], "SUCCESS")
            self.assertTrue((output / "model_leaderboard.csv").is_file())
            self.assertTrue((output / "oos_nav.csv").is_file())
            self.assertTrue((output / "forward_model_scores.csv").is_file())
            summary = json.loads((output / "model_lab_summary.json").read_text(encoding="utf-8"))
            self.assertFalse(summary["live_capital_approved"])
            self.assertTrue(summary["walk_forward"]["label_end_purge"])
            with ZipFile(output / "model_lab_output.zip") as archive:
                names = set(archive.namelist())
            self.assertIn("model_leaderboard.csv", names)
            self.assertIn("manifest.json", names)
            self.assertFalse(any("credential" in name.lower() or "raw" in name.lower() for name in names))


if __name__ == "__main__":
    unittest.main()
