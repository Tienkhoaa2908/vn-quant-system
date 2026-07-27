# Kế hoạch tổng thể

## Mốc 0 — Nền tảng và kiểm tra dữ liệu

Trạng thái: **đã hoàn thành và đã gộp**.

## Mốc 1 — Dữ liệu thị trường thật

Trạng thái: **đã hoàn thành và đã đóng hoàn toàn**.

- Vnstock Community 4.0.4/KBS.
- JSON thô bất biến, SHA-256, chuẩn hóa, chất lượng và CSV sẵn sàng.
- FPT, HPG, MBB được xác minh cục bộ; không commit dữ liệu thật.

## Mốc 2 — Tập cổ phiếu và đường cơ sở

Trạng thái: **đã hoàn thành và đã đóng hoàn toàn**.

- Tập cổ phiếu point-in-time, thanh khoản, MA250 và động lượng.
- Không dùng ảnh chụp tương lai; đầu ra CSV/JSON ổn định.
- Merge commit: `6e8d2ed49c2ef57e43c9f0f2249361b26b838b33`.

## Mốc 3 — Mô phỏng giao dịch và backtest

Trạng thái: **đã hoàn thành và đã đóng hoàn toàn**.

- PR triển khai số 7, merge commit `79a044d75f3a66e5c636f0a83613fc9af0cac3fc`.
- PR điều phối số 8, merge commit `bb25ff16761b7c79e701fbd4f3a5af02f1644e07`.
- CI cuối trên `main`: run `#185`, Run ID `30151712433`, Job ID `89663090052`, `completed/success`.
- Engine T/T+1, lệnh DAY, phí, thuế, trượt giá, lot size, tiền mặt, vị thế, sổ cái, NAV và corporate actions MVP.
- 121 kiểm thử ngoại tuyến.
- Xác minh kỹ thuật trên FPT, HPG, MBB; không dùng kết quả làm bằng chứng hiệu quả đầu tư.

## Mốc 4 — Dữ liệu nhiều năm, đặc trưng, xếp hạng và học máy cơ sở

Trạng thái: **final tree kỹ thuật đã được đoạn 00 phê duyệt; PR clean-history #14 đang Draft và sửa blocker tài liệu tích lũy**.

- Đặc tả: `tai_lieu/dac_ta_moc_4.md`.
- PR đặc tả số 9 đã gộp bằng merge commit `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`.
- CI sau gộp trên `main`:
  - workflow `kiem_tra_tu_dong`;
  - run `#187`;
  - Run ID `30162993192`;
  - Job ID `89691237408`;
  - trigger `push`;
  - checkout `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`;
  - `completed/success`.
- Source kỹ thuật cuối: `5aec6ace8423fbf30442aa77db6ff63adb3c854e`.
- Branch clean-history: `m4-dac_trung-xep-hang-hoc_may-sach-final`.
- PR chính thức: #14, Open, Draft, chưa merge.
- PR nguồn #13 tiếp tục Open, Draft, chưa merge.
- CI source run #334: Ubuntu Job `89890344314`, Windows Job `89890344310`, success.
- CI PR #14 trước correction tài liệu: run #335, Run ID `30241263742`, Ubuntu Job `89898799819`, Windows Job `89898799861`, success.
- Lock đa nền tảng Linux x86_64/Windows AMD64; Python 3.12.13, uv 0.11.32, scikit-learn 1.9.0.
- Publication theo capability: file fsync hai nền tảng; directory fsync POSIX; Windows unsupported; atomic replace và rollback giữ nguyên.
- 320 test discovery.
- Tier A/Tier B chưa chạy; không có dữ liệu thật trong repository.

Phạm vi đã phê duyệt:

- VN100 point-in-time hoặc universe thanh khoản cao point-in-time được phê duyệt;
- dữ liệu nhiều năm, mục tiêu ít nhất 5 năm và ưu tiên 7–10 năm khi chất lượng cho phép;
- kiểm soát survivorship bias, look-ahead, mã mới niêm yết và warm-up MA250;
- feature giá, xu hướng, động lượng, biến động, thanh khoản và market regime;
- nhãn lợi nhuận tương đối 20 phiên;
- walk-forward có purge/embargo;
- baseline momentum và Logistic Regression;
- ranking, `top_k` và backtest ngoài mẫu qua engine Mốc 3;
- LightGBM chỉ sau quyết định riêng.

