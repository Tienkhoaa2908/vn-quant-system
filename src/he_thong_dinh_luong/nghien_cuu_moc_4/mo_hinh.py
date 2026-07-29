"""Hop dong du lieu va cau hinh tap trung cho nghien cuu Moc 4."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from .phong_ve import xac_thuc_cau_truc_huu_han, xac_thuc_so_huu_han

MUC_DICH_HOP_LE = {"kiem_tra_ky_thuat", "nghien_cuu"}
TAN_SUAT_MAU_HOP_LE = {"cuoi_thang"}
CO_SO_GIA_HOP_LE = {"gia_dieu_chinh", "gia_khong_dieu_chinh"}
STOCK_PRICE_BASIS_CHUA_XAC_NHAN = "CHUA_XAC_NHAN"
PRICE_CONTRACT_STRICT = "strict_ohlcv"
PRICE_CONTRACT_REDUCED = "reduced_open_close_volume_v1"
UNIVERSE_CONTRACT_PIT = "pit_membership_v1"
UNIVERSE_CONTRACT_TECHNICAL = "technical_candidate_union_v1"
BENCHMARK_CONTRACT = "close_only"
BENCHMARK_UNIT = "index_points"
PRICE_BASIS_UNCONFIRMED = "PRICE_BASIS_UNCONFIRMED"
VAI_TRO_HOP_LE = {"train", "validation", "refit_train_validation", "test"}
VAI_TRO_DU_DOAN_HOP_LE = {"validation", "test"}
CANH_BAO_BENCHMARK_CLOSE_ONLY = "BENCHMARK_CLOSE_ONLY"
CANH_BAO_BENCHMARK_SEMANTICS = "BENCHMARK_OHLC_SEMANTICS_CHUA_XAC_NHAN"


class ThanhCoGiaDongCua(Protocol):
    """Giao dien toi thieu cho feature/label chi doc gia dong cua."""

    ma: str
    ngay: date
    gia_dong_cua: float


class ThanhGiaCoPhieu(ThanhCoGiaDongCua, Protocol):
    """Giao dien toi thieu cho feature, eligibility va open T+1."""

    gia_mo_cua: float
    khoi_luong: int
    nguon: str
    phien_ban: str
    co_so_gia: str


def xac_thuc_timestamp(value: datetime, ten: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{ten} phai la datetime; khong ep kieu ngam.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{ten} phai co mui gio.")
    return value


def _int_that(value: object, ten: str, *, min_value: int | None = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{ten} phai la int; khong ep kieu ngam.")
    if min_value is not None and value < min_value:
        raise ValueError(f"{ten} phai >= {min_value}.")
    return value


def _bool_that(value: object, ten: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{ten} phai la bool; khong ep kieu ngam.")
    return value


def _str_that(value: object, ten: str) -> str:
    if not isinstance(value, str) or not value:
        raise TypeError(f"{ten} phai la chuoi khong rong; khong ep kieu ngam.")
    return value


def _optional_str(value: object, ten: str) -> str | None:
    if value is None:
        return None
    return _str_that(value, ten)


def _float_that(value: object, ten: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"{ten} phai la so; khong ep chuoi thanh so.")
    result = float(value)
    if not (result > 0.0):
        raise ValueError(f"{ten} phai lon hon 0.")
    return result


def _float_khong_am(value: object, ten: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"{ten} phai la so; khong ep chuoi thanh so.")
    result = float(value)
    if result < 0.0:
        raise ValueError(f"{ten} phai >= 0.")
    return result


def _ty_le(value: object, ten: str) -> float:
    result = _float_khong_am(value, ten)
    if result > 1.0:
        raise ValueError(f"{ten} phai trong [0,1].")
    return result


_CAU_HINH_CHUNG = {
    "muc_dich_lan_chay", "tan_suat_mau_mo_hinh", "benchmark",
    "corporate_actions_day_du", "label_horizon", "purge_phien", "embargo_phien",
    "so_thang_train_toi_thieu", "so_thang_validation", "so_thang_test", "top_k",
    "cua_so_thanh_khoan", "nguong_gtgd_tb_toi_thieu", "ty_le_coverage_toi_thieu",
    "so_ma_eligible_toi_thieu", "feature_order", "feature_bat_buoc", "C_grid",
    "solver", "max_iter", "class_weight", "seed", "thu_muc_dau_ra",
}
_CAU_HINH_LEGACY = _CAU_HINH_CHUNG | {"co_so_gia", "co_so_gia_da_xac_nhan"}
_CAU_HINH_CONTRACT_V1 = _CAU_HINH_CHUNG | {
    "price_contract", "universe_contract", "stock_price_basis",
    "stock_price_basis_confirmed", "benchmark_contract", "benchmark_unit",
    "benchmark_price_basis_confirmed", "candidate_union_name",
    "candidate_union_expected_count", "candidate_union_is_point_in_time",
}


@dataclass(frozen=True)
class CauHinhMoc4:
    muc_dich_lan_chay: str
    tan_suat_mau_mo_hinh: str
    benchmark: str
    co_so_gia: str
    co_so_gia_da_xac_nhan: bool
    corporate_actions_day_du: bool
    label_horizon: int
    purge_phien: int
    embargo_phien: int
    so_thang_train_toi_thieu: int
    so_thang_validation: int
    so_thang_test: int
    top_k: int
    cua_so_thanh_khoan: int
    nguong_gtgd_tb_toi_thieu: float
    ty_le_coverage_toi_thieu: float
    so_ma_eligible_toi_thieu: int
    feature_order: tuple[str, ...]
    feature_bat_buoc: tuple[str, ...]
    C_grid: tuple[float, ...]
    solver: str
    max_iter: int
    class_weight: None
    seed: int
    thu_muc_dau_ra: Path
    price_contract: str = PRICE_CONTRACT_STRICT
    universe_contract: str = UNIVERSE_CONTRACT_PIT
    candidate_union_name: str | None = None
    candidate_union_expected_count: int | None = None
    candidate_union_is_point_in_time: bool | None = None
    benchmark_contract: str = BENCHMARK_CONTRACT
    benchmark_unit: str = BENCHMARK_UNIT
    benchmark_price_basis_confirmed: bool = False
    schema_hop_dong_moi: bool = False

    @property
    def stock_price_basis(self) -> str:
        return self.co_so_gia

    @property
    def stock_price_basis_confirmed(self) -> bool:
        return self.co_so_gia_da_xac_nhan

    @property
    def la_reduced(self) -> bool:
        return self.price_contract == PRICE_CONTRACT_REDUCED

    @classmethod
    def tu_mapping(cls, data: Mapping[str, object]) -> "CauHinhMoc4":
        schema_moi = "price_contract" in data
        expected = _CAU_HINH_CONTRACT_V1 if schema_moi else _CAU_HINH_LEGACY
        missing = sorted(expected - set(data))
        extra = sorted(set(data) - expected)
        if missing:
            raise ValueError(f"Thieu cau hinh: {', '.join(missing)}.")
        if extra:
            raise ValueError(f"Cau hinh ngoai hop dong: {', '.join(extra)}.")

        feature_order = data["feature_order"]
        required = data["feature_bat_buoc"]
        c_grid = data["C_grid"]
        if not isinstance(feature_order, list) or not all(isinstance(x, str) and x for x in feature_order):
            raise TypeError("feature_order phai la list chuoi khong rong.")
        if len(set(feature_order)) != len(feature_order):
            raise ValueError("feature_order khong duoc trung.")
        if not isinstance(required, list) or not all(isinstance(x, str) and x for x in required):
            raise TypeError("feature_bat_buoc phai la list chuoi khong rong.")
        if len(set(required)) != len(required):
            raise ValueError("feature_bat_buoc khong duoc trung.")
        if not set(required).issubset(feature_order):
            raise ValueError("feature_bat_buoc phai la tap con cua feature_order.")
        if not isinstance(c_grid, list) or not c_grid:
            raise TypeError("C_grid phai la list khong rong.")
        parsed_c = tuple(_float_that(x, "C_grid") for x in c_grid)

        if schema_moi:
            basis = _str_that(data["stock_price_basis"], "stock_price_basis")
            basis_confirmed = _bool_that(data["stock_price_basis_confirmed"], "stock_price_basis_confirmed")
            price_contract = _str_that(data["price_contract"], "price_contract")
            universe_contract = _str_that(data["universe_contract"], "universe_contract")
            candidate_name = _optional_str(data["candidate_union_name"], "candidate_union_name")
            candidate_count_raw = data["candidate_union_expected_count"]
            candidate_count = None if candidate_count_raw is None else _int_that(candidate_count_raw, "candidate_union_expected_count", min_value=1)
            candidate_pit_raw = data["candidate_union_is_point_in_time"]
            candidate_pit = None if candidate_pit_raw is None else _bool_that(candidate_pit_raw, "candidate_union_is_point_in_time")
            benchmark_contract = _str_that(data["benchmark_contract"], "benchmark_contract")
            benchmark_unit = _str_that(data["benchmark_unit"], "benchmark_unit")
            benchmark_confirmed = _bool_that(data["benchmark_price_basis_confirmed"], "benchmark_price_basis_confirmed")
        else:
            basis = _str_that(data["co_so_gia"], "co_so_gia")
            basis_confirmed = _bool_that(data["co_so_gia_da_xac_nhan"], "co_so_gia_da_xac_nhan")
            price_contract = PRICE_CONTRACT_STRICT
            universe_contract = UNIVERSE_CONTRACT_PIT
            candidate_name = None
            candidate_count = None
            candidate_pit = None
            benchmark_contract = BENCHMARK_CONTRACT
            benchmark_unit = BENCHMARK_UNIT
            benchmark_confirmed = False

        result = cls(
            muc_dich_lan_chay=_str_that(data["muc_dich_lan_chay"], "muc_dich_lan_chay"),
            tan_suat_mau_mo_hinh=_str_that(data["tan_suat_mau_mo_hinh"], "tan_suat_mau_mo_hinh"),
            benchmark=_str_that(data["benchmark"], "benchmark"),
            co_so_gia=basis,
            co_so_gia_da_xac_nhan=basis_confirmed,
            corporate_actions_day_du=_bool_that(data["corporate_actions_day_du"], "corporate_actions_day_du"),
            label_horizon=_int_that(data["label_horizon"], "label_horizon", min_value=1),
            purge_phien=_int_that(data["purge_phien"], "purge_phien", min_value=0),
            embargo_phien=_int_that(data["embargo_phien"], "embargo_phien", min_value=0),
            so_thang_train_toi_thieu=_int_that(data["so_thang_train_toi_thieu"], "so_thang_train_toi_thieu", min_value=1),
            so_thang_validation=_int_that(data["so_thang_validation"], "so_thang_validation", min_value=1),
            so_thang_test=_int_that(data["so_thang_test"], "so_thang_test", min_value=1),
            top_k=_int_that(data["top_k"], "top_k", min_value=1),
            cua_so_thanh_khoan=_int_that(data["cua_so_thanh_khoan"], "cua_so_thanh_khoan", min_value=1),
            nguong_gtgd_tb_toi_thieu=_float_khong_am(data["nguong_gtgd_tb_toi_thieu"], "nguong_gtgd_tb_toi_thieu"),
            ty_le_coverage_toi_thieu=_ty_le(data["ty_le_coverage_toi_thieu"], "ty_le_coverage_toi_thieu"),
            so_ma_eligible_toi_thieu=_int_that(data["so_ma_eligible_toi_thieu"], "so_ma_eligible_toi_thieu", min_value=0),
            feature_order=tuple(feature_order),
            feature_bat_buoc=tuple(required),
            C_grid=parsed_c,
            solver=_str_that(data["solver"], "solver"),
            max_iter=_int_that(data["max_iter"], "max_iter", min_value=1),
            class_weight=data["class_weight"] if data["class_weight"] is None else (_ for _ in ()).throw(ValueError("class_weight MVP phai la null.")),
            seed=_int_that(data["seed"], "seed", min_value=0),
            thu_muc_dau_ra=Path(_str_that(data["thu_muc_dau_ra"], "thu_muc_dau_ra")),
            price_contract=price_contract,
            universe_contract=universe_contract,
            candidate_union_name=candidate_name,
            candidate_union_expected_count=candidate_count,
            candidate_union_is_point_in_time=candidate_pit,
            benchmark_contract=benchmark_contract,
            benchmark_unit=benchmark_unit,
            benchmark_price_basis_confirmed=benchmark_confirmed,
            schema_hop_dong_moi=schema_moi,
        )
        result.xac_thuc_mvp()
        return result

    def xac_thuc_mvp(self) -> None:
        if self.muc_dich_lan_chay not in MUC_DICH_HOP_LE:
            raise ValueError("muc_dich_lan_chay khong hop le.")
        if self.tan_suat_mau_mo_hinh not in TAN_SUAT_MAU_HOP_LE:
            raise ValueError("MVP chi ho tro tan_suat_mau_mo_hinh=cuoi_thang.")
        if self.benchmark != "VNINDEX":
            raise ValueError("MVP khoa benchmark=VNINDEX.")
        if self.price_contract not in {PRICE_CONTRACT_STRICT, PRICE_CONTRACT_REDUCED}:
            raise ValueError("price_contract khong hop le.")
        if self.universe_contract not in {UNIVERSE_CONTRACT_PIT, UNIVERSE_CONTRACT_TECHNICAL}:
            raise ValueError("universe_contract khong hop le.")
        if self.benchmark_contract != BENCHMARK_CONTRACT:
            raise ValueError("benchmark_contract phai bang close_only.")
        if self.benchmark_unit != BENCHMARK_UNIT:
            raise ValueError("benchmark_unit phai bang index_points.")
        if self.benchmark_price_basis_confirmed:
            raise ValueError("benchmark_price_basis_confirmed phai bang false trong hop dong hien tai.")
        if self.label_horizon != 20:
            raise ValueError("MVP khoa label_horizon=20.")
        if self.purge_phien < self.label_horizon:
            raise ValueError("purge_phien phai >= label_horizon.")
        if self.so_thang_test != 1:
            raise ValueError("MVP khoa so_thang_test=1.")
        if self.cua_so_thanh_khoan != 20:
            raise ValueError("MVP khoa cua_so_thanh_khoan=20 phien benchmark.")
        if self.C_grid != (0.1, 1.0, 10.0):
            raise ValueError("MVP khoa C_grid=[0.1, 1.0, 10.0].")
        if self.solver != "lbfgs" or self.max_iter != 1000 or self.seed != 20260725:
            raise ValueError("solver, max_iter hoac seed khong dung hop dong MVP.")

        if self.la_reduced:
            from .dac_trung import FEATURE_ORDER_REDUCED_OPEN_CLOSE_VOLUME_V1
            if self.universe_contract != UNIVERSE_CONTRACT_TECHNICAL:
                raise ValueError("Reduced mode bat buoc universe_contract=technical_candidate_union_v1.")
            if self.muc_dich_lan_chay != "kiem_tra_ky_thuat":
                raise ValueError(PRICE_BASIS_UNCONFIRMED)
            if self.co_so_gia != STOCK_PRICE_BASIS_CHUA_XAC_NHAN or self.co_so_gia_da_xac_nhan:
                raise ValueError(PRICE_BASIS_UNCONFIRMED)
            if self.corporate_actions_day_du:
                raise ValueError("Reduced mode khong duoc khai bao corporate_actions_day_du=true.")
            if not self.candidate_union_name or self.candidate_union_expected_count is None:
                raise ValueError("Reduced mode bat buoc ho so candidate union day du.")
            if self.candidate_union_is_point_in_time is not False:
                raise ValueError("candidate_union_is_point_in_time phai bang false.")
            if self.feature_order != FEATURE_ORDER_REDUCED_OPEN_CLOSE_VOLUME_V1:
                raise ValueError("feature_order reduced khong dung 23 dac trung canonical.")
            if self.feature_bat_buoc != FEATURE_ORDER_REDUCED_OPEN_CLOSE_VOLUME_V1:
                raise ValueError("feature_bat_buoc reduced khong dung 23 dac trung canonical.")
            canonical = (
                self.purge_phien == 20 and self.embargo_phien == 0
                and self.so_thang_train_toi_thieu == 24 and self.so_thang_validation == 6
                and self.so_thang_test == 1 and self.top_k == 2
                and self.cua_so_thanh_khoan == 20
                and self.nguong_gtgd_tb_toi_thieu == 0.0
                and self.ty_le_coverage_toi_thieu == 0.0
                and self.so_ma_eligible_toi_thieu == 0
            )
            if not canonical:
                raise ValueError("Reduced mode phai giu nguyen cau hinh canonical Moc 4.")
        else:
            if self.universe_contract != UNIVERSE_CONTRACT_PIT:
                raise ValueError("strict_ohlcv bat buoc universe_contract=pit_membership_v1.")
            if any(value is not None for value in (self.candidate_union_name, self.candidate_union_expected_count, self.candidate_union_is_point_in_time)):
                raise ValueError("strict_ohlcv khong duoc khai bao candidate union profile.")
            if self.co_so_gia not in CO_SO_GIA_HOP_LE:
                raise ValueError("co_so_gia khong hop le.")
            if self.muc_dich_lan_chay == "nghien_cuu":
                if not self.co_so_gia_da_xac_nhan:
                    raise ValueError("nghien_cuu tu choi co_so_gia chua xac nhan.")
                if self.co_so_gia == "gia_khong_dieu_chinh" and not self.corporate_actions_day_du:
                    raise ValueError("nghien_cuu gia_khong_dieu_chinh can corporate actions day du.")

    def canh_bao_muc_dich(self) -> tuple[str, ...]:
        warnings: list[str] = []
        if self.muc_dich_lan_chay == "kiem_tra_ky_thuat":
            warnings.append("CHI_KIEM_TRA_KY_THUAT_KHONG_KET_LUAN_HIEU_QUA")
        if not self.co_so_gia_da_xac_nhan:
            warnings.append(PRICE_BASIS_UNCONFIRMED)
            if not self.la_reduced:
                warnings.append("CO_SO_GIA_CHUA_XAC_NHAN")
        if self.la_reduced or (self.co_so_gia == "gia_khong_dieu_chinh" and not self.corporate_actions_day_du):
            warnings.append("CORPORATE_ACTIONS_CHUA_DAY_DU")
        warnings.extend((CANH_BAO_BENCHMARK_CLOSE_ONLY, CANH_BAO_BENCHMARK_SEMANTICS))
        return tuple(dict.fromkeys(warnings))

    def thanh_mapping(self) -> dict[str, object]:
        result: dict[str, object] = {
            "muc_dich_lan_chay": self.muc_dich_lan_chay,
            "tan_suat_mau_mo_hinh": self.tan_suat_mau_mo_hinh,
            "benchmark": self.benchmark,
            "corporate_actions_day_du": self.corporate_actions_day_du,
            "label_horizon": self.label_horizon,
            "purge_phien": self.purge_phien,
            "embargo_phien": self.embargo_phien,
            "so_thang_train_toi_thieu": self.so_thang_train_toi_thieu,
            "so_thang_validation": self.so_thang_validation,
            "so_thang_test": self.so_thang_test,
            "top_k": self.top_k,
            "cua_so_thanh_khoan": self.cua_so_thanh_khoan,
            "nguong_gtgd_tb_toi_thieu": self.nguong_gtgd_tb_toi_thieu,
            "ty_le_coverage_toi_thieu": self.ty_le_coverage_toi_thieu,
            "so_ma_eligible_toi_thieu": self.so_ma_eligible_toi_thieu,
            "feature_order": list(self.feature_order),
            "feature_bat_buoc": list(self.feature_bat_buoc),
            "C_grid": list(self.C_grid),
            "solver": self.solver,
            "max_iter": self.max_iter,
            "class_weight": self.class_weight,
            "seed": self.seed,
            "thu_muc_dau_ra": str(self.thu_muc_dau_ra),
        }
        if self.schema_hop_dong_moi:
            result.update({
                "price_contract": self.price_contract,
                "universe_contract": self.universe_contract,
                "stock_price_basis": self.stock_price_basis,
                "stock_price_basis_confirmed": self.stock_price_basis_confirmed,
                "benchmark_contract": self.benchmark_contract,
                "benchmark_unit": self.benchmark_unit,
                "benchmark_price_basis_confirmed": self.benchmark_price_basis_confirmed,
                "candidate_union_name": self.candidate_union_name,
                "candidate_union_expected_count": self.candidate_union_expected_count,
                "candidate_union_is_point_in_time": self.candidate_union_is_point_in_time,
            })
        else:
            result.update({"co_so_gia": self.co_so_gia, "co_so_gia_da_xac_nhan": self.co_so_gia_da_xac_nhan})
        return result


@dataclass(frozen=True)
class ThanhOHLCV:
    ma: str
    ngay: date
    gia_mo_cua: float
    gia_cao_nhat: float
    gia_thap_nhat: float
    gia_dong_cua: float
    khoi_luong: int
    nguon: str = "fixture"
    phien_ban: str = "1"
    co_so_gia: str = "gia_dieu_chinh"

    def __post_init__(self) -> None:
        if not self.ma or self.ma != self.ma.upper():
            raise ValueError("ma phai la chu hoa khong rong.")
        for ten in ("gia_mo_cua", "gia_cao_nhat", "gia_thap_nhat", "gia_dong_cua"):
            value = xac_thuc_so_huu_han(getattr(self, ten), ten)
            if value <= 0:
                raise ValueError(f"{ten} phai la so duong.")
        if not isinstance(self.khoi_luong, int) or isinstance(self.khoi_luong, bool) or self.khoi_luong < 0:
            raise ValueError("khoi_luong phai la int khong am.")
        if self.gia_cao_nhat < max(self.gia_mo_cua, self.gia_dong_cua, self.gia_thap_nhat):
            raise ValueError("gia_cao_nhat khong hop le.")
        if self.gia_thap_nhat > min(self.gia_mo_cua, self.gia_dong_cua, self.gia_cao_nhat):
            raise ValueError("gia_thap_nhat khong hop le.")


@dataclass(frozen=True)
class ThanhGiaMoDongKhoiLuong:
    ma: str
    ngay: date
    gia_mo_cua: float
    gia_dong_cua: float
    khoi_luong: int
    nguon: str
    phien_ban: str
    co_so_gia: str
    raw_sha256: str

    def __post_init__(self) -> None:
        if not self.ma or self.ma != self.ma.upper():
            raise ValueError("ma reduced phai la chu hoa khong rong.")
        if not isinstance(self.ngay, date):
            raise TypeError("ngay reduced phai la date.")
        for ten in ("gia_mo_cua", "gia_dong_cua"):
            value = xac_thuc_so_huu_han(getattr(self, ten), ten)
            if value <= 0:
                raise ValueError(f"{ten} phai la so duong.")
        if not isinstance(self.khoi_luong, int) or isinstance(self.khoi_luong, bool) or self.khoi_luong < 0:
            raise ValueError("khoi_luong reduced phai la int khong am.")
        if not self.nguon or not self.phien_ban:
            raise ValueError("Reduced row thieu nguon/phien_ban.")
        if self.co_so_gia != STOCK_PRICE_BASIS_CHUA_XAC_NHAN:
            raise ValueError(PRICE_BASIS_UNCONFIRMED)
        if len(self.raw_sha256) != 64 or self.raw_sha256.lower() != self.raw_sha256 or any(ch not in "0123456789abcdef" for ch in self.raw_sha256):
            raise ValueError("raw_sha256 phai la 64 ky tu hex chu thuong.")


@dataclass(frozen=True)
class ThanhBenchmarkDongCua:
    """Thanh benchmark canonical khong mang OHLC/volume chua xac nhan."""
    ma: str
    ngay: date
    gia_dong_cua: float
    nguon: str
    phien_ban: str
    co_so_gia: str

    def __post_init__(self) -> None:
        if not isinstance(self.ma, str) or not self.ma or self.ma != self.ma.upper():
            raise ValueError("ma benchmark phai la chu hoa khong rong.")
        if not isinstance(self.ngay, date):
            raise TypeError("ngay benchmark phai la date.")
        close = xac_thuc_so_huu_han(self.gia_dong_cua, "gia_dong_cua benchmark")
        if close <= 0.0:
            raise ValueError("gia_dong_cua benchmark phai la so duong.")
        for ten in ("nguon", "phien_ban", "co_so_gia"):
            value = getattr(self, ten)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Benchmark thieu {ten}.")


@dataclass(frozen=True)
class BanGhiUniverse:
    ngay_hieu_luc: date
    ma: str
    thuoc_universe: bool
    nguon: str
    phien_ban: str
    thoi_diem_cong_bo: datetime

    def __post_init__(self) -> None:
        if not self.ma or self.ma != self.ma.upper():
            raise ValueError("ma universe phai la chu hoa khong rong.")
        if not isinstance(self.thuoc_universe, bool):
            raise TypeError("thuoc_universe phai la bool.")
        xac_thuc_timestamp(self.thoi_diem_cong_bo, "thoi_diem_cong_bo")

    def khoa(self) -> tuple[object, ...]:
        return self.ma, self.ngay_hieu_luc, self.thoi_diem_cong_bo


@dataclass(frozen=True)
class BanGhiPointInTime:
    """Ban ghi PIT dung chung cho benchmark metadata, corporate actions va event."""
    loai_du_lieu: str
    khoa_ban_ghi: str
    ngay_hieu_luc: date
    nguon: str
    phien_ban: str
    thoi_diem_cong_bo: datetime
    du_lieu: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.loai_du_lieu not in {"benchmark_metadata", "corporate_action", "su_kien_point_in_time"}:
            raise ValueError("loai_du_lieu PIT khong hop le.")
        if not self.khoa_ban_ghi or not self.nguon or not self.phien_ban:
            raise ValueError("Ban ghi PIT thieu khoa, nguon hoac phien_ban.")
        xac_thuc_timestamp(self.thoi_diem_cong_bo, "thoi_diem_cong_bo")

    def khoa(self) -> tuple[object, ...]:
        return (self.loai_du_lieu, self.khoa_ban_ghi, self.ngay_hieu_luc, self.thoi_diem_cong_bo, self.nguon, self.phien_ban)


@dataclass(frozen=True)
class TrangThaiUniverse:
    ngay: date
    ma: str
    thuoc_universe: bool
    ly_do: str | None
    ban_ghi: BanGhiUniverse | None


@dataclass(frozen=True)
class DongFeature:
    ngay: date
    ma: str
    gia_tri: Mapping[str, float | bool | int | None]
    hop_le: bool
    ly_do: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.ma:
            raise ValueError("ma feature khong duoc rong.")
        xac_thuc_cau_truc_huu_han(self.gia_tri, f"feature.{self.ma}.{self.ngay}")


@dataclass(frozen=True)
class DongNhan:
    ngay: date
    ma: str
    T_H: date | None
    ngay_ket_thuc_nhan: date | None
    loi_nhuan_co_phieu: float | None
    loi_nhuan_benchmark: float | None
    loi_nhuan_tuong_doi: float | None
    nhan: int | None
    ly_do_nhan_rong: str | None

    def __post_init__(self) -> None:
        if not self.ma:
            raise ValueError("ma nhan khong duoc rong.")
        for ten in ("loi_nhuan_co_phieu", "loi_nhuan_benchmark", "loi_nhuan_tuong_doi"):
            value = getattr(self, ten)
            if value is not None:
                xac_thuc_so_huu_han(value, ten)
        if self.nhan not in {None, 0, 1}:
            raise ValueError("nhan khong hop le.")


@dataclass(frozen=True)
class MauMoHinh:
    ngay: date
    ma: str
    feature: tuple[float, ...]
    nhan: int
    ngay_ket_thuc_nhan: date
    loi_nhuan_tuong_doi: float

    def __post_init__(self) -> None:
        if self.nhan not in {0, 1}:
            raise ValueError("nhan mau mo hinh khong hop le.")
        if not self.feature:
            raise ValueError("feature mau mo hinh khong duoc rong.")
        for index, value in enumerate(self.feature):
            xac_thuc_so_huu_han(value, f"feature[{index}]")
        xac_thuc_so_huu_han(self.loi_nhuan_tuong_doi, "loi_nhuan_tuong_doi")


@dataclass(frozen=True)
class FoldWalkForward:
    fold: str
    train_dates: tuple[date, ...]
    validation_dates: tuple[date, ...]
    test_dates: tuple[date, ...]
    cutoff_train: date
    cutoff_validation: date
    cutoff_refit: date
    purge_dates: tuple[date, ...]
    embargo_dates: tuple[date, ...]


@dataclass(frozen=True)
class DuDoan:
    fold: str
    model_id: str
    vai_tro_du_lieu: str
    ngay: date
    ma: str
    xac_suat_nhan_1: float
    nhan: int | None = None
    loi_nhuan_tuong_doi: float | None = None

    def __post_init__(self) -> None:
        if self.vai_tro_du_lieu not in VAI_TRO_DU_DOAN_HOP_LE:
            raise ValueError("Du doan chi co vai tro validation hoac test.")
        probability = xac_thuc_so_huu_han(self.xac_suat_nhan_1, "xac_suat_nhan_1")
        if not 0.0 <= probability <= 1.0:
            raise ValueError("xac_suat_nhan_1 phai trong [0,1].")
        if self.nhan not in {None, 0, 1}:
            raise ValueError("nhan du doan khong hop le.")
        if self.loi_nhuan_tuong_doi is not None:
            xac_thuc_so_huu_han(self.loi_nhuan_tuong_doi, "loi_nhuan_tuong_doi")

    def khoa(self) -> tuple[date, str]:
        return self.ngay, self.ma


@dataclass(frozen=True)
class DongXepHang:
    fold: str
    model_id: str
    ngay: date
    ma: str
    xac_suat_nhan_1: float
    thu_hang: int
    duoc_chon: bool
    ty_trong_muc_tieu: float
    nhan: int | None
    loi_nhuan_tuong_doi: float | None
    vai_tro_du_lieu: str = "test"

    def __post_init__(self) -> None:
        if not self.fold or not self.model_id or not self.ma:
            raise ValueError("fold/model_id/ma ranking khong duoc rong.")
        if self.vai_tro_du_lieu != "test":
            raise ValueError("Ranking cuoi chi chap nhan vai_tro_du_lieu=test.")
        probability = xac_thuc_so_huu_han(self.xac_suat_nhan_1, "xac_suat_nhan_1")
        weight = xac_thuc_so_huu_han(self.ty_trong_muc_tieu, "ty_trong_muc_tieu")
        if not 0.0 <= probability <= 1.0 or not 0.0 <= weight <= 1.0:
            raise ValueError("Probability/target weight ranking khong hop le.")
        if self.nhan not in {None, 0, 1}:
            raise ValueError("nhan ranking khong hop le.")
        if self.loi_nhuan_tuong_doi is not None:
            xac_thuc_so_huu_han(self.loi_nhuan_tuong_doi, "loi_nhuan_tuong_doi")


@dataclass(frozen=True)
class KetQuaHuanLuyen:
    fold: str
    model_id: str
    C: float | None
    pipeline: Any | None
    validation_predictions: tuple[DuDoan, ...]
    validation_log_loss: float | None
    validation_auc: float | None
    thanh_cong: bool
    ly_do_that_bai: str | None
    metadata: Mapping[str, object] = field(default_factory=dict)
    selection_model_id: str | None = None
    refit_model_id: str | None = None
    selection_pipeline: Any | None = None


def xac_thuc_co_so_gia_va_su_kien(cau_hinh: CauHinhMoc4, *, so_su_kien: int) -> tuple[str, ...]:
    """Khoa hop dong co so gia truoc khi chuyen corporate actions vao engine."""
    if not isinstance(so_su_kien, int) or isinstance(so_su_kien, bool) or so_su_kien < 0:
        raise TypeError("so_su_kien phai la int khong am; khong ep kieu ngam.")
    if cau_hinh.la_reduced and so_su_kien > 0:
        raise ValueError("Reduced mode khong duoc ap dung corporate actions khi price basis chua xac nhan.")
    if cau_hinh.co_so_gia == "gia_dieu_chinh" and so_su_kien > 0:
        raise ValueError("gia_dieu_chinh khong duoc kem corporate actions.")
    if cau_hinh.muc_dich_lan_chay == "nghien_cuu" and not cau_hinh.stock_price_basis_confirmed:
        raise ValueError(PRICE_BASIS_UNCONFIRMED)
    if cau_hinh.muc_dich_lan_chay == "nghien_cuu" and cau_hinh.co_so_gia == "gia_khong_dieu_chinh" and not cau_hinh.corporate_actions_day_du:
        raise ValueError("nghien_cuu gia_khong_dieu_chinh can corporate actions day du.")
    return cau_hinh.canh_bao_muc_dich()
