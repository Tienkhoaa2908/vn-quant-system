# Anti-regression: C3 + HOSE research

Tài liệu này là guardrail bắt buộc cho các đoạn chat và work package kế tiếp. Khi lịch sử trò chuyện hết dung lượng, phải đọc tài liệu này trước khi thay đổi research architecture.

## 1. Nguồn sự thật và thứ tự ưu tiên

1. GitHub repository, commit history, PR, CI, `DECISIONS.md`, tài liệu điều phối và artifact workstation là nguồn sự thật.
2. Không yêu cầu người vận hành kể lại lịch sử bằng trí nhớ nếu có thể khôi phục từ repo.
3. CI chỉ xác minh code/contract. Kết quả nghiên cứu chỉ tồn tại sau khi runner chạy trên workstation data thật và artifact được kiểm tra.
4. Không suy ra kết quả từ runtime nhanh/chậm, số dòng event hay trạng thái `SUCCESS` một cách cơ học.

## 2. Champion/model nền không được tự ý thay

- Champion hiện hành: `C3_STABLE_3_PAST_IC_SHRUNK`.
- Ba component gốc của C3: `low_volatility`, `relative_strength_120`, `high_52_week`.
- C3 học trọng số từ IC của nhãn quá khứ đã hoàn tất và shrink về equal weight.
- C3 là baseline/champion bắt buộc cho nghiên cứu tiếp theo.
- Logistic Regression, HistGradientBoosting, LightGBM hoặc model khác chỉ là challenger/augmentation. Không được đổi champion chỉ vì challenger mới được triển khai hoặc chạy được.
- Challenger chỉ được promote sau so sánh causal OOS trên cùng data/fold, stability theo era/year, portfolio simulation exposure-normalized và paper OOS theo quy trình dự án.

## 3. Môi trường chạy và kiến trúc model là hai khái niệm độc lập

- Canonical workstation environment hiện hành: `vn_quant_local_system/.venv`.
- Việc thiếu package trong environment không phải lý do để thay model nền hoặc dựng một hệ thống vận hành thứ hai.
- Nếu challenger cần dependency mới, xử lý dependency như một thay đổi môi trường có kiểm soát; không dùng nó để thay đổi champion ngầm.
- V66 đã mắc lỗi tách sang root `.venv` để chữa dependency và đồng thời train model độc lập; cách hiểu này bị hủy bỏ về mặt kiến trúc.

## 4. Training truth là HOSE master history local

- Phạm vi mặc định: cổ phiếu HOSE.
- Dữ liệu train chuẩn phải dựng lại từ kho local 11 năm, ưu tiên `vn_quant_local_system/data/market/dnse_ohlcv.sqlite3` và các metadata lịch sử đi kèm.
- V22, candidate list, Top-N snapshot hoặc vài mã focus không phải training truth khi có thể dựng lại từ store tổng hợp.
- Membership HOSE phải point-in-time. Static mapping hiện tại áp ngược lịch sử bị cấm vì survivorship/migration bias.
- Nếu store thiếu exchange history/bar-level venue thì fail-closed và xuất schema/census; không tự đoán danh sách HOSE.
- Price basis, corporate actions và delisting lineage phải được audit trước live promotion.

## 5. Causality và boundary bắt buộc

- Signal chỉ dùng dữ liệu đã hoàn tất tại close phiên `t`; entry sớm nhất ở open phiên kế tiếp `t+1`.
- Mọi label dùng để train trọng số/model phải có `label_end < signal_day` tại thời điểm fit.
- Không random split chuỗi thời gian.
- Monthly canonical chỉ được tạo từ tháng đã hoàn tất. Analysis end giữa tháng, ví dụ 2026-08-13, không được biến 2026-08-13 thành monthly snapshot.
- August 2026 đã được nhìn thấy trong quá trình thiết kế V63+ nên chỉ là shadow audit, không phải pristine OOS và không được tune threshold.
- Shadow signal-state phải được ghi ngay cả khi chưa có future outcome; không được làm biến mất tín hiệu mới nhất chỉ vì label tương lai chưa tồn tại.

## 6. Sai lầm đã gặp và quy tắc sửa

### V61: exposure/redeployment confounder

Sai lầm: so policy khi baseline stock exposure quá thấp, làm kết quả bị chi phối bởi mức đầu tư chứ không phải policy signal.

Sửa: mọi portfolio simulation sau này phải dùng exposure-normalized baseline kiểu V62 hoặc kiểm soát stock exposure/recycling tương đương. Không so policy khi exposure khác biệt lớn mà không decomposition.

### V62: không được bỏ qua kết quả không robust

V62 cho thấy bridge có thể cải thiện tail nhưng không robust return và có cross-era polarity. Không được cherry-pick một metric tốt để promote policy.

Sửa: tách mục tiêu protection và opportunity. Protection có thể chịu insurance cost giới hạn nếu tail/single-name damage cải thiện; opportunity phải tạo incremental return/capture benefit.

### V63: rank-only protection không bắt được VPI

Sai lầm giả định: canonical Top10 rơi khỏi Preview Top20 là đủ làm protection gate.