Mã Mốc 4 chỉ được triển khai trên nhánh chuyên môn và PR phải giữ Draft đến khi đoạn 00 phê duyệt. Vòng hiện tại chỉ sửa tài liệu tích lũy; không Ready, merge hoặc chạy Tier A.

## Mốc 5 — Chia vốn

Trạng thái: **chưa mở**.

- Inverse volatility.
- Tối đa 15% mỗi mã, 25% mỗi ngành.
- Tiền mặt theo market regime.

## Mốc 6 — Kiểm toán và giao dịch giả lập

Trạng thái: **chưa mở**.

- Rà soát rò rỉ dữ liệu, thiên lệch sống sót và tối ưu quá mức.
- Paper trading hằng ngày, chỉ sinh lệnh đề xuất để người dùng tự đặt trên SSI.

## Cap nhat QD-0061: contract benchmark close-only

PR canonical hien tai la #16 tren nhanh `m4-dac_trung-xep-hang-hoc_may-sach-final-v2`. Giai doan 2A da hoan tat voi `D.OFFICIAL_VALUES_UNAVAILABLE`, `SEMANTICS_DEFINITION_NOT_FOUND` va `CLOSE_ONLY_BENCHMARK_CONTRACT`; cac tham chieu PR #14/CI cu o phan lich su khong phai trang thai current-head. CI #347 chi la baseline cua head cu truoc patch nay.

Co phieu tiep tuc dung `ThanhOHLCV` strict. Benchmark dung `ThanhBenchmarkDongCua` va schema CSV dung sau cot `ma,ngay,gia_dong_cua,nguon,phien_ban,co_so_gia`; open/high/low/volume benchmark khong duoc dua vao canonical input, sua, suy dien hoac dung trong feature/label. Raw KBS va ho so audit run `m4_tier_a_20260727T081753Z_e2c866db` giu bat bien; khong co correction overlay hay replacement values. Manifest/bao cao cong bo `benchmark_contract=close_only`, hai canh bao bat buoc va gioi han chi kiem tra ky thuat. Exact official OHLC van chua co; dieu nay khong xac nhan co so gia co phieu. Normalization, Tier A pipeline, Tier B va Moc 5 chua chay.

## Cap nhat QD-0062: reporting/provenance blocker

Canonical PR la #16 tren nhanh `m4-dac_trung-xep-hang-hoc_may-sach-final-v2`. Head truoc correction la `2efa627c65cb5387bcc4aa77f4063070812d6aa6`; close-only QD-0061 va CI #351 da dat. Giai doan 2A da hoan tat; blocker hien tai chi la generic runner hard-code reporting/provenance khong thuoc kha nang tu xac minh. Correction QD-0062 tach policy khoi runtime fact, khong chay lai Tier A pipeline va khong mo Giai doan 2B, Tier B hay Moc 5.

## Moc kiem soat QD-0063 trong ke hoach tong the

Tier A technical validation complete la diem dung truoc PR finalization. Ke hoach tiep theo chi duoc thay doi sau khi CI current-head cua PR #16 dat; PR #13/#14 van Open/Draft trong luc cho xac minh.

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

### Trang thai dieu phoi

- PR canonical: `#16`.
- Branch canonical: `m4-dac_trung-xep-hang-hoc_may-sach-final-v2`.
- Head truoc final-documentation commit: `27077ed1066b0c5813d9bb5276a6c618633fe345`.
- CI `#353`, Run ID `30264618547`, la current-head baseline truoc final-documentation commit; sau push no khong con la current-head evidence.
- Tier A technical validation complete; buoc hien tai la final documentation va current-head CI.
- PR #13 va PR #14 tiep tuc Open/Draft cho toi khi CI cuoi cua PR #16 duoc xac minh.
- PR #16 tiep tuc Open/Draft, chua Ready va chua merge.
- Tier B va Moc 5 chua mo.
