from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(sys.argv[1]).resolve()


def replace_exact(path_text: str, old: str, new: str, *, expected: int = 1) -> None:
    path = ROOT / path_text
    text = path.read_text(encoding="utf-8")
    actual = text.count(old)
    if actual != expected:
        raise RuntimeError(f"{path_text}: expected {expected} matches, found {actual}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def append_once(path_text: str, marker: str, addition: str) -> None:
    path = ROOT / path_text
    text = path.read_text(encoding="utf-8")
    if marker in text:
        raise RuntimeError(f"{path_text}: marker already exists: {marker}")
    path.write_text(text.rstrip() + "\n\n" + addition.strip() + "\n", encoding="utf-8")


runner = "src/he_thong_dinh_luong/nghien_cuu_moc_4/runner.py"
replace_exact(
    runner,
    '''    limitations = [
        "TIER_A_TIER_B_CHUA_CHAY",
        "NGUON_DU_LIEU_THAT_CHUA_DUOC_PHE_DUYET",
        "BENCHMARK_EXACT_OFFICIAL_OHLC_CHUA_CO",
        "BENCHMARK_RAW_SOURCE_GIU_BAT_BIEN",
        "KHONG_CORRECTION_OVERLAY",
        "KHONG_DUOC_TUYEN_BO_HIEU_QUA_CHIEN_LUOC",
        "KHONG_LIGHTGBM_KHONG_SSI_KHONG_MOC_5",
    ]
''',
    '''    is_technical = config.muc_dich_lan_chay == "kiem_tra_ky_thuat"
    limitations = [
        "BENCHMARK_EXACT_OFFICIAL_OHLC_CHUA_CO",
        "BENCHMARK_RAW_SOURCE_PHAI_GIU_BAT_BIEN",
        "KHONG_CORRECTION_OVERLAY",
        "KHONG_LIGHTGBM_KHONG_SSI_KHONG_MOC_5",
    ]
    if is_technical:
        limitations.append("KHONG_DUOC_TUYEN_BO_HIEU_QUA_CHIEN_LUOC")
''',
)
replace_exact(
    runner,
    '''        "benchmark_policy": {
            "features_va_labels_chi_dung_close": True,
            "open_high_low_volume_duoc_dung": False,
            "correction_overlay": False,
            "raw_source_giu_bat_bien": True,
            "exact_official_ohlc_da_co": False,
            "chi_kiem_tra_ky_thuat": True,
        },
''',
    '''        "benchmark_policy": {
            "features_va_labels_chi_dung_close": True,
            "open_high_low_volume_duoc_dung": False,
            "correction_overlay_duoc_phep": False,
            "raw_source_bat_buoc_giu_bat_bien": True,
            "exact_official_ohlc_hien_co": False,
            "chi_kiem_tra_ky_thuat": is_technical,
        },
''',
    expected=2,
)

test_path = "tests/test_m4_benchmark_close_only.py"
replace_exact(
    test_path,
    '''    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()
''',
    '''        research_fixture = cls.root / "fixture-research"
        research_fixture.mkdir()
        cls.research_paths = tao_fixture_runner(research_fixture)
        research_config = json.loads(cls.research_paths["cau_hinh"].read_text(encoding="utf-8"))
        research_config["moc_4"]["muc_dich_lan_chay"] = "nghien_cuu"
        research_config["moc_4"]["co_so_gia_da_xac_nhan"] = True
        cls.research_paths["cau_hinh"].write_text(
            json.dumps(research_config, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        cls.research_result = chay_nghien_cuu_moc_4(
            duong_dan_cau_hinh=cls.research_paths["cau_hinh"],
            duong_dan_ohlcv=cls.research_paths["ohlcv"],
            duong_dan_benchmark=cls.research_paths["benchmark"],
            duong_dan_lich_benchmark=cls.research_paths["lich_benchmark"],
            duong_dan_universe=cls.research_paths["universe"],
            duong_dan_corporate_actions=cls.research_paths["corporate_actions"],
            thu_muc_dau_ra=cls.root / "out-research",
            ma_lan_chay="close-only-research",
            git_commit=GIT_SHA,
            thoi_diem_utc=FIXED_TIME,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()
''',
)
replace_exact(
    test_path,
    '''    def test_manifest_report_co_contract_va_hai_warning(self):
        report = json.loads((self.result.thu_muc_san_pham / "bao_cao.json").read_text(encoding="utf-8"))
        manifest = json.loads((self.result.thu_muc_san_pham / "manifest.json").read_text(encoding="utf-8"))
        for payload in (report, manifest["metadata"]):
            self.assertEqual(payload["benchmark_contract"], BENCHMARK_CONTRACT)
            self.assertTrue(payload["benchmark_policy"]["features_va_labels_chi_dung_close"])
            self.assertFalse(payload["benchmark_policy"]["open_high_low_volume_duoc_dung"])
            self.assertFalse(payload["benchmark_policy"]["correction_overlay"])
            self.assertTrue(payload["benchmark_policy"]["raw_source_giu_bat_bien"])
            self.assertFalse(payload["benchmark_policy"]["exact_official_ohlc_da_co"])
            self.assertIn("BENCHMARK_CLOSE_ONLY", payload["canh_bao"])
            self.assertIn("BENCHMARK_OHLC_SEMANTICS_CHUA_XAC_NHAN", payload["canh_bao"])
''',
    '''    def test_manifest_report_technical_co_policy_dong_va_hai_warning(self):
        report = json.loads((self.result.thu_muc_san_pham / "bao_cao.json").read_text(encoding="utf-8"))
        manifest = json.loads((self.result.thu_muc_san_pham / "manifest.json").read_text(encoding="utf-8"))
        for payload in (report, manifest["metadata"]):
            self.assertEqual(payload["benchmark_contract"], BENCHMARK_CONTRACT)
            policy = payload["benchmark_policy"]
            self.assertTrue(policy["features_va_labels_chi_dung_close"])
            self.assertFalse(policy["open_high_low_volume_duoc_dung"])
            self.assertFalse(policy["correction_overlay_duoc_phep"])
            self.assertTrue(policy["raw_source_bat_buoc_giu_bat_bien"])
            self.assertFalse(policy["exact_official_ohlc_hien_co"])
            self.assertTrue(policy["chi_kiem_tra_ky_thuat"])
            self.assertIn("BENCHMARK_CLOSE_ONLY", payload["canh_bao"])
            self.assertIn("BENCHMARK_OHLC_SEMANTICS_CHUA_XAC_NHAN", payload["canh_bao"])
            self.assertIn("CHI_KIEM_TRA_KY_THUAT_KHONG_KET_LUAN_HIEU_QUA", payload["canh_bao"])
            self.assertIn("KHONG_DUOC_TUYEN_BO_HIEU_QUA_CHIEN_LUOC", payload["gioi_han"])
''',
)
replace_exact(
    test_path,
    '''    def test_runner_end_to_end_nhan_benchmark_close_only(self):
''',
    '''    def test_manifest_report_research_khong_mang_gioi_han_technical(self):
        report = json.loads((self.research_result.thu_muc_san_pham / "bao_cao.json").read_text(encoding="utf-8"))
        manifest = json.loads((self.research_result.thu_muc_san_pham / "manifest.json").read_text(encoding="utf-8"))
        for payload in (report, manifest["metadata"]):
            self.assertFalse(payload["benchmark_policy"]["chi_kiem_tra_ky_thuat"])
            self.assertNotIn("KHONG_DUOC_TUYEN_BO_HIEU_QUA_CHIEN_LUOC", payload["gioi_han"])
            self.assertNotIn("CHI_KIEM_TRA_KY_THUAT_KHONG_KET_LUAN_HIEU_QUA", payload["canh_bao"])
            self.assertIn("BENCHMARK_CLOSE_ONLY", payload["canh_bao"])
            self.assertIn("BENCHMARK_OHLC_SEMANTICS_CHUA_XAC_NHAN", payload["canh_bao"])

    def test_report_manifest_khong_chua_assertion_mo_ho_hoac_trang_thai_dieu_phoi(self):
        forbidden_limits = {
            "TIER_A_TIER_B_CHUA_CHAY",
            "NGUON_DU_LIEU_THAT_CHUA_DUOC_PHE_DUYET",
        }
        forbidden_policy_keys = {
            "correction_overlay",
            "raw_source_giu_bat_bien",
            "exact_official_ohlc_da_co",
        }
        for result in (self.result, self.research_result):
            report = json.loads((result.thu_muc_san_pham / "bao_cao.json").read_text(encoding="utf-8"))
            manifest = json.loads((result.thu_muc_san_pham / "manifest.json").read_text(encoding="utf-8"))
            for payload in (report, manifest["metadata"]):
                self.assertTrue(forbidden_limits.isdisjoint(payload["gioi_han"]))
                self.assertTrue(forbidden_policy_keys.isdisjoint(payload["benchmark_policy"]))
                self.assertFalse(payload["benchmark_policy"]["correction_overlay_duoc_phep"])
                self.assertTrue(payload["benchmark_policy"]["raw_source_bat_buoc_giu_bat_bien"])
                self.assertFalse(payload["benchmark_policy"]["exact_official_ohlc_hien_co"])

    def test_runner_end_to_end_nhan_benchmark_close_only(self):
''',
)

append_once(
    "DECISIONS.md",
    "## QD-0062: Tach reporting policy khoi execution provenance",
    '''## QD-0062: Tach reporting policy khoi execution provenance

Generic runner Moc 4 chi cong bo dieu no tu xac minh trong code hoac suy ra truc tiep tu cau hinh. Trang thai dieu phoi Tier A/Tier B va phe duyet nguon du lieu khong duoc hard-code trong san pham bat bien. `chi_kiem_tra_ky_thuat` duoc suy ra tu `muc_dich_lan_chay`; gioi han `KHONG_DUOC_TUYEN_BO_HIEU_QUA_CHIEN_LUOC` chi xuat hien cho technical run.

`benchmark_policy` mo ta yeu cau contract: correction overlay khong duoc phep, raw acquisition source bat buoc giu bat bien va exact official OHLC hien chua co. Generic runner khong tu nhan da chung minh raw bat bien hay absence of overlay. Hai actual run facts nay phai duoc khoa bang external execution provenance manifest cua Tier A. San pham runner khong duoc chua trang thai dieu phoi co the sai sau khi pipeline thuc su chay.

Trang thai ap dung: PR canonical #16, head truoc correction `2efa627c65cb5387bcc4aa77f4063070812d6aa6`; close-only contract QD-0061 va CI #351 da dat. Vong QD-0062 chi sua reporting/provenance, khong chay Tier A pipeline, Tier B, normalization, calendar, corporate actions hoac Moc 5. Giai doan 2B chua mo.''',
)
append_once(
    "README.md",
    "## Cap nhat QD-0062: reporting va provenance",
    '''## Cap nhat QD-0062: reporting va provenance

Runner Moc 4 phan biet policy voi runtime fact. `chi_kiem_tra_ky_thuat` duoc suy ra tu cau hinh; gioi han cam tuyen bo hieu qua chi ap dung cho technical run. Runner khong hard-code trang thai Tier A/Tier B, phe duyet nguon, raw immutability hay absence of correction overlay nhu ket qua tu xac minh. Cac actual acquisition facts thuoc external execution provenance manifest. PR canonical van la #16; head truoc correction la `2efa627c65cb5387bcc4aa77f4063070812d6aa6`, CI #351 la baseline close-only head cu, Giai doan 2B chua mo.''',
)
append_once(
    "tai_lieu/dac_ta_moc_4.md",
    "## QD-0062 - dac ta reporting/provenance",
    '''## QD-0062 - dac ta reporting/provenance

San pham runner chi duoc cong bo fact do runner tu xac minh hoac suy ra tu config. `benchmark_policy` dung cac ten requirement `correction_overlay_duoc_phep`, `raw_source_bat_buoc_giu_bat_bien` va `exact_official_ohlc_hien_co`; khong duoc dung key mo ho nhu mot runtime attestation. `chi_kiem_tra_ky_thuat` bang ket qua so sanh `muc_dich_lan_chay == kiem_tra_ky_thuat`. Tier A/Tier B status va acquisition provenance nam ngoai generic runner va phai duoc ghi trong external execution provenance manifest.''',
)
append_once(
    "tai_lieu/kien_truc_moc_4.md",
    "## QD-0062 - bien kien truc provenance",
    '''## QD-0062 - bien kien truc provenance

Generic runner la lop tinh toan/cong bo, khong phai acquisition attestor. Lop nay cong bo close-only contract va policy requirement, nhung khong khang dinh raw bundle da bat bien hay overlay thuc te khong ton tai khi khong nhan acquisition manifest. Execution provenance cua Tier A giu cac hash, run facts va bang chung ben ngoai. Trang thai technical/research duoc suy ra tu config; trang thai dieu phoi khong duoc dong bang trong artifact bat bien.''',
)
coordination_text = '''## Cap nhat QD-0062: reporting/provenance blocker

Canonical PR la #16 tren nhanh `m4-dac_trung-xep-hang-hoc_may-sach-final-v2`. Head truoc correction la `2efa627c65cb5387bcc4aa77f4063070812d6aa6`; close-only QD-0061 va CI #351 da dat. Giai doan 2A da hoan tat; blocker hien tai chi la generic runner hard-code reporting/provenance khong thuoc kha nang tu xac minh. Correction QD-0062 tach policy khoi runtime fact, khong chay lai Tier A pipeline va khong mo Giai doan 2B, Tier B hay Moc 5.'''
for path in (
    "tai_lieu_dieu_phoi/trang_thai_du_an.md",
    "tai_lieu_dieu_phoi/cong_viec_hien_tai.md",
    "tai_lieu_dieu_phoi/ban_giao_doan_chat.md",
    "tai_lieu_dieu_phoi/ke_hoach_tong_the.md",
):
    append_once(path, "## Cap nhat QD-0062: reporting/provenance blocker", coordination_text)

print("M4_REPORTING_PROVENANCE_PATCH_APPLIED")
