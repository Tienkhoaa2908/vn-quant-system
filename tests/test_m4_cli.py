from __future__ import annotations
import contextlib
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from he_thong_dinh_luong.nghien_cuu_moc_4.dong_lenh import main
from ho_tro_m4 import cau_hinh_mapping


class TestCliM4(unittest.TestCase):
    def test_cli_xac_thuc_fixture_ngoai_tuyen(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"config.json"
            path.write_text(json.dumps(cau_hinh_mapping()),encoding="utf-8")
            output=StringIO()
            with contextlib.redirect_stdout(output):
                code=main(["--kiem-tra-cau-hinh",str(path)])
            self.assertEqual(code,0)
            self.assertTrue(json.loads(output.getvalue())["hop_le"])

    def test_cli_khong_co_tham_so_mang(self):
        with self.assertRaises(SystemExit):
            main(["--url","https://example.com"])
