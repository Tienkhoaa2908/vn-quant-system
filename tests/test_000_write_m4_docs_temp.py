from __future__ import annotations

import os
from pathlib import Path
import platform
import subprocess
import tempfile
import unittest

BRANCH = "m4-chay-lai-vn100-rong"
SECTIONS = {
    "DECISIONS.md": r'''

## QD-0068: Runtime rut gon Moc 4, publication v2 va auditor doc lap

`strict_ohlcv` tiep tuc la hop dong mac dinh va giu tuong thich nguoc. Runtime
khong tu nhan dang schema; hop dong rut gon chi duoc kich hoat ro rang bang
`price_contract=reduced_open_close_volume_v1` va chi hop le voi
`muc_dich_lan_chay=kiem_tra_ky_thuat`.

`technical_candidate_union_v1` la tap ung vien ky thuat theo ho so thu thap,
khong phai universe thanh phan point-in-time. Ho so hien tai co ten
`technical_candidate_union_121`, nhung so ma va so dong khong duoc hard-code
trong runtime chung; runtime doc so du kien tu run profile/publication manifest
va doi soat lai so quan sat.

Feature order reduced co dung 23 truong. Truong duy nhat bi loai so voi strict la
`bien_do_cao_thap_chuan_hoa`. High/low khong duoc doc trong schema reduced,
khong duoc dung, tao, noi suy, dien, sua hoac thay bang feature khac. Feature,
label, MA250, regime va valuation dung close; thanh khoan dung `close * volume`;
thuc thi dung open dung phien T+1.

Metadata stock va benchmark la hai hop dong doc lap. Stock reduced ghi
`stock_price_basis=CHUA_XAC_NHAN` va `stock_price_basis_confirmed=false`.
Benchmark ghi `benchmark_contract=close_only`, `benchmark_unit=index_points` va
`benchmark_price_basis_confirmed=false`. Khong co yeu cau hai price basis bang
nhau. `CHUA_XAC_NHAN` la trang thai basis rieng, khong duoc anh xa, dien giai
hoac xu ly nhu `dieu_chinh` hay `khong_dieu_chinh`. Cau hinh mo phong M3 phai
mang trang thai nay bang `cau_hinh_mo_phong` da xac thuc; engine fail closed neu
co corporate action.

Publication v2 gom 22 san pham nghiep vu va `manifest.json`, tong cong 23 tep.
Ngoai 16 san pham v1, v2 bo sung `lenh.csv`, `khop_lenh.csv`, `so_cai.csv`,
`vi_the.csv`, `nav.csv` va `su_kien_da_ap_dung.csv`. Manifest ghi tach stock va
benchmark basis, contract/version, count du kien/quan sat, research gate va cac
cam ket khong dung/suy dung high/low.

Auditor `m4_product_audit_v1` la chuong trinh chi doc. Auditor khong import hoac
goi pipeline, trainer, model refit hay backtest engine; khong sua san pham; kiem
tra tap tep, SHA-256, config, fold chronology, purge/embargo, prediction,
ranking/tie-break/top-k, T+1, cash, position, NAV/ledger va reconciliation. Hai
lan audit cung input va cung ma audit phai tao cung byte va SHA-256.

Research gate cua reduced runtime luon `FAIL` va bat buoc co ma
`PRICE_BASIS_UNCONFIRMED`. Dau ra chi la bang chung kiem tra ky thuat; cam dung
lam tin hieu van hanh, khuyen nghi giao dich, ket luan alpha, hieu qua dau tu
hoac kha nang giao dich that.
''',
    "README.md": r'''

## Runtime rut gon Moc 4 cho kiem tra ky thuat

Moc 4 co hai hop dong input tach biet:

- `strict_ohlcv`: mac dinh, giu tuong thich nguoc va tiep tuc yeu cau open/high/low/close/volume;
- `reduced_open_close_volume_v1`: opt-in ro rang, chi dung cho `kiem_tra_ky_thuat`, khong tu nhan dang schema.

Reduced runtime dung `technical_candidate_union_v1`. Day la candidate union
phuc vu kiem tra ky thuat, khong phai universe point-in-time. Ten profile hien
tai la `technical_candidate_union_121`; count phai duoc doc tu profile va
publication manifest, khong hard-code trong runtime chung.

Feature reduced co dung 23 truong, loai duy nhat
`bien_do_cao_thap_chuan_hoa`. High/low khong ton tai trong input reduced, khong
duoc dung hay suy dung va khong co feature thay the. Close duoc dung cho
feature, label, MA250, regime va valuation; `close * volume` cho thanh khoan;
open dung cho phien T+1.

Stock basis va benchmark basis duoc cong bo rieng. Stock reduced la
`CHUA_XAC_NHAN` voi confirmed=false. Benchmark la `close_only`, don vi
`index_points`, confirmed=false. `CHUA_XAC_NHAN` khong dong nghia voi gia dieu
chinh hoac gia khong dieu chinh. M3 engine nhan trang thai nay qua cau hinh typed
va tu choi corporate actions.

Publication v2 co tong 23 tep: 22 san pham nghiep vu va `manifest.json`.
Auditor `m4_product_audit_v1` chi doc, deterministic, khong goi pipeline,
huan luyen hay backtest va khong sua san pham. Auditor doi soat hash, fold,
prediction, ranking, T+1, cash, position, NAV/ledger va reconciliation.

Reduced research gate luon `FAIL` voi `PRICE_BASIS_UNCONFIRMED`. Khong duoc dung
bat ky dau ra nao cua mode nay lam tin hieu van hanh, khuyen nghi giao dich hay
bang chung ve alpha/hieu qua dau tu.
''',
    "tai_lieu/dac_ta_moc_4.md": r'''

## 14. Hop dong runtime rut gon va kiem toan san pham v2

### 14.1 Lua chon hop dong

`strict_ohlcv` giu nguyen contract va hanh vi tuong thich nguoc. Reduced mode
chi duoc chon bang cau hinh ro rang:

```text
price_contract=reduced_open_close_volume_v1
universe_contract=technical_candidate_union_v1
muc_dich_lan_chay=kiem_tra_ky_thuat
```

Khong duoc auto-detect schema. `technical_candidate_union_v1` khong phai
universe PIT. Profile hien tai `technical_candidate_union_121` chi la ten ho so
lan chay; runtime phai doc expected counts tu profile/publication manifest va
doi soat observed counts.

### 14.2 Feature va du lieu gia

Reduced feature order co dung 23 truong. Sai khac duy nhat so voi strict feature
order la loai `bien_do_cao_thap_chuan_hoa`. Cam tao feature thay the. Cam doc,
dung, noi suy, dien, sua hoac tong hop high/low. Close duoc dung cho feature,
label, MA250, market regime va valuation; thanh khoan dung `close * volume`;
execution dung open cua dung phien benchmark T+1. Khong fill-forward, carry hay
gan missing return bang 0.

### 14.3 Price basis va corporate actions

Metadata bat buoc:

```text
stock_price_basis=CHUA_XAC_NHAN
stock_price_basis_confirmed=false
benchmark_contract=close_only
benchmark_unit=index_points
benchmark_price_basis_confirmed=false
stock_benchmark_price_basis_equality_required=false
```

`CHUA_XAC_NHAN` la gia tri contract doc lap, khong phai alias cua
`dieu_chinh` hoac `khong_dieu_chinh`. `mo_phong.co_so_gia` phai giu nguyen gia
tri nay trong reduced publication. Cau hinh M3 phai duoc tao qua
`cau_hinh_mo_phong.tu_mapping`; object ngoai kieu bi tu choi. Corporate actions
khong duoc chuan hoa hoac ap dung khi basis chua xac nhan; engine fail closed.

### 14.4 Publication v2

Publication v2 gom 22 san pham nghiep vu va `manifest.json`, tong 23 tep. Sau
san pham bo sung so voi v1:

```text
lenh.csv
khop_lenh.csv
so_cai.csv
vi_the.csv
nav.csv
su_kien_da_ap_dung.csv
```

Manifest phai ghi version contract, SHA-256/size cua moi san pham, input hashes,
stock/benchmark metadata tach biet, candidate/profile counts du kien va quan
sat, high/low policy, corporate-action policy va research gate.

### 14.5 Auditor v1

`m4_product_audit_v1` chi doc publication da co. Auditor khong duoc import hoac
goi runner, pipeline, trainer, refit hay backtest; khong duoc sua san pham.
Auditor fail closed tren toi thieu: thieu/thua tep, hash/size, config canonical,
fold chronology, purge/embargo, prediction uniqueness/range, ranking order,
tie-break, top-k/weight, exact T+1, cash/position, NAV-ledger va reconciliation.
Destination audit khong duoc ton tai. Hai audit cung input va cung audit ID phai
cho output byte-identical va SHA-256-identical.

### 14.6 Cua dien giai

Reduced research gate luon:

```text
research_gate=FAIL
PRICE_BASIS_UNCONFIRMED
```

Dau ra reduced chi dung de xac minh runtime. Cam dung lam signal van hanh,
khuyen nghi giao dich, ket luan alpha, research validation hoac danh gia hieu
qua dau tu.
''',
    "tai_lieu/kien_truc_moc_4.md": r'''

## 31. Kien truc dual-contract, publication v2 va auditor v1

### 31.1 Bien hop dong

Parser co hai entry path khong giao nhau. `strict_ohlcv` tiep tuc doc schema
OHLCV va universe PIT cu. `reduced_open_close_volume_v1` chi doc publication
reduced khi config opt-in; truyen `--ohlcv`/`--universe` vao reduced path bi tu
choi, va truyen reduced publication vao strict path cung bi tu choi. Khong co
schema sniffing.

Reduced path dung `technical_candidate_union_v1`, mot candidate union khong PIT.
Profile `technical_candidate_union_121` la metadata cua lan chay hien tai, khong
phai constant runtime. Parser doi soat expected symbol/row counts tu profile,
coverage va publication manifest voi observed CSV counts.

### 31.2 Feature graph

Strict graph giu 24 feature. Reduced graph dung cung code close-only cho 23
feature va bo duy nhat node `bien_do_cao_thap_chuan_hoa`. Khong co node thay
the, high/low synthetic, fill-forward hay fallback. Eligibility theo cap
ma-ngay duoc tinh tu bar T, lich su exact-session, MA250/feature, liquidity
`close * volume` va open dung T+1.

### 31.3 Typed price-basis boundary

`cau_hinh_mo_phong` co ba trang thai hop le:

```text
dieu_chinh
khong_dieu_chinh
CHUA_XAC_NHAN
```

Trang thai thu ba khong anh xa sang hai trang thai dau. Reduced adapter tao
`cau_hinh_mo_phong` truc tiep qua validation chinh thuc; khong dung
`SimpleNamespace` hay object duck-typed. Engine kiem tra dung kieu
`cau_hinh_mo_phong` va fail closed neu danh sach corporate action khong rong khi
basis la `CHUA_XAC_NHAN`. Stock basis va benchmark basis di qua hai metadata
channel rieng; khong co equality constraint.

### 31.4 Publication v2

Publisher v2 mo rong 16 product v1 bang sau bang chi tiet backtest:
`lenh.csv`, `khop_lenh.csv`, `so_cai.csv`, `vi_the.csv`, `nav.csv` va
`su_kien_da_ap_dung.csv`. Tong tap publication la 22 product cong
`manifest.json`, tuc 23 tep. Ghi tep theo create-only, fsync, staging cung
filesystem va atomic replace; destination ton tai thi fail closed.

### 31.5 Auditor process boundary

Auditor v1 la module stdlib-only va khong co import dependency den runner,
logistic trainer, adapter backtest hay engine. No doc product bytes va manifest,
kiem tra hash/size va cac invariant ngu nghia, roi ghi mot publication audit moi
ben ngoai thu muc product. Auditor khong thay doi input. Test guard AST/import va
mock call bat buoc fail neu pipeline, trainer hay backtest bi import/goi.

Hai audit cung product va audit ID tao cung JSON, CSV doi soat va `sha256.txt`.
Ma tran am bao gom product set/hash, fold/purge/embargo, prediction, ranking va
tie-break, top-k/weight, exact T+1, cash/position, NAV-ledger, reconciliation,
research gate va existing destination.

### 31.6 Research boundary

Moi reduced publication ghi `research_gate=FAIL` va
`PRICE_BASIS_UNCONFIRMED`. Output khong duoc chuyen thanh operational signal,
trading recommendation, alpha claim hay research conclusion. Strict contract
khong bi thay doi boi bien kien truc reduced nay.
''',
}


