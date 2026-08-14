from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from he_thong_dinh_luong import model_lab_upgrade_v11 as v11
from he_thong_dinh_luong import model_lab_upgrade_v12 as v12


class ModelLabUpgradeV12RecursionTests(unittest.TestCase):
    def test_run_model_lab_does_not_monkeypatch_v11_turnover_function(self):
        original_turnover = v11.turnover_capped_periods

        def fake_v11_run(**kwargs: object) -> dict[str, object]:
            self.assertIs(v11.turnover_capped_periods, original_turnover)
            self.assertEqual(Path(str(kwargs["output_dir"])), Path("unused"))
            return {"base": "ok"}

        with (
            patch.object(v12.v11, "run_model_lab", side_effect=fake_v11_run),
            patch.object(
                v12,
                "publish_v12_contract",
                return_value={"audit": "ok"},
            ),
        ):
            result = v12.run_model_lab(output_dir=Path("unused"))

        self.assertEqual(result, {"base": "ok", "audit": "ok"})
        self.assertIs(v11.turnover_capped_periods, original_turnover)


if __name__ == "__main__":
    unittest.main()
