from __future__ import annotations
import unittest
from datetime import datetime

from he_thong_dinh_luong.nghien_cuu_moc_4.mo_hinh import CauHinhMoc4, xac_thuc_timestamp
from ho_tro_m4 import cau_hinh, cau_hinh_mapping


class TestCauHinhM4(unittest.TestCase):
    def test_cau_hinh_hop_le(self):
        config = cau_hinh()
        self.assertEqual(config.label_horizon, 20)
        self.assertEqual(config.C_grid, (0.1, 1.0, 10.0))

    def test_thieu_khoa_bi_tu_choi(self):
        data = cau_hinh_mapping(); del data["top_k"]
        with self.assertRaisesRegex(ValueError, "Thieu cau hinh"):
            CauHinhMoc4.tu_mapping(data)

    def test_khoa_thua_bi_tu_choi(self):
        data = cau_hinh_mapping(); data["ngoai_hop_dong"] = 1
        with self.assertRaisesRegex(ValueError, "ngoai hop dong"):
            CauHinhMoc4.tu_mapping(data)

    def test_khong_ep_chuoi_thanh_so(self):
        with self.assertRaises(TypeError):
            CauHinhMoc4.tu_mapping(cau_hinh_mapping(top_k="3"))

    def test_khong_ep_int_thanh_bool(self):
        with self.assertRaises(TypeError):
            CauHinhMoc4.tu_mapping(cau_hinh_mapping(co_so_gia_da_xac_nhan=1))

    def test_monthly_sample_bat_buoc(self):
        with self.assertRaisesRegex(ValueError, "cuoi_thang"):
            CauHinhMoc4.tu_mapping(cau_hinh_mapping(tan_suat_mau_mo_hinh="hang_ngay"))

    def test_test_fold_mot_thang_bat_buoc(self):
        with self.assertRaisesRegex(ValueError, "so_thang_test=1"):
            CauHinhMoc4.tu_mapping(cau_hinh_mapping(so_thang_test=2))

    def test_purge_nho_hon_horizon_bi_tu_choi(self):
        with self.assertRaisesRegex(ValueError, "purge_phien"):
            CauHinhMoc4.tu_mapping(cau_hinh_mapping(purge_phien=19))

    def test_c_grid_chinh_xac(self):
        with self.assertRaisesRegex(ValueError, "C_grid"):
            CauHinhMoc4.tu_mapping(cau_hinh_mapping(C_grid=[1.0]))

    def test_logistic_contract_chinh_xac(self):
        with self.assertRaises(ValueError):
            CauHinhMoc4.tu_mapping(cau_hinh_mapping(solver="liblinear"))
        with self.assertRaises(ValueError):
            CauHinhMoc4.tu_mapping(cau_hinh_mapping(max_iter=500))
        with self.assertRaises(ValueError):
            CauHinhMoc4.tu_mapping(cau_hinh_mapping(seed=1))

    def test_class_weight_phai_null(self):
        with self.assertRaisesRegex(ValueError, "class_weight"):
            CauHinhMoc4.tu_mapping(cau_hinh_mapping(class_weight="balanced"))

    def test_nghien_cuu_fail_neu_gia_chua_xac_nhan(self):
        with self.assertRaisesRegex(ValueError, "chua xac nhan"):
            CauHinhMoc4.tu_mapping(cau_hinh_mapping(muc_dich_lan_chay="nghien_cuu"))

    def test_nghien_cuu_gia_khong_dieu_chinh_can_ca(self):
        with self.assertRaisesRegex(ValueError, "corporate actions"):
            CauHinhMoc4.tu_mapping(cau_hinh_mapping(
                muc_dich_lan_chay="nghien_cuu", co_so_gia="gia_khong_dieu_chinh",
                co_so_gia_da_xac_nhan=True, corporate_actions_day_du=False,
            ))

    def test_kiem_tra_ky_thuat_co_canh_bao(self):
        warnings = cau_hinh().canh_bao_muc_dich()
        self.assertIn("CHI_KIEM_TRA_KY_THUAT_KHONG_KET_LUAN_HIEU_QUA", warnings)

    def test_timestamp_thieu_mui_gio_bi_tu_choi(self):
        with self.assertRaisesRegex(ValueError, "mui gio"):
            xac_thuc_timestamp(datetime(2026, 1, 1), "x")
