# Chuẩn nghiên cứu và backtest VN Quant System

Tài liệu này là playbook bắt buộc cho mọi work package nghiên cứu C3/HOSE từ V70 trở đi. Chat mới phải đọc tài liệu này trước khi thiết kế nghiên cứu mới. Nếu một experiment không đi qua đủ các tầng liên quan dưới đây thì không được gọi là kết luận nghiên cứu hoàn chỉnh.

## 1. Mục tiêu tối ưu

Mục tiêu không phải tối đa hóa một metric predictive riêng lẻ. Mục tiêu là tạo **alpha danh mục sau cơ chế giao dịch thực tế**, có độ bền theo thời gian và đặc biệt không sụp đổ tương đối trong regime khó.

Ưu tiên theo thứ tự:

1. data correctness và causality;
2. alpha so với benchmark trên cùng lịch và cùng exposure contract;
3. drawdown/tail risk;
4. stability qua year/era/rolling windows;
5. turnover và cost drag;
6. operational feasibility;
7. chỉ sau đó mới tăng độ phức tạp model.

Một năm lỗ tuyệt đối không tự động làm model thất bại nếu benchmark cũng lỗ và model vẫn tạo alpha/risk-adjusted benefit. Ngược lại, **thị trường xấu không được dùng để bào chữa cho underperformance tương đối**. Năm 2026 đã được quan sát nên chỉ là stress/audit set, không được dùng để tune threshold.

## 2. Tầng A — data lineage trước sophistication

Mọi nghiên cứu phải audit:

- nguồn dữ liệu, hash, date coverage, symbol coverage;
- HOSE membership point-in-time;
- price basis/corporate actions;
- duplicate/conflict/revision;
- benchmark calendar;
- sector master point-in-time nếu dùng sector cap.

Thiếu PIT HOSE hoặc price basis không nhất thiết chặn diagnostic research, nhưng phải gắn `provisional` và chặn canonical claim/promotion.

Không dùng current universe áp ngược lịch sử. Không dùng Top-N/candidate snapshot làm training truth nếu local master history có thể dựng lại.

## 3. Tầng B — frozen champion và causal signal research

Champion mặc định: `C3_STABLE_3_PAST_IC_SHRUNK`.

C3 training label phải giữ nguyên:

`close(T) -> close(T+20)` benchmark-relative.

Tradable execution là contract riêng:

`signal after close(T) -> earliest entry open(T+1)`.

Không đổi C3 thành challenger chỉ vì package/model mới chạy được. Model mới chỉ được coi là challenger cho tới khi thắng C3 qua causal OOS + deep backtest + paper holdout.

Weekly protection/opportunity hypothesis phải predeclare. August 2026 và mọi period đã nhìn thấy không được dùng để đặt threshold.

## 4. Tầng C — matched control và dependence-correct inference

Không so hai unconditional historical means rồi gọi là incremental edge.

Leader signal phải so với comparator cùng tuần/cùng scope. Risk signal phải so với canonical peer control cùng tuần khi có thể.

Overlapping weekly observations không phải independent samples. Bắt buộc báo unique weeks, unique symbols, concentration và overlap.

Bootstrap dùng cho confidence interval không được tự gọi là null p-value. P-value cần null procedure hợp lệ như block sign-flip/permutation; finite-sample correction `(extreme+1)/(B+1)`; multiple testing correction áp trên p-value hợp lệ.

## 5. Tầng D — deep portfolio backtest bắt buộc

Sau signal/model research, mọi work package phải chạy deep backtest trước khi kết luận giá trị chiến lược.

### 5.1 Execution

- monthly/weekly signal hình thành sau close;
- trade sớm nhất ở next-session open;
- không dùng future substitute khi giá entry/exit thiếu;
- actual shares, không chỉ weight proxy;
- lot 100;
- cash ledger không âm;
- settlement sensitivity khi sale proceeds có thể không tái dùng ngay;
- missing target open -> để phần vốn đó ở cash;
- missing held sell open -> giữ vị thế và log blocker, không lấy giá tương lai.

### 5.2 Allocation

Ít nhất phải có frozen baseline và các policy predeclared. Với C3:

- equal weight baseline;
- inverse-volatility diagnostic;
- max 15%/symbol;
- cash/exposure policy theo regime phải báo actual/intended exposure;
- sector cap 25% chỉ enforce khi có PIT sector master; nếu chưa có phải ghi blocker.

Policy khác exposure không được so raw return đơn giản. Bắt buộc có exposure-matched benchmark/decomposition để tránh lặp exposure confounder V61.

