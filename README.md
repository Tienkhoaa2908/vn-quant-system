# vn-quant-system

He thong dinh luong co phieu Viet Nam. Moc 0–3 da dong; Moc 4 dang duoc trien khai va ra soat tren PR so 10 o trang thai Draft.

## Pham vi hien tai

- Moc 1: thu thap OHLCV ngay qua Vnstock Community 4.0.4/KBS, du lieu tho bat bien, chuan hoa, chat luong va SHA-256.
- Moc 2: tap co phieu point-in-time, thanh khoan, MA250 va dong luong khong nhin truoc.
- Moc 3: mo phong giao dich long-only, lenh DAY, tien mat, vi the, corporate actions MVP, so cai, NAV, chi so va dau ra bat bien.
- Moc 4: universe point-in-time, feature va nhan monthly, walk-forward purge/embargo, momentum baseline, Logistic Regression, ranking, metric ngoai mau va adapter sang engine Moc 3.

Khong thuoc Moc 4: LightGBM, deep learning, inverse volatility san xuat, tran 15% moi ma/25% moi nganh, ket noi SSI, doc tai khoan hay gui lenh.

## Moc 4 — pipeline dau-cuoi bang fixture ngoai tuyen

Ma nam trong:

```text
src/he_thong_dinh_luong/nghien_cuu_moc_4/
```

Ham dieu phoi chinh:

```python
chay_nghien_cuu_moc_4(...)
```

Luồng runner chi doc tep cuc bo:

```text
cau hinh va dau vao
→ PIT universe/benchmark metadata/corporate actions
→ coverage
→ feature cuoi thang theo lich benchmark chinh thuc
→ nhan T+H
→ samples va walk-forward folds
→ momentum baseline va Logistic Regression
→ prediction test, ranking va target weights
→ hai backtest OOS lien tuc qua engine Moc 3
→ model/ranking/backtest metrics
→ 16 san pham + manifest
→ cong bo nguyen tu
```

Bat bien chinh:

- Cutoff PIT: `thoi_diem_cong_bo <= thoi_diem_tao_tin_hieu`; timestamp phai co mui gio.
- Lich benchmark duoc truyen rieng. Moi cua so va endpoint `T-N` dung dung phien benchmark; khong nen thoi gian, forward-fill, tim phien thay the hoac lay bar cu de bu.
- Thieu bat ky bar bat buoc trong MA, momentum, volatility, liquidity hay regime thi feature tuong ung rong; dong thieu feature bat buoc bi loai va ghi coverage.
- T+H la phien thu H sau T tren lich benchmark; thieu stock/benchmark dung T/T+H thi nhan rong.
- Expanding monthly walk-forward co purge/embargo; chi prediction test vao metric cuoi va backtest.
- Dependency khoa `scikit-learn==1.9.0`; khong pandas, khong LightGBM.
- Momentum baseline va Logistic Regression dung cung test dates, universe, eligibility, top_k, chi phi va engine.
- Adapter bat buoc `che_do_ma_khong_xuat_hien=muc_tieu_bang_0`, phat target 0 cho ma roi top_k va bieu dien ngay tai can bang rong de ve tien mat.
- Manifest tu tinh SHA-256 tung dau vao va tung san pham; metadata version/cau hinh/canh bao/gioi han la bat buoc.
- NaN/Inf bi tu choi trong dau vao, feature, probability, relative return, metric va san pham.
- Cong bo 17 tep bang staging, fsync, rename nguyen tu va rollback.

CLI chay dau-cuoi:

```bash
PYTHONPATH=src uv run --python 3.12 \
  python -m he_thong_dinh_luong.nghien_cuu_moc_4 \
  --cau-hinh duong_dan/cau_hinh.json \
  --ohlcv duong_dan/ohlcv.csv \
  --benchmark duong_dan/benchmark.csv \
  --lich-benchmark duong_dan/lich_benchmark.csv \
  --universe duong_dan/universe.csv \
  --corporate-actions duong_dan/corporate_actions_metadata.csv \
  --thu-muc-dau-ra duong_dan/ket_qua \
  --ma-lan-chay ma_lan_chay_duy_nhat \
  --git-commit <SHA-40-ky-tu>
```

Che do chi xac thuc cau hinh van duoc giu:

```bash
PYTHONPATH=src uv run --python 3.12 \
  python -m he_thong_dinh_luong.nghien_cuu_moc_4 \
  --kiem-tra-cau-hinh duong_dan/cau_hinh.json
```

Suite hien co 146 test Mốc 4 va 121 test hoi quy Mốc 0–3, tong 267 test ngoai tuyen. Kich ban vang chay runner hai lan byte-for-byte va chay CLI tren fixture; khong goi mang.

