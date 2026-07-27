# Công việc hiện tại

Cập nhật: 2026-07-27

## Mục tiêu vòng

Sửa `PR14_DOCUMENTATION_REGRESSION_BLOCKER` trên PR #14 bằng một commit nối tiếp, không viết lại lịch sử.

## Nền

- Repository: `Tienkhoaa2908/vn-quant-system`.
- Branch: `m4-dac_trung-xep-hang-hoc_may-sach-final`.
- Head trước sửa: `07bc48075be5e44cd410ff8fc2ef02828fc8fd73`.
- Source kỹ thuật: `5aec6ace8423fbf30442aa77db6ff63adb3c854e`.
- Doc base: `8452cfb8ddc521c80d7f1128acd72039b1fca0eb`.
- PR #14 và PR #13 đều phải giữ Open, Draft, chưa merge.

## Phạm vi

1. Phục hồi nguyên nội dung tích lũy của bảy tài liệu từ commit thứ tư.
2. Giữ toàn bộ QD-0001..QD-0059 và nối QD-0060.
3. Giữ toàn bộ README, CLI, hợp đồng Mốc 0–4 và lịch sử Mốc 0–3.
4. Giữ toàn bộ kiến trúc Mốc 4; chỉ thêm durability đa nền tảng tại phần publication.
5. Giữ lộ trình M0–M6 trong kế hoạch tổng thể; chỉ cập nhật trạng thái M4.
6. Cập nhật PR #14, branch final, run #335 và hai Job ID.
7. Không sửa code, test, workflow, `pyproject.toml` hoặc `uv.lock`.

## Cửa hoàn tất

- Tất cả bảy tài liệu có số dòng không thấp hơn bản tại doc base.
- `DECISIONS.md` chứa QD-0001, QD-0059 và QD-0060.
- Diff ngoài bảy tài liệu so với source kỹ thuật bằng 0.
- CI head mới checkout `refs/pull/14/merge`, đạt lock check, frozen sync, compileall và toàn bộ unittest trên Ubuntu/Windows.

## Cấm hiện hành

Không force-push, rebase, squash hoặc amend; không Tier A/Tier B, dữ liệu thật, Ready, merge, LightGBM hoặc Mốc 5.

## Cap nhat QD-0061: contract benchmark close-only

PR canonical hien tai la #16 tren nhanh `m4-dac_trung-xep-hang-hoc_may-sach-final-v2`. Giai doan 2A da hoan tat voi `D.OFFICIAL_VALUES_UNAVAILABLE`, `SEMANTICS_DEFINITION_NOT_FOUND` va `CLOSE_ONLY_BENCHMARK_CONTRACT`; cac tham chieu PR #14/CI cu o phan lich su khong phai trang thai current-head. CI #347 chi la baseline cua head cu truoc patch nay.

Co phieu tiep tuc dung `ThanhOHLCV` strict. Benchmark dung `ThanhBenchmarkDongCua` va schema CSV dung sau cot `ma,ngay,gia_dong_cua,nguon,phien_ban,co_so_gia`; open/high/low/volume benchmark khong duoc dua vao canonical input, sua, suy dien hoac dung trong feature/label. Raw KBS va ho so audit run `m4_tier_a_20260727T081753Z_e2c866db` giu bat bien; khong co correction overlay hay replacement values. Manifest/bao cao cong bo `benchmark_contract=close_only`, hai canh bao bat buoc va gioi han chi kiem tra ky thuat. Exact official OHLC van chua co; dieu nay khong xac nhan co so gia co phieu. Normalization, Tier A pipeline, Tier B va Moc 5 chua chay.

## Cap nhat QD-0062: reporting/provenance blocker

Canonical PR la #16 tren nhanh `m4-dac_trung-xep-hang-hoc_may-sach-final-v2`. Head truoc correction la `2efa627c65cb5387bcc4aa77f4063070812d6aa6`; close-only QD-0061 va CI #351 da dat. Giai doan 2A da hoan tat; blocker hien tai chi la generic runner hard-code reporting/provenance khong thuoc kha nang tu xac minh. Correction QD-0062 tach policy khoi runtime fact, khong chay lai Tier A pipeline va khong mo Giai doan 2B, Tier B hay Moc 5.

## Cong viec hien tai sau QD-0063

Cong viec duy nhat trong vong nay la khoa tai lieu, push mot final-documentation commit va xac minh CI moi tren `refs/pull/16/merge`. Khong chay lai raw acquisition, G2B1, G2B2, pipeline hoac test du lieu that.

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
