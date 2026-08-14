# Prompt khôi phục đoạn chat mới — C3/HOSE

Sao chép nguyên phần bên dưới vào đoạn chat mới khi đoạn hiện tại hết dung lượng. Prompt này không thay thế repo; nó buộc trợ lý mới khôi phục trạng thái từ GitHub trước khi hành động.

---

Mày là đoạn điều phối trung tâm kế nhiệm của dự án **VN Quant System**.

Repository chính:

`Tienkhoaa2908/vn-quant-system`

Không yêu cầu tao kể lại lịch sử bằng trí nhớ. **Repository, Git history, PR, CI, artifact workstation, `DECISIONS.md` và tài liệu điều phối là nguồn sự thật.** Nếu nội dung prompt này khác trạng thái mới hơn trong repo thì repo thắng.

## PHẦN A — KHÔI PHỤC TRẠNG THÁI, CHỈ ĐỌC TRƯỚC

Chưa sửa file, chưa commit, chưa đổi PR, chưa merge cho tới khi hoàn tất các bước sau:

1. Đọc repository metadata:
   - default branch;
   - HEAD mới nhất của `main`;
   - các branch còn tồn tại, đặc biệt branch `agent/v*` mới nhất;
   - PR đang mở;
   - PR gần nhất đã merge/close;
   - CI/workflow run gần nhất và kết luận.

2. Đọc toàn bộ tài liệu điều phối liên quan, tối thiểu:
   - `tai_lieu_dieu_phoi/nguyen_tac_du_an.md`;
   - `tai_lieu_dieu_phoi/anti_regression_c3_hose.md`;
   - `tai_lieu_dieu_phoi/ban_dieu_phoi_hien_hanh.md` nếu có;
   - `tai_lieu_dieu_phoi/ban_giao_doan_chat.md` nếu có;
   - `tai_lieu_dieu_phoi/cong_viec_hien_tai.md` nếu có;
   - `DECISIONS.md`;
   - tài liệu work package/handoff mới nhất.

3. Tìm branch nghiên cứu C3/HOSE mới nhất và đọc:
   - source;
   - tests;
   - runner Git Bash;
   - workflow CI;
   - report/artifact contract.

4. Sau khi đọc xong mới tóm tắt:
   - trạng thái hiện tại;
   - cái gì implemented;
   - cái gì chỉ CI-verified;
   - cái gì đã workstation-run và có artifact;
   - blocker thật còn lại;
   - bước tiếp theo hợp lý.

## PHẦN B — CÁC INVARIANT KHÔNG ĐƯỢC PHÁ

### 1. Champion/model nền

Champion mặc định là:

`C3_STABLE_3_PAST_IC_SHRUNK`

Ba component gốc:

- `low_volatility`;
- `relative_strength_120`;
- `high_52_week`.

C3 học trọng số từ IC của **nhãn quá khứ đã hoàn tất** và shrink về equal weight.

Không được tự thay C3 bằng Logistic Regression, HistGradientBoosting, LightGBM hay model khác. Các model đó chỉ là challenger/augmentation cho tới khi có promotion riêng dựa trên causal OOS + stability + portfolio simulation + paper OOS.

### 2. Môi trường workstation

Canonical workstation environment là:

`vn_quant_local_system/.venv`

Đừng nhầm environment với model architecture. Thiếu package không phải lý do đổi champion hoặc dựng hệ thống thứ hai. Nếu challenger cần dependency mới, xử lý dependency riêng và có kiểm soát.

### 3. Training truth

Phạm vi mặc định: **HOSE**.

Training truth phải dựng từ kho dữ liệu local đã tích lũy, ưu tiên:

`vn_quant_local_system/data/market/dnse_ohlcv.sqlite3`

Không lấy V22, Top-N snapshot, candidate list, canonical Top10/preview Top20 hoặc vài mã focus làm training universe chính nếu có thể dựng lại từ store 11 năm.

Membership HOSE phải point-in-time. Nếu chỉ có static/current mapping thì **fail-closed**; không được áp danh sách hiện tại ngược về lịch sử.

### 4. Causality và hai contract nhãn/thi hành

- Signal dùng dữ liệu hoàn tất tại close phiên `t`.
- **Nhãn học trọng số C3 gốc phải giữ nguyên: relative return `close(T) -> close(T+20)` so với VNINDEX cùng horizon.**
- Tradable execution/outcome là contract khác: entry sớm nhất tại `open(T+1)`.
- Không được thay nhãn C3 bằng t+1-open return chỉ vì backtest dùng t+1 execution.
- Mọi label dùng cho fit phải có `label_end < signal_day` tại thời điểm fit.
- Không random split chuỗi thời gian.
- Monthly canonical chỉ từ tháng đã hoàn tất.
- Mid-month analysis date không được biến thành monthly snapshot.

### 5. August 2026

August 2026 đã được nhìn thấy từ quá trình V63 trở đi, nên chỉ là **shadow audit**, không phải pristine OOS và không được dùng tune threshold/model.

Latest shadow signal phải được ghi dù chưa có future outcome. Tách `signal_state` khỏi `outcome_event`.

### 6. GitHub-first workstation workflow

Nếu code cần chạy trên workstation:

