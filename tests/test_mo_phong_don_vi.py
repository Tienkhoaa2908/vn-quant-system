import json
import unittest
from he_thong_dinh_luong.mo_phong.bao_cao import tao_noi_dung_san_pham
from he_thong_dinh_luong.mo_phong.engine import chay_mo_phong
from ho_tro_mo_phong import D1,D2,bar,cfg,tg

class KiemTraDonVi(unittest.TestCase):
    def test_dong_dong_hop_le(self):
        self.assertEqual(cfg(don_vi_gia="dong",don_vi_tien="dong").don_vi_tien,"dong")
    def test_nghin_dong_nghin_dong_hop_le(self):
        self.assertEqual(cfg().don_vi_gia,"nghin_dong")
    def test_khong_duoc_tron_nghin_dong_voi_dong(self):
        with self.assertRaisesRegex(ValueError,"khong duoc tron don vi"): cfg(don_vi_gia="nghin_dong",don_vi_tien="dong")
    def test_don_vi_xuat_hien_trong_ba_san_pham_json(self):
        k=chay_mo_phong([bar("A",D1),bar("A",D2)],[tg(D1,"A",".1")],cfg(kich_thuoc_lo=1))
        n=tao_noi_dung_san_pham(k,ma_lan_chay="x",thoi_diem_chay_utc="x",git_commit="abc",python_version="3.12",uv_version="uv",nguon_du_lieu={},sha256_dau_vao={},gioi_han=[])
        cau_hinh=json.loads(n["cau_hinh.json"]);bao_cao=json.loads(n["bao_cao.json"]);manifest=json.loads(n["manifest.json"])
        self.assertEqual(cau_hinh["don_vi_gia"],"nghin_dong")
        self.assertEqual(bao_cao["don_vi"]["don_vi_tien"],"nghin_dong")
        self.assertEqual(manifest["don_vi"]["don_vi_gia"],"nghin_dong")
