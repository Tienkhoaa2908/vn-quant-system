# V79 — C3 tactical capital-action policy research contract

## Mục tiêu

V79 không tìm champion mới và không refit C3. `C3_STABLE_3_PAST_IC_SHRUNK` tiếp tục là stock-ranking core hàng tháng.

V79 trả lời cùng lúc bốn câu hỏi ở tầng phân bổ vốn giữa hai lần rebalance tháng:

1. khi nào incumbent C3 đang kéo danh mục đủ mạnh và đủ bền để giảm vốn;
2. khi nào mã ngoài Top10 tháng vượt exact opportunity gate để được cấp vốn;
3. vốn cho leader mới lấy từ cash hay tái chế từ incumbent yếu;
4. mức can thiệp 25%, 50% hay severe exit có cải thiện P&L/risk sau phí hay không.

Toàn bộ hướng trên phải chạy trong **một work package, một executable matrix, một workstation run**. Không yêu cầu user chạy riêng từng giả thuyết.

## Invariant

- champion: `C3_STABLE_3_PAST_IC_SHRUNK`;
- không mở lại model/hyperparameter search;
- monthly C3 Top10/rebalance vẫn là core;
- weekly tactical observation hình thành sau close;
- earliest execution = next market-session open;
- monthly rebalance precedence nếu trùng execution day;
- lot size 100;
- single-name cap 15%;
- không leverage;
- không broker order;
- research-only, promotion=false, live-orders=false;
- 2026 chỉ observed shadow/stress, không dùng chọn threshold/policy;
- PIT HOSE membership, price basis, corporate actions, PIT sector master vẫn fail-closed.

## Engine reuse

V79 reuse V68 causal weekly states, V70 execution primitives và V72 exact L15.

Ba anchor V72 không được copy/reimplement mà delegate thẳng vào V72 simulator:

- `R07_TRIM50_CASH`;
- `R08_TRIM50_CASH`;
- `L15_SWAP50_WORST`.

`NO_OVERLAY` cũng dùng V72/V70 baseline path. Baseline reconstruction drift so với V70 là hard failure.

## Direct incumbent drag

Tại mỗi weekly evaluation:

- period entry = first market open strictly after canonical monthly C3 signal;
- period mark = weekly evaluation close;
- benchmark = VNINDEX cùng entry open -> weekly close;
- `dragging_current_period=true` chỉ khi stock return <0 và benchmark-relative return <0.

Contract:

`NEXT_SESSION_OPEN_AFTER_MONTHLY_SIGNAL_TO_WEEKLY_EVALUATION_CLOSE_GROSS`

## Persistent deterioration

`DRAG_PERSIST` chỉ active nếu incumbent canonical Top10 và đồng thời:

- actual current-period drag=true;
- current preview rank >15;
- có real prior weekly preview;
- prior preview rank >10;
- relative5 <= -2%.

Không có prior preview => không trigger.

`SEVERE_DRAG` = `DRAG_PERSIST` cộng ít nhất một trong:

- current eligibility lost;
- DD20 <= -8%;
- DD60 <= -12%.

Exit 100% chỉ là research arm, không phải production rule.

## Emerging leader

Exact L15 giữ nguyên V72:

- canonical rank >10;
- current preview rank <=5;
- prior-week preview rank <=10;
- relative5 >= +2%;
- volume ratio 5/20 >=1.

Không đủ persistence => không L15.

## Policy matrix — một lần chạy

Baseline/anchors:

- `NO_OVERLAY`
- `R07_TRIM50_CASH`
- `R08_TRIM50_CASH`
- `L15_SWAP50_WORST`

Incumbent-cut:

- `DRAG_PERSIST_TRIM25_CASH`
- `DRAG_PERSIST_TRIM50_CASH`
- `SEVERE_DRAG_EXIT100_CASH`

Emerging-add:

- `L15_SWAP25_WORST`
- `L15_CASH_ADD25_SLOT`

Cash-add chỉ dùng cash thật trong simulated state, không bán core, không leverage. Nominal cap của arm này = 25% của 10% slot = 2.5% NAV trước execution/cap constraints.

Rotation:

- `DRAG_L15_ROTATE25`
- `DRAG_L15_ROTATE50`

Combined:

- `COMBINED50_CASHFALLBACK25`

Priority combined:

1. risk + L15 => rotate 50%;
2. risk nhưng không leader => trim 50% về cash;
3. leader nhưng không risk => cash-add chỉ nếu có idle cash thật và monthly regime risk_on;
4. không gate => no action.

## One-shot runner

`scripts/run_v79_tactical_capital_policy_gitbash.sh`

Runner tự làm:

1. branch/clean-tree/canonical-Python/store preflight;
2. compile + V72/V79 regression;
3. rebuild V68 causal weekly states;
4. reconstruct V70 frozen-C3 baseline;
5. chạy toàn bộ 12 policy;
6. EQUAL + INVOL60;
7. GROSS + BASE_DNSE + STRESS + SEVERE;
8. T2_NO_ADVANCE sensitivity;
9. 100M/1B/10B capital sensitivity;
10. pre-2026 inference + BH-FDR;
11. 2026 shadow only;
12. profit/family-ablation report;
13. verify market-store SHA unchanged;
14. bundle một ZIP gồm log/provenance/full outputs.

Không tách thành nhiều runner và không bắt user upload từng giả thuyết.

## Inference discipline

Primary selection cutoff: `2025-12-31`.

Mỗi nonbaseline policy so với `NO_OVERLAY` trên paired monthly periods trước 2026. Bắt buộc report mean/median delta, positive-month rate, block sign-flip p, block bootstrap CI, BH-FDR trong toàn bộ nonbaseline policies cùng variant+allocator, total-return/CAGR/MDD/p10-month delta và positive annual delta rate.

2026 không tham gia selection.

## Evidence bắt buộc

Artifact xuất monthly/annual/rolling returns, daily equity, exact trade ledger, tactical action ledger, missing-price events, modeled costs/tax/slippage, turnover, ADV20 participation, capital/T2/cost sensitivity, family ablation và 2026 shadow.

Không kết luận từ hit-rate hay vài mã hiện tại.

## Fail-closed interpretation

V79 chỉ được tạo diagnostic candidate/watchlist. Nó không auto-promote, không auto-sell, không auto-buy, không thay C3 và không đóng data-lineage gates. VPI/VIC/TLG August 2026 không được dùng tune rule.

## Workstation artifact

Success artifact:

`artifacts/UPLOAD_THIS_v79_TACTICAL_CAPITAL_POLICY-*.zip`

Review order: branch/head -> env -> store SHA before/after -> tests -> V68/V70 status -> baseline reconstruction -> policy completeness -> GAP18_CLEAN/Equal/BASE_DNSE profit -> inference/BH-FDR -> family ablation -> cost/T2/capital sensitivity -> action/ledger sanity -> 2026 used_for_selection=false -> promotion/live=false.
