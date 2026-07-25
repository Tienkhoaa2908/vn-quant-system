import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from he_thong_dinh_luong.mo_phong.dong_lenh import main

class KiemTraLamSachStdout(unittest.TestCase):
    def _stdout(self, noi_dung):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/"out"
            buf=io.StringIO()
            with patch("he_thong_dinh_luong.mo_phong.dong_lenh._doc_json",side_effect=ValueError(noi_dung)),redirect_stdout(buf):
                self.assertEqual(main(["--duong_co_so","g.csv","--ty_trong_muc_tieu","t.csv","--cau_hinh","c.json","--thu_muc_dau_ra",str(out)]),2)
            return buf.getvalue(),(out/"bao_cao_loi.json").read_text()
    def test_stdout_an_token(self):
        stdout,bao_cao=self._stdout("token=BI_MAT");self.assertNotIn("BI_MAT",stdout);self.assertNotIn("BI_MAT",bao_cao)
    def test_stdout_an_secret(self):
        stdout,bao_cao=self._stdout("secret=BI_MAT");self.assertNotIn("BI_MAT",stdout);self.assertNotIn("BI_MAT",bao_cao)
    def test_stdout_an_password(self):
        stdout,bao_cao=self._stdout("password=BI_MAT");self.assertNotIn("BI_MAT",stdout);self.assertNotIn("BI_MAT",bao_cao)
    def test_stdout_an_bearer(self):
        stdout,bao_cao=self._stdout("Bearer BI_MAT");self.assertNotIn("BI_MAT",stdout);self.assertNotIn("BI_MAT",bao_cao)
