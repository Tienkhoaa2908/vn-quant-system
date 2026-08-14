from __future__ import annotations

import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from he_thong_dinh_luong import component_breadth_ablation_v27 as v27
from he_thong_dinh_luong import predictive_target_lab_v29 as core
from he_thong_dinh_luong import predictive_target_lab_v29_runner as runner


FEATURE_FIELDS = (
    "dong_luong_12_1",
    "bien_dong_60",
    "suc_manh_tuong_doi_120",
    "khoang_cach_ma60",
    "khoang_cach_ma120",
    "khoang_cach_ma250",
    "loi_nhuan_20",
    "loi_nhuan_60",
    "loi_nhuan_120",
    "loi_nhuan_250",
    "ty_le_dinh_52_tuan",
)


def _csv_bytes(rows: list[dict[str, object]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=list(rows[0]),
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def _write_v22_zip(path: Path) -> None:
    feature_rows: list[dict[str, object]] = []
    label_rows: list[dict[str, object]] = []
    for symbol, regime in (("AAA", "true"), ("BBB", "false")):
        feature = {
            "ngay": "2020-01-31",
            "ma": symbol,
            "hop_le": "true",
            "eligible": "true",
            **{name: "0.1" for name in FEATURE_FIELDS},
            "vnindex_tren_ma250": regime,
        }
        feature_rows.append(feature)
        label_rows.append({
            "ngay": "2020-01-31",
            "ma": symbol,
            "ngay_ket_thuc_nhan": "2020-02-28",
            "loi_nhuan_co_phieu": "0.02",
            "loi_nhuan_benchmark": "0.01",
            "loi_nhuan_tuong_doi": "0.01",
        })
    with zipfile.ZipFile(
        path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.writestr("feature_raw.csv", _csv_bytes(feature_rows))
        archive.writestr("nhan.csv", _csv_bytes(label_rows))
        archive.writestr(
            "manifest.json",
            json.dumps({"schema_version": "historical_research_input_v22"}),
        )


class PredictiveTargetLabV29RunnerTests(unittest.TestCase):
    def test_real_v22_boolean_rows_are_not_silently_discarded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "daily_prediction_input.zip"
            _write_v22_zip(path)
            with self.assertRaisesRegex(ValueError, "V27_NO_USABLE_ROWS"):
                v27._load_input_zip(path)
            rows, manifest = runner.load_input_zip_v22_compatible(path)
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            manifest["schema_version"],
            "historical_research_input_v22",
        )
        self.assertEqual(rows[0].features["vnindex_tren_ma250"], 1.0)
        self.assertEqual(rows[1].features["vnindex_tren_ma250"], 0.0)

    def test_v22_boolean_adapter_is_strict(self) -> None:
        self.assertEqual(
            runner._finite_with_v22_boolean(
                v27._finite,
                "true",
                name="vnindex_tren_ma250",
            ),
            1.0,
        )
        self.assertEqual(
            runner._finite_with_v22_boolean(
                v27._finite,
                "false",
                name="vnindex_tren_ma250",
            ),
            0.0,
        )
        with self.assertRaisesRegex(ValueError, "V29_INVALID_V22_BOOLEAN"):
            runner._finite_with_v22_boolean(
                v27._finite,
                "unknown",
                name="vnindex_tren_ma250",
            )

    def test_union_writer_keeps_logit_and_hybrid_audit_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "selection.csv"
            runner._write_csv_with_union_fields(path, [
                {"model": "ridge", "selected_alpha": 10.0},
                {
                    "model": "logit",
                    "selected_c": 1.0,
                    "validation_bottom20_recall": 0.4,
                },
                {
                    "model": "hybrid",
                    "rank_weight": 0.5,
                    "bottom_safe_weight": 0.5,
                },
            ])
            with path.open(
                "r",
                encoding="utf-8-sig",
                newline="",
            ) as stream:
                rows = list(csv.DictReader(stream))
        self.assertIn("selected_c", rows[0])
        self.assertIn("validation_bottom20_recall", rows[0])
        self.assertIn("rank_weight", rows[0])
        self.assertIn("bottom_safe_weight", rows[0])
        self.assertEqual(rows[1]["selected_c"], "1.0")
        self.assertEqual(rows[2]["bottom_safe_weight"], "0.5")

    def test_run_restores_original_parser_and_writer(self) -> None:
        original_finite = v27._finite
        original_writer = core._write_csv

        def fake_run(**kwargs: object) -> dict[str, object]:
            self.assertEqual(
                v27._finite("true", name="vnindex_tren_ma250"),
                1.0,
            )
            self.assertIs(core._write_csv, runner._write_csv_with_union_fields)
            return {"status": "SUCCESS", **kwargs}

        with patch.object(
            core,
            "run_predictive_target_lab",
            side_effect=fake_run,
        ):
            result = runner.run_predictive_target_lab_v22_compatible(
                input_zip=Path("input.zip"),
                output_dir=Path("output"),
            )
        self.assertEqual(result["status"], "SUCCESS")
        self.assertIs(v27._finite, original_finite)
        self.assertIs(core._write_csv, original_writer)


if __name__ == "__main__":
    unittest.main()
