# Kiến trúc Mốc 5 — Chia vốn, danh mục mục tiêu và proposed orders

## 1. Phạm vi

Mốc 5 là pipeline ngoại tuyến, deterministic và fail closed. Nó chỉ đọc publication bất biến của Mốc 4 cùng snapshot point-in-time; không gọi SSI, không đọc tài khoản trực tiếp và không đặt lệnh.

PR này chỉ khóa kiến trúc và hợp đồng. Không sửa `src/`, `tests/`, workflow hoặc dependency.

## 2. Data flow và trust boundary

```text
Mốc 4 immutable ranking/selection
                |
sector PIT / volatility / regime
NAV / cash / holdings / price / lot
                |
                v
         Input Validation
 identity → PIT cutoff → reconciliation
                |
                v
        Allocation Core — pure
 eligibility → inverse vol → feasibility
 → caps → cash policy → water-filling
                |
                v
          Target Portfolio
 weights / sector exposure / cash
                |
                v
 Proposed-Order Adapter — non-executing
 value / lot / implementation gap
                |
                v
 Validation → SHA-256 → immutable publication
                |
                v
       người dùng tự nhập SSI
```

- Mốc 4 artifacts read-only;
- external snapshots không được tin trước validation;
- allocation core không biết SSI;
- order adapter không có quyền execution;
- publication append-only theo `allocation_run_id`.

## 3. Module plan dự kiến

```text
phan_bo_moc_5/
  hop_dong.py
  phong_ve.py
  danh_tinh.py
  sector_pit.py
  bien_dong.py
  eligibility.py
  che_do_thi_truong.py
  inverse_volatility.py
  gioi_han.py
  tai_phan_bo.py
  danh_muc_muc_tieu.py
  lenh_de_xuat.py
  kiem_tra.py
  cong_bo.py
  runner.py
  dong_lenh.py
  __main__.py
```

Đây là boundary dự kiến, không phải implementation trong PR đặc tả.

## 4. Cấu hình khóa

```text
ticker_cap = Decimal("0.15")
sector_cap = Decimal("0.25")
cash_target_risk_on = Decimal("0.10")
cash_target_risk_off = Decimal("0.50")
volatility_return_count = 60
weight_quantum = Decimal("0.000000000001")
max_signal_age_trading_sessions = 1
currency = "VND"
manual_entry_only = true
```

Các giá trị này không được CLI override trong MVP. Thay đổi cần quyết định kiến trúc mới.

## 5. Core records

```text
AllocationBundle
  identity
  ranking_rows
  sector_records
  volatility_rows
  regime_snapshot
  portfolio_snapshot
  holding_rows
  order_reference_rows
  config

EligibleCandidate
  ticker, rank, sector, volatility, inverse_vol_score

AllocationState
  ticker_weights, sector_weights
  remaining_equity
  active/frozen tickers and sectors
  iteration events

FinalTarget
  ticker, sector, target_weight, target_value

ProposedOrder
  ticker, side, current/target/proposed quantity
  reference_price, lot_size
  estimated_notional/cost, projected_cash
  implementation_gap
```

Public money/weight fields là Decimal hoặc canonical Decimal string; không dùng float.

## 6. State machine

```text
CREATED
→ INPUTS_LOADED
→ IDENTITY_VALIDATED
→ PIT_VALIDATED
→ ELIGIBILITY_RESOLVED
→ FEASIBILITY_VALIDATED
→ ALLOCATION_COMPUTED
→ ALLOCATION_VALIDATED
→ ORDERS_PROPOSED
→ PUBLICATION_VALIDATED
→ PUBLISHED
```

Failure:

```text
bất kỳ state trước PUBLISHED
→ BLOCKED
→ FAILED_PUBLICATION_VALIDATED
→ FAILED_PUBLISHED
```

Order-only failure:

```text
ALLOCATION_VALIDATED
→ ORDERS_BLOCKED
→ PUBLICATION_VALIDATED
→ PUBLISHED
```

