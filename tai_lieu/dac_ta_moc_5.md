# Đặc tả Mốc 5 — Chia vốn và danh mục mục tiêu

## 1. Trạng thái và nền

- Trạng thái: **đặc tả, chưa triển khai**.
- Repository: `Tienkhoaa2908/vn-quant-system`.
- Base `main` bắt buộc: `e59dca55fa37d88bd0e0f6e8e78bc6d282e4996b`.
- Nhánh: `dac_ta-moc-5`.
- Mốc 4 đã hoàn tất; không sửa hoặc chạy lại Mốc 4.
- PR của vòng này phải tiếp tục **Draft**, chưa Ready và chưa merge.

## 2. Mục tiêu

```text
ranking + target-selection Mốc 4
→ kiểm tra identity và point-in-time
→ eligible target set
→ inverse volatility
→ ticker cap 15% NAV
→ sector cap 25% NAV
→ cash target theo VNINDEX regime
→ iterative redistribution xác định
→ final target weights
→ proposed orders theo giá/lot
→ người dùng tự nhập lệnh thủ công vào SSI
```

Mốc 5 không thay đổi model, probability, score, rank hoặc target-selection flag của Mốc 4; không chứng minh hiệu quả đầu tư và không tự động giao dịch.

## 3. Phạm vi

Trong phạm vi:

- nhận publication bất biến của Mốc 4;
- đọc sector point-in-time, volatility history và VNINDEX regime;
- đọc NAV, cash và holdings hiện tại;
- tính inverse-volatility weights;
- áp cap `0.15` mỗi mã và `0.25` mỗi ngành;
- đặt cash target theo regime;
- tạo allocation proposal, proposed orders, validation report và manifest;
- deterministic publication, SHA-256 và provenance;
- kiểm thử ngoại tuyến.

Ngoài phạm vi:

- SSI API, credential, kết nối tài khoản, gửi/sửa/hủy lệnh;
- tự động giao dịch;
- Tier B, LightGBM hoặc deep learning;
- thay đổi model/ranking Mốc 4;
- short, margin, leverage;
- implementation Mốc 5 trong PR đặc tả này.

## 4. Bất biến

```text
0 <= final_target_weight_i <= 0.15
sector_weight_s <= 0.25
final_cash_weight >= cash_target
sum(final_target_weight_i) + final_cash_weight = 1
NAV > 0
cash_current >= 0
holding_quantity_i >= 0
không short
không leverage
```

Tiền và trọng số công bố dùng `Decimal`, không dùng binary float.

## 5. Input contract

Mọi input phải thuộc cùng:

```text
schema_version
portfolio_id
signal_run_id
signal_date
signal_created_at
source_manifest_sha256
```

Timestamp phải ISO-8601 có UTC offset; SHA-256 đúng 64 ký tự hex. Identity sai hoặc thiếu chặn toàn bộ proposal.

### 5.1 Ranking/selection từ Mốc 4

```text
signal_date,ticker,rank,probability,score,target_selection_flag,
model_id,fold_id,signal_run_id,ranking_manifest_sha256
```

- ticker viết hoa, duy nhất;
- rank là số nguyên dương và duy nhất;
- probability/score hữu hạn;
- selection flag là boolean thực sự;
- Mốc 5 không sắp hạng lại, không đổi score và không chọn top-k mới;
- rank chỉ dùng cho audit và ưu tiên proposed buy.

### 5.2 Sector point-in-time

```text
ticker,sector_code,effective_from,published_at,source,version
```

Tại ngày tín hiệu `T`:

```text
effective_from <= T
published_at <= signal_created_at
```

Chọn `effective_from` mới nhất, sau đó `published_at` mới nhất. Nếu vẫn hòa, sector rỗng hoặc thiếu sector cho mã selected/đang nắm giữ thì fail closed. Không dùng sector hiện tại áp ngược lịch sử.

### 5.3 Volatility history

```text
ticker,date,adjusted_close,price_basis,source,version
```

MVP khóa:

```text
daily_return_t = adjusted_close_t / adjusted_close_(t-1) - 1
volatility_60 = sample_std(60 daily returns)
inverse_vol_score = 1 / volatility_60
```

