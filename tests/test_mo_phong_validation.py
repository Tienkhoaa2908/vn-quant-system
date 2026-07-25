import unittest
from decimal import Decimal
from he_thong_dinh_luong.mo_phong.engine import chay_mo_phong
from ho_tro_mo_phong import D1,D2,bar,cfg,tg

class KiemTraBienChiPhi(unittest.TestCase):
    def test_truot_gia_bang_0_hop_le(self):
        self.assertEqual(cfg(truot_gia_bps=0).truot_gia_bps,0)
    def test_truot_gia_9999_hop_le_va_gia_ban_duong(self):
        k=chay_mo_phong([bar("A",D1),bar("A",D2)],[tg(D1,"A",".1")],cfg(truot_gia_bps=9999,kich_thuoc_lo=1))
        self.assertGreater(k.khop_lenh[0].gia_khop,0)
    def test_truot_gia_10000_bi_tu_choi(self):
        with self.assertRaisesRegex(ValueError,"nho hon 10000"): cfg(truot_gia_bps=10000)
    def test_truot_gia_am_bi_tu_choi(self):
        with self.assertRaises(ValueError): cfg(truot_gia_bps=-1)
    def test_phi_va_thue_ban_bang_10000_khong_am(self):
        self.assertEqual(cfg(phi_ban_bps=6000,thue_ban_bps=4000).phi_ban_bps,Decimal("6000"))
    def test_phi_va_thue_ban_vuot_10000_bi_tu_choi(self):
        with self.assertRaisesRegex(ValueError,"tien ban rong am"): cfg(phi_ban_bps=6001,thue_ban_bps=4000)
    def test_kich_thuoc_lo_float_khong_duoc_ep_int(self):
        with self.assertRaisesRegex(ValueError,"so nguyen thuc su"): cfg(kich_thuoc_lo=100.0)
    def test_so_phien_moi_nam_float_khong_duoc_ep_int(self):
        with self.assertRaisesRegex(ValueError,"so nguyen thuc su"): cfg(so_phien_moi_nam=252.0)
    def test_kich_thuoc_lo_bool_bi_tu_choi(self):
        with self.assertRaises(ValueError): cfg(kich_thuoc_lo=True)
    def test_so_phien_moi_nam_0_bi_tu_choi(self):
        with self.assertRaises(ValueError): cfg(so_phien_moi_nam=0)