def run_git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


class TestWriteM4DocsTemp(unittest.TestCase):
    def test_append_docs_on_target_branch(self) -> None:
        if os.environ.get("GITHUB_ACTIONS") != "true":
            self.skipTest("chi chay tren GitHub Actions")
        if platform.system() != "Linux":
            self.skipTest("chi Ubuntu duoc phep ghi tai lieu")
        if os.environ.get("GITHUB_HEAD_REF") != BRANCH:
            self.skipTest("khong phai PR cua nhanh muc tieu")
        run_git("fetch", "origin", BRANCH)
        with tempfile.TemporaryDirectory() as tmp:
            worktree = Path(tmp) / "docs"
            run_git("worktree", "add", "--detach", str(worktree), "FETCH_HEAD")
            try:
                for path_text, section in SECTIONS.items():
                    path = worktree / path_text
                    original = path.read_text(encoding="utf-8")
                    marker = section.strip().splitlines()[0]
                    if marker not in original:
                        path.write_text(original.rstrip() + section + "\n", encoding="utf-8")
                run_git("config", "user.name", "github-actions[bot]", cwd=worktree)
                run_git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com", cwd=worktree)
                run_git("add", *SECTIONS, cwd=worktree)
                changed = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=worktree).returncode != 0
                if changed:
                    run_git("commit", "-m", "bo sung tai lieu ky thuat runtime rut gon Moc 4", cwd=worktree)
                    run_git("push", "origin", f"HEAD:refs/heads/{BRANCH}", cwd=worktree)
            finally:
                subprocess.run(["git", "worktree", "remove", "--force", str(worktree)], check=False)
        self.assertEqual(set(SECTIONS), {
            "DECISIONS.md", "README.md", "tai_lieu/dac_ta_moc_4.md", "tai_lieu/kien_truc_moc_4.md",
        })


if __name__ == "__main__":
    unittest.main()
