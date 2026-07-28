from __future__ import annotations

import base64
import json
from pathlib import Path


CAC_TAI_LIEU = (
    "tai_lieu/cua_du_lieu_vn100.md",
    "tai_lieu_dieu_phoi/trang_thai_du_an.md",
    "tai_lieu_dieu_phoi/cong_viec_hien_tai.md",
    "tai_lieu_dieu_phoi/ban_giao_doan_chat.md",
    "tai_lieu_dieu_phoi/ke_hoach_tong_the.md",
)

KHOI_PUBLICATION = r'''

## Publication hop dong gia rut gon VN100 ngay 2026-07-28

Publication ngoai tuyen da hoan tat tren 121 raw da co, khong goi KBS, khong tai
lai va khong sua du lieu goc:

```text
ma_lan_chay: vn100_rut_gon_20260728_38b67395
so_du_lieu_goc: 121
so_ma_dat: 121
so_ma_bi_loai: 0
tong_so_dong: 231151
hai_lan_cong_bo_cung_byte: true
```

SHA-256 san pham:

```text
du_lieu_gia_mo_dong_khoi_luong.csv
121cd49d401b1ba0d3a97a8f44aac0d2a9f7a7acb9b573d0fa1a2131de1545d6

bao_cao_do_phu_hop_dong_rut_gon.json
af3dd7edfd741fcd6a82d832f89fbfdc5d73701ad428f336b829f4cfdd971b92

bao_cao_ma_bi_loai.json
e46592af96417155ebcd8902bfb23f95926b7d8696bdffb77bf750d88ff6ff8d

manifest.json
88825dbd21364ef23116409b2979f885757c0a29dd1a7af8debfa1df60f0f0ef

sha256.txt
461cf6573a45746a84db7ebd2987920b19b059db931d6f0bf95cbb45ec2e8a04
```

Toan bo san pham publication va raw nam ngoai kho ma, khong duoc commit vao Git.

Ngoai le do phu bat buoc:

- ITA ket thuc tai `2024-09-25`;
- BCG ket thuc tai `2025-10-08`;
- TMS ket thuc tai `2026-07-23`;
- DSE va VPL co lich su ngan theo ngay bat dau du lieu cua tung ma;
- khong forward-fill va khong mang gia cuoi cung sang ngay sau;
- khong bien thieu du lieu thanh loi suat bang 0;
- eligibility va MA250 phai duoc danh gia theo tung cap `ma-ngay`;
- hop 121 ma chi la union thu thap, khong phai universe co dinh dung theo moi
  thoi diem.

Publication nay chi xac nhan hop dong ky thuat open/close/volume va tinh tai lap
byte. Cua nghien cuu chinh thuc van `FAIL` do lich su thanh phan VN100 chua lien
tuc, chua doi chieu HOSE EOD, kiem ke corporate actions chua day du va price
basis chua xac nhan. Khong duoc dien giai publication thanh bang chung alpha,
hieu qua mo hinh, hieu qua dau tu, tin hieu van hanh hay khuyen nghi giao dich.
Moc 4 chua chay lai; Moc 5 chua trien khai.
'''


def test_tao_payload_tai_lieu_publication_vn100_tam() -> None:
    marker = "## Publication hop dong gia rut gon VN100 ngay 2026-07-28"
    payload: dict[str, str] = {}
    for ten in CAC_TAI_LIEU:
        path = Path(ten)
        noi_dung = path.read_text(encoding="utf-8")
        assert marker not in noi_dung
        payload[ten] = noi_dung.rstrip() + KHOI_PUBLICATION + "\n"

    encoded = base64.b64encode(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).decode("ascii")
    for ten_artifact in ("phien-ban-ci-ubuntu.txt", "phien-ban-ci-windows.txt"):
        path = Path(ten_artifact)
        if path.exists():
            with path.open("a", encoding="utf-8", newline="\n") as tep:
                tep.write("VN100_DOC_PAYLOAD_BEGIN\n")
                tep.write(encoded + "\n")
                tep.write("VN100_DOC_PAYLOAD_END\n")
    assert len(payload) == 5
