import unittest
from he_thong_dinh_luong.mo_phong.engine import chay_mo_phong
from ho_tro_mo_phong import D1,D2,D3,bar,cfg,tg

class KiemTraEligibility(unittest.TestCase):
    def _mo_moi(self,tv,tk):
        return chay_mo_phong([bar("A",D1,tv=tv,tk=tk),bar("A",D2,tv=tv,tk=tk)],[tg(D1,"A",".1")],cfg(kich_thuoc_lo=1))
    def test_mo_moi_chi_khi_membership_true_liquidity_true(self):
        self.assertEqual(self._mo_moi(True,True).lenh[0].trang_thai,"da_khop")
    def test_mo_moi_tu_choi_membership_false(self):
        self.assertEqual(self._mo_moi(False,True).lenh[0].ly_do_tu_choi_hoac_het_han,"eligibility_khong_dat_fail_closed")
    def test_mo_moi_tu_choi_membership_none(self):
        self.assertEqual(self._mo_moi(None,True).lenh[0].ly_do_tu_choi_hoac_het_han,"eligibility_khong_dat_fail_closed")
    def test_mo_moi_tu_choi_liquidity_false(self):
        self.assertEqual(self._mo_moi(True,False).lenh[0].ly_do_tu_choi_hoac_het_han,"eligibility_khong_dat_fail_closed")
    def test_mo_moi_tu_choi_liquidity_none(self):
        self.assertEqual(self._mo_moi(True,None).lenh[0].ly_do_tu_choi_hoac_het_han,"eligibility_khong_dat_fail_closed")
    def test_tang_vi_the_fail_closed_khi_du_lieu_thieu(self):
        g=[bar("A",D1),bar("A",D2,tv=None,tk=True),bar("A",D3)]
        k=chay_mo_phong(g,[tg(D1,"A",".1"),tg(D2,"A",".2")],cfg(kich_thuoc_lo=1))
        self.assertEqual(k.lenh[-1].trang_thai,"tu_choi")
        self.assertEqual(k.lenh[-1].ly_do_tu_choi_hoac_het_han,"eligibility_khong_dat_fail_closed")
    def test_giam_vi_the_duoc_phep_va_co_canh_bao(self):
        g=[bar("A",D1),bar("A",D2,tv=False,tk=None),bar("A",D3)]
        k=chay_mo_phong(g,[tg(D1,"A",".1"),tg(D2,"A",".05")],cfg(kich_thuoc_lo=1))
        self.assertEqual(k.lenh[-1].chieu,"BAN")
        self.assertEqual(k.lenh[-1].trang_thai,"da_khop")
        self.assertTrue(any("eligibility khong dat" in x for x in k.canh_bao))
    def test_dong_vi_the_duoc_phep_va_co_canh_bao(self):
        g=[bar("A",D1),bar("A",D2,tv=None,tk=False),bar("A",D3)]
        k=chay_mo_phong(g,[tg(D1,"A",".1"),tg(D2,"A","0")],cfg(kich_thuoc_lo=1))
        self.assertEqual(k.lenh[-1].chieu,"BAN")
        self.assertEqual(k.lenh[-1].trang_thai,"da_khop")
        self.assertTrue(k.canh_bao)
