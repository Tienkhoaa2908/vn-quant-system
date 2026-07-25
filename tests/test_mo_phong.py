from __future__ import annotations
import json, tempfile, unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from he_thong_dinh_luong.mo_phong.bao_cao import TEN_TEP_THANH_CONG, cong_bo_bao_cao_loi, cong_bo_san_pham, tao_noi_dung_san_pham
from he_thong_dinh_luong.mo_phong.baseline import baseline_can_bang_deu, baseline_ma250_dong_luong, baseline_mua_va_giu
from he_thong_dinh_luong.mo_phong.chi_so import tinh_chi_so
from he_thong_dinh_luong.mo_phong.dong_lenh import main
from he_thong_dinh_luong.mo_phong.engine import _thuc_thi_lenh, chay_mo_phong
from he_thong_dinh_luong.mo_phong.mo_hinh import cau_hinh_mo_phong, chuan_hoa_su_kien, chuan_hoa_ty_trong, dong_nav, ket_qua_mo_phong, lenh, su_kien_doanh_nghiep, thanh_gia, ty_trong_muc_tieu, vi_the
D1,D2,D3,D4=(date(2026,1,n) for n in (5,6,7,8))
def cfg(**kw):
    x={"von_ban_dau":"100000","phi_mua_bps":"10","phi_ban_bps":"20","thue_ban_bps":"10","truot_gia_bps":"100","kich_thuoc_lo":100,"so_phien_moi_nam":252,"lai_suat_phi_rui_ro":"0","che_do_ma_khong_xuat_hien":"muc_tieu_bang_0","cho_phep_ban_le_khi_dong_vi_the":False,"co_so_gia":"khong_dieu_chinh"};x.update(kw);return cau_hinh_mo_phong.tu_mapping(x)
def bar(ma,ngay,mo="10",dong="10",**kw):
    return thanh_gia(ma,ngay,Decimal(mo) if mo is not None else None,Decimal(dong),1000,kw.get("tv",True),kw.get("tk",True),kw.get("ma250",True),Decimal(kw.get("dl","0.1")) if kw.get("dl","0.1") is not None else None)