- dùng đúng 60 returns kết thúc tại `T`, tương ứng 61 close;
- cửa sổ theo lịch benchmark Mốc 4;
- không dùng dữ liệu sau `T`, không fill/nội suy/tìm phiên thay thế;
- price basis nhất quán;
- volatility hữu hạn và `> 0`;
- không annualize.

Mã mới không đủ lịch sử nhận `VOL_INSUFFICIENT_HISTORY`, bị loại khỏi eligible set và không được gán fallback. Nếu tập còn lại không khả thi dưới cap thì toàn bộ proposal bị chặn. NaN/Inf, volatility `<= 0`, trộn price basis hoặc cutoff sau `T` là blocker toàn run.

### 5.4 VNINDEX regime

```text
signal_date,benchmark,benchmark_close,benchmark_ma250,regime,
regime_computed_at,source,version
```

Chỉ chấp nhận:

```text
RISK_ON  khi VNINDEX close >= MA250
RISK_OFF khi VNINDEX close < MA250
```

`regime_computed_at <= signal_created_at`. Unknown/rỗng/mâu thuẫn close-MA250 làm run bị chặn.

Cash policy MVP:

```text
RISK_ON  → cash_target = 0.10
RISK_OFF → cash_target = 0.50
```

Không có neutral regime. Thay đổi mapping cần quyết định kiến trúc mới.

### 5.5 NAV, cash và holdings hiện tại

Snapshot:

```text
portfolio_id,account_snapshot_id,as_of,currency,nav,cash,
holdings_manifest_sha256
```

Holdings:

```text
portfolio_id,account_snapshot_id,ticker,quantity,market_value
```

Quy tắc:

- `currency = VND`;
- `nav > 0`, `cash >= 0`;
- quantity là integer không âm; mỗi ticker duy nhất;
- `as_of >= signal_created_at`;
- `abs(nav - cash - sum(market_value)) <= 1 VND`;
- identity phải khớp mọi dòng;
- holdings không selected có target 0;
- không tự suy ra ticker alias.

### 5.6 Giá tham chiếu và lot-size

Chỉ thuộc proposed-order layer:

```text
ticker,price_date,reference_price,price_type,lot_size,
published_at,source,version
```

- price hữu hạn, `> 0`;
- lot-size là integer dương;
- `price_date <= T`;
- thiếu/invalid price hoặc lot-size không được sinh quantity hành động;
- allocation vẫn có thể công bố với status `ALLOCATION_VALID_ORDERS_BLOCKED`;
- giá/lot không được làm thay đổi final target weights.

## 6. Staleness

```text
execution_date = đúng phiên benchmark kế tiếp sau T
max_signal_age_trading_sessions = 1
```

Signal stale khi proposal được tạo sau khi execution date kết thúc, bundle bị superseded, identity không còn canonical hoặc không xác định được phiên kế tiếp. Stale signal chặn toàn run; không có override thủ công trong MVP.

## 7. Allocation sequence

### 7.1 Eligible holdings

Tập ban đầu là các dòng `target_selection_flag is True`.

Một mã chỉ eligible khi identity, sector PIT, 60-return window, volatility và cutoff đều hợp lệ. Holdings hiện tại không selected hoặc bị controlled exclusion có target 0; chỉ được đề xuất giảm/đóng.

### 7.2 Raw inverse-volatility weights

```text
inverse_vol_score_i = 1 / volatility_60_i
raw_weight_i = inverse_vol_score_i / sum(inverse_vol_score_j)
```

Raw weights tổng đúng 1 trong phần cổ phiếu. Không nhân probability/score.

### 7.3 Caps và cash target

```text
ticker_cap = Decimal("0.15")
sector_cap = Decimal("0.25")
cash_target = Decimal("0.10") hoặc Decimal("0.50")
equity_budget = 1 - cash_target
```

Caps là tỷ trọng tuyệt đối của NAV, không phải tỷ trọng tương đối trong equity sleeve.

### 7.4 Feasibility

```text
max_equity_capacity =
  sum(min(sector_cap, ticker_count_in_sector * ticker_cap)
      for each sector)
```

Nếu `max_equity_capacity < equity_budget` thì `CONSTRAINTS_INFEASIBLE` và toàn run bị chặn. Không được tăng cap, giảm cash target, thêm mã không selected, gán sector giả hoặc giữ allocation gần đúng.

