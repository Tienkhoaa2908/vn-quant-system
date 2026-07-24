"""Bộ chuyển đổi Vnstock Community 4.0.4 dùng nguồn KBS."""

from __future__ import annotations

from importlib import metadata
from typing import Any, Callable

from .mo_hinh import bang_du_lieu_nguon, khong_co_du_lieu, loi_nguon_du_lieu

PHIEN_BAN_VNSTOCK = "4.0.4"
CAC_COT_VNSTOCK = ("time", "open", "high", "low", "close", "volume")
ANH_XA_COT_VNSTOCK = {
    "time": "ngay",
    "open": "gia_mo_cua",
    "high": "gia_cao_nhat",
    "low": "gia_thap_nhat",
    "close": "gia_dong_cua",
    "volume": "khoi_luong",
}


def _la_loi_tam_thoi(loi: BaseException) -> bool:
    ten = type(loi).__name__.lower()
    noi_dung = str(loi).lower()
    dau_hieu = (
        "timeout",
        "connection",
        "network",
        "temporarily",
        "429",
        "500",
        "502",
        "503",
        "504",
        "rate limit",
    )
    return any(muc in ten or muc in noi_dung for muc in dau_hieu)


def _la_khong_co_du_lieu(loi: BaseException) -> bool:
    noi_dung = str(loi).lower()
    return any(
        muc in noi_dung
        for muc in (
            "không tìm thấy dữ liệu",
            "khong tim thay du lieu",
            "dữ liệu trống",
            "du lieu trong",
            "no data",
        )
    )


class nguon_vnstock:
    """Cô lập toàn bộ phụ thuộc Vnstock khỏi phần còn lại của hệ thống."""

    ten_nguon = "vnstock_kbs"

    def __init__(
        self,
        *,
        ham_tao_thi_truong: Callable[[], Any] | None = None,
        ham_lay_phien_ban: Callable[[str], str] | None = None,
    ) -> None:
        self._ham_tao_thi_truong = ham_tao_thi_truong
        self._ham_lay_phien_ban = ham_lay_phien_ban or metadata.version
        self.phien_ban = self._ham_lay_phien_ban("vnstock")
        if self.phien_ban != PHIEN_BAN_VNSTOCK:
            raise RuntimeError(
                f"Can vnstock=={PHIEN_BAN_VNSTOCK}, dang co {self.phien_ban}."
            )

    def _tao_thi_truong(self) -> Any:
        if self._ham_tao_thi_truong is not None:
            return self._ham_tao_thi_truong()
        try:
            from vnstock import Market
        except ImportError as exc:
            raise RuntimeError(
                f"Chua cai vnstock=={PHIEN_BAN_VNSTOCK}."
            ) from exc
        return Market()

    def lay_du_lieu(
        self, ma: str, ngay_bat_dau: str, ngay_ket_thuc: str
    ) -> bang_du_lieu_nguon:
        ma = ma.strip().upper()
        try:
            thi_truong = self._tao_thi_truong()
            if ma == "VNINDEX":
                bo_doc = thi_truong.index(symbol=ma)
            else:
                bo_doc = thi_truong.equity(symbol=ma)
            bang = bo_doc.ohlcv(
                start=ngay_bat_dau,
                end=ngay_ket_thuc,
                interval="1D",
                source="kbs",
            )
        except Exception as exc:
            if _la_khong_co_du_lieu(exc):
                raise khong_co_du_lieu(str(exc)) from exc
            raise loi_nguon_du_lieu(
                str(exc), tam_thoi=_la_loi_tam_thoi(exc)
            ) from exc

        if bang is None or bool(getattr(bang, "empty", False)):
            raise khong_co_du_lieu(f"Vnstock khong tra du lieu cho {ma}.")

        cac_cot = tuple(str(cot) for cot in bang.columns)
        thieu_cot = [cot for cot in CAC_COT_VNSTOCK if cot not in cac_cot]
        if thieu_cot:
            raise loi_nguon_du_lieu(
                f"Vnstock thieu cot bat buoc: {', '.join(thieu_cot)}."
            )

        kieu_du_lieu = {cot: str(bang[cot].dtype) for cot in cac_cot}
        cac_dong = tuple(dict(dong) for dong in bang.to_dict(orient="records"))
        if not cac_dong:
            raise khong_co_du_lieu(f"Vnstock khong tra du lieu cho {ma}.")

        la_chi_so = ma == "VNINDEX"
        return bang_du_lieu_nguon(
            ma=ma,
            cac_cot=cac_cot,
            kieu_du_lieu=kieu_du_lieu,
            cac_dong=cac_dong,
            anh_xa_cot=ANH_XA_COT_VNSTOCK,
            don_vi_gia="diem" if la_chi_so else "nghin_dong",
            ghi_chu_khoi_luong=(
                "Truong volume do KBS cung cap cho chi so; can doi chieu log that "
                "truoc khi dung lam khoi luong giao dich."
                if la_chi_so
                else "So luong co phieu theo truong volume cua Vnstock/KBS."
            ),
            tham_so_gia=None,
        )
