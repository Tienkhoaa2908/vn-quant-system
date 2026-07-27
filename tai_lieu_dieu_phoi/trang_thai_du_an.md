# Trạng thái dự án

Cập nhật gần nhất: 2026-07-27

## Kho mã nguồn

- Kho: `Tienkhoaa2908/vn-quant-system`.
- Main hien hanh: `67d09c85a3f3fef855b536172e43966a3269d5ce`.
- PR #16 da merge bang merge commit `67d09c85a3f3fef855b536172e43966a3269d5ce`.
- CI post-merge tren main: workflow `kiem_tra_tu_dong`, run #355, Run ID `30281747970`, `completed/success`.
- PR #13 va PR #14 da dong, khong merge, do PR #16 thay the.
- Mốc 4 da complete; Mốc 5 chua mo.

## Portability công bố Mốc 4

Dependency lock đa nền tảng đã đạt frozen sync trên Ubuntu và Windows. Publication giữ file fsync cho 16 sản phẩm cùng manifest, atomic replace, chống ghi đè và rollback staging.

POSIX/Linux mở directory bằng `O_RDONLY`, thêm `O_DIRECTORY` khi có, fsync descriptor, đóng descriptor trong `finally` và propagate lỗi thật. Windows không gọi `os.open` trên directory và trả capability unsupported; không tuyên bố directory-entry crash durability tương đương POSIX.

Bổ sung test riêng cho file fsync, POSIX error propagation, Windows unsupported capability, publication 17 file, manifest hash, one-shot replace, cùng parent filesystem, rollback, tính tái lập và dọn staging.

## CI kỹ thuật đã phê duyệt

- Source run: #334, `completed/success`.
- Ubuntu Job: `89890344314`, success.
- Windows Job: `89890344310`, success.
- Python `3.12.13`, uv `0.11.32`, scikit-learn `1.9.0`.
- Tổng 320 test được discovery.

## CI clean-history trước correction tài liệu

- PR #14 run #335, Run ID `30241263742`, `completed/success`.
- Ubuntu Job `89898799819`, success.
- Windows Job `89898799861`, success.
- Merge ref đã kiểm tra: `refs/pull/14/merge`.

## Blocker tài liệu và cửa kiểm soát

Commit thứ năm đã rút gọn tài liệu tích lũy. Vòng hiện tại phục hồi đầy đủ nội dung từ commit thứ tư và nối QD-0060/trạng thái final, chỉ trong bảy tệp tài liệu được phê duyệt.

- Code, workflow, dependency và test phải tiếp tục giống source `5aec6ace8423fbf30442aa77db6ff63adb3c854e`.
- Tier A/Tier B chưa chạy; chưa có raw data thật.
- Không thay đổi feature, label, folds, model, ranking, adapter, backtest hoặc dependency version.
- Không LightGBM, SSI, Ready, merge hoặc Mốc 5.

## Cap nhat QD-0061: contract benchmark close-only

PR canonical hien tai la #16 tren nhanh `m4-dac_trung-xep-hang-hoc_may-sach-final-v2`. Giai doan 2A da hoan tat voi `D.OFFICIAL_VALUES_UNAVAILABLE`, `SEMANTICS_DEFINITION_NOT_FOUND` va `CLOSE_ONLY_BENCHMARK_CONTRACT`; cac tham chieu PR #14/CI cu o phan lich su khong phai trang thai current-head. CI #347 chi la baseline cua head cu truoc patch nay.

Co phieu tiep tuc dung `ThanhOHLCV` strict. Benchmark dung `ThanhBenchmarkDongCua` va schema CSV dung sau cot `ma,ngay,gia_dong_cua,nguon,phien_ban,co_so_gia`; open/high/low/volume benchmark khong duoc dua vao canonical input, sua, suy dien hoac dung trong feature/label. Raw KBS va ho so audit run `m4_tier_a_20260727T081753Z_e2c866db` giu bat bien; khong co correction overlay hay replacement values. Manifest/bao cao cong bo `benchmark_contract=close_only`, hai canh bao bat buoc va gioi han chi kiem tra ky thuat. Exact official OHLC van chua co; dieu nay khong xac nhan co so gia co phieu. Normalization, Tier A pipeline, Tier B va Moc 5 chua chay.

## Cap nhat QD-0062: reporting/provenance blocker

Canonical PR la #16 tren nhanh `m4-dac_trung-xep-hang-hoc_may-sach-final-v2`. Head truoc correction la `2efa627c65cb5387bcc4aa77f4063070812d6aa6`; close-only QD-0061 va CI #351 da dat. Giai doan 2A da hoan tat; blocker hien tai chi la generic runner hard-code reporting/provenance khong thuoc kha nang tu xac minh. Correction QD-0062 tach policy khoi runtime fact, khong chay lai Tier A pipeline va khong mo Giai doan 2B, Tier B hay Moc 5.

## Trang thai sau QD-0063

Tier A technical validation cua Moc 4 da complete. Final-documentation commit va CI current-head cua PR #16 la cua cuoi hien tai; khong mo Tier B hay Moc 5 trong vong nay.

### Bang chung Tier A hien hanh

