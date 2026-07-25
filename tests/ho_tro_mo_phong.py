from datetime import date
from decimal import Decimal
from he_thong_dinh_luong.mo_phong.mo_hinh import cau_hinh_mo_phong, thanh_gia, ty_trong_muc_tieu, su_kien_doanh_nghiep

D1, D2, D3, D4, D5 = (date(2026, 1, n) for n in (5, 6, 7, 8, 9))

def cfg(**kw):
    x = {
        "von_ban_dau": "100000",
        "phi_mua_bps": "10",
        "phi_ban_bps": "20",
        "thue_ban_bps": "10",
        "truot_gia_bps": "100",
        "kich_thuoc_lo": 100,
        "so_phien_moi_nam": 252,
        "lai_suat_phi_rui_ro": "0",
        "che_do_ma_khong_xuat_hien": "muc_tieu_bang_0",
        "cho_phep_ban_le_khi_dong_vi_the": False,
        "co_so_gia": "khong_dieu_chinh",
        "don_vi_gia": "nghin_dong",
        "don_vi_tien": "nghin_dong",
    }
    x.update(kw)
    return cau_hinh_mo_phong.tu_mapping(x)

def bar(ma, ngay, mo="10", dong="10", *, tv=True, tk=True, ma250=True, dl="0.1"):
    return thanh_gia(
        ma,
        ngay,
        Decimal(mo) if mo is not None else None,
        Decimal(dong),
        1000,
        tv,
        tk,
        ma250,
        Decimal(dl) if dl is not None else None,
    )

def tg(ngay, ma, ty, ten="kiem_thu"):
    return ty_trong_muc_tieu(ngay, ma, Decimal(ty), ten)

def co_tuc(ma="A", hieu_luc=D3, thanh_toan=D5, gia_tri="1"):
    return su_kien_doanh_nghiep(ma, "co_tuc_tien_mat", hieu_luc, thanh_toan, None, Decimal(gia_tri), "gia_lap")