def tg(ngay,ma,ty): return ty_trong_muc_tieu(ngay,ma,Decimal(ty),"kiem_thu")
class KiemTraMoPhong(unittest.TestCase):
    def test_01_xac_thuc_cau_hinh_va_ty_trong(self):
        with self.assertRaises(ValueError): cau_hinh_mo_phong.tu_mapping({})
        with self.assertRaises(ValueError): chuan_hoa_ty_trong([{"ngay_tin_hieu":D1,"ma":"A","ty_trong_muc_tieu":-1,"ten_chien_luoc":"x"}])
        with self.assertRaises(ValueError): chuan_hoa_ty_trong([{"ngay_tin_hieu":D1,"ma":"A","ty_trong_muc_tieu":.6,"ten_chien_luoc":"x"},{"ngay_tin_hieu":D1,"ma":"B","ty_trong_muc_tieu":.5,"ten_chien_luoc":"x"}])
    def test_02_tin_hieu_T_khop_mo_cua_T1_va_truot_gia_mua(self):
        k=chay_mo_phong([bar("A",D1),bar("A",D2,"20","20")],[tg(D1,"A","0.1")],cfg(kich_thuoc_lo=1));self.assertEqual((k.lenh[0].ngay_thuc_thi,k.khop_lenh[0].ngay_khop),(D2,D2));self.assertEqual(k.khop_lenh[0].gia_khop,Decimal("20.2"))
    def test_03_phi_thue_truot_gia_ban(self):
        k=chay_mo_phong([bar("A",D1),bar("A",D2),bar("A",D3,"12","12")],[tg(D1,"A","0.1"),tg(D2,"A","0")],cfg(kich_thuoc_lo=1));mua,ban=k.khop_lenh;self.assertEqual(mua.thue,0);self.assertEqual(ban.gia_khop,Decimal("11.88"));self.assertEqual(ban.phi,ban.gia_tri_giao_dich*Decimal(20)/10000);self.assertEqual(ban.thue,ban.gia_tri_giao_dich*Decimal(10)/10000)
    def test_04_day_thieu_bar_khong_tim_xa_hon(self):
        k=chay_mo_phong([bar("A",D1),bar("B",D2),bar("A",D3)],[tg(D1,"A","0.1")],cfg(kich_thuoc_lo=1));self.assertEqual(k.lenh[0].trang_thai,"het_han");self.assertFalse(k.khop_lenh)
    def test_05_thieu_open_khong_thay_close(self):
        k=chay_mo_phong([bar("A",D1),bar("A",D2,None,"11")],[tg(D1,"A","0.1")],cfg(kich_thuoc_lo=1));self.assertEqual(k.lenh[0].trang_thai,"het_han")
    def test_06_lam_tron_lo_va_khong_tien_am(self):
        k=chay_mo_phong([bar("A",D1,dong="11"),bar("A",D2)],[tg(D1,"A","0.015")],cfg());self.assertEqual(k.lenh[0].so_luong,100)
        k=chay_mo_phong([bar("A",D1),bar("A",D2,"20","20")],[tg(D1,"A","1")],cfg(kich_thuoc_lo=1));self.assertEqual(k.lenh[0].trang_thai,"tu_choi");self.assertGreaterEqual(k.so_cai[-1].tien_mat_cuoi_ngay,0)
    def test_07_ban_vuot_vi_the_bi_tu_choi(self):
        l=lenh("L1",D1,D2,"A","BAN",Decimal(200));v={"A":vi_the("A",Decimal(100),Decimal(10))};_,khop,*_=_thuc_thi_lenh(D2,[l],tien_mat=Decimal(0),cac_vi_the=v,bang_gia={(D2,"A"):bar("A",D2)},cau_hinh=cfg());self.assertEqual(l.trang_thai,"tu_choi");self.assertFalse(khop);self.assertEqual(v["A"].so_luong,100)
    def test_08_thu_tu_mua_canh_tranh_tien_mat(self):
        g=[bar(m,d,mo,dong) for d,mo,dong in ((D1,"10","10"),(D2,"20","20")) for m in ("B","A")];k=chay_mo_phong(g,[tg(D1,"B","0.3"),tg(D1,"A","0.3")],cfg(kich_thuoc_lo=1));self.assertEqual([(x.ma,x.trang_thai) for x in k.lenh],[("A","da_khop"),("B","tu_choi")])
    def test_09_che_do_ma_khong_xuat_hien(self):
        g=[bar("A",d) for d in (D1,D2,D3)]+[bar("B",d) for d in (D2,D3)];k=chay_mo_phong(g,[tg(D1,"A","0.1"),tg(D2,"B","0")],cfg(kich_thuoc_lo=1));self.assertEqual(k.khop_lenh[-1].chieu,"BAN")
        k=chay_mo_phong(g,[tg(D1,"A","0.1"),tg(D2,"B","0")],cfg(kich_thuoc_lo=1,che_do_ma_khong_xuat_hien="giu_nguyen"));self.assertFalse(any(x.chieu=="BAN" for x in k.lenh))
    def test_10_chia_tach_thuong_va_lenh_cho(self):
        for loai,ty,gia,sl in (("chia_tach","2","5","2000"),("co_phieu_thuong","1.25","8","1250")):
            k=chay_mo_phong([bar("A",D1),bar("A",D2),bar("A",D3,gia,gia)],[tg(D1,"A","0.1")],cfg(kich_thuoc_lo=1,truot_gia_bps=0,phi_mua_bps=0),[su_kien_doanh_nghiep("A",loai,D3,None,Decimal(ty),None,"x")]);self.assertEqual(k.vi_the_hang_ngay[-1].so_luong,Decimal(sl));self.assertEqual(k.vi_the_hang_ngay[-1].lai_lo_chua_thuc_hien,0)
        k=chay_mo_phong([bar("A",D1),bar("A",D2,"5","5")],[tg(D1,"A","0.1")],cfg(kich_thuoc_lo=1,truot_gia_bps=0,phi_mua_bps=0),[su_kien_doanh_nghiep("A","chia_tach",D2,None,Decimal(2),None,"x")]);self.assertEqual(k.lenh[0].so_luong,2000)
    def test_11_co_tuc_tien_mat_ngay_thanh_toan(self):
        k=chay_mo_phong([bar("A",d) for d in (D1,D2,D3)],[tg(D1,"A","0.1")],cfg(kich_thuoc_lo=1,truot_gia_bps=0,phi_mua_bps=0),[su_kien_doanh_nghiep("A","co_tuc_tien_mat",D1,D3,None,Decimal(1),"x")]);self.assertEqual([x.dong_tien_su_kien for x in k.so_cai],[0,0,Decimal(1000)])
    def test_12_chong_tinh_su_kien_hai_lan(self):
        with self.assertRaises(ValueError): chuan_hoa_su_kien([{"ma":"A","loai_su_kien":"co_tuc_tien_mat","ngay_thanh_toan":D2,"gia_tri_tien_mat":1,"nguon":"x"}],co_so_gia="dieu_chinh")
    def test_13_nav_drawdown_sharpe_turnover(self):
        k=chay_mo_phong([bar("A",d) for d in (D1,D2,D3)],[tg(D1,"A","0.1"),tg(D2,"A","0")],cfg(kich_thuoc_lo=1,phi_mua_bps=0,phi_ban_bps=0,thue_ban_bps=0,truot_gia_bps=0));self.assertEqual(k.so_cai[-1].nav,k.so_cai[-1].tien_mat_cuoi_ngay+k.so_cai[-1].gia_tri_vi_the);self.assertEqual(tinh_chi_so(k)["turnover"],Decimal("0.1"))
        q=ket_qua_mo_phong(cfg(von_ban_dau=100));q.nav=[dong_nav(D1,Decimal(100),Decimal(0),Decimal(100),Decimal(1)),dong_nav(D2,Decimal(120),Decimal('.2'),Decimal(120),Decimal(1)),dong_nav(D3,Decimal(90),Decimal('-.25'),Decimal(90),Decimal(1))];self.assertEqual(tinh_chi_so(q)["maximum_drawdown"],Decimal('-.25'))
        q.nav=[dong_nav(D1,Decimal(100),Decimal(0),Decimal(100),Decimal(1)),dong_nav(D2,Decimal(100),Decimal(0),Decimal(100),Decimal(1))];self.assertIsNone(tinh_chi_so(q)["sharpe"])
        q.nav=[dong_nav(D1,Decimal(101),Decimal('.01'),Decimal(101),Decimal(1)),dong_nav(D2,Decimal('103.02'),Decimal('.02'),Decimal('103.02'),Decimal(1))];self.assertIsNotNone(tinh_chi_so(q)["sharpe"])
    def test_14_kich_ban_vang(self):
        k=chay_mo_phong([bar("A",D1),bar("A",D2,"10","11"),bar("A",D3,"12","12")],[tg(D1,"A",".5"),tg(D2,"A","0")],cfg(von_ban_dau=10000,kich_thuoc_lo=1,phi_mua_bps=10,phi_ban_bps=10,thue_ban_bps=10,truot_gia_bps=100));self.assertEqual(k.khop_lenh[0].gia_khop,Decimal('10.10'));self.assertEqual(k.so_cai[-1].nav,Decimal('10873.07000'))
    def test_15_baseline(self):
        g=[bar("B",D1,dl=".2"),bar("A",D1,dl=".2"),bar("C",D1,dl=".1",tk=False)];self.assertEqual([x.ma for x in baseline_mua_va_giu(g)],["A","B"]);self.assertEqual([x.ma for x in baseline_can_bang_deu(g,cac_ngay_tai_can_bang=[D1])],["A","B"]);self.assertEqual([x.ma for x in baseline_ma250_dong_luong(g,cac_ngay_tai_can_bang=[D1],top_k=1)],["A"])
    def test_16_cong_bo_bat_bien_rollback_tai_lap(self):
        k=chay_mo_phong([bar("A",D1),bar("A",D2)],[tg(D1,"A",".1")],cfg(kich_thuoc_lo=1));n=tao_noi_dung_san_pham(k,ma_lan_chay="x",thoi_diem_chay_utc="x",git_commit="abc",python_version="3.12",uv_version="uv",nguon_du_lieu={},sha256_dau_vao={},gioi_han=[]);self.assertEqual(set(n),set(TEN_TEP_THANH_CONG))
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/"x";cong_bo_san_pham(out,n);cu={p.name:p.read_bytes() for p in out.iterdir()}
            with self.assertRaises(FileExistsError): cong_bo_san_pham(out,n)
            self.assertEqual(cu,{p.name:p.read_bytes() for p in out.iterdir()});out2=Path(td)/"y"
            with patch("he_thong_dinh_luong.mo_phong.bao_cao.os.rename",side_effect=OSError("loi")):
                with self.assertRaises(OSError): cong_bo_san_pham(out2,n)
            self.assertFalse(out2.exists());loi=Path(td)/"loi";cong_bo_bao_cao_loi(loi,ValueError("token=BI_MAT"));self.assertEqual([p.name for p in loi.iterdir()],["bao_cao_loi.json"]);self.assertNotIn("BI_MAT",(loi/"bao_cao_loi.json").read_text())
        k2=chay_mo_phong([bar("A",D1),bar("A",D2)],[tg(D1,"A",".1")],cfg(kich_thuoc_lo=1));self.assertEqual((k.lenh,k.khop_lenh,k.so_cai,k.nav),(k2.lenh,k2.khop_lenh,k2.so_cai,k2.nav))
    def test_17_cli_chin_san_pham(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/"g.csv").write_text("ma,ngay,gia_mo_cua,gia_dong_cua\nA,2026-01-05,10,10\nA,2026-01-06,10,10\n");(p/"t.csv").write_text("ngay_tin_hieu,ma,ty_trong_muc_tieu,ten_chien_luoc\n2026-01-05,A,.1,x\n");(p/"c.json").write_text(json.dumps(cfg(kich_thuoc_lo=1).thanh_tu_dien()));out=p/"out";self.assertEqual(main(["--duong_co_so",str(p/"g.csv"),"--ty_trong_muc_tieu",str(p/"t.csv"),"--cau_hinh",str(p/"c.json"),"--thu_muc_dau_ra",str(out),"--git_commit","abc"]),0);self.assertEqual({x.name for x in out.iterdir()},set(TEN_TEP_THANH_CONG))
if __name__=="__main__": unittest.main()
