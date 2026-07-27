# Công việc hiện tại

Cập nhật: 2026-07-27

## Mục tiêu vòng

Tao PR dieu phoi hau Moc 4 de ghi nhan PR #16 da merge bang merge commit `67d09c85a3f3fef855b536172e43966a3269d5ce` va CI post-merge main #355 da dat.

## Nền

- Repository: `Tienkhoaa2908/vn-quant-system`.
- Main bat buoc: `67d09c85a3f3fef855b536172e43966a3269d5ce`.
- PR #16: merged bang merge commit `67d09c85a3f3fef855b536172e43966a3269d5ce`.
- CI main: workflow `kiem_tra_tu_dong`, run #355, Run ID `30281747970`, Ubuntu Job `90029586084`, Windows Job `90029585961`, completed/success.
- PR #13 va PR #14: closed, unmerged, da duoc PR #16 thay the.

## Phạm vi

1. Noi QD-0064 vao `DECISIONS.md`.
2. Cap nhat dung bon tai lieu dieu phoi con lai ve current state sau merge.
3. Chi thay doi dung nam tai lieu duoc phep.
4. Khong sua code, test, workflow, README, dac ta/kien truc Moc 4, dependency hoac lockfile.
5. Khong chay lai Tier A, du lieu that hoac pipeline.
6. Khong mo Tier B, LightGBM, SSI hoac Moc 5.

## Cửa hoàn tất

- Diff chi co dung nam tai lieu duoc phep.
- QD-0063 va QD-0064 cung ton tai.
- Diff ky thuat so voi `67d09c85a3f3fef855b536172e43966a3269d5ce` bang 0.
- Mot commit duy nhat `chot Moc 4 sau merge va CI main`.
- PR moi Open, Draft, chua merge.

## Cấm hiện hành

Khong force-push, amend, squash hoac merge PR moi. Khong research claim; khong dien giai NAV/AUC/Sharpe thanh hieu qua dau tu.

## Cap nhat QD-0061: contract benchmark close-only

PR canonical hien tai la #16 tren nhanh `m4-dac_trung-xep-hang-hoc_may-sach-final-v2`. Giai doan 2A da hoan tat voi `D.OFFICIAL_VALUES_UNAVAILABLE`, `SEMANTICS_DEFINITION_NOT_FOUND` va `CLOSE_ONLY_BENCHMARK_CONTRACT`; cac tham chieu PR #14/CI cu o phan lich su khong phai trang thai current-head. CI #347 chi la baseline cua head cu truoc patch nay.

Co phieu tiep tuc dung `ThanhOHLCV` strict. Benchmark dung `ThanhBenchmarkDongCua` va schema CSV dung sau cot `ma,ngay,gia_dong_cua,nguon,phien_ban,co_so_gia`; open/high/low/volume benchmark khong duoc dua vao canonical input, sua, suy dien hoac dung trong feature/label. Raw KBS va ho so audit run `m4_tier_a_20260727T081753Z_e2c866db` giu bat bien; khong co correction overlay hay replacement values. Manifest/bao cao cong bo `benchmark_contract=close_only`, hai canh bao bat buoc va gioi han chi kiem tra ky thuat. Exact official OHLC van chua co; dieu nay khong xac nhan co so gia co phieu. Normalization, Tier A pipeline, Tier B va Moc 5 chua chay.

## Cap nhat QD-0062: reporting/provenance blocker

Canonical PR la #16 tren nhanh `m4-dac_trung-xep-hang-hoc_may-sach-final-v2`. Head truoc correction la `2efa627c65cb5387bcc4aa77f4063070812d6aa6`; close-only QD-0061 va CI #351 da dat. Giai doan 2A da hoan tat; blocker hien tai chi la generic runner hard-code reporting/provenance khong thuoc kha nang tu xac minh. Correction QD-0062 tach policy khoi runtime fact, khong chay lai Tier A pipeline va khong mo Giai doan 2B, Tier B hay Moc 5.

## Cong viec hien tai sau QD-0064

Moc 4 da complete, PR #16 da merge va CI post-merge main #355 da dat. Cong viec hien tai chi la PR dieu phoi hau Moc 4; khong co technical work va khong mo Moc 5.

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

## Cap nhat 2026-07-28 — QD-0065 va dac ta Moc 5

Trang thai hien hanh o phan nay thay the cac dong `MOC_5_NOT_OPENED` o phan lich su phia tren.

### Muc tieu vong

Soan dac ta Moc 5 — chia von va danh muc muc tieu — tu base main bat buoc `e59dca55fa37d88bd0e0f6e8e78bc6d282e4996b`, tren nhanh `dac_ta-moc-5`; tao Draft PR vao `main` va dung sau bao cao doan 00.

### Pham vi khoa

- Chi thay doi dac ta, kien truc, `DECISIONS.md` va tai lieu dieu phoi.
- Khong sua `src/`, `tests/`, workflow, dependency hoac lockfile.
- Khong sua/chay lai Moc 4; khong Tier B, LightGBM, SSI API hoac auto-trading.
- Khoa input contract tu ranking/selection M4, sector PIT, volatility 60 returns, VNINDEX regime, NAV/cash/holdings va order references.
- Khoa inverse volatility, ticker cap 15%, sector cap 25%, cash 10% RISK_ON / 50% RISK_OFF, feasibility va deterministic water-filling.
- Khoa Decimal, SHA-256, provenance, immutable publication, fail-closed validation va proposed orders `MANUAL_ENTRY_ONLY`.

### Quyet dinh con mo

1. Nguon/taxonomy/version sector PIT canonical.
2. Nguon gia tham chieu va lot-size PIT canonical.
3. Gia tri phi, thue va slippage cho proposal van hanh.
4. Nguon lich canonical xac nhan execution date.

### Cua hoan tat cua vong dac ta

- Diff chi nam trong tai lieu duoc phep.
- Draft PR Open, chua Ready va chua merge.
- Bao cao doan 00 gom branch, final head commit, PR URL, files thay doi, toan bo open decisions va CI current-head.
- `MOC_5_SPEC_OPEN`; `MOC_5_IMPLEMENTATION_NOT_STARTED`; `NO_SSI_INTEGRATION`; `NO_READY_NO_MERGE`.
