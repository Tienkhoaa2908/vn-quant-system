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

from he_thong_dinh_luong.nghien_cuu_moc_4.du_doan_tien_phuong import (
    Metrics,
    REGIME_FEATURES,
    STOCK_RANK_FEATURES,
    Row,
    _average_percentile,
    _champion,
    _load_verified_input,
    _split_history,
    run_forward_prediction,
)

class _FakeRanker:
    def __init__(self, params):
        self.params = dict(params)
        self.best_iteration_ = 1

    def fit(self, X, y, **kwargs):
        self.best_iteration_ = 1
        return self

    def predict(self, X, num_iteration=None):
        return [float(row[0]) for row in X]

def _csv_bytes(rows, fields):
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")

def _make_input_zip(path: Path) -> None:
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
    symbols = ["AAA", "BBB", "CCC", "DDD"]
    day = date(2024, 1, 31)
    history_days = []
    for month in range(16):
        current = day + timedelta(days=30 * month)
        history_days.append(current)
        for index, symbol in enumerate(symbols):
            base = float(index + 1 + month / 10)
            values = {name: base + offset / 100 for offset, name in enumerate(STOCK_RANK_FEATURES)}
            values.update({
                "gia_tren_ma250": "true",
                "vnindex_tren_ma250": "true",
                "vnindex_momentum_60": "0.1",
                "vnindex_bien_dong_20": "0.02",
                "vnindex_bien_dong_60": "0.03",
            })
            feature_rows.append({
                "ngay": current.isoformat(), "ma": symbol, "hop_le": "true", "ly_do": "",
                "eligible": "true", "ly_do_eligibility": "", "gtgd_tb_20_eligibility": "1",
                "T1": (current + timedelta(days=1)).isoformat(), "open_t1_hop_le": "true", **values,
            })
            relative = (index - 1.5) / 100 + month / 10000
            label_end = current + timedelta(days=20)
            label_rows.append({
                "ngay": current.isoformat(), "ma": symbol, "T_H": label_end.isoformat(),
                "ngay_ket_thuc_nhan": label_end.isoformat(), "loi_nhuan_co_phieu": str(relative + 0.01),
                "loi_nhuan_benchmark": "0.01", "loi_nhuan_tuong_doi": str(relative),
                "nhan": "1" if relative > 0 else "0", "ly_do_nhan_rong": "",
            })
    forward_day = history_days[-1] + timedelta(days=30)
    for index, symbol in enumerate(symbols):
        base = float(index + 3)
        values = {name: base + offset / 100 for offset, name in enumerate(STOCK_RANK_FEATURES)}
        values.update({
            "gia_tren_ma250": "true",
            "vnindex_tren_ma250": "false",
            "vnindex_momentum_60": "-0.1",
            "vnindex_bien_dong_20": "0.02",
            "vnindex_bien_dong_60": "0.03",
        })
        feature_rows.append({
            "ngay": forward_day.isoformat(), "ma": symbol, "hop_le": "true", "ly_do": "",
            "eligible": "false", "ly_do_eligibility": "thieu_open_t1",
            "gtgd_tb_20_eligibility": "1", "T1": "", "open_t1_hop_le": "false", **values,
        })
    blobs = {
        "cau_hinh.json": json.dumps({"moc_4": {"feature_order": feature_order}}, sort_keys=True).encode(),
        "feature_raw.csv": _csv_bytes(feature_rows, feature_fields),
        "nhan.csv": _csv_bytes(label_rows, label_fields),
        "chi_so_mo_hinh.json": b'{"logistic":{"auc":0.5}}\n',
    }
    manifest = {
        "manifest_schema_version": "m4_manifest_v2",
        "files": {name: {"sha256": sha256(payload).hexdigest(), "size": len(payload)} for name, payload in blobs.items()},
    }
    with ZipFile(path, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        for name, payload in blobs.items():
            archive.writestr(name, payload)

class ForwardPredictionTests(unittest.TestCase):
    def test_average_percentile_ties(self):
        self.assertEqual(_average_percentile([1.0, 1.0, 3.0]), [0.25, 0.25, 1.0])

    def test_temporal_split_removes_overlapping_labels(self):
        rows = []
        start = date(2024, 1, 1)
        for index in range(20):
            day = start + timedelta(days=30 * index)
            rows.append(Row(day, "AAA", {}, 0.01, day + timedelta(days=20)))
        train, validation, validation_start = _split_history(rows, 3)
        self.assertTrue(validation)
        self.assertTrue(train)
        self.assertTrue(all(row.label_end < validation_start for row in train))

    def test_champion_gate_is_fail_closed(self):
        momentum = Metrics(0.02, 0.5, 0.01, 0.3, 12)
        weak = Metrics(0.01, 0.6, 0.02, 0.2, 12)
        champion, checks = _champion(weak, momentum)
        self.assertEqual(champion, "momentum_baseline")
        self.assertFalse(checks["rank_ic_beats_momentum"])
        strong = Metrics(0.05, 0.6, 0.03, 0.4, 12)
        champion, checks = _champion(strong, momentum)
        self.assertEqual(champion, "lightgbm_ranker")
        self.assertTrue(all(checks.values()))

    def test_input_hash_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "input.zip"
            _make_input_zip(path)
            bad = root / "bad.zip"
            with ZipFile(path) as source, ZipFile(bad, "w") as target:
                for name in source.namelist():
                    target.writestr(name, b"tampered" if name == "feature_raw.csv" else source.read(name))
            with self.assertRaisesRegex(ValueError, "INPUT_FILE_SHA_MISMATCH"):
                _load_verified_input(bad)

    def test_forward_run_ignores_missing_open_t1_and_publishes_safe_zip(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_zip = root / "input.zip"
            output = root / "output"
            _make_input_zip(input_zip)
            result = run_forward_prediction(
                input_zip=input_zip,
                output_dir=output,
                top_k=2,
                validation_months=3,
                ranker_factory=lambda params: _FakeRanker(params),
            )
            self.assertEqual(result["status"], "SUCCESS")
            self.assertEqual(result["market_regime"], "RISK_OFF")
            predictions = (output / "latest_prediction.csv").read_text(encoding="utf-8-sig")
            self.assertIn("AAA", predictions)
            self.assertIn("DDD", predictions)
            with ZipFile(output / "forward_prediction_output.zip") as archive:
                names = set(archive.namelist())
            self.assertEqual(names, {"latest_prediction.csv", "model_comparison.json", "prediction_summary.txt", "manifest.json"})
            self.assertFalse(any("raw" in name.lower() for name in names))

if __name__ == "__main__":
    unittest.main()
