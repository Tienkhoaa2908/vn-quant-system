# Bàn giao đoạn chat điều phối

Cập nhật: 2026-07-27

## Nền

- Kho: `Tienkhoaa2908/vn-quant-system`.
- Main hien hanh: `67d09c85a3f3fef855b536172e43966a3269d5ce`.
- PR #16 da merge bang merge commit `67d09c85a3f3fef855b536172e43966a3269d5ce`.
- CI post-merge main #355 / Run ID `30281747970` da completed/success tren Ubuntu va Windows.
- PR #13 va PR #14 da closed/unmerged do PR #16 thay the.
- Mốc 4 complete; Mốc 5 chua mo.

## Trạng thái kỹ thuật

Lock đa nền tảng đạt frozen sync trên Ubuntu/Windows với Python 3.12.13, uv 0.11.32 và scikit-learn 1.9.0. Patch portability giữ file fsync và atomic publication, chỉ phân nhánh capability directory fsync: POSIX thực hiện và propagate lỗi; Windows trả unsupported mà không giả lập thành công.

CI source run #334 đã xanh: Ubuntu Job `89890344314`, Windows Job `89890344310`. Final tree có 320 test discovery.

PR #14 run #335 cũng đã xanh trước correction tài liệu: Ubuntu Job `89898799819`, Windows Job `89898799861`, Run ID `30241263742`.

## Blocker được review phát hiện

Commit thứ năm của PR #14 đã thay các tài liệu tích lũy bằng bản tóm tắt ngắn, làm mất QD-0001..QD-0059 và nhiều nội dung README/kiến trúc/lộ trình. Vòng hiện tại phục hồi bảy tài liệu từ commit thứ tư và cập nhật cộng dồn, không sửa kỹ thuật.

## Cửa tiếp theo

PR dieu phoi hau Moc 4 chi cap nhat nam tai lieu, phai giu Draft/Open/chua merge. Khong co technical drift, khong chay lai Tier A/du lieu that, khong Tier B, LightGBM, SSI va khong mo Moc 5.

## Cap nhat QD-0061: contract benchmark close-only

PR canonical hien tai la #16 tren nhanh `m4-dac_trung-xep-hang-hoc_may-sach-final-v2`. Giai doan 2A da hoan tat voi `D.OFFICIAL_VALUES_UNAVAILABLE`, `SEMANTICS_DEFINITION_NOT_FOUND` va `CLOSE_ONLY_BENCHMARK_CONTRACT`; cac tham chieu PR #14/CI cu o phan lich su khong phai trang thai current-head. CI #347 chi la baseline cua head cu truoc patch nay.

Co phieu tiep tuc dung `ThanhOHLCV` strict. Benchmark dung `ThanhBenchmarkDongCua` va schema CSV dung sau cot `ma,ngay,gia_dong_cua,nguon,phien_ban,co_so_gia`; open/high/low/volume benchmark khong duoc dua vao canonical input, sua, suy dien hoac dung trong feature/label. Raw KBS va ho so audit run `m4_tier_a_20260727T081753Z_e2c866db` giu bat bien; khong co correction overlay hay replacement values. Manifest/bao cao cong bo `benchmark_contract=close_only`, hai canh bao bat buoc va gioi han chi kiem tra ky thuat. Exact official OHLC van chua co; dieu nay khong xac nhan co so gia co phieu. Normalization, Tier A pipeline, Tier B va Moc 5 chua chay.

## Cap nhat QD-0062: reporting/provenance blocker

Canonical PR la #16 tren nhanh `m4-dac_trung-xep-hang-hoc_may-sach-final-v2`. Head truoc correction la `2efa627c65cb5387bcc4aa77f4063070812d6aa6`; close-only QD-0061 va CI #351 da dat. Giai doan 2A da hoan tat; blocker hien tai chi la generic runner hard-code reporting/provenance khong thuoc kha nang tu xac minh. Correction QD-0062 tach policy khoi runtime fact, khong chay lai Tier A pipeline va khong mo Giai doan 2B, Tier B hay Moc 5.

## Ban giao QD-0063

Doan chat tiep theo phai coi cac Run ID va hash duoi day la immutable anchors. Khong duoc tai dien false-blocker hashes nhu final evidence va khong duoc chay lai pipeline de thay the san pham da khoa.

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
Cap nhat: 2026-07-28

## Anchor

- Branch: `du_lieu-vn100-toan-phan`.
- Parent truoc QD-0067: `bb3fc035c6ebd885cf4083184ea8a96c7b0f2401`.
- PR #21 phai giu Open/Draft/chua merge.
- PR #20 khong duoc sua.

## Du lieu khoa

- 121 raw, 121 hash khop, 231.151 dong;
- 45 strict-pass, 76 high/low-only;
- 121 open/close/volume-pass, 0 excluded theo hop dong rut gon;
- 159 cap ma-ngay bat thuong, 35 ngay lich;
- khong duplicate/non-finite/non-positive/negative-volume.

QD-0067 phe duyet hop dong rut gon chi cho technical validation. High/low khong
vao san pham va khong duoc dung trong feature/label/ranking/backtest. Close dung
cho feature/label/MA250/regime/dinh gia, `close*volume` cho thanh khoan, open cho
T+1 execution.

Doan tiep theo chi duoc chay bo chuyen doi ngoai tuyen tren raw hien co. Khong
goi mang, khong sua raw, khong research claim. Cua chinh thuc van fail vi
membership PIT, HOSE EOD, corporate actions va price basis. Moc 4 chua chay lai;
Moc 5 chua trien khai.

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