### 7.5 Iterative redistribution

Water-filling xác định:

1. `weight_i = 0`, `remaining = equity_budget`;
2. active set gồm ticker chưa chạm ticker cap và không thuộc sector đã chạm sector cap;
3. provisional increment:

```text
delta_i = remaining * inverse_vol_score_i / sum(inverse_vol_score_active)
```

4. constraint ratios:

```text
alpha_ticker_i = ticker_room_i / delta_i
alpha_sector_s = sector_room_s / sum(delta_i in active sector_s)
alpha = min(1, all positive ratios)
```

5. cộng `alpha * delta_i`;
6. freeze mọi ticker/sector cùng chạm cap;
7. lặp đến khi remaining bằng 0;
8. active set rỗng khi remaining dương là invariant failure.

Stable audit ordering:

```text
constraint type: ticker trước sector
constraint id: tăng dần
ticker: tăng dần
```

### 7.6 Deterministic residual cash

Internal Decimal precision tối thiểu 50.

```text
WEIGHT_QUANTUM = Decimal("0.000000000001")
```

Final ticker weights quantize xuống bằng `ROUND_FLOOR`. Sau đó:

```text
final_cash_weight = 1 - sum(published_ticker_weights)
rounding_residual_cash = final_cash_weight - cash_target
```

Residual không được phân lại. Tổng weights + cash phải đúng `Decimal("1")`, không dùng tolerance float.

## 8. Proposed-order layer

```text
target_value_i = nav * final_target_weight_i
target_quantity_i =
  floor(target_value_i / reference_price_i / lot_size_i) * lot_size_i
delta_quantity_i = target_quantity_i - current_quantity_i
```

- delta dương: proposed buy;
- delta âm: proposed sell;
- không sell vượt holdings, không tạo short;
- odd-lot không tự động xử lý; ghi `odd_lot_remainder` và `manual_review_required`;
- sells theo ticker tăng dần;
- buys theo rank tăng dần, hòa theo ticker tăng dần.

Dùng semantics phí/thuế/slippage Mốc 3 để ước tính pre-trade cash. Nếu projected cash âm, giảm buy theo thứ tự ngược ưu tiên, mỗi lần một lot; target weights không đổi và chênh lệch ghi `implementation_gap`. Nếu vẫn âm, order layer bị chặn.

Output bắt buộc có `MANUAL_ENTRY_ONLY`. Không endpoint, token, credential, HTTP call hoặc trạng thái đã khớp. Người dùng tự kiểm tra và tự nhập lệnh vào SSI.

## 9. Fail-closed rules

Blocker toàn allocation:

```text
SECTOR_PIT_MISSING
SECTOR_PIT_AMBIGUOUS
VOLATILITY_INVALID
VOLATILITY_CUTOFF_VIOLATION
PRICE_BASIS_MISMATCH
CONSTRAINTS_INFEASIBLE
STALE_SIGNAL
INPUT_IDENTITY_MISMATCH
HOLDINGS_IDENTITY_MISMATCH
NAV_RECONCILIATION_FAILED
NEGATIVE_CASH_INPUT
NEGATIVE_HOLDING
LEVERAGE_DETECTED
REGIME_INVALID
DUPLICATE_TICKER
NONFINITE_INPUT
```

Controlled exclusion duy nhất:

```text
VOL_INSUFFICIENT_HISTORY
```

Order-layer blockers:

```text
REFERENCE_PRICE_MISSING
REFERENCE_PRICE_INVALID
LOT_SIZE_MISSING
LOT_SIZE_INVALID
ORDER_CASH_INFEASIBLE
```

Blocked run vẫn công bố validation report và manifest bất biến, nhưng không công bố quantity có thể hành động.

## 10. Determinism và provenance

- tiền, volatility, weights và order values công bố bằng canonical Decimal strings;
- không `-0`, scientific notation, NaN hoặc Infinity;
- ticker/sector/validation rows stable order;
- JSON keys sắp xếp; CSV column order cố định; UTF-8, LF, không BOM;
- SHA-256 cho từng input/output canonical;
- cùng input/config tạo byte-for-byte output giống nhau.

Manifest tối thiểu:

