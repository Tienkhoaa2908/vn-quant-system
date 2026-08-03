from __future__ import annotations

import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from he_thong_dinh_luong import all_history_protocol_v31 as core
from he_thong_dinh_luong.all_history_protocol_v31_compat_runner import (
    _finite_feature,
    _load_all_history_zip_compatible,
)


class V31BooleanCompatibilityTests(unittest.TestCase):
    def test_canonical_boolean_text_becomes_numeric(self) -> None:
        self.assertEqual(_finite_feature("true", name="x"), 1.0)
        self.assertEqual(_finite_feature("false", name="x"), 0.0)
        self.assertEqual(_finite_feature("1", name="x"), 1.0)
        self.assertEqual(_finite_feature("0", name="x"), 0.0)
        self.assertEqual(_finite_feature("0.25", name="x"), 0.25)

    def test_noneligible_complete_row_is_trainable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "input.zip"
            feature_fields = [
                "ngay",
                "ma",
                "hop_le",
                "eligible",
                "gia_tren_ma250",
                *core.MODEL_FEATURE_FIELDS,
            ]
            feature_row = {
                "ngay": "2020-01-31",
                "ma": "AAA",
                "hop_le": "true",
                "eligible": "false",
                "gia_tren_ma250": "false",
            }
            for name in core.MODEL_FEATURE_FIELDS:
                feature_row[name] = "0.1"
            feature_row["vnindex_tren_ma250"] = "true"

            label_fields = [
                "ngay",
                "ma",
                "ngay_ket_thuc_nhan",
                "loi_nhuan_co_phieu",
                "loi_nhuan_benchmark",
                "loi_nhuan_tuong_doi",
            ]
            label_row = {
                "ngay": "2020-01-31",
                "ma": "AAA",
                "ngay_ket_thuc_nhan": "2020-02-28",
                "loi_nhuan_co_phieu": "0.08",
                "loi_nhuan_benchmark": "0.03",
                "loi_nhuan_tuong_doi": "0.05",
            }

            def csv_bytes(fields: list[str], row: dict[str, str]) -> bytes:
                buffer = io.StringIO(newline="")
                writer = csv.DictWriter(
                    buffer,
                    fieldnames=fields,
                    lineterminator="\n",
                )
                writer.writeheader()
                writer.writerow(row)
                return buffer.getvalue().encode("utf-8-sig")

            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("manifest.json", json.dumps({}))
                archive.writestr(
                    "feature_raw.csv",
                    csv_bytes(feature_fields, feature_row),
                )
                archive.writestr(
                    "nhan.csv",
                    csv_bytes(label_fields, label_row),
                )

            rows, _, coverage = _load_all_history_zip_compatible(path)

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].features["vnindex_tren_ma250"], 1.0)
            self.assertEqual(coverage["model_trainable_row_count"], 1)
            self.assertEqual(
                coverage["non_portfolio_eligible_trainable_row_count"],
                1,
            )
            self.assertEqual(
                coverage["below_or_not_above_ma250_trainable_row_count"],
                1,
            )
            self.assertEqual(coverage["invalid_model_field_counts"], {})


if __name__ == "__main__":
    unittest.main()