### 5.3 Chi phí

Bắt buộc chạy tối thiểu:

- GROSS;
- BASE_DNSE;
- STRESS;
- SEVERE.

Frozen BASE research contract hiện hành:

- broker fee: 0 bps nếu contract local đang dùng chính sách cash fee-free;
- exchange fee: 2.7 bps mỗi chiều;
- sell tax: 10 bps;
- transfer fee: 0.3 VND/share;
- slippage: 5 bps mỗi chiều.

STRESS dùng 10 bps slippage, SEVERE dùng 20 bps, trừ khi một quyết định canonical mới thay contract.

Phải báo cost drag, turnover, ADV participation. Fixed slippage không được giả vờ là exact market impact.

### 5.4 P&L output bắt buộc

Mọi bundle/reply research phải có:

- total return;
- benchmark total return;
- total alpha;
- CAGR;
- max drawdown và benchmark drawdown;
- annual return + annual alpha;
- rolling 3/6/12-month alpha;
- Sharpe/Sortino/Calmar/Information Ratio khi đủ mẫu;
- positive month rate;
- beat-benchmark month rate;
- down-market alpha + beat rate;
- up-market alpha + beat rate;
- turnover;
- gross/base/stress/severe cost drag;
- capital/lot sensitivity;
- missing-price/feasibility events;
- equity curve và trade ledger.

Báo cáo phải nói rõ `gross`, `modeled-cost`, hay `exact cash ledger`. Không được dùng proxy rồi gọi là exact P&L.

## 6. Tầng E — bear/regime stress

Đặc biệt với 2026 và các regime xấu:

- đo strategy return, benchmark return, alpha;
- đo drawdown tương đối;
- tách stock-selection failure với exposure/regime-timing failure;
- xem rolling alpha trước và trong stress;
- xác định worst relative months;
- không tune trực tiếp trên stress slice đã quan sát.

Mục tiêu là thắng thị trường qua chu kỳ, kể cả khi absolute return âm trong bear market. Một policy giảm lỗ nhưng chỉ nhờ giảm exposure phải được đánh giá bằng exposure-matched benchmark.

## 7. Tầng F — macro lane tùy chọn, không thêm cho đủ feature

Chỉ thêm macro khi technical/portfolio attribution cho thấy còn failure mode có cơ chế kinh tế hợp lý.

Macro contract bắt buộc:

- nguồn chính thức trước: cơ quan thống kê, NHNN, Hải quan/nguồn nhà nước tương ứng;
- feature chỉ khả dụng sau **publication/release timestamp**, không dùng reference-month date như thể đã biết sớm;
- ưu tiên first release/vintage, không backfill revision vào quá khứ;
- lag publication conservatively nếu timestamp không đủ chính xác;
- predeclare feature family và sign/mechanism;
- purged walk-forward ablation: C3 vs C3+macro trên cùng folds và cùng backtest;
- macro phải tạo incremental OOS alpha hoặc tail protection sau chi phí; nếu không thì bỏ.

Candidate family hợp lý để nghiên cứu sau V70: CPI/core inflation, USD/VND trend, policy/interbank rates/liquidity, credit/money growth, trade balance/export growth. Không tự động đưa tất cả vào model.

## 8. Tầng G — promotion

Historical research, dù mạnh, không tự cấp quyền live.

Promotion cần:

1. data gates đủ;
2. causal OOS evidence;
3. deep backtest sau chi phí;
4. robustness qua year/era/rolling;
5. no single-symbol/single-era dependence;
6. future paper holdout;
7. explicit promotion decision.

## 9. One-shot work package

Workstation run mặc định phải gom các lane độc lập có thể chạy cùng lúc:

`data audit -> C3 -> matched controls -> profit reference -> deep backtest -> bear scorecard -> bundle`.

Không bắt người vận hành chạy nhiều probe nhỏ nếu một consolidated package có thể thu thập tất cả evidence an toàn.

Trước khi giao runner:

- compile;
- pure tests;
- synthetic end-to-end;
- Linux CI;
- Windows CI cho workstation-critical behavior;
- runner syntax/contract gates.

## 10. Cách đọc kết quả

Thứ tự báo cáo chuẩn:

1. **P&L / benchmark / alpha / drawdown**;
2. data/provenance gate;
3. signal/model findings;
4. deep backtest mechanics/cost/feasibility;
5. bear-market/2026 attribution;
6. robustness và statistical evidence;
7. blocker;
8. experiment tiếp theo.

Không đảo thứ tự để metric predictive đẹp che đi P&L kém.
