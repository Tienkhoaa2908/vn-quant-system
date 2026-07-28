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

Trạng thái: **đã hoàn thành, đã merge và đã vượt CI post-merge trên main**.

- Đặc tả: `tai_lieu/dac_ta_moc_4.md`.
- PR #16 đã merge bằng merge commit `67d09c85a3f3fef855b536172e43966a3269d5ce`.
- CI post-merge trên `main`:
  - workflow `kiem_tra_tu_dong`;
  - run `#355`;
  - Run ID `30281747970`;
  - event `push`;
  - head `67d09c85a3f3fef855b536172e43966a3269d5ce`;
  - Ubuntu Job `90029586084`, success;
  - Windows Job `90029585961`, success;
  - artifacts `phien-ban-ci-ubuntu`, `phien-ban-ci-windows`;
  - uv `0.11.32`, Python `3.12.13`, scikit-learn `1.9.0`.
- PR #13 và PR #14 đã đóng, không merge, do PR #16 thay thế.
- Mốc 4 implementation và Tier A technical validation đã hoàn tất.
- Tier A chỉ là technical validation; universe `FPT/HPG/MBB` là synthetic technical control, không phải VN100 PIT.
- `price_basis_confirmed=false`; corporate-action inventory partial; benchmark close-only.
- Không research claim; NAV/AUC/Sharpe không phải bằng chứng hiệu quả đầu tư.
- Tier B chưa chạy; không LightGBM hoặc SSI.

Phạm vi kỹ thuật đã triển khai giữ nguyên: dữ liệu nhiều năm, kiểm soát PIT/look-ahead, feature, nhãn lợi nhuận tương đối, walk-forward purge/embargo, momentum baseline, Logistic Regression, ranking, `top_k`, backtest OOS và publication nguyên tử. Không có thay đổi kỹ thuật trong PR điều phối hậu Mốc 4.

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

## Moc kiem soat QD-0064 trong ke hoach tong the

Moc 4 da complete, PR #16 da merge va CI post-merge main #355 da dat. Day la diem dung dieu phoi. Tier B chua chay va Moc 5 chua mo.

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
## Moc 0–3

Da hoan tat va da merge. Cac quyet dinh/implementation lich su giu nguyen.

## Moc 4

Implementation va Tier A tren fixture FPT/HPG/MBB da hoan tat truoc do. Vong
hien tai chua chay lai Moc 4 tren VN100.

QD-0067 mo mot input contract rieng cho technical validation tren 121 ma:
open/close/volume co provenance raw. Close dung cho feature, label, MA250,
regime va dinh gia; thanh khoan dung close*volume; execution T+1 dung open.
Khong high/low feature va khong feature thay the sau khi nhin ket qua.

Tai gia 121 ma da hoan tat; raw/hash audit dat. Tuy nhien research gate van fail
do universe membership PIT chua lien tuc, HOSE EOD chua doi chieu dat,
corporate-action inventory chua day du va price basis chua xac nhan. Technical
publication khong duoc dien giai thanh hieu qua dau tu.

## Moc 5

Chua trien khai trong PR #21. PR #20 giu Open/Draft rieng, khong bi sua.

## Moc 6

Chua mo. Khong paper trading hoac tin hieu van hanh tu hop dong rut gon.

## Publication hop dong gia rut gon VN100 ngay 2026-07-28

Publication ngoai tuyen da hoan tat tren 121 raw da co, khong goi KBS, khong tai
lai va khong sua du lieu goc:

```text
ma_lan_chay: vn100_rut_gon_20260728_38b67395
so_du_lieu_goc: 121
so_ma_dat: 121
so_ma_bi_loai: 0
tong_so_dong: 231151
hai_lan_cong_bo_cung_byte: true
```

SHA-256 san pham:

```text
du_lieu_gia_mo_dong_khoi_luong.csv
121cd49d401b1ba0d3a97a8f44aac0d2a9f7a7acb9b573d0fa1a2131de1545d6

bao_cao_do_phu_hop_dong_rut_gon.json
af3dd7edfd741fcd6a82d832f89fbfdc5d73701ad428f336b829f4cfdd971b92

bao_cao_ma_bi_loai.json
e46592af96417155ebcd8902bfb23f95926b7d8696bdffb77bf750d88ff6ff8d

manifest.json
88825dbd21364ef23116409b2979f885757c0a29dd1a7af8debfa1df60f0f0ef

sha256.txt
461cf6573a45746a84db7ebd2987920b19b059db931d6f0bf95cbb45ec2e8a04
```

Toan bo san pham publication va raw nam ngoai kho ma, khong duoc commit vao Git.

Ngoai le do phu bat buoc:

- ITA ket thuc tai `2024-09-25`;
- BCG ket thuc tai `2025-10-08`;
- TMS ket thuc tai `2026-07-23`;
- DSE va VPL co lich su ngan theo ngay bat dau du lieu cua tung ma;
- khong forward-fill va khong mang gia cuoi cung sang ngay sau;
- khong bien thieu du lieu thanh loi suat bang 0;
- eligibility va MA250 phai duoc danh gia theo tung cap `ma-ngay`;
- hop 121 ma chi la union thu thap, khong phai universe co dinh dung theo moi
  thoi diem.

Publication nay chi xac nhan hop dong ky thuat open/close/volume va tinh tai lap
byte. Cua nghien cuu chinh thuc van `FAIL` do lich su thanh phan VN100 chua lien
tuc, chua doi chieu HOSE EOD, kiem ke corporate actions chua day du va price
basis chua xac nhan. Khong duoc dien giai publication thanh bang chung alpha,
hieu qua mo hinh, hieu qua dau tu, tin hieu van hanh hay khuyen nghi giao dich.
Moc 4 chua chay lai; Moc 5 chua trien khai.
