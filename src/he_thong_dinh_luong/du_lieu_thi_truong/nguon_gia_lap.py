"""Nguồn giả phục vụ kiểm thử ngoại tuyến."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence

from .mo_hinh import bang_du_lieu_nguon


class nguon_gia_lap:
    ten_nguon = "gia_lap"
    phien_ban = "1"

    def __init__(
        self,
        du_lieu: Mapping[str, bang_du_lieu_nguon],
        loi: Mapping[str, BaseException | Sequence[BaseException]] | None = None,
    ) -> None:
        self._du_lieu = {ma.upper(): bang for ma, bang in du_lieu.items()}
        self._loi = {ma.upper(): gia_tri for ma, gia_tri in (loi or {}).items()}
        self.so_lan_goi: defaultdict[str, int] = defaultdict(int)

    def lay_du_lieu(
        self, ma: str, ngay_bat_dau: str, ngay_ket_thuc: str
    ) -> bang_du_lieu_nguon:
        del ngay_bat_dau, ngay_ket_thuc
        ma = ma.upper()
        lan_goi = self.so_lan_goi[ma]
        self.so_lan_goi[ma] += 1
        loi = self._loi.get(ma)
        if isinstance(loi, Sequence) and not isinstance(loi, (str, bytes)):
            if lan_goi < len(loi):
                raise loi[lan_goi]
        elif loi is not None:
            raise loi
        return self._du_lieu[ma]