- G2B1 Run ID: `m4_tier_a_exec_20260727T130417Z_27077ed`.
- G2B1 `input_manifest`: `aa3cddbf51f7440a16bd4c7e2d6d29311d8c68fc19475b08e9d69c12ce93fdc4`.
- G2B1 `input_sha256`: `5b74568f6be4639a4b67ffd1ee6f35d61ea6ebc72360f6fae0377dffb10c576c`.
- G2B1 `g2b1_final_artifacts`: `b1e5588c21da002b663cada27a8b06a4bd4d03245ad739fe7c9c20d1bb522c1d`.
- G2B2 Pipeline Run ID: `m4_tier_a_pipeline_20260727T141935Z_27077ed`.
- Product manifest: `363662bfa0d31b4ae1399cca171ef33936935f701254b58a653ab51fde8b1a91`.
- Pipeline verification: `24ab8e49ad4b9bb43301f1818c3b851f93df724b98e8024bc4d7d93d89717633`.
- Pipeline execution provenance: `c09ab566e889c071baae88cd2a6f5cf1ab6bca874fd389a93427256c150b08eb`.
- External final-hash file: `8eeb5b9f407754bdda28154f0d9e5b3b39192a66975c53229dfe38a7492775ff`.

### Ket qua technical validation da khoa

- Pipeline tao dung 17 san pham va chi chay mot lan.
- Tong 36 fold; 34 fold thanh cong.
- `fold_035` that bai voi exact reason `test_rong`.
- `fold_036` that bai voi exact reason `test_rong`.
- 102 Logistic test predictions va 102 momentum test predictions.
- 204 ranking rows va 204 target-weight rows.
- OOS tu `2023-08-31` den `2026-06-26`; metric start `2023-09-05`.
- Toan bo execution duoc doi soat dung T+1.
- NAV reconciliation cua ca hai chien luoc bang `0E-18`.
- External audit khong phat hien leakage sau khi contract verifier duoc sua dung.
- Technical gate khong yeu cau loi nhuan duong.
- Observed technical outputs: Logistic NAV `1339417920.647295`, AUC `0.6051518646674355`, Sharpe `0.5716438544137741`; momentum NAV `1738588942.107435`, AUC `0.5638216070742023`, Sharpe `0.9412394202346132`.

### Lich su external verifier

Pipeline chay dung mot lan. External verifier ban dau tao false blocker `G2B2_NO_LEAKAGE_AUDIT_FAILED`; cac blocker tiep theo nam trong verifier contract, gom gia dinh expanding train phai tang nghiem ngat va target-strategy detection khong khop contract san pham. Verifier duoc sua va chay lai tren cung 17 san pham; pipeline khong chay lai. Byte cua 17 san pham va product manifest khong doi. External verification/provenance artifacts duoc tai tao. Chi bon hash G2B2 canonical hien hanh o tren duoc dung lam bang chung cuoi; hash cua false-blocker state la superseded evidence, khong phai final canonical evidence.

### Gioi han va cach dien giai bat buoc

- Tier A chi la technical validation; khong phai research validation.
- Universe chi gom `FPT/HPG/MBB`, la synthetic technical control; khong phai VN100 point-in-time.
- Calendar duoc lap tu observed VNINDEX bars ket hop official notices; khong phai official exchange export.
- Corporate-action inventory chi partial; corporate actions khong duoc ap dung trong run.
- `price_basis_confirmed=false`; operational mode `gia_dieu_chinh` khong phai empirical confirmation cua price basis.
- Benchmark theo contract close-only; exact official VNINDEX OHLC chua co.
- Khong Tier B; khong research claim; khong ket luan alpha, hieu qua chien luoc, kha nang giao dich that hoac khuyen nghi dau tu.
- Khong LightGBM, SSI hoac Moc 5.
- NAV, AUC va Sharpe neu duoc ghi chi la observed technical outputs; khong duoc mo ta la tot, hieu qua, vuot troi hoac dung de khuyen nghi dau tu.

### Trang thai dieu phoi sau QD-0064

- `MOC_4_COMPLETE`: implementation Moc 4 va Tier A technical validation da hoan tat.
- `PR16_MERGED`: PR #16 da merge bang merge commit `67d09c85a3f3fef855b536172e43966a3269d5ce`.
- `MAIN_CI_355_SUCCESS`: workflow `kiem_tra_tu_dong`, run #355, Run ID `30281747970`, event `push`, branch `main`, `completed/success`.
- Ubuntu Job `90029586084` va Windows Job `90029585961` deu success; artifacts `phien-ban-ci-ubuntu` va `phien-ban-ci-windows` ton tai; uv `0.11.32`, Python `3.12.13`, scikit-learn `1.9.0`.
- `PR13_CLOSED_UNMERGED`: PR #13 da dong, khong merge, do PR #16 thay the.
- `PR14_CLOSED_UNMERGED`: PR #14 da dong, khong merge, do PR #16 thay the.
- Tier A chi la technical validation; universe `FPT/HPG/MBB` la synthetic technical control, khong phai VN100 PIT.
- `price_basis_confirmed=false`; corporate-action inventory van partial; corporate actions khong duoc ap dung trong Tier A.
- Khong research claim; NAV/AUC/Sharpe khong duoc dien giai thanh hieu qua dau tu, alpha, kha nang giao dich that hay khuyen nghi dau tu.
- Tier B chua chay; khong LightGBM, SSI.
- `MOC_5_NOT_OPENED`.
