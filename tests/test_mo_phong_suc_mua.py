import unittest
from decimal import Decimal, ROUND_FLOOR
from he_thong_dinh_luong.mo_phong.engine import chay_mo_phong
from ho_tro_mo_phong import D1,D2,bar,cfg,tg

class KiemTraSucMua(unittest.TestCase):
    def test_buy_and_hold_ty_trong_mot_van_mua_toi_da(self):
        k=chay_mo_phong([bar("A",D1),bar("A",D2)],[tg(D1,"A","1")],cfg(kich_thuoc_lo=1))
        toi_da=(Decimal("100000")/(Decimal("10.1")*Decimal("1.001"))).to_integral_value(rounding=ROUND_FLOOR)
        self.assertEqual(k.khop_lenh[0].so_luong,toi_da)
        self.assertGreater(k.khop_lenh[0].so_luong_bi_giam,0)
    def test_equal_weight_tong_ty_trong_mot(self):
        gia=[bar(ma,d) for d in (D1,D2) for ma in ("A","B")]
        k=chay_mo_phong(gia,[tg(D1,"A",".5"),tg(D1,"B",".5")],cfg(kich_thuoc_lo=1))
        self.assertEqual(len(k.khop_lenh),2)
        self.assertTrue(all(x.trang_thai=="da_khop" for x in k.lenh))
    def test_gap_up_giam_khoi_luong_thay_vi_tu_choi_toan_bo(self):
        k=chay_mo_phong([bar("A",D1),bar("A",D2,"25","25")],[tg(D1,"A","1")],cfg(kich_thuoc_lo=1))
        self.assertEqual(k.lenh[0].trang_thai,"da_khop")
        self.assertGreater(k.lenh[0].so_luong_bi_giam,0)
        self.assertEqual(k.lenh[0].ly_do_giam,"gioi_han_suc_mua_sau_phi_va_truot_gia")
    def test_nhieu_lenh_canh_tranh_tien_mat_theo_ma_tang_dan(self):
        gia=[bar(ma,D1) for ma in ("C","B","A")]+[bar(ma,D2,"30","30") for ma in ("C","B","A")]
        k=chay_mo_phong(gia,[tg(D1,"C",".34"),tg(D1,"B",".33"),tg(D1,"A",".33")],cfg(kich_thuoc_lo=1))
        self.assertEqual([x.ma for x in k.lenh],["A","B","C"])
        self.assertGreaterEqual(k.lenh[-1].so_luong_bi_giam,0)
    def test_ket_qua_khong_phu_thuoc_thu_tu_dong_dau_vao(self):
        gia=[bar(ma,d,mo,dong) for d,mo,dong in ((D1,"10","10"),(D2,"20","20")) for ma in ("B","A")]
        ty=[tg(D1,"B",".5"),tg(D1,"A",".5")]
        k1=chay_mo_phong(gia,ty,cfg(kich_thuoc_lo=1))
        k2=chay_mo_phong(list(reversed(gia)),list(reversed(ty)),cfg(kich_thuoc_lo=1))
        self.assertEqual(k1.lenh,k2.lenh)
        self.assertEqual(k1.khop_lenh,k2.khop_lenh)
        self.assertEqual(k1.so_cai,k2.so_cai)
    def test_tien_mat_khong_am_sau_moi_giao_dich(self):
        gia=[bar(ma,d,mo,dong) for d,mo,dong in ((D1,"10","10"),(D2,"100","100")) for ma in ("A","B","C")]
        k=chay_mo_phong(gia,[tg(D1,"A",".34"),tg(D1,"B",".33"),tg(D1,"C",".33")],cfg(kich_thuoc_lo=1))
        self.assertTrue(all(x.tien_mat_cuoi_ngay>=0 for x in k.so_cai))
