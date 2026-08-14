from __future__ import annotations

import csv
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZIP_DEFLATED, ZipFile

from he_thong_dinh_luong import portfolio_ablation_v32 as v32


def _csv_bytes(rows: list[dict[str, object]], fields: list[str]) -> bytes:
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue().encode("utf-8-sig")


class PortfolioAblationV32Tests(unittest.TestCase):
    def test_v22_policy_contract_parses_boolean_regime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "input.zip"
            rows = [
                {
                    "ngay": "2022-01-31",
                    "ma": "AAA",
                    "eligible": "true",
                    "vnindex_tren_ma250": "true",
                },
                {
                    "ngay": "2022-01-31",
                    "ma": "BBB",
                    "eligible": "false",
                    "vnindex_tren_ma250": "true",
                },
                {
                    "ngay": "2022-02-28",
                    "ma": "AAA",
                    "eligible": "true",
                    "vnindex_tren_ma250": "false",
                },
            ]
            with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
                archive.writestr(
                    "manifest.json",
                    json.dumps({"schema_version": "synthetic"}),
                )
                archive.writestr(
                    "feature_raw.csv",
                    _csv_bytes(
                        rows,
                        [
                            "ngay",
                            "ma",
                            "eligible",
                            "vnindex_tren_ma250",
                        ],
                    ),
                )
            eligible, regime, metadata = v32._load_v22_policy_contract(
                path,
                expected_sha256=None,
            )
            self.assertEqual(
                eligible,
                {("2022-01-31", "AAA"), ("2022-02-28", "AAA")},
            )
            self.assertEqual(
                regime,
                {"2022-01-31": 1.0, "2022-02-28": 0.0},
            )
            self.assertEqual(metadata["eligible_key_count"], 2)

    def test_eligibility_filter_and_regime_gates(self) -> None:
        predictions: list[dict[str, object]] = []
        for day in ("2022-01-31", "2022-02-28"):
            for model_index, model in enumerate(v32.SOURCE_MODELS):
                for symbol_index, symbol in enumerate(("AAA", "BBB", "CCC")):
                    predictions.append(
                        {
                            "protocol": v32.PRIMARY_PROTOCOL,
                            "model": model,
                            "test_date": day,
                            "symbol": symbol,
                            "score": model_index + symbol_index / 10.0,
                            "stock_return": 0.02,
                            "benchmark_return": 0.01,
                            "relative_return": 0.01,
                            "label_end": "2022-03-31",
                        }
                    )
        eligible = {
            ("2022-01-31", "AAA"),
            ("2022-01-31", "BBB"),
            ("2022-02-28", "AAA"),
            ("2022-02-28", "BBB"),
        }
        rows, metadata = v32._eligible_primary_predictions(
            predictions,
            eligible_keys=eligible,
            regime_by_day={
                "2022-01-31": 1.0,
                "2022-02-28": 0.0,
            },
        )
        self.assertEqual(len(rows), len(eligible) * len(v32.CANDIDATE_MODELS))
        self.assertEqual(
            metadata["excluded_noneligible_prediction_key_count_per_model"],
            2,
        )
        gated_c3 = [
            row
            for row in rows
            if row["model"] == v32.LOGIT_ON_C3_OFF
        ]
        source_by_day = {
            str(row["test_date"]): str(row["source_model_by_regime"])
            for row in gated_c3
        }
        self.assertEqual(
            source_by_day["2022-01-31"],
            v32.LOGIT_MODEL,
        )
        self.assertEqual(
            source_by_day["2022-02-28"],
            v32.FROZEN_MODEL,
        )

    def test_rank_is_recomputed_per_model_and_month(self) -> None:
        rows = [
            {
                "model": "A",
                "test_date": "2022-01-31",
                "symbol": "AAA",
                "score": 0.1,
            },
            {
                "model": "A",
                "test_date": "2022-01-31",
                "symbol": "BBB",
                "score": 0.9,
            },
            {
                "model": "A",
                "test_date": "2022-02-28",
                "symbol": "AAA",
                "score": 0.8,
            },
            {
                "model": "A",
                "test_date": "2022-02-28",
                "symbol": "BBB",
                "score": 0.2,
            },
        ]
        ranked = v32._recompute_rank(rows)
        best = {
            str(row["test_date"]): str(row["symbol"])
            for row in ranked
            if int(row["rank"]) == 1
        }
        self.assertEqual(
            best,
            {
                "2022-01-31": "BBB",
                "2022-02-28": "AAA",
            },
        )

    def test_inconsistent_regime_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "input.zip"
            rows = [
                {
                    "ngay": "2022-01-31",
                    "ma": "AAA",
                    "eligible": "true",
                    "vnindex_tren_ma250": "true",
                },
                {
                    "ngay": "2022-01-31",
                    "ma": "BBB",
                    "eligible": "true",
                    "vnindex_tren_ma250": "false",
                },
            ]
            with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
                archive.writestr(
                    "manifest.json",
                    json.dumps({"schema_version": "synthetic"}),
                )
                archive.writestr(
                    "feature_raw.csv",
                    _csv_bytes(
                        rows,
                        [
                            "ngay",
                            "ma",
                            "eligible",
                            "vnindex_tren_ma250",
                        ],
                    ),
                )
            with self.assertRaisesRegex(ValueError, "V32_V22_REGIME_CONFLICT"):
                v32._load_v22_policy_contract(
                    path,
                    expected_sha256=None,
                )


if __name__ == "__main__":
    unittest.main()
