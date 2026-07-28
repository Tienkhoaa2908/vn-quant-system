"""Mo hinh mien nghiep vu va bo doc dau vao cho Moc 3."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Iterable, Mapping

SO_KHONG = Decimal("0")
MOT = Decimal("1")
DON_VI_HOP_LE = {"dong", "nghin_dong"}
CO_SO_GIA_DIEU_CHINH = "dieu_chinh"
CO_SO_GIA_KHONG_DIEU_CHINH = "khong_dieu_chinh"
CO_SO_GIA_CHUA_XAC_NHAN = "CHUA_XAC_NHAN"
CO_SO_GIA_HOP_LE = frozenset({
    CO_SO_GIA_DIEU_CHINH,
    CO_SO_GIA_KHONG_DIEU_CHINH,
    CO_SO_GIA_CHUA_XAC_NHAN,
})
PRICE_BASIS_UNCONFIRMED = "PRICE_BASIS_UNCONFIRMED"


def so_thap_phan(gia_tri: object, ten: str, *, cho_phep_rong: bool = False) -> Decimal | None:
    if gia_tri is None or (isinstance(gia_tri, str) and not gia_tri.strip()):
        if cho_phep_rong:
            return None
        raise ValueError(f"{ten} khong duoc rong.")
    try:
        ket_qua = Decimal(str(gia_tri).strip())
    except (InvalidOperation, AttributeError, ValueError) as exc:
        raise ValueError(f"{ten} khong phai so hop le.") from exc
    if not ket_qua.is_finite():
        raise ValueError(f"{ten} phai la so huu han.")
    return ket_qua


def so_nguyen_duong(gia_tri: object, ten: str) -> int:
    """Doc so nguyen ma khong am tham ep float ve int."""
    if isinstance(gia_tri, bool):
        raise ValueError(f"{ten} phai la so nguyen thuc su.")
    if isinstance(gia_tri, int):
        ket_qua = gia_tri
    elif isinstance(gia_tri, str) and gia_tri.strip().isdigit():
        ket_qua = int(gia_tri.strip())
    else:
        raise ValueError(f"{ten} phai la so nguyen thuc su.")
    if ket_qua <= 0:
        raise ValueError(f"{ten} phai la so nguyen duong.")
    return ket_qua


def doc_bool(gia_tri: object, ten: str, *, cho_phep_rong: bool = True) -> bool | None:
    if gia_tri is None or (isinstance(gia_tri, str) and not gia_tri.strip()):
        if cho_phep_rong:
            return None
        raise ValueError(f"{ten} khong duoc rong.")
    if isinstance(gia_tri, bool):
        return gia_tri
    chuoi = str(gia_tri).strip().lower()
    if chuoi in {"true", "1", "co", "yes"}:
        return True
    if chuoi in {"false", "0", "khong", "no"}:
        return False
    raise ValueError(f"{ten} khong phai gia tri boolean hop le.")


@dataclass(frozen=True)
class cau_hinh_mo_phong:
    von_ban_dau: Decimal
    phi_mua_bps: Decimal
    phi_ban_bps: Decimal
    thue_ban_bps: Decimal
    truot_gia_bps: Decimal
    kich_thuoc_lo: int
    so_phien_moi_nam: int
    lai_suat_phi_rui_ro: Decimal
    che_do_ma_khong_xuat_hien: str
    cho_phep_ban_le_khi_dong_vi_the: bool
    co_so_gia: str
    don_vi_gia: str
    don_vi_tien: str

    def __post_init__(self) -> None:
        if self.von_ban_dau <= 0:
            raise ValueError("von_ban_dau phai lon hon 0.")
        for ten in ("phi_mua_bps", "phi_ban_bps", "thue_ban_bps", "truot_gia_bps"):
            if getattr(self, ten) < 0:
                raise ValueError(f"{ten} khong duoc am.")
        if self.truot_gia_bps >= Decimal("10000"):
            raise ValueError("truot_gia_bps phai nho hon 10000.")
        if self.phi_ban_bps + self.thue_ban_bps > Decimal("10000"):
            raise ValueError("Tong phi_ban_bps va thue_ban_bps khong duoc lam tien ban rong am.")
        if not isinstance(self.kich_thuoc_lo, int) or isinstance(self.kich_thuoc_lo, bool):
            raise ValueError("kich_thuoc_lo phai la so nguyen thuc su.")
        if not isinstance(self.so_phien_moi_nam, int) or isinstance(self.so_phien_moi_nam, bool):
            raise ValueError("so_phien_moi_nam phai la so nguyen thuc su.")
        if self.kich_thuoc_lo <= 0 or self.so_phien_moi_nam <= 0:
            raise ValueError("kich_thuoc_lo va so_phien_moi_nam phai la so nguyen duong.")
        if self.lai_suat_phi_rui_ro <= -1:
            raise ValueError("lai_suat_phi_rui_ro phai lon hon -1.")
        if self.che_do_ma_khong_xuat_hien not in {"giu_nguyen", "muc_tieu_bang_0"}:
            raise ValueError("che_do_ma_khong_xuat_hien khong hop le.")
        if self.co_so_gia not in CO_SO_GIA_HOP_LE:
            raise ValueError("co_so_gia khong hop le.")
        if self.don_vi_gia not in DON_VI_HOP_LE or self.don_vi_tien not in DON_VI_HOP_LE:
            raise ValueError("don_vi_gia va don_vi_tien khong hop le.")
        if self.don_vi_gia != self.don_vi_tien:
            raise ValueError("don_vi_gia va don_vi_tien phai thong nhat; khong duoc tron don vi.")

    @property
    def co_so_gia_da_xac_nhan(self) -> bool:
        return self.co_so_gia != CO_SO_GIA_CHUA_XAC_NHAN

    @classmethod
    def tu_mapping(cls, du_lieu: Mapping[str, object]) -> "cau_hinh_mo_phong":
        khoa = (
            "von_ban_dau", "phi_mua_bps", "phi_ban_bps", "thue_ban_bps",
            "truot_gia_bps", "kich_thuoc_lo", "so_phien_moi_nam",
            "lai_suat_phi_rui_ro", "che_do_ma_khong_xuat_hien",
            "cho_phep_ban_le_khi_dong_vi_the", "co_so_gia",
            "don_vi_gia", "don_vi_tien",
        )
        thieu = [ten for ten in khoa if ten not in du_lieu]
        if thieu:
            raise ValueError(f"Thieu cau hinh bat buoc: {', '.join(thieu)}.")
        return cls(
            so_thap_phan(du_lieu["von_ban_dau"], "von_ban_dau"),
            so_thap_phan(du_lieu["phi_mua_bps"], "phi_mua_bps"),
            so_thap_phan(du_lieu["phi_ban_bps"], "phi_ban_bps"),
            so_thap_phan(du_lieu["thue_ban_bps"], "thue_ban_bps"),
            so_thap_phan(du_lieu["truot_gia_bps"], "truot_gia_bps"),
            so_nguyen_duong(du_lieu["kich_thuoc_lo"], "kich_thuoc_lo"),
            so_nguyen_duong(du_lieu["so_phien_moi_nam"], "so_phien_moi_nam"),
            so_thap_phan(du_lieu["lai_suat_phi_rui_ro"], "lai_suat_phi_rui_ro"),
            str(du_lieu["che_do_ma_khong_xuat_hien"]).strip(),
            bool(doc_bool(du_lieu["cho_phep_ban_le_khi_dong_vi_the"], "cho_phep_ban_le_khi_dong_vi_the", cho_phep_rong=False)),
            str(du_lieu["co_so_gia"]).strip(),
            str(du_lieu["don_vi_gia"]).strip(),
            str(du_lieu["don_vi_tien"]).strip(),
        )

    def thanh_tu_dien(self) -> dict[str, object]:
        return {
            "von_ban_dau": str(self.von_ban_dau),
            "phi_mua_bps": str(self.phi_mua_bps),
            "phi_ban_bps": str(self.phi_ban_bps),
            "thue_ban_bps": str(self.thue_ban_bps),
            "truot_gia_bps": str(self.truot_gia_bps),
            "kich_thuoc_lo": self.kich_thuoc_lo,
            "so_phien_moi_nam": self.so_phien_moi_nam,
            "lai_suat_phi_rui_ro": str(self.lai_suat_phi_rui_ro),
            "che_do_ma_khong_xuat_hien": self.che_do_ma_khong_xuat_hien,
            "cho_phep_ban_le_khi_dong_vi_the": self.cho_phep_ban_le_khi_dong_vi_the,
            "co_so_gia": self.co_so_gia,
            "don_vi_gia": self.don_vi_gia,
            "don_vi_tien": self.don_vi_tien,
        }


@dataclass(frozen=True)
class thanh_gia:
    ma: str
    ngay: date
    gia_mo_cua: Decimal | None
    gia_dong_cua: Decimal
    khoi_luong: int | None = None
    thuoc_tap_co_phieu: bool | None = None
    dat_thanh_khoan: bool | None = None
    tren_ma250: bool | None = None
    dong_luong: Decimal | None = None


@dataclass(frozen=True)
class ty_trong_muc_tieu:
    ngay_tin_hieu: date
    ma: str
    ty_trong: Decimal
    ten_chien_luoc: str


@dataclass(frozen=True)
class su_kien_doanh_nghiep:
    ma: str
    loai_su_kien: str
    ngay_hieu_luc: date | None
    ngay_thanh_toan: date | None
    ty_le: Decimal | None
    gia_tri_tien_mat: Decimal | None
    nguon: str
    phien_ban: str | None = None

    def khoa(self) -> tuple[object, ...]:
        return (
            self.ma, self.loai_su_kien, self.ngay_hieu_luc,
            self.ngay_thanh_toan, self.ty_le, self.gia_tri_tien_mat,
            self.nguon, self.phien_ban,
        )


@dataclass
class lenh:
    ma_lenh: str
    ngay_tin_hieu: date
    ngay_thuc_thi: date | None
    ma: str
    chieu: str
    so_luong: Decimal
    loai_lenh: str = "DAY"
    trang_thai: str = "cho_khop"
    ly_do_tu_choi_hoac_het_han: str | None = None
    so_luong_yeu_cau: Decimal | None = None
    so_luong_bi_giam: Decimal = SO_KHONG
    ly_do_giam: str | None = None

    def __post_init__(self) -> None:
        if self.so_luong_yeu_cau is None:
            self.so_luong_yeu_cau = self.so_luong


@dataclass(frozen=True)
class khop_lenh:
    ma_lenh: str
    ma: str
    ngay_khop: date
    chieu: str
    so_luong: Decimal
    gia_mo_cua: Decimal
    gia_khop: Decimal
    gia_tri_giao_dich: Decimal
    phi: Decimal
    thue: Decimal
    chi_phi_truot_gia: Decimal
    so_luong_yeu_cau: Decimal
    so_luong_bi_giam: Decimal
    ly_do_giam: str | None


@dataclass
class vi_the:
    ma: str
    so_luong: Decimal = SO_KHONG
    gia_von: Decimal = SO_KHONG

    def gia_tri_thi_truong(self, gia: Decimal) -> Decimal:
        return self.so_luong * gia

    def lai_lo_chua_thuc_hien(self, gia: Decimal) -> Decimal:
        return (gia - self.gia_von) * self.so_luong


@dataclass(frozen=True)
class dong_vi_the:
    ngay: date
    ma: str
    so_luong: Decimal
    gia_von: Decimal
    gia_dong_cua: Decimal
    gia_tri_thi_truong: Decimal
    lai_lo_chua_thuc_hien: Decimal


@dataclass(frozen=True)
class dong_so_cai:
    ngay: date
    tien_mat_dau_ngay: Decimal
    dong_tien_su_kien: Decimal
    tien_mua: Decimal
    tien_ban: Decimal
    phi: Decimal
    thue: Decimal
    tien_mat_cuoi_ngay: Decimal
    gia_tri_vi_the: Decimal
    nav: Decimal
    lai_lo_da_thuc_hien: Decimal = SO_KHONG
    lai_lo_da_thuc_hien_luy_ke: Decimal = SO_KHONG
    lai_lo_chua_thuc_hien: Decimal = SO_KHONG
    co_tuc_tien_mat: Decimal = SO_KHONG
    co_tuc_tien_mat_luy_ke: Decimal = SO_KHONG
    chi_phi_truot_gia: Decimal = SO_KHONG
    phi_mua: Decimal = SO_KHONG
    phi_ban: Decimal = SO_KHONG
    thue_ban: Decimal = SO_KHONG
    phi_mua_luy_ke: Decimal = SO_KHONG
    phi_ban_luy_ke: Decimal = SO_KHONG
    thue_ban_luy_ke: Decimal = SO_KHONG
    chenh_lech_doi_soat: Decimal = SO_KHONG


@dataclass(frozen=True)
class dong_nav:
    ngay: date
    nav: Decimal
    loi_nhuan_phien: Decimal | None
    tien_mat: Decimal
    ty_trong_tien_mat: Decimal | None


@dataclass
class ket_qua_mo_phong:
    cau_hinh: cau_hinh_mo_phong
    lenh: list[lenh] = field(default_factory=list)
    khop_lenh: list[khop_lenh] = field(default_factory=list)
    vi_the_hang_ngay: list[dong_vi_the] = field(default_factory=list)
    so_cai: list[dong_so_cai] = field(default_factory=list)
    nav: list[dong_nav] = field(default_factory=list)
    su_kien_da_ap_dung: list[dict[str, object]] = field(default_factory=list)
    so_lan_tai_can_bang: int = 0
    canh_bao: list[str] = field(default_factory=list)


def chuan_hoa_gia(cac_dong: Iterable[Mapping[str, object]]) -> list[thanh_gia]:
    ket_qua: list[thanh_gia] = []
    da_gap: set[tuple[str, date]] = set()
    for so_dong, dong in enumerate(cac_dong, 2):
        ma = str(dong.get("ma", "")).strip().upper()
        if not ma:
            raise ValueError(f"Ma rong tai dong gia {so_dong}.")
        try:
            ngay = date.fromisoformat(str(dong.get("ngay", "")).strip()[:10])
        except ValueError as exc:
            raise ValueError(f"Ngay khong hop le tai dong gia {so_dong}.") from exc
        if (ma, ngay) in da_gap:
            raise ValueError(f"Trung ma va ngay trong du lieu gia: {ma}, {ngay}.")
        da_gap.add((ma, ngay))
        gia_mo = so_thap_phan(dong.get("gia_mo_cua"), "gia_mo_cua", cho_phep_rong=True)
        gia_dong = so_thap_phan(dong.get("gia_dong_cua"), "gia_dong_cua")
        if (gia_mo is not None and gia_mo <= 0) or gia_dong <= 0:
            raise ValueError(f"Gia phai duong tai {ma}, {ngay}.")
        khoi_luong = None
        if dong.get("khoi_luong") not in (None, ""):
            khoi_luong = so_nguyen_duong(dong["khoi_luong"], "khoi_luong") if str(dong["khoi_luong"]) != "0" else 0
        ket_qua.append(thanh_gia(
            ma, ngay, gia_mo, gia_dong, khoi_luong,
            doc_bool(dong.get("thuoc_tap_co_phieu"), "thuoc_tap_co_phieu"),
            doc_bool(dong.get("dat_thanh_khoan"), "dat_thanh_khoan"),
            doc_bool(dong.get("tren_ma250"), "tren_ma250"),
            so_thap_phan(dong.get("dong_luong"), "dong_luong", cho_phep_rong=True),
        ))
    if not ket_qua:
        raise ValueError("Du lieu gia khong co dong nao.")
    return sorted(ket_qua, key=lambda muc: (muc.ngay, muc.ma))


def chuan_hoa_ty_trong(cac_dong: Iterable[Mapping[str, object]]) -> list[ty_trong_muc_tieu]:
    ket_qua: list[ty_trong_muc_tieu] = []
    da_gap: set[tuple[date, str]] = set()
    tong: dict[date, Decimal] = {}
    chien_luoc: dict[date, str] = {}
    for so_dong, dong in enumerate(cac_dong, 2):
        try:
            ngay = date.fromisoformat(str(dong.get("ngay_tin_hieu", "")).strip()[:10])
        except ValueError as exc:
            raise ValueError(f"Ngay tin hieu khong hop le tai dong {so_dong}.") from exc
        ma = str(dong.get("ma", "")).strip().upper()
        ty = so_thap_phan(dong.get("ty_trong_muc_tieu"), "ty_trong_muc_tieu")
        ten = str(dong.get("ten_chien_luoc", "")).strip()
        if not ma or not ten:
            raise ValueError("Ma va ten_chien_luoc khong duoc rong.")
        if ty < 0 or ty > 1:
            raise ValueError("ty_trong_muc_tieu phai nam trong [0,1].")
        if (ngay, ma) in da_gap:
            raise ValueError(f"Trung ty trong tai {ngay}, {ma}.")
        da_gap.add((ngay, ma))
        tong[ngay] = tong.get(ngay, SO_KHONG) + ty
        if tong[ngay] > 1:
            raise ValueError(f"Tong ty trong tai {ngay} vuot qua 1.")
        if ngay in chien_luoc and chien_luoc[ngay] != ten:
            raise ValueError(f"Mot ngay chi duoc co mot ten chien luoc: {ngay}.")
        chien_luoc[ngay] = ten
        ket_qua.append(ty_trong_muc_tieu(ngay, ma, ty, ten))
    return sorted(ket_qua, key=lambda muc: (muc.ngay_tin_hieu, muc.ma))


def chuan_hoa_su_kien(cac_dong: Iterable[Mapping[str, object]], *, co_so_gia: str) -> list[su_kien_doanh_nghiep]:
    if co_so_gia not in CO_SO_GIA_HOP_LE:
        raise ValueError("co_so_gia khong hop le khi chuan hoa su kien.")
    ket_qua: list[su_kien_doanh_nghiep] = []
    da_gap: set[tuple[object, ...]] = set()
    for so_dong, dong in enumerate(cac_dong, 2):
        ma = str(dong.get("ma", "")).strip().upper()
        loai = str(dong.get("loai_su_kien", "")).strip()
        nguon = str(dong.get("nguon", "")).strip()
        if not ma or not loai or not nguon:
            raise ValueError(f"Su kien tai dong {so_dong} thieu ma, loai hoac nguon.")
        hieu_luc = date.fromisoformat(str(dong["ngay_hieu_luc"]).strip()[:10]) if str(dong.get("ngay_hieu_luc", "")).strip() else None
        thanh_toan = date.fromisoformat(str(dong["ngay_thanh_toan"]).strip()[:10]) if str(dong.get("ngay_thanh_toan", "")).strip() else None
        ty_le = so_thap_phan(dong.get("ty_le"), "ty_le", cho_phep_rong=True)
        tien = so_thap_phan(dong.get("gia_tri_tien_mat"), "gia_tri_tien_mat", cho_phep_rong=True)
        if loai in {"chia_tach", "co_phieu_thuong", "chia_tach_hoac_thuong_co_phieu"}:
            if hieu_luc is None or ty_le is None or ty_le <= 0:
                raise ValueError("Chia tach/co phieu thuong can ngay_hieu_luc va ty_le > 0.")
        elif loai == "co_tuc_tien_mat":
            if hieu_luc is None or thanh_toan is None or tien is None or tien < 0:
                raise ValueError("Co tuc tien mat can ngay_hieu_luc, ngay_thanh_toan va gia_tri_tien_mat >= 0.")
            if thanh_toan < hieu_luc:
                raise ValueError("ngay_thanh_toan co tuc khong duoc truoc ngay_hieu_luc.")
        else:
            raise ValueError(f"Loai su kien chua duoc ho tro: {loai}.")
        phien_ban = str(dong.get("phien_ban", "")).strip() or None
        su_kien = su_kien_doanh_nghiep(ma, loai, hieu_luc, thanh_toan, ty_le, tien, nguon, phien_ban)
        khoa = su_kien.khoa()
        if khoa in da_gap:
            raise ValueError("Trung su kien doanh nghiep.")
        da_gap.add(khoa)
        ket_qua.append(su_kien)
    if ket_qua and co_so_gia == CO_SO_GIA_DIEU_CHINH:
        raise ValueError("Du lieu gia dieu_chinh kem corporate actions co nguy co tinh hai lan.")
    if ket_qua and co_so_gia == CO_SO_GIA_CHUA_XAC_NHAN:
        raise ValueError(
            f"{PRICE_BASIS_UNCONFIRMED}: khong duoc chuan hoa corporate actions "
            "khi co_so_gia=CHUA_XAC_NHAN."
        )
    return sorted(ket_qua, key=lambda muc: (muc.ngay_hieu_luc or muc.ngay_thanh_toan or date.min, muc.ma, muc.loai_su_kien))
