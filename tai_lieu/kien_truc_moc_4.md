# Kien truc Moc 4 — final

## Pham vi

Moc 4 trien khai pipeline nghien cuu ngoai mau tren OHLCV ngay: universe point-in-time, coverage, feature, label, walk-forward purge/embargo, momentum baseline, Logistic Regression, ranking, target weights, adapter sang engine Moc 3, backtest OOS lien tuc, metric va cong bo san pham bat bien.

Final source ky thuat: `5aec6ace8423fbf30442aa77db6ff63adb3c854e`.
Base: `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`.

Khong thuoc pham vi: LightGBM, deep learning, Tier B, SSI, gui lenh, chia von san xuat va Moc 5.

## Cua point-in-time va fail closed

Moi universe record, benchmark metadata va corporate action chi duoc dung khi timestamp cong bo co mui gio va khong sau cutoff tin hieu. Eligibility tai T la phep AND cua membership PIT, thanh khoan PIT, warm-up, feature bat buoc, chat luong du lieu, benchmark metadata PIT va open dung T+1.

Khong forward-fill, khong tim phien thay the, khong dung du lieu sau cutoff. Fold test rong hoac khong co prediction test bi fail closed. Research mode khong duoc cong bo thanh cong rong.

## OOS va model audit

Backtest khoa `oos_start`, `ngay_bat_dau_metric`, `oos_end`; warm-up/train khong vao metric. Von khoi tao mot lan va chuoi OOS lien tuc. Model audit tach `validation_selection` va `final_refit`, luu scaler, C, coefficient, intercept, convergence, warning, feature order, cutoff va version scikit-learn.

Dependency khoa `scikit-learn==1.9.0`; lock ho tro Linux x86_64 va Windows AMD64.

## Cong bo 17 tep

Cong bo tao 16 san pham va `manifest.json` trong staging cung parent filesystem voi destination. Moi file duoc mo bang mode tao moi, ghi, `flush()` va file fsync. Manifest cung duoc flush va file fsync. Sau do publication dung mot `os.replace(staging, destination)`, tu choi destination ton tai va rollback staging neu co loi.

### Durability theo capability nen tang

- `file_fsync`: ap dung cho 16 san pham va manifest tren Ubuntu va Windows.
- POSIX/Linux `directory_fsync`: `_fsync_dir` dung `O_RDONLY`, them `O_DIRECTORY` khi co, fsync descriptor, dong descriptor trong `finally`; loi open/fsync phai propagate.
- Windows MVP `directory_fsync`: unsupported trong implementation Python; `_fsync_dir` khong goi `os.open` tren directory va tra `False`.
- `atomic_replace`, same-parent staging, chong ghi de va rollback: ap dung tren ca hai nen tang.

Khong tuyen bo Windows co directory-entry crash durability tuong duong POSIX.

## Kiem thu va CI

Final source co 320 test duoc discovery, gom suite nen 308 test va 12 test portability. CI run #334 da thanh cong tren:

- Ubuntu Job `89890344314`;
- Windows Server 2025 Job `89890344310`.

Ca hai dung Python 3.12.13, uv 0.11.32, scikit-learn 1.9.0, `uv lock --check`, frozen sync, compileall va unittest ngoai tuyen.

## Gioi han du lieu that

Tier A/Tier B chua chay. Khong co raw data, normalized data, product hoac log thi truong that trong repository. Metric fixture va metric ky thuat khong phai bang chung hieu qua chien luoc.
