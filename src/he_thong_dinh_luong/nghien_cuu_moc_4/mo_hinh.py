"""Hop dong du lieu va cau hinh tap trung cho nghien cuu Moc 4."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping

MUC_DICH_HOP_LE = {"kiem_tra_ky_thuat", "nghien_cuu"}
TAN_SUAT_MAU_HOP_LE = {"cuoi_thang"}
CO_SO_GIA_HOP_LE = {"gia_dieu_chinh", "gia_khong_dieu_chinh"}
VAI_TRO_HOP_LE = {"train", "validation", "refit_train_validation", "test"}
VAI_TRO_DU_DOAN_HOP_LE = {"validation", "test"}


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


def _float_that(value: object, ten: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"{ten} phai la so; khong ep chuoi thanh so.")
    result = float(value)
    if not (result > 0.0):
        raise ValueError(f"{ten} phai lon hon 0.")
    return result


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
    feature_order: tuple[str, ...]
    feature_bat_buoc: tuple[str, ...]
    C_grid: tuple[float, ...]
    solver: str
    max_iter: int
    class_weight: None
    seed: int
    thu_muc_dau_ra: Path

    @classmethod
    def tu_mapping(cls, data: Mapping[str, object]) -> "CauHinhMoc4":
        expected = {
            "muc_dich_lan_chay", "tan_suat_mau_mo_hinh", "benchmark", "co_so_gia",
            "co_so_gia_da_xac_nhan", "corporate_actions_day_du", "label_horizon",
            "purge_phien", "embargo_phien", "so_thang_train_toi_thieu",
            "so_thang_validation", "so_thang_test", "top_k", "feature_order",
            "feature_bat_buoc", "C_grid", "solver", "max_iter", "class_weight",
            "seed", "thu_muc_dau_ra",
        }
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
        if data["class_weight"] is not None:
            raise ValueError("class_weight MVP phai la null.")
        result = cls(
            muc_dich_lan_chay=_str_that(data["muc_dich_lan_chay"], "muc_dich_lan_chay"),
            tan_suat_mau_mo_hinh=_str_that(data["tan_suat_mau_mo_hinh"], "tan_suat_mau_mo_hinh"),
            benchmark=_str_that(data["benchmark"], "benchmark"),
            co_so_gia=_str_that(data["co_so_gia"], "co_so_gia"),
            co_so_gia_da_xac_nhan=_bool_that(data["co_so_gia_da_xac_nhan"], "co_so_gia_da_xac_nhan"),
            corporate_actions_day_du=_bool_that(data["corporate_actions_day_du"], "corporate_actions_day_du"),
            label_horizon=_int_that(data["label_horizon"], "label_horizon", min_value=1),
            purge_phien=_int_that(data["purge_phien"], "purge_phien", min_value=0),
            embargo_phien=_int_that(data["embargo_phien"], "embargo_phien", min_value=0),
            so_thang_train_toi_thieu=_int_that(data["so_thang_train_toi_thieu"], "so_thang_train_toi_thieu", min_value=1),
            so_thang_validation=_int_that(data["so_thang_validation"], "so_thang_validation", min_value=1),
            so_thang_test=_int_that(data["so_thang_test"], "so_thang_test", min_value=1),
            top_k=_int_that(data["top_k"], "top_k", min_value=1),
            feature_order=tuple(feature_order),
            feature_bat_buoc=tuple(required),
            C_grid=parsed_c,
            solver=_str_that(data["solver"], "solver"),
            max_iter=_int_that(data["max_iter"], "max_iter", min_value=1),
            class_weight=None,
            seed=_int_that(data["seed"], "seed", min_value=0),
            thu_muc_dau_ra=Path(_str_that(data["thu_muc_dau_ra"], "thu_muc_dau_ra")),
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
        if self.co_so_gia not in CO_SO_GIA_HOP_LE:
            raise ValueError("co_so_gia khong hop le.")
        if self.label_horizon != 20:
            raise ValueError("MVP khoa label_horizon=20.")
        if self.purge_phien < self.label_horizon:
            raise ValueError("purge_phien phai >= label_horizon.")
        if self.so_thang_test != 1:
            raise ValueError("MVP khoa so_thang_test=1.")
        if self.C_grid != (0.1, 1.0, 10.0):
            raise ValueError("MVP khoa C_grid=[0.1, 1.0, 10.0].")
        if self.solver != "lbfgs" or self.max_iter != 1000 or self.seed != 20260725:
            raise ValueError("solver, max_iter hoac seed khong dung hop dong MVP.")
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
            warnings.append("CO_SO_GIA_CHUA_XAC_NHAN")
        if self.co_so_gia == "gia_khong_dieu_chinh" and not self.corporate_actions_day_du:
            warnings.append("CORPORATE_ACTIONS_CHUA_DAY_DU")
        return tuple(warnings)

    def thanh_mapping(self) -> dict[str, object]:
        return {
            "muc_dich_lan_chay": self.muc_dich_lan_chay,
            "tan_suat_mau_mo_hinh": self.tan_suat_mau_mo_hinh,
            "benchmark": self.benchmark,
            "co_so_gia": self.co_so_gia,
            "co_so_gia_da_xac_nhan": self.co_so_gia_da_xac_nhan,
            "corporate_actions_day_du": self.corporate_actions_day_du,
            "label_horizon": self.label_horizon,
            "purge_phien": self.purge_phien,
            "embargo_phien": self.embargo_phien,
            "so_thang_train_toi_thieu": self.so_thang_train_toi_thieu,
            "so_thang_validation": self.so_thang_validation,
            "so_thang_test": self.so_thang_test,
            "top_k": self.top_k,
            "feature_order": list(self.feature_order),
            "feature_bat_buoc": list(self.feature_bat_buoc),
            "C_grid": list(self.C_grid),
            "solver": self.solver,
            "max_iter": self.max_iter,
            "class_weight": self.class_weight,
            "seed": self.seed,
            "thu_muc_dau_ra": str(self.thu_muc_dau_ra),
        }


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
            value = getattr(self, ten)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{ten} phai la so duong.")
        if not isinstance(self.khoi_luong, int) or isinstance(self.khoi_luong, bool) or self.khoi_luong < 0:
            raise ValueError("khoi_luong phai la int khong am.")
        if self.gia_cao_nhat < max(self.gia_mo_cua, self.gia_dong_cua, self.gia_thap_nhat):
            raise ValueError("gia_cao_nhat khong hop le.")
        if self.gia_thap_nhat > min(self.gia_mo_cua, self.gia_dong_cua, self.gia_cao_nhat):
            raise ValueError("gia_thap_nhat khong hop le.")


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


@dataclass(frozen=True)
class MauMoHinh:
    ngay: date
    ma: str
    feature: tuple[float, ...]
    nhan: int
    ngay_ket_thuc_nhan: date
    loi_nhuan_tuong_doi: float


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
        if not 0.0 <= self.xac_suat_nhan_1 <= 1.0:
            raise ValueError("xac_suat_nhan_1 phai trong [0,1].")
        if self.nhan not in {None, 0, 1}:
            raise ValueError("nhan du doan khong hop le.")

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
