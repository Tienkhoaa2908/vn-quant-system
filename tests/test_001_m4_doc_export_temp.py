from __future__ import annotations

import base64
from pathlib import Path
import platform
import unittest


SECTIONS = {
    "DECISIONS.md": r'''

## QD-0068: Runtime Moc 4 rut gon chi cho kiem tra ky thuat

Moc 4 giu nguyen `strict_ohlcv` va `pit_membership_v1` de tuong thich nguoc. Che do moi chi duoc kich hoat ro rang bang `price_contract=reduced_open_close_volume_v1` ket hop `universe_contract=technical_candidate_union_v1`; runner khong tu nhan dang schema va khong cho tron tham so strict/reduced.

Hop dong reduced doc publication bat bien gom dung nam tep, xac minh SHA-256, schema chin cot `ma,ngay,gia_mo_cua,gia_dong_cua,khoi_luong,nguon,phien_ban,co_so_gia,raw_sha256`, khoa duy nhat va thu tu `ma,ngay`. Khoi luong phai la chuoi so nguyen thap phan khong am; gia tri thap phan, ky phap khoa hoc, lam tron va ep kieu ngam deu bi tu choi.

Reduced dung dung 23 dac trung canonical: tap strict bo duy nhat `bien_do_cao_thap_chuan_hoa`. Khong co dac trung thay the, khong tao/dien high-low va khong forward-fill, carry, zero-return hoac tim phien thay the. Feature, nhan T+20, Logistic Regression, hyperparameter, `top_k=2` va quy tac mo phong giu nguyen cau hinh canonical da phuc hoi.

`technical_candidate_union_v1` la enum runtime tong quat. `technical_candidate_union_121` chi la ten ho so du lieu hien tai; `candidate_union_expected_count=121` nam trong run profile, khong nam trong parser chung. So ma va so dong du kien duoc doc tu run profile/publication manifest va doi chieu so quan sat. Candidate union khong phai membership point-in-time; tai moi T, ma chi vao universe ky thuat khi co bar dung T, sau do van phai qua warm-up/MA250, feature, thanh khoan va open dung T+1.

Metadata co so gia duoc tach: co phieu dung `stock_price_basis=CHUA_XAC_NHAN`, `stock_price_basis_confirmed=false`; benchmark dung `benchmark_contract=close_only`, `benchmark_unit=index_points`, `benchmark_price_basis_confirmed=false`. Khong yeu cau equality giua stock basis va benchmark basis. Trong reduced mode, san pham cau hinh ghi `mo_phong.co_so_gia=CHUA_XAC_NHAN`; corporate actions khong duoc ap dung.

Cua nghien cuu reduced luon `FAIL` va giu ma `PRICE_BASIS_UNCONFIRMED`, cung ba blocker membership PIT, doi chieu HOSE EOD va corporate actions. Publication v2 tao 22 payload cung `manifest.json`, gom them lenh, khop lenh, so cai, vi the, NAV va su kien da ap dung. Auditor doc lap chi doc san pham, khong import/goi runner, trainer hoac engine, khong sua san pham; hai lan audit cung input/ma audit phai cung byte. Doi soat Decimal chap nhan sai so toi da `1E-18`, duoc cong bo trong bao cao audit.

Vong trien khai nay chi chay fixture ngoai tuyen va CI Ubuntu/Windows. Khong chay publication 121 ma, khong research claim, khong sua PR #20 va khong trien khai Moc 5.
''',
    "README.md": r'''

## Moc 4 — runtime gia rut gon cho kiem tra ky thuat

Runtime Moc 4 co hai hop dong ro rang:

- `strict_ohlcv` + `pit_membership_v1`: duong cu, giu tuong thich nguoc va 24 dac trung.
- `reduced_open_close_volume_v1` + `technical_candidate_union_v1`: opt-in technical-only, dung open/close/volume va 23 dac trung; loai duy nhat `bien_do_cao_thap_chuan_hoa`.

Reduced mode khong tu nhan dang schema, khong nhan `--ohlcv`/`--universe`, khong tao high-low va khong thay the feature. Publication input phai co dung nam tep canonical va SHA-256 hop le. So ma/so dong du kien duoc doc tu run profile va publication manifest, khong hard-code trong runtime chung.

Cau hinh profile hien tai dung `candidate_union_name=technical_candidate_union_121`, `candidate_union_expected_count=121`, `candidate_union_is_point_in_time=false`. Day la union thu thap, khong phai VN100 membership PIT. Eligibility duoc danh gia theo tung ma-ngay, co bar dung T, lich su/MA250/feature/thanh khoan va open dung T+1; khong carry bar cu.

Metadata reduced bat buoc tach biet:

```text
stock_price_basis=CHUA_XAC_NHAN
stock_price_basis_confirmed=false
benchmark_contract=close_only
benchmark_unit=index_points
benchmark_price_basis_confirmed=false
```

Khong yeu cau stock basis bang benchmark basis. `mo_phong.co_so_gia` trong san pham reduced bang `CHUA_XAC_NHAN`; corporate actions khong duoc ap dung. Research gate luon `FAIL`, gom ma `PRICE_BASIS_UNCONFIRMED`.

CLI reduced:

```bash
PYTHONPATH=src uv run --python 3.12 \
  python -m he_thong_dinh_luong.nghien_cuu_moc_4 \
  --cau-hinh duong_dan/cau_hinh_reduced.json \
  --thu-muc-publication-gia-rut-gon duong_dan/publication \
  --benchmark duong_dan/benchmark.csv \
  --lich-benchmark duong_dan/lich_benchmark.csv \
  --corporate-actions duong_dan/corporate_actions_metadata.csv \
  --thu-muc-dau-ra duong_dan/ket_qua \
  --ma-lan-chay ma_lan_chay_duy_nhat \
  --git-commit <SHA-40-ky-tu>
```

Publication v2 gom 22 payload va `manifest.json`. Auditor doc lap:

```bash
PYTHONPATH=src uv run --python 3.12 \
  python -m he_thong_dinh_luong.nghien_cuu_moc_4.kiem_toan_san_pham \
  --thu-muc-san-pham duong_dan/ket_qua/ma_lan_chay \
  --thu-muc-bao-cao duong_dan/audit_01 \
  --ma-kiem-toan audit_ma_lan_chay
```

Auditor chi doc san pham, khong chay lai pipeline/model/backtest va khong sua output. Hai lan audit cung input va `ma_kiem_toan` tao cung byte/SHA-256. Vong nay chi kiem thu fixture ngoai tuyen; chua chay publication 121 ma va khong duoc dien giai ket qua nhu hieu qua dau tu.
''',
    "tai_lieu/dac_ta_moc_4.md": r'''

## Phu luc: hop dong runtime rut gon v1

### Pham vi va mode

`strict_ohlcv` giu nguyen schema, feature order, PIT membership va publication v1. Reduced chi hop le khi dong thoi co:

```text
muc_dich_lan_chay=kiem_tra_ky_thuat
price_contract=reduced_open_close_volume_v1
universe_contract=technical_candidate_union_v1
stock_price_basis=CHUA_XAC_NHAN
stock_price_basis_confirmed=false
benchmark_contract=close_only
benchmark_unit=index_points
benchmark_price_basis_confirmed=false
corporate_actions_day_du=false
```

Khong auto-detection. Reduced cam input `--ohlcv` va `--universe`; strict cam `--thu-muc-publication-gia-rut-gon`.

### Cau hinh canonical bat bien

```text
label_horizon=20
purge_phien=20
embargo_phien=0
so_thang_train_toi_thieu=24
so_thang_validation=6
so_thang_test=1
top_k=2
cua_so_thanh_khoan=20
nguong_gtgd_tb_toi_thieu=0.0
ty_le_coverage_toi_thieu=0.0
so_ma_eligible_toi_thieu=0
C_grid=[0.1,1.0,10.0]
solver=lbfgs
max_iter=1000
class_weight=null
seed=20260725
```

Mo phong giu von `1000000000`, phi mua/ban `15/15` bps, thue ban `100` bps, slippage `10` bps, lot `1`, `250` phien/nam, lai phi rui ro `0`, `muc_tieu_bang_0`, khong ban le khi dong vi the va don vi `dong/dong`. Chi truong `co_so_gia` cua san pham reduced chuyen thanh `CHUA_XAC_NHAN`; khong duoc dien giai thanh dieu chinh.

### Publication input

Thu muc input co dung:

```text
du_lieu_gia_mo_dong_khoi_luong.csv
bao_cao_do_phu_hop_dong_rut_gon.json
bao_cao_ma_bi_loai.json
manifest.json
sha256.txt
```

CSV co dung thu tu chin cot. Gia open/close huu han duong; volume la integer decimal syntax khong am; `(ma,ngay)` duy nhat va file sap xep nghiem ngat; `raw_sha256` la 64 hex chu thuong. Nguon, phien ban va basis dong nhat. SHA trong `sha256.txt`, manifest va byte thuc te phai khop.

Runtime khong hard-code count. `candidate_union_expected_count` doc tu run profile; expected symbol/row count doc tu publication manifest/coverage; tat ca phai bang observed. Profile hien tai co ten `technical_candidate_union_121`, expected count `121`, PIT flag `false`.

### Feature va universe

Reduced feature order bang strict order bo duy nhat `bien_do_cao_thap_chuan_hoa`, tong 23. Khong replacement, high-low synthesis, imputation, forward-fill, carry hoac zero return. Candidate union chi dinh danh tap ma; tai T phai co bar T, du warm-up/MA250, feature bat buoc, thanh khoan va open exact T+1.

### Metadata va research gate

Stock/benchmark basis duoc validate rieng; khong co equality gate. Reduced khong ap dung corporate actions. Cua nghien cuu:

```text
research_gate=FAIL
PRICE_BASIS_UNCONFIRMED
VN100_POINT_IN_TIME_HISTORY_INCOMPLETE
HOSE_EOD_CROSSCHECK_INCOMPLETE
CORPORATE_ACTION_INVENTORY_INCOMPLETE
```

### San pham v2 va audit

V2 them `lenh.csv`, `khop_lenh.csv`, `so_cai.csv`, `vi_the.csv`, `nav.csv`, `su_kien_da_ap_dung.csv`; tong 22 payload + manifest. Manifest ghi contract/model/audit versions, expected/observed counts, basis tach biet, high-low flags, research gate va hash tat ca input/output.

Auditor doc lap khong import/goi runner, trainer, adapter backtest hoac engine. No xac minh hash, config, feature columns, ranking/top-k/tie-break, T+1, order/fill, cash/position, NAV/ledger va corporate-actions-empty. Auditor khong sua product; cung input va `ma_kiem_toan` phai cung byte. Tolerance doi soat Decimal la `1E-18` va phai duoc ghi trong report.
''',
    "tai_lieu/kien_truc_moc_4.md": r'''

## 15. Kien truc runtime rut gon va auditor v1

### Phan nhanh hop dong

`CauHinhMoc4` doc hai schema ro rang. Schema legacy khong co `price_contract` va duoc chuyen thanh strict/PIT. Schema moi bat buoc khai bao day du price/universe/stock-basis/benchmark metadata/candidate profile. Khong co heuristic tu header hoac duong dan.

```text
config
├─ strict_ohlcv + pit_membership_v1
│  ├─ _doc_ohlcv
│  ├─ _doc_universe
│  ├─ FEATURE_ORDER_STRICT_OHLCV_V1 (24)
│  └─ publication v1
└─ reduced_open_close_volume_v1 + technical_candidate_union_v1
   ├─ _doc_publication_rut_gon
   ├─ xac_dinh_technical_candidate_union
   ├─ FEATURE_ORDER_REDUCED_OPEN_CLOSE_VOLUME_V1 (23)
   └─ publication v2 + independent audit
```

### Parser publication reduced

Parser xac minh tap nam tep truoc khi doc CSV; doi chieu `sha256.txt`, `manifest.san_pham_sha256` va byte. Symbol/row expected duoc lay tu profile va publication, sau do doi chieu observed. Parser chung khong biet gia tri 121/231151. Data model reduced chi co open/close/volume va provenance; khong co attribute high/low.

### Feature va candidate state

`tao_feature_cuoi_thang` nhan `feature_order` canonical. High-low block chi chay neu feature strict ton tai; reduced khong truy cap, tao hoac dien high/low. Tat ca window van dung exact benchmark sessions. `technical_candidate_union_v1` tao state theo exact `(ma,T)`; no khong tao PIT record gia va khong mang bar cu qua ngay sau. Eligibility layer giu AND cua state, feature, liquidity, benchmark metadata va open exact T+1.

### Adapter mo phong

Reduced tao view cau hinh engine giu nguyen moi tham so canonical, chi doi basis thanh `CHUA_XAC_NHAN`. Danh sach corporate actions bat buoc rong; neu PIT input co event thi fail closed truoc backtest. Price rows van chi mang open/close va eligibility, khong thay doi fill/fee/tax/slippage/lot logic M3.

### Publication v2

Publisher v1 va v2 dung chung staging/fsync/atomic replace, nhung co tap ten va metadata required rieng. V2 cong bo 22 payload, sau do manifest co:

```text
manifest_schema_version=m4_manifest_v2
product_contract_version=m4_products_v2
model_contract_version=m4_logistic_reduced_open_close_volume_v1
audit_contract_version=m4_product_audit_v1
```

Sau payload M4 cu, v2 serialize truc tiep hai ket qua OOS thanh order/fill/ledger/position/NAV/event tables. Serialization khong chay lai engine.

### Auditor doc lap

Module `kiem_toan_san_pham` chi dung standard library va chi doc thu muc product. No khong import `runner`, `logistic`, `adapter_mo_phong` hoac `mo_phong.engine`. Thu tu audit:

```text
manifest versions/product set/hash/size
→ canonical config va metadata gate
→ feature order 23/no high-low
→ ranking order/ticker tie-break/top_k=2/weight=0.5
→ order exact T+1, fill duong
→ cash/position khong am
→ NAV bang ledger NAV, reconciliation <= 1E-18
→ corporate actions empty
→ deterministic report + reconciliation CSV + sha256.txt
```

Bao cao audit khong chua timestamp runtime, hostname, absolute output path hoac UUID. Hai destination khac nhau voi cung product va `ma_kiem_toan` tao ba file cung byte. Exit code `0` khi pass, `2` khi fail; product khong bao gio bi sua.

### Gioi han thuc thi

Kiem thu end-to-end chi dung publication tong hop ba ma de chung minh runtime khong hard-code 121. Vong trien khai khong chay raw/publication that, khong huan luyen hoac backtest tren 121 ma, khong research claim va khong mo Moc 5.
''',
}


class TestDocExportTemp(unittest.TestCase):
    def test_export_full_docs_for_contents_api(self) -> None:
        suffix = "windows" if platform.system() == "Windows" else "ubuntu"
        artifact = Path(f"phien-ban-ci-{suffix}.txt")
        with artifact.open("a", encoding="utf-8") as handle:
            for path_text, section in SECTIONS.items():
                path = Path(path_text)
                original = path.read_text(encoding="utf-8")
                marker = section.strip().splitlines()[0]
                final = original if marker in original else original.rstrip() + section + "\n"
                encoded = base64.b64encode(final.encode("utf-8")).decode("ascii")
                handle.write(f"\nM4_DOC_EXPORT_BEGIN {path_text}\n{encoded}\nM4_DOC_EXPORT_END {path_text}\n")
        self.assertEqual(set(SECTIONS), {
            "DECISIONS.md", "README.md", "tai_lieu/dac_ta_moc_4.md", "tai_lieu/kien_truc_moc_4.md",
        })


if __name__ == "__main__":
    unittest.main()