Chua chay Tier A/Tier B, chua tai VN100/VNINDEX that, nguon that chua duoc phe duyet va khong duoc dien giai metric fixture nhu hieu qua chien luoc.

## Dau vao Moc 3

### Duong co so va gia

CSV toi thieu:

```text
ma,ngay,gia_mo_cua,gia_dong_cua,thuoc_tap_co_phieu,dat_thanh_khoan
```

`thuoc_tap_co_phieu` va `dat_thanh_khoan` fail closed: chi `true/true` moi cho phep mo hoac tang vi the. `false` hoac rong deu khong dat. Giam va dong vi the van duoc phep, kem canh bao.

### Ty trong muc tieu

```text
ngay_tin_hieu,ma,ty_trong_muc_tieu,ten_chien_luoc
```

Ty trong moi ma nam trong `[0,1]`; tong tai mot ngay khong vuot `1`. Phan con lai la tien mat. Che do ma khong xuat hien phai khai bao la `giu_nguyen` hoac `muc_tieu_bang_0`.

### Cau hinh

```json
{
  "von_ban_dau": "1000000000",
  "phi_mua_bps": "15",
  "phi_ban_bps": "15",
  "thue_ban_bps": "100",
  "truot_gia_bps": "10",
  "kich_thuoc_lo": 100,
  "so_phien_moi_nam": 252,
  "lai_suat_phi_rui_ro": "0",
  "che_do_ma_khong_xuat_hien": "muc_tieu_bang_0",
  "cho_phep_ban_le_khi_dong_vi_the": false,
  "co_so_gia": "khong_dieu_chinh",
  "don_vi_gia": "dong",
  "don_vi_tien": "dong"
}
```

Cac gia tri tren chi minh hoa giao dien, khong phai cau hinh san xuat. `don_vi_gia` va `don_vi_tien` phai cung la `dong` hoac cung la `nghin_dong`; khong duoc tron gia nghin dong voi von bang dong.

Validation chinh:

- `0 <= truot_gia_bps < 10000`;
- `phi_ban_bps + thue_ban_bps <= 10000`;
- `kich_thuoc_lo` va `so_phien_moi_nam` la so nguyen thuc su va duong, khong ep float thanh int;
- gia khop va gia tri giao dich phai duong;
- tien ban rong khong am.

### Corporate actions

CSV:

```text
ma,loai_su_kien,ngay_hieu_luc,ngay_thanh_toan,ty_le,gia_tri_tien_mat,nguon,phien_ban
```

MVP ho tro `chia_tach`, `co_phieu_thuong`, `chia_tach_hoac_thuong_co_phieu` va `co_tuc_tien_mat`.

Voi co tuc tien mat, `ngay_hieu_luc`, `ngay_thanh_toan`, `gia_tri_tien_mat` va `nguon` deu bat buoc. Engine chot so luong duoc huong tai ngay hieu luc, luu nghia vu, va chi cong tien tai ngay thanh toan. Mua hoac ban sau ngay chot quyen khong thay doi quyen. Su kien trung lap va gia da dieu chinh kem corporate actions bi tu choi.

## Quy tac giao dich

- Tin hieu duoc tao sau close `T`; lenh chi khop tai open cua dung phien thi truong ke tiep.
- Mua: `gia_khop = open * (1 + truot_gia_bps/10000)`.
- Ban: `gia_khop = open * (1 - truot_gia_bps/10000)`.
- Lenh DAY het han neu thieu bar/open tai ngay thuc thi; khong tim phien xa hon va khong thay open bang close.
- Ban chay truoc mua; trong moi chieu sap xep ma tang dan.
- Nhu cau muc tieu va khoi luong co the thuc thi duoc ghi rieng.
- Sau ban, engine tinh tien mat kha dung, gia khop, phi, slippage va lot size de giam khoi luong mua toi muc toi da hop le.
- Viec giam khoi luong truoc khi gui khop la pre-trade sizing, khong phai market partial fill.
- `lenh.csv` va `khop_lenh.csv` ghi khoi luong yeu cau, chap nhan, bi giam va ly do.
- Khong short, margin, tien mat am, ban vuot vi the hoac vi the am.

## Quy uoc so cai

- Gia von binh quan gom gia khop da co slippage, khong gom phi mua.
- Realized P&L: `(gia_khop_ban - gia_von_binh_quan) * so_luong_ban`, truoc phi ban va thue.
- Unrealized P&L: `(close - gia_von_binh_quan) * so_luong_con_lai`.
- So cai tach `phi_mua`, `phi_ban`, `thue_ban`, `chi_phi_truot_gia`, `co_tuc_tien_mat`, realized va unrealized P&L.
- Slippage da nam trong gia khop, nen khong bi tru lan hai trong doi soat.