```text
schema_version
allocation_run_id
portfolio_id
signal_run_id
signal_date
signal_created_at
proposal_created_at
base_git_commit
ranking_manifest_sha256
holdings_manifest_sha256
input_sha256[]
output_sha256[]
config_sha256
cash_policy
ticker_cap
sector_cap
volatility_contract
weight_quantum
status
warnings[]
limitations[]
```

Publication:

- staging cùng filesystem;
- flush/fsync file;
- manifest tạo cuối;
- atomic replace sang run directory mới;
- không ghi đè;
- failed/successful runs tách riêng;
- không sửa file sau publication.

## 11. Outputs bắt buộc

1. `allocation_inputs.json`;
2. `raw_weights.csv`;
3. `capped_weights.csv`;
4. `sector_exposure.csv`;
5. `cash_target.json`;
6. `final_target_weights.csv`;
7. `proposed_orders.csv`;
8. `validation_report.json`;
9. `manifest.json`.

Blocked publication tối thiểu có `allocation_inputs.json`, `validation_report.json`, `manifest.json`. `proposed_orders.csv` không được chứa action quantity khi order layer blocked.

## 12. Validation checks

```text
V_INPUT_IDENTITY
V_SIGNAL_FRESH
V_NO_LOOKAHEAD
V_SECTOR_PIT
V_VOLATILITY
V_NAV_RECONCILIATION
V_NO_NEGATIVE_POSITION
V_CONSTRAINT_FEASIBILITY
V_WEIGHT_SUM_EXACT
V_TICKER_CAP
V_SECTOR_CAP
V_CASH_FLOOR
V_NO_LEVERAGE
V_ORDER_PRICE
V_ORDER_LOT_SIZE
V_ORDER_CASH
V_DETERMINISTIC_ORDER
V_MANIFEST_HASHES
V_NO_SSI_INTEGRATION
```

Mỗi check ghi `PASS`, `FAIL` hoặc `NOT_RUN` cùng evidence. Không hạ `FAIL` thành warning.

## 13. Tests và acceptance criteria

Tests tối thiểu:

- volatility sample std 60 returns và cutoff T;
- inverse-vol raw weights;
- ticker/sector caps;
- multi-iteration water-filling và tie-break;
- Decimal rounding/residual cash;
- new ticker thiếu lịch sử;
- missing/ambiguous sector;
- invalid volatility;
- infeasible ticker/sector counts;
- stale signal;
- missing price/lot;
- holdings identity và NAV mismatch;
- cash/holding âm;
- lot sizing, odd-lot, sell bound và buy cash reduction;
- permutation input không đổi output;
- thêm dữ liệu sau T không đổi output;
- golden fixtures RISK_ON/RISK_OFF/infeasible;
- source/config scan chứng minh không SSI integration, LightGBM hoặc network.

Acceptance:

1. `sum(weights) + cash == Decimal("1")`.
2. Mọi ticker `<= 0.15`.
3. Mọi sector `<= 0.25`.
4. Không cash âm, position âm hoặc leverage.
5. Không look-ahead.
6. Deterministic byte-for-byte và SHA-256.
7. Infeasible constraints fail closed.
8. Invalid/missing sector fail closed.
9. Invalid volatility không được impute.
10. New ticker chỉ được controlled exclusion; run tiếp tục khi vẫn khả thi.
11. Missing price không sinh proposed quantity hành động.
12. Proposed orders có `MANUAL_ENTRY_ONLY`.
13. Không SSI API/SDK/credential/network/auto-trading.
14. Không Tier B hoặc LightGBM.
15. Không thay đổi Mốc 4.
16. Publication bất biến.
17. PR implementation tương lai phải đạt CI Ubuntu/Windows hiện hành.

## 14. Quyết định còn mở

Thuật toán allocation, cash policy, caps, volatility contract, rounding và fail-closed behavior đã khóa. Các data/config gates còn mở:

1. nguồn và taxonomy/version sector point-in-time canonical;
2. nguồn giá tham chiếu và lot-size point-in-time canonical;
3. giá trị phí, thuế, slippage cụ thể cho proposal vận hành;
4. nguồn lịch canonical xác nhận `execution_date`.

Không được tự suy đoán các điểm này trong implementation hoặc data run.
