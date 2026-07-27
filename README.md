# vn-quant-system — Moc 4 final clean history

He thong dinh luong co phieu Viet Nam. Moc 4 gom universe point-in-time, coverage, feature, label, walk-forward purge/embargo, momentum baseline, Logistic Regression, ranking, target weights, backtest OOS lien tuc qua engine Moc 3, metric va cong bo 17 tep bat bien.

## Nguon final

- Base: `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`.
- Final source ky thuat: `5aec6ace8423fbf30442aa77db6ff63adb3c854e`.
- CI tham chieu: run #334 `completed/success`.
- Ubuntu Job `89890344314`: success.
- Windows Job `89890344310`: success.
- Python 3.12.13, uv 0.11.32, scikit-learn 1.9.0.
- Tong 320 test discovery.

## Dependency va CI

`[tool.uv]` khoa Linux x86_64 va Windows AMD64. `uv.lock` giu scikit-learn 1.9.0, NumPy 2.3.5, SciPy 1.17.0, joblib 1.5.3, narwhals 2.0.1 va threadpoolctl 3.6.0, voi wheel CPython 3.12 manylinux x86_64 va win_amd64. CI matrix chay `uv lock --check`, frozen sync, compileall va unittest tren Ubuntu 24.04 va Windows Server 2025.

## Durability cong bo

- File fsync ap dung cho 16 san pham va manifest tren Ubuntu/Windows.
- POSIX directory fsync dung `O_DIRECTORY` khi co; loi open/fsync propagate.
- Windows MVP khong goi `os.open` tren directory va tra capability unsupported.
- Atomic replace, same-parent staging, chong ghi de va rollback ap dung tren ca hai nen tang.
- Khong tuyen bo Windows co directory-entry crash durability tuong duong POSIX.

## Gioi han

Tier A/Tier B chua chay. Khong co raw data, normalized data, product hoac log thi truong that trong repository. Metric fixture khong phai bang chung hieu qua chien luoc. Khong LightGBM, SSI, Ready, merge hoac Moc 5 trong vong clean-history.
