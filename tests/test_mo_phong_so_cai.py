import unittest
from decimal import Decimal
from he_thong_dinh_luong.mo_phong.engine import _thuc_thi_lenh, chay_mo_phong
from he_thong_dinh_luong.mo_phong.mo_hinh import lenh, vi_the
from ho_tro_mo_phong import D1,D2,D3,D4,D5,bar,cfg,tg,co_tuc

class KiemTraSoCai(unittest.TestCase):
    def test_gia_von_gom_gia_khop_khong_gom_phi_mua(self):
        k=chay_mo_phong([bar("A",D1),bar("A",D2)],[tg(D1,"A",".1")],cfg(kich_thuoc_lo=1,phi_mua_bps=100,truot_gia_bps=100))
        self.assertEqual(k.vi_the_hang_ngay[-1].gia_von,Decimal("10.1"))
        self.assertGreater(k.so_cai[-1].phi_mua,0)
    def test_realized_pnl_ban_mot_phan(self):
        order=lenh("L1",D1,D2,"A","BAN",Decimal("400"))
        v={"A":vi_the("A",Decimal("1000"),Decimal("10"))}
        result=_thuc_thi_lenh(D2,[order],tien_mat=Decimal(0),cac_vi_the=v,bang_gia={(D2,"A"):bar("A",D2,"12","12")},cau_hinh=cfg(phi_ban_bps=0,thue_ban_bps=0,truot_gia_bps=0,kich_thuoc_lo=1))
        self.assertEqual(result[-1],Decimal("800"))
        self.assertEqual(v["A"].so_luong,Decimal("600"))
        self.assertEqual(v["A"].gia_von,Decimal("10"))
    def test_realized_pnl_dong_toan_bo_vi_the(self):
        order=lenh("L1",D1,D2,"A","BAN",Decimal("1000"))
        v={"A":vi_the("A",Decimal("1000"),Decimal("10"))}
        result=_thuc_thi_lenh(D2,[order],tien_mat=Decimal(0),cac_vi_the=v,bang_gia={(D2,"A"):bar("A",D2,"12","12")},cau_hinh=cfg(phi_ban_bps=0,thue_ban_bps=0,truot_gia_bps=0,kich_thuoc_lo=1))
        self.assertEqual(result[-1],Decimal("2000"))
        self.assertEqual(v["A"].so_luong,0)
        self.assertEqual(v["A"].gia_von,0)
    def test_phuong_trinh_doi_soat_nav(self):
        k=chay_mo_phong([bar("A",d,"12" if d>=D3 else "10","12" if d>=D3 else "10") for d in (D1,D2,D3,D4,D5)],[tg(D1,"A",".5"),tg(D3,"A",".2")],cfg(kich_thuoc_lo=1),[co_tuc(hieu_luc=D3,thanh_toan=D5,gia_tri="1")])
        cuoi=k.so_cai[-1]
        rhs=(k.cau_hinh.von_ban_dau+cuoi.lai_lo_da_thuc_hien_luy_ke+cuoi.lai_lo_chua_thuc_hien+cuoi.co_tuc_tien_mat_luy_ke-cuoi.phi_mua_luy_ke-cuoi.phi_ban_luy_ke-cuoi.thue_ban_luy_ke)
        self.assertEqual(cuoi.nav,rhs)
        self.assertEqual(cuoi.chenh_lech_doi_soat,0)
    def test_so_cai_tach_phi_thue_va_truot_gia(self):
        k=chay_mo_phong([bar("A",D1),bar("A",D2),bar("A",D3,"12","12")],[tg(D1,"A",".1"),tg(D2,"A","0")],cfg(kich_thuoc_lo=1))
        self.assertGreater(k.so_cai[1].phi_mua,0)
        self.assertGreater(k.so_cai[1].chi_phi_truot_gia,0)
        self.assertGreater(k.so_cai[2].phi_ban,0)
        self.assertGreater(k.so_cai[2].thue_ban,0)