Doi soat cuoi moi phien:

```text
NAV
= von_ban_dau
+ realized_P&L_luy_ke
+ unrealized_P&L
+ co_tuc_luy_ke
- phi_mua_luy_ke
- phi_ban_luy_ke
- thue_ban_luy_ke
```

## Chay CLI Moc 3

```bash
PYTHONPATH=src uv run --python 3.12 \
  python -m he_thong_dinh_luong.mo_phong \
  --duong_co_so du_lieu/duong_co_so.csv \
  --ty_trong_muc_tieu du_lieu/ty_trong_muc_tieu.csv \
  --cau_hinh du_lieu/cau_hinh_moc_3.json \
  --su_kien_doanh_nghiep du_lieu/su_kien.csv \
  --thu_muc_dau_ra du_lieu/backtest/<ma_lan_chay_moi>
```

`--su_kien_doanh_nghiep` la tuy chon. Thu muc dau ra khong duoc ton tai truoc lan chay. Loi do CLI kiem soat duoc lam sach dong nhat trong stdout va `bao_cao_loi.json`; token, secret, password, API key va Bearer credential khong duoc lo.

## San pham Moc 3

Mot lan chay thanh cong tao dung chin tep:

```text
cau_hinh.json
lenh.csv
khop_lenh.csv
vi_the.csv
so_cai.csv
nav.csv
chi_so.json
bao_cao.json
manifest.json
```

`don_vi_gia` va `don_vi_tien` xuat hien trong `cau_hinh.json`, `bao_cao.json` va `manifest.json`. San pham duoc chuan bi trong thu muc tam, fsync va rename nguyen tu. Khong ghi de; thu muc thanh cong va that bai khong tron.

## Chi so

Bao gom tong loi nhuan, CAGR khi du dieu kien, maximum drawdown, Sharpe, turnover, tong mua/ban, phi mua/ban, thue ban, slippage, realized/unrealized P&L, co tuc va chenh lech doi soat. Sharpe tra `null` khi thieu quan sat hoac phuong sai loi nhuan bang 0.

Chi tiet: `tai_lieu/kien_truc_moc_3.md`.

## Kiem thu ngoai tuyen

```bash
uv sync --frozen --python 3.12
PYTHONPATH=src uv run --python 3.12 python -m compileall -q src tests
PYTHONPATH=src uv run --python 3.12 \
  python -m unittest discover -s tests -p 'test_*.py' -v
```

Bo kiem thu Moc 4 tach rieng theo loi nghiep vu va giu toan bo 121 test Moc 0–3. CI khong goi mang va khong goi Vnstock.

## Xac minh ky thuat tren du lieu that

Lan chay `xac_minh_fpt_hpg_mbb_20260725T074736Z` da xac minh engine Moc 3 tren FPT, HPG va MBB voi 287 phien moi ma, tong 861 dong sau khi ghep gia Moc 1 voi trang thai Moc 2. Engine tao 287 dong NAV, 287 dong so cai, 6/6 lenh khop, khong co lenh het han/tu choi, dong het ba vi the, tien mat khong am, doi soat bang `0.0000000`, tao dung 9 san pham va xac minh SHA-256 manifest.

Ket qua chi la xac minh ky thuat. Ty trong 30% moi ma la kich ban kiem tra; lan chay khong dung baseline MA250-dong-luong, khong co corporate actions that, va khong duoc dien giai loi nhuan am hay duong nhu danh gia chien luoc.

So lieu, phuong phap va gioi han: `tai_lieu/ket_qua_xac_minh_that_moc_3.md`.

## Nguyen tac va cua kiem soat

- GitHub la nguon su that ve nhanh, commit, PR va CI.
- Khong dung du lieu tuong lai va khong tu dien gia/phien/thanh vien thieu.
- Khong commit du lieu thi truong that, san pham backtest, log that, khoa hay token.
- Snapshot membership chua phai lich su thanh vien that; nguong thanh khoan chua phai cau hinh san xuat.
- Co so gia `khong_dieu_chinh` chua duoc nguon xac nhan doc lap.
- Baseline chi kiem tra engine, khong phai chien luoc san xuat.
- Moc 4 chua chay du lieu that; chua co LightGBM, chia von san xuat hay SSI.
- PR so 10 phai giu Draft; khong Ready, khong gop va khong mo Moc 5.