Quan sát: VPI vẫn Preview rank cao trong August shadow dù forward path xấu, nên rank collapse đơn lẻ có blind spot.

Sửa: protection phải xem price-path/trend/relative weakness/drawdown/volatility cùng rank. Không tune threshold từ VPI August.

### V64: event count lớn không đồng nghĩa sample độc lập lớn

Sai lầm: 124k cohort-events nhìn rất lớn nhưng chỉ sinh từ khoảng 10k weekly-symbol states và một state có thể kích hoạt nhiều cohort.

Sửa: luôn báo unique week, unique symbol, overlap/concentration; dùng cluster-aware robustness khi cần. Không dùng raw event count làm bằng chứng sức mạnh.

### V64: shadow event bị thiếu khi chưa có future outcome

Sai lầm: TLG latest shadow không xuất hiện trong event table vì event chỉ được tạo khi có future label.

Sửa: tách `signal_state` khỏi `outcome_event`. Latest signal phải tồn tại dù outcome chưa biết.

### V64/V65: canonical stale do frozen V22

Sai lầm: August audit từng dùng canonical 2026-06-30 vì V22 thiếu July snapshot.

Sửa: khi có market store 11 năm, phải rebuild monthly C3 trực tiếp từ store để July canonical được tạo causal; V22 chỉ là lineage/reference nếu cần.

### V64/V65: 119 mã không phải toàn thị trường

Sai lầm: nghiên cứu trên union canonical Top10 + preview Top20/V22 có thể bị hiểu là broad market.

Sửa: mặc định nghiên cứu trên HOSE point-in-time broad universe từ local store; focus symbols chỉ để audit case, không phải universe train.

### V65: robustness không sửa được data lineage thiếu

Robust bootstrap/FDR không biến universe không point-in-time thành dữ liệu đúng.

Sửa: data lineage gate đứng trước model sophistication.

### V66: thay C3 bằng model độc lập

Sai lầm: triển khai Logistic/HGB trực tiếp trên HOSE panel rồi gọi đó là hướng nghiên cứu chính, làm mất champion C3.

Sửa: C3 phải được rebuild/train/evaluate trước. Challenger chỉ chạy sau baseline C3 sạch và phải đấu trực tiếp với C3.

### V66: đổi environment để chữa dependency

Sai lầm: chuyển runner sang root `.venv` để có sklearn, trong khi workstation trước giờ dùng `vn_quant_local_system/.venv`.

Sửa: V67 quay lại canonical local environment và không cần sklearn. Dependency của challenger sẽ được xử lý riêng sau.

### CI thành công không đồng nghĩa nghiên cứu thành công

Sai lầm tiềm ẩn: xem compile/tests/CI xanh là kết quả research.

Sửa: chỉ kết luận sau artifact chạy thật trên local data và deep audit provenance/data/model/output.

## 7. Cost, turnover và vốn nhỏ

- BASE cost là kịch bản chính; STRESS/SEVERE là diagnostics, không tự động veto edge.
- Với vốn giao dịch nhỏ, không để cost assumption quá bảo thủ che mất signal quality, nhưng vẫn phải model phí/thuế/slippage ở portfolio stage.
- Turnover không phải objective chính ở screening signal, nhưng phải quay lại ở simulation.

## 8. Protection và opportunity phải đánh giá riêng

Protection:
- mục tiêu: giảm single-name damage, tail loss, adverse excursion, drawdown;
- không bắt buộc standalone return dương;
- phải đo false positives/rebound cost và insurance cost.

Opportunity:
- mục tiêu: bắt leader mới mà monthly C3 chậm phản ứng;
- phải đo incremental edge so với raw C3/Top5 baseline, không chỉ so với zero;
- persistence/relative strength/trend/volume chỉ là hypothesis, không được coi là đúng trước khi OOS.

Sau khi từng lane có bằng chứng riêng mới thử combined policy.

## 9. Thứ tự nghiên cứu chuẩn từ V67

1. Census DB + point-in-time HOSE membership.
2. Rebuild monthly C3 trên toàn lịch sử local.
3. Xác minh C3 weight history dùng completed labels only.
4. Đo C3 monthly OOS baseline theo year/era.
5. Dựng weekly C3 preview trên cùng HOSE universe và cùng C3 weights.
6. Re-test protection/opportunity hypotheses trên nền C3 native.
7. Audit overlap, concentration, shadow state, VPI/TLG/BAF chỉ như case audit.
8. Chỉ sau khi baseline sạch mới mở Logistic/LightGBM challenger trên cùng folds.
9. Portfolio simulation phải exposure-normalized và causal t+1.
10. Paper OOS trước mọi live promotion.

## 10. Điều cấm

- Không tự đổi champion.
- Không tự đổi canonical environment rồi coi như kiến trúc mới.
- Không dùng current membership làm lịch sử.
- Không dùng August 2026 để tune.
- Không dùng focus symbols làm training universe.
- Không dùng raw event count làm sample size độc lập.
- Không promote từ CI hoặc historical research sang live.
- Không tạo order/live broker action trong research runner.
- Không giao patch/ZIP code thủ công nếu GitHub connector còn ghi được; workstation chỉ fetch/switch/pull và chạy runner.
