import unittest
from decimal import Decimal
from he_thong_dinh_luong.mo_phong.engine import chay_mo_phong
from ho_tro_mo_phong import D1,D2,D3,D4,D5,bar,cfg,tg,co_tuc

class KiemTraQuyenCoTuc(unittest.TestCase):
    def test_mua_sau_ngay_hieu_luc_khong_nhan_co_tuc(self):
        k=chay_mo_phong([bar("A",d) for d in (D1,D2,D3,D4)],[tg(D2,"A",".1")],cfg(kich_thuoc_lo=1,phi_mua_bps=0,truot_gia_bps=0),[co_tuc(hieu_luc=D1,thanh_toan=D4)])
        self.assertEqual(k.so_cai[-1].co_tuc_tien_mat_luy_ke,0)
    def test_giu_tai_ngay_hieu_luc_ban_truoc_thanh_toan_van_nhan(self):
        k=chay_mo_phong([bar("A",d) for d in (D1,D2,D3,D4,D5)],[tg(D1,"A",".1"),tg(D3,"A","0")],cfg(kich_thuoc_lo=1,phi_mua_bps=0,phi_ban_bps=0,thue_ban_bps=0,truot_gia_bps=0),[co_tuc(hieu_luc=D3,thanh_toan=D5)])
        self.assertEqual(k.khop_lenh[-1].chieu,"BAN")
        self.assertFalse(any(x.ngay==D5 for x in k.vi_the_hang_ngay))
        self.assertEqual(k.so_cai[-1].co_tuc_tien_mat_luy_ke,Decimal("1000"))
    def test_mua_them_sau_ngay_hieu_luc_khong_tang_quyen(self):
        k=chay_mo_phong([bar("A",d) for d in (D1,D2,D3,D4,D5)],[tg(D1,"A",".1"),tg(D3,"A",".2")],cfg(kich_thuoc_lo=1,phi_mua_bps=0,truot_gia_bps=0),[co_tuc(hieu_luc=D3,thanh_toan=D5)])
        self.assertGreater(k.vi_the_hang_ngay[-1].so_luong,Decimal("1000"))
        self.assertEqual(k.so_cai[-1].co_tuc_tien_mat_luy_ke,Decimal("1000"))
    def test_ban_bot_sau_ngay_hieu_luc_khong_giam_quyen(self):
        k=chay_mo_phong([bar("A",d) for d in (D1,D2,D3,D4,D5)],[tg(D1,"A",".1"),tg(D3,"A",".05")],cfg(kich_thuoc_lo=1,phi_mua_bps=0,phi_ban_bps=0,thue_ban_bps=0,truot_gia_bps=0),[co_tuc(hieu_luc=D3,thanh_toan=D5)])
        self.assertLess(k.vi_the_hang_ngay[-1].so_luong,Decimal("1000"))
        self.assertEqual(k.so_cai[-1].co_tuc_tien_mat_luy_ke,Decimal("1000"))
    def test_chi_cong_tien_dung_ngay_thanh_toan(self):
        k=chay_mo_phong([bar("A",d) for d in (D1,D2,D3,D4,D5)],[tg(D1,"A",".1")],cfg(kich_thuoc_lo=1,phi_mua_bps=0,truot_gia_bps=0),[co_tuc(hieu_luc=D3,thanh_toan=D5)])
        self.assertEqual([x.co_tuc_tien_mat for x in k.so_cai],[0,0,0,0,Decimal("1000")])
    def test_cung_su_kien_khong_ap_dung_hai_lan(self):
        su_kien=co_tuc(hieu_luc=D3,thanh_toan=D5)
        with self.assertRaisesRegex(ValueError,"Trung su kien"):
            chay_mo_phong([bar("A",d) for d in (D1,D2,D3,D4,D5)],[tg(D1,"A",".1")],cfg(),[su_kien,su_kien])
