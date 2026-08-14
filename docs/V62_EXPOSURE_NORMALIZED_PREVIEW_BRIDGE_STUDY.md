# V62 — Exposure-normalized C3 preview bridge study

## Vì sao V61 chưa đủ để ra quyết định

Workstation artifact V61 ngày 2026-08-13 đã chạy thành công trên:

- branch `agent/v61-adaptive-c3-portfolio-policy-study`;
- HEAD `06326ad9806f8921a9e938018c66659734e36784`;
- frozen input SHA256 `66f4dd6699026289501b260949237772f832ac716e700fa686f8b0b8accd38e5`;
- market DB SHA256 `2959f8cce0c11e8e4186fcb49ae75bf7babf86b84afe64ca3b843a7470d58b1a`.

V61 trả `NO_ROBUST_POLICY_FOUND`, nhưng artifact cho thấy ba confounder quan trọng cần sửa trước khi kết luận.

### 1. Cash recycling của harness cũ không đại diện một danh mục đã trưởng thành

Ở cell 250k/BASE, `BASELINE_P1` kết thúc với cash ratio khoảng **95.47%**; stock exposure trung bình chỉ khoảng **20.35%**, median khoảng **10.70%**, và cuối kỳ chỉ còn khoảng **4.53%** NAV ở cổ phiếu. Nguyên nhân là baseline chỉ cho core tái giải ngân tối đa một weekly contribution sau khi bán. Tiền bán tích lũy thành cash thay vì được tái phân bổ về target sleeve.

Do đó, một phần return/drawdown khác biệt của V61 phản ánh **mức độ deploy vốn** chứ chưa tách sạch chất lượng policy.

### 2. Tactical sleeve V61 bị starvation cơ học

V61 dùng 5%-10% của **một weekly contribution** cho tactical starter. Với contribution 250k, 5% chỉ là 12.5k và 10% chỉ là 25k — thấp hơn giá một cổ phiếu của rất nhiều mã.

Ở 250k/BASE:

- PERSIST: 150 candidate events nhưng chỉ 27 buys;
- VOLUME: 78 → 17;
- VELOCITY: 73 → 20;
- COMBO 5%: 22 → 2;
- COMBO 10%: 19 → 8.

Vì vậy kết luận “weekly new leader không có giá trị” là quá sớm; V61 nhiều lúc **không mua được 1 share** dù candidate đã qua filter.

### 3. Raw single-name loss metric bị bootstrap artifact chi phối

`worst_single_name_unrealized_nav` của mọi policy 250k/BASE đều bằng khoảng **-2.193%**, xảy ra ngay tuần đầu `2017-07-03` khi PVT là vị thế duy nhất và chiếm khoảng **98.46% NAV**. Đây không phải dạng “một VPI thứ hai” trong danh mục đã trưởng thành.

Metric hữu ích hơn là weighted peak-to-current damage sau khi danh mục đã có đủ thời gian và breadth.

## Tín hiệu thực sự có ích từ V61

Các policy trim **không rotate mạnh** có cấu trúc khá hứa hẹn dù gate V61 loại vì portfolio max drawdown tuyệt đối xấu hơn baseline.

`AGE10_TRIM25_BREAK2` trên 9 contribution/slippage cells:

- annualized return tốt hơn baseline: 9/9;
- median annualized return delta: khoảng **+0.785 điểm %/năm**;
- Calmar tốt hơn: 8/9;
- weighted single-name peak damage tốt hơn: 9/9;
- median peak-damage improvement: khoảng **+0.367 điểm % NAV**;
- median số damage-weeks >1% NAV giảm khoảng 2;
- nhưng median portfolio max-drawdown xấu hơn khoảng **2.22 điểm %**.

`TRIM25_BREAK1` an toàn hơn một chút ở portfolio DD và cải thiện peak-damage tương tự. Ngược lại, rotation 25%-50% tăng return nhưng làm single-name damage weeks và max drawdown xấu rõ, nên V62 không ưu tiên rotation mạnh.

## Mục tiêu V62

V62 không đổi frozen monthly C3 selector. Nó chỉ sửa **research portfolio mechanics** và kiểm tra bridge giữa monthly canonical model với weekly preview.

### Exposure normalization

Tất cả policy V62:

- tái sử dụng realized cash thay vì giới hạn core budget ở một weekly contribution;
- target stock sleeve = 100% khi C3 `risk_on`, 50% khi `risk_off`;
- không leverage;
- symbol cap 15%;
- core có thể dùng tối đa 10 odd-lot buy orders/tuần để tiến về inverse-vol target;
- preview routing có thể để một phần target không được deploy nếu canonical holding đã breakdown.

### Safety policies

- `RECYCLE_NOADD20`;
- `RECYCLE_TRIM25_BREAK1`;
- `RECYCLE_AGE10_TRIM25_BREAK2`.

Trimmed symbol bị block re-buy trong cùng tuần. P1 monthly two-month outside-Top20 full exit vẫn giữ nguyên.

### Opportunity bridge

Một mã ngoài monthly canonical Top-10 có thể vào bridge nếu ở weekly Preview Top-5 và:

- persistent từ prior Preview Top-10 **hoặc** tăng tốc từ prior rank 6-20 ít nhất 3 bậc;
- volume ratio 5/20 >= 1.0;
- 5-session return <= 10%;
- distance MA20 <= 8%.

Sizing không còn lấy 5% của weekly contribution. V62 dùng 3% hoặc 5% NAV starter, tổng bridge sleeve tối đa 10% NAV. Nếu target budget nhỏ hơn giá 1 share, được phép mua đúng 1 share chỉ khi 1 share <= 5% NAV, vẫn nằm dưới aggregate tactical cap và symbol cap.

Bridge lot:

- promote thẳng thành core nếu monthly C3 Top-10 sau đó nhận nó;
- exit nếu age >= 15 sessions hoặc Preview rank >20;
- không round-trip khi đã promote.

V62 đo `early_capture_rate`: trong các monthly Top-10 entrants từng được bridge filter nhìn thấy trước tháng mới, bao nhiêu mã đã được sở hữu sớm trước khi canonical promotion xảy ra.

## Risk metrics mới

V62 giữ raw metrics để audit nhưng decision gate dùng mature risk window:

- week number >= 13;
- position count >= 5.

Primary stock-specific risk metric là weighted peak-to-current damage as NAV contribution, không phải unrealized loss tuần bootstrap.

Historical candidate gate yêu cầu đồng thời:

- return tốt hơn baseline tối thiểu 6/9 cells và median delta >0;
- Calmar tốt hơn tối thiểu 6/9;
- mature peak-tail tốt hơn tối thiểu 7/9 và median không xấu đi;
- median stock-exposure delta không lệch quá 5 điểm % so với recycle baseline;
- severe-cost return delta không âm;
- year-level return win rate >=55%.

Đây vẫn là historical robustness gate, **không** phải pristine OOS gate.

## Không được suy diễn

- August-2026 VPI không dùng để chọn threshold;
- former V60 holdout đã bị dùng, không còn independent holdout sạch;
- point-in-time universe, corporate actions, price basis và odd-lot order-book history vẫn chưa hoàn chỉnh;
- không cấp live capital, không tạo automatic live order, không thay model production.