Không retry trong cùng `allocation_run_id`.

## 7. Adapter contracts

### 7.1 Mốc 4 adapter

Chỉ đọc signal, ticker, rank, probability/score, selection flag, model/fold identity và manifest hash. Không fit model, đổi rank, đổi selection hoặc chọn top-k.

### 7.2 Sector PIT adapter

Lookup:

```text
effective_from <= signal_date
published_at <= signal_created_at
```

Sort `effective_from desc`, rồi `published_at desc`. Hòa còn lại là ambiguous blocker.

### 7.3 Volatility adapter

Join theo benchmark calendar. Cần đúng 61 close/60 returns kết thúc tại T. Không fill. Lịch sử ngắn tạo controlled exclusion; lỗi nội dung/cutoff/price basis tạo blocker.

### 7.4 Portfolio adapter

Reconcile:

```text
abs(nav - cash - sum(market_value)) <= 1 VND
```

Khóa portfolio/snapshot identity trước khi join ticker. Không alias mapping ngoài contract.

### 7.5 Order reference adapter

Tách khỏi allocation core. Missing price/lot không được fallback và không được làm đổi target weights.

## 8. Allocation core

Core là pure function:

```text
same canonical inputs + same config
→ same canonical allocation result
```

Clock được inject từ boundary; core không đọc file, environment, network hoặc credential.

### 8.1 Eligibility

Kết quả gồm:

```text
eligible_targets
controlled_exclusions
run_blockers
```

Chỉ `VOL_INSUFFICIENT_HISTORY` là controlled exclusion.

### 8.2 Inverse volatility

Dùng Decimal precision tối thiểu 50:

```text
score_i = 1 / vol_i
raw_i = score_i / sum(score)
```

### 8.3 Feasibility

Tính exact upper bound theo số ticker trong từng sector trước khi allocation. Không tạo partial allocation rồi mới downgrade thành extra cash.

### 8.4 Water-filling

Mỗi iteration công bố:

```text
iteration
remaining_before
active_tickers
provisional_deltas
binding_alpha
binding_constraints
increments
remaining_after
```

Freeze tất cả ticker/sector cùng chạm. Guard:

```text
max_iterations <= eligible_count + sector_count + 1
```

Vượt guard là invariant failure.

### 8.5 Rounding

Internal precision cao; public weights `ROUND_FLOOR` theo quantum. Cash hấp thụ toàn bộ rounding residual để không vượt cap.

## 9. Sector exposure

Output phải có:

```text
sector
eligible_ticker_count
raw_equity_share
raw_nav_exposure_at_equity_budget
final_nav_exposure
sector_cap
headroom
binding
```

Phải đủ evidence audit redistribution, không chỉ aggregate cuối.

## 10. Current holdings và target-zero

Universe của order layer:

```text
eligible target tickers ∪ current holding tickers
```

- holding không selected: target 0;
- selected nhưng controlled exclusion: target 0;
- current holding thiếu sector PIT: block;
- không holding và target 0: không order;
- sell không được vượt quantity.

## 11. Proposed-order adapter

### 11.1 Boundary

Adapter chỉ tạo candidate instruction; không exchange fill, không settlement tracking, không trạng thái accepted.

### 11.2 Lot sizing

```text
target_qty =
 floor(target_value / reference_price / lot_size) * lot_size
```

Ghi `lot_sized_value`, `absolute_gap`, `weight_gap`, odd-lot remainder.

### 11.3 Cash simulation

Tái sử dụng semantics Mốc 3:

- sells trước buys;
- sells ticker tăng;
- buys rank tăng/ticker tăng;
- fee/tax/slippage từ config đã phê duyệt;
- cash không âm;
- không bán quá holdings.

Nếu giảm buys, ghi đầy đủ reduction events. Final target weights không đổi.

### 11.4 Manual-only guard

- không SSI SDK;
- config không có SSI endpoint/account/token;
- không HTTP client trong package M5;
- output `MANUAL_ENTRY_ONLY`;
- CLI không có `submit`, `place`, `cancel`, `sync_account`.