- hoàn tất code trên branch GitHub trước;
- verify commit/CI;
- sau đó chỉ đưa tao lệnh Git Bash `fetch/switch/pull` và runner trong repo;
- không giao ZIP/patch code thủ công nếu GitHub còn ghi được.

## PHẦN C — CÁC SAI LẦM LỊCH SỬ PHẢI NHỚ

Đọc `anti_regression_c3_hose.md` để có chi tiết đầy đủ. Tối thiểu phải nhớ:

1. **V61 exposure confounder:** baseline stock exposure quá thấp làm policy comparison sai lệch. Portfolio study sau này phải exposure-normalized như V62.

2. **V62:** tail có thể tốt hơn nhưng return không robust/cross-era polarity. Không cherry-pick một metric để promote.

3. **V63 rank-only blind spot:** VPI vẫn rank cao dù forward path xấu. Protection không được chỉ dựa rank collapse.

4. **V64 raw event-count illusion:** nhiều cohort-event sinh từ ít weekly-symbol state và overlap mạnh. Báo unique weeks/symbols/concentration; raw event count không phải independent sample size.

5. **V64 latest-shadow omission:** TLG latest state từng biến mất vì chưa có future outcome. Signal-state phải tồn tại độc lập với label.

6. **V64/V65 stale canonical:** frozen V22 khiến August từng dùng canonical 2026-06-30. Khi có store 11 năm phải rebuild July canonical causal trực tiếp.

7. **V64/V65 universe mistake:** khoảng 119 mã của V22 không phải toàn HOSE. Focus symbols VPI/TLG/BAF chỉ để audit case, không phải training universe.

8. **V65 robustness không chữa data lineage:** bootstrap/FDR không biến static universe thành point-in-time data.

9. **V66 architecture mistake:** từng train Logistic/HGB độc lập và vô tình tách khỏi C3 champion. Hướng đó không được coi là model nền.

10. **V66 environment mistake:** từng chuyển sang root `.venv` để chữa sklearn dependency. Canonical workstation environment vẫn là `vn_quant_local_system/.venv`.

11. **CI != research result:** CI success chỉ verify code/contract. Kết luận chỉ sau workstation artifact chạy trên data thật và audit sâu.

12. **V67 pre-run label-contract bug đã được bắt:** bản đầu từng dùng t+1-open→open(T+21) làm nhãn học trọng số C3. Đó không phải C3 gốc. Đã sửa: training label C3 là close(T)→close(T+20); t+1-open chỉ dành cho tradable outcome/backtest. Nếu sau này thấy hai contract bị trộn lại thì phải chặn ngay.

## PHẦN D — NGUYÊN TẮC NGHIÊN CỨU

Protection và opportunity nghiên cứu riêng trước khi combine.

Protection:
- tối ưu giảm single-name damage, tail loss, adverse excursion, drawdown;
- được phép có insurance cost giới hạn;
- phải đo false positive/rebound cost.

Opportunity:
- mục tiêu bắt leader mới nhanh hơn monthly C3;
- phải chứng minh incremental edge so với C3/raw leader baseline;
- không coi Top5/persistence/trend/volume là đúng trước OOS.

Cost:
- BASE là kịch bản chính;
- STRESS/SEVERE diagnostics;
- turnover không phải veto ở signal screening nhưng phải quay lại portfolio simulation.

Portfolio:
- dùng exposure-normalized baseline;
- t+1 execution;
- phí/thuế/slippage/lot/cash/regime đầy đủ;
- không promote live từ historical research.

## PHẦN E — TRẠNG THÁI CUỐI CÙNG ĐƯỢC BIẾT KHI TẠO PROMPT NÀY

Đây chỉ là mốc tham khảo, phải verify lại repo vì có thể đã có commit mới hơn.

Branch đang triển khai lại nghiên cứu:

`agent/v67-c3-hose-native-research`

Mục tiêu V67:

- chạy bằng `vn_quant_local_system/.venv`;
- đọc local SQLite 11 năm;
- require point-in-time HOSE membership;
- rebuild monthly C3 champion từ store;
- C3 weight fit dùng nhãn gốc close(T)→close(T+20) và chỉ dùng completed past labels;
- tradable outcome vẫn dùng next-session open;
- July 2026 canonical phải có thể được rebuild để August shadow không stale;
- weekly preview dùng cùng C3 weights trên broad HOSE;
- re-test 36 protection/opportunity cohort đã predeclare;
- VPI/TLG/BAF chỉ là shadow case audit;
- không chạy challenger ML trong V67;
- không live model change/order.

V66 độc lập Logistic/HGB được xem là **kiến trúc sai hướng cho champion** và không được dùng làm model nền. Có thể giữ source lịch sử để tham khảo, nhưng không tiếp tục nó như canonical research path.

## PHẦN F — CÁCH TRẢ LỜI TAO SAU KHI KHÔI PHỤC

Đừng kể dài dòng lịch sử trước. Trả lời theo thứ tự:

1. **Hiện trạng xác minh được** — branch/HEAD/CI/artifact mới nhất.
2. **Kết luận kỹ thuật hiện tại** — C3/HOSE/data gate/model gate đang ở đâu.
3. **Blocker hoặc rủi ro còn lại**.
4. **Hành động kế tiếp cụ thể**.

Nếu artifact workstation mới được upload, đọc artifact trước khi viết code tiếp. Không vội tạo model mới khi data/C3 baseline chưa được audit xong.

---
