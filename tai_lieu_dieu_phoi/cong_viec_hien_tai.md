# Công việc hiện tại

Cập nhật: 2026-07-29

## Mục tiêu vòng 01E

Đóng cửa điều phối hậu gộp PR #23 và ghi nhận lần chạy lại kỹ thuật Mốc 4 trên tập rộng. Vòng này chỉ cập nhật bốn tài liệu điều phối; không sửa mã, kiểm thử, workflow, dependency, lockfile, PR #20 hoặc mã Mốc 5.

## Nền bắt buộc

- Repository: `Tienkhoaa2908/vn-quant-system`.
- Base chính xác: `3ff2ed3c8b18eebd9095e9af182b004f4d0aee67`.
- PR #23 đã merge bằng merge commit `3ff2ed3c8b18eebd9095e9af182b004f4d0aee67`; head đã gộp `f813cd3cda4c0129f53deb9ffb8a9a42f18b5220`.
- CI hậu gộp `main`: Run ID `30436034585`, Ubuntu Job `90523874732`, Windows Job `90523875099`, đều thành công.

## Kết quả chạy rộng đã khóa

- Nguồn: `121` mã, `231151` dòng.
- `120` mã có dự báo; `TMS` bị loại có kiểm soát do thiếu lịch sử đặc trưng bắt buộc.
- `36` fold, `34` fold thành công.
- `fold_035` và `fold_036` có `test_rong` tại biên cuối dữ liệu vì thiếu `20` phiên tương lai để tạo nhãn.
- `3840` dự báo Logistic và `3840` dự báo động lượng.
- `23` tệp sản phẩm.
- Hai lượt kiểm toán độc lập đều đạt và giống nhau tuyệt đối theo byte/SHA-256.
- Đầu vào không đổi trước và sau chạy.
- Logistic chỉ là đường chuẩn kỹ thuật và yếu hơn động lượng trong lần chạy này.
- Cấm diễn giải thành alpha, tín hiệu vận hành, khả năng giao dịch thực hoặc khuyến nghị đầu tư.

## Cửa nghiên cứu và Mốc 5

- `RESEARCH_GATE=FAIL`.
- `VN100_POINT_IN_TIME_HISTORY_INCOMPLETE`.
- `HOSE_EOD_CROSSCHECK_INCOMPLETE`.
- `CORPORATE_ACTION_INVENTORY_INCOMPLETE`.
- `PRICE_BASIS_UNCONFIRMED`.
- Mốc 5 tiếp tục tạm dừng; PR #20 không bị sửa; không triển khai mã Mốc 5.

## Cửa hoàn tất vòng 01E

- Net diff chỉ có đúng bốn tài liệu điều phối.
- Kiểm tra ngoại tuyến đầy đủ đạt.
- Nhánh `dieu_phoi-hau-gop-pr23` được đẩy từ đúng base.
- PR mới phải giữ Open/Draft/chưa merge.
- Không squash, không rebase, không merge `main`.

## Mục tiêu vòng

Tạo PR điều phối hậu gộp PR #21 để ghi nhận merge commit `ae807ee1ae06d81b655b8a4961673a4d9ebd629c` và CI post-merge main #379 đã đạt. Chỉ cập nhật tài liệu điều phối; chưa chạy lại Mốc 4 và chưa triển khai Mốc 5.

## Nền

- Repository: `Tienkhoaa2908/vn-quant-system`.
- Main bắt buộc: `ae807ee1ae06d81b655b8a4961673a4d9ebd629c`.
- PR #21: merged bằng merge commit `ae807ee1ae06d81b655b8a4961673a4d9ebd629c`.
- CI main: workflow `kiem_tra_tu_dong`, run #379, Run ID `30341585611`, Ubuntu Job `90218164153`, Windows Job `90218164026`, completed/success.
- PR #20 vẫn Open/Draft và không bị sửa.

## Phạm vi

1. Cập nhật đúng bốn tài liệu điều phối bắt buộc.
2. Ghi nhận PR #21 đã gộp và CI hậu gộp trên `main` đã đạt.
3. Chỉ mở bước chuẩn bị chạy lại Mốc 4 kỹ thuật trên tập rộng.
4. Không sửa code, test, workflow, dependency, lockfile hoặc dữ liệu vận hành.
5. Không chạy pipeline, không huấn luyện và không backtest trong vòng này.
6. Không triển khai Mốc 5; PR #20 tiếp tục tạm dừng.

## Cửa hoàn tất

- Diff chỉ có đúng bốn tài liệu điều phối.
- Merge commit PR #21 và CI main #379 được ghi chính xác.
- Cửa nghiên cứu chính thức tiếp tục `FAIL`.
- PR điều phối mới Open/Draft/chưa merge.

## Cấm hiện hành

Không force-push, amend, squash hoặc merge PR mới. Không research claim; không diễn giải publication hoặc chỉ số Mốc 4 thành hiệu quả đầu tư.

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
Cap nhat: 2026-07-28

## Pham vi PR #21

Khoa QD-0067 va bo chuyen doi ngoai tuyen tu raw VN100 sang hop dong:

```text
ma,ngay,gia_mo_cua,gia_dong_cua,khoi_luong,
nguon,phien_ban,co_so_gia,raw_sha256
```

Bat buoc: khong goi KBS, khong tai lai 121 ma, khong sua raw, khong commit san
pham van hanh/checkpoint, khong chay Moc 4, khong huan luyen/backtest va khong
trien khai Moc 5.

## Cua hoan tat

- publication gom CSV, coverage, exclusion, manifest va sha256;
- fail closed theo raw/hash/identity/source/version/open/close/volume/date;
- high/low khong chan va khong vao CSV;
- output sap xep xac dinh, khong ghi de;
- hai lan chay cung input tao cung byte;
- manifest truy vet dung raw SHA-256;
- PR #21 giu Draft/Open/chua merge.

Cua nghien cuu chinh thuc van fail vi membership PIT, HOSE EOD, corporate
actions va price basis.

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

## Công việc hiện hành sau gộp PR #21

- PR #21 đã merge tại `ae807ee1ae06d81b655b8a4961673a4d9ebd629c`.
- CI hậu gộp main #379 / Run ID `30341585611` đã `completed/success` trên Ubuntu và Windows.
- Việc tiếp theo chỉ là chuẩn bị đặc tả vận hành cho lần chạy lại Mốc 4 kỹ thuật trên tập rộng.
- Chưa được chạy pipeline, huấn luyện, xếp hạng hoặc backtest cho tới khi có vòng chuyên trách và cửa đầu vào riêng.
- PR #20 giữ Open/Draft; Mốc 5 tiếp tục tạm dừng.
- Cửa nghiên cứu chính thức vẫn `FAIL`: membership PIT chưa liên tục, HOSE EOD chưa đối chiếu đạt, corporate actions chưa đầy đủ và price basis chưa xác nhận.