## 12. Failure architecture

Severity:

```text
BLOCKER
CONTROLLED_EXCLUSION
ORDER_BLOCKER
WARNING
INFO
```

Không dùng warning cho identity, PIT, constraint, negative cash hoặc leverage.

No silent downgrade:

- missing sector không thành `OTHER`;
- missing volatility không thành median;
- missing price không thành zero;
- infeasible budget không thành extra cash;
- blocked run không thành technical success.

Failed publication:

```text
allocation_runs/failed/<allocation_run_id>/
  allocation_inputs.json
  validation_report.json
  manifest.json
```

Không chứa action quantity.

## 13. Deterministic serialization

CSV:

- UTF-8, LF, header/column order cố định;
- stable rows;
- Decimal string cố định;
- empty là chuỗi rỗng, không `nan`.

JSON:

- keys sort;
- Decimal thành string;
- timestamp canonical;
- không NaN/Infinity;
- LF cuối file.

Hash sau canonical serialization, trước publication.

## 14. Publication topology

```text
allocation_runs/
  successful/<allocation_run_id>/
    allocation_inputs.json
    raw_weights.csv
    capped_weights.csv
    sector_exposure.csv
    cash_target.json
    final_target_weights.csv
    proposed_orders.csv
    validation_report.json
    manifest.json
  failed/<allocation_run_id>/
    allocation_inputs.json
    validation_report.json
    manifest.json
```

`ALLOCATION_VALID_ORDERS_BLOCKED` vẫn là allocation success nhưng proposed orders không có action quantity và manifest phải ghi rõ.

## 15. Validation architecture

Bốn lớp:

1. input/schema;
2. identity/PIT;
3. allocation invariants;
4. order/publication invariants.

Mỗi check có status, observed value, expected relation và evidence hash. Không hạ `FAIL` thành warning.

## 16. Test architecture

Fixture matrix tối thiểu:

- 8 ticker/4 sector RISK_ON feasible;
- 4 ticker/2 sector RISK_OFF feasible;
- low-vol ticker chạm 15%;
- sector chạm 25%;
- nhiều constraint cùng chạm;
- new ticker thiếu history;
- missing sector;
- infeasible 5 ticker/1 sector;
- stale signal;
- missing price;
- odd-lot holding;
- buy cash reduction;
- duplicate và identity mismatch.

Metamorphic tests:

- shuffle rows không đổi output;
- cùng instant với timezone representation khác không đổi output;
- thêm post-cutoff data không đổi output;
- rerun Ubuntu/Windows cho cùng canonical bytes.

Negative capability tests:

- không network client;
- không SSI env/credential;
- không command gửi lệnh;
- không LightGBM;
- không mutate M4 artifacts.

## 17. CLI contract dự kiến

```text
python -m phan_bo_moc_5 de_xuat \
  --ranking <path> \
  --sector-pit <path> \
  --volatility-history <path> \
  --regime <path> \
  --portfolio-snapshot <path> \
  --holdings <path> \
  --order-reference <path> \
  --output-root <path>
```

Local files only. Exit nonzero khi allocation `BLOCKED`. Trường hợp orders blocked phải ghi rõ không có action order. Không có SSI subcommand.

## 18. Acceptance gate

Implementation tương lai không được merge nếu thiếu:

- M4 adapter không mutate ranking;
- exact Decimal sum;
- ticker/sector caps;
- feasibility fail closed;
- PIT/no-look-ahead tests;
- deterministic byte hashes;
- negative cash/leverage guards;
- order-layer separation;
- manual-only guard;
- no SSI integration;
- immutable publication;
- Ubuntu/Windows CI.

## 19. Quyết định vận hành còn mở

- sector PIT source/taxonomy canonical;
- price và lot-size source canonical;
- execution calendar source canonical;
- fee/tax/slippage values cho proposal vận hành.

Các source/config này phải được đoạn 00 phê duyệt riêng. Allocation core không phụ thuộc vendor.
