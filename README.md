# vn-quant-system

He thong dinh luong co phieu Viet Nam. Moc 0–3 da dong; Moc 4 dang duoc trien khai va ra soat tren PR #10 o trang thai Draft.

## Pham vi hien tai

- Moc 1: thu thap OHLCV ngay, du lieu tho bat bien, chuan hoa, kiem tra chat luong va SHA-256.
- Moc 2: tap co phieu point-in-time, thanh khoan, MA250 va dong luong khong nhin truoc.
- Moc 3: mo phong giao dich long-only, lenh DAY, T/T+1, tien mat, vi the, corporate actions MVP, so cai, NAV, chi so va dau ra bat bien.
- Moc 4: universe point-in-time, feature va nhan monthly, walk-forward purge/embargo, momentum baseline, Logistic Regression, ranking, metric ngoai mau va adapter sang engine Moc 3.

Ngoai pham vi Moc 4: LightGBM, deep learning, inverse volatility san xuat, tran 15% moi ma/25% moi nganh, ket noi SSI, doc tai khoan va gui lenh.

## Moc 4 — fixture ngoai tuyen

Ma nam trong:

```text
src/he_thong_dinh_luong/nghien_cuu_moc_4/
```

Cac module tach rieng hop dong/cau hinh, universe, coverage, feature, nhan, walk-forward, tien xu ly, baseline, Logistic Regression, ranking, adapter Moc 3, metric, cong bo va CLI.

### Bat bien du lieu va mau

- Cutoff point-in-time: `thoi_diem_cong_bo <= thoi_diem_tao_tin_hieu`; hai timestamp phai co mui gio.
- Mau model chi sinh tai phien benchmark cuoi thang.
- Feature chi dung quan sat tai hoac truoc T; them du lieu sau T khong duoc thay doi feature tai T.
- T+H la phien thu H sau T tren lich benchmark, khong phai bar thu H con ton tai cua tung ma.
- Thieu stock hoac benchmark tai dung T/T+H thi nhan rong; khong forward-fill va khong tim phien xa hon.

### Walk-forward va model

- Expanding window, tai huan luyen hang thang, test mot thang va khong chong lan.
- Purge train–validation toi thieu bang label horizon; embargo validation–test theo lich benchmark.
- Mau train/validation/refit chi duoc dung khi `ngay_ket_thuc_nhan` khong sau cutoff cua tap.
- C chi duoc chon bang validation log loss; hoa chon C nho hon; test khong chon tham so.
- Refit tren train+validation hop le truoc test.
- Train/refit mot lop hoac ConvergenceWarning khong xu ly duoc lam fold fail closed va khong tao prediction test.

Dependency ML duoc khoa:

```text
scikit-learn==1.9.0
```

Pipeline:

```text
StandardScaler(with_mean=True, with_std=True)
LogisticRegression(
  penalty="l2",
  solver="lbfgs",
  max_iter=1000,
  class_weight=None,
  C=<selected>,
  random_state=20260725
)
```

Khong co pandas hoac LightGBM.

### Ranking, OOS va cong bo

- Probability giam dan, tie-break ma tang dan, chon `top_k`.
- Moi ma duoc chon co ty trong `1/top_k`; phan thieu la tien mat.
- Chi prediction `test` vao metric cuoi, target weights va backtest.
- Target weights test duoc ghep theo thoi gian thanh mot backtest OOS lien tuc; von chi khoi tao mot lan.
- Adapter tai su dung engine Moc 3 de khop open dung T+1.
- Cong bo 17 tep bang staging, fsync, rename nguyen tu, rollback va SHA-256; khong ghi de.

CLI hien tai chi xac thuc cau hinh fixture ngoai tuyen:

```bash
PYTHONPATH=src uv run --python 3.12 \
  python -m he_thong_dinh_luong.nghien_cuu_moc_4 \
  --kiem-tra-cau-hinh duong_dan/cau_hinh.json
```

## Moc 3 — giao dien engine

### Ty trong muc tieu

```text
ngay_tin_hieu,ma,ty_trong_muc_tieu,ten_chien_luoc
```

Ty trong moi ma trong `[0,1]`, tong tai mot ngay khong vuot `1`; phan con lai la tien mat. Tin hieu close T chi khop tai open dung phien thi truong ke tiep. Lenh DAY het han neu thieu bar/open; engine khong tim phien xa hon va khong thay open bang close.

### Cau hinh mo phong

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

Cac gia tri chi minh hoa giao dien, khong phai cau hinh san xuat. Chi tiet engine, corporate actions, so cai, P&L, metric va chin san pham: `tai_lieu/kien_truc_moc_3.md`.

## Kiem thu ngoai tuyen

```bash
uv sync --frozen --python 3.12
PYTHONPATH=src uv run --python 3.12 python -m compileall -q src tests
PYTHONPATH=src uv run --python 3.12 \
  python -m unittest discover -s tests -p 'test_*.py' -v
```

Moc 4 bo sung 97 test theo loi nghiep vu; 121 test hoi quy Moc 0–3 tiep tuc duoc chay. CI khong goi Vnstock va khong tai du lieu thi truong.

## Xac minh du lieu that va cua kiem soat

- Lan xac minh FPT, HPG, MBB cua Moc 3 chi xac minh ky thuat engine; khong la danh gia chien luoc.
- Moc 4 chua chay Tier A/Tier B, chua tai VN100/VNINDEX that va chua cong bo ket qua hieu qua.
- Chua co lich su VN100 point-in-time that duoc phe duyet.
- Co so gia va corporate actions that chua duoc xac nhan day du.
- Khong commit du lieu thi truong, san pham that, log that, khoa hoac token.
- PR #10 phai giu Draft; khong Ready, khong tu gop va khong mo Moc 5.
