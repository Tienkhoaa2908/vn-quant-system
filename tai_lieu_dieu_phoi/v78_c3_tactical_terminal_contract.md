# V78 — C3 operational tactical terminal contract

## Quyết định vận hành

`C3_STABLE_3_PAST_IC_SHRUNK` được chốt là **mô hình chính vận hành**. V78 không mở lại historical champion search.

`V76_RIDGE_RANK` chỉ là secondary shadow/confirmation/emergence radar. Không được tự thay C3, không có vốn riêng, không tự sinh lệnh thật.

## Vấn đề V78 giải quyết

Monthly C3 Top10 không đủ linh hoạt cho hai tình huống intra-month:

1. mã mới tăng relative performance mạnh trước khi hết tháng nhưng chưa nằm trong Top10 tháng trước;
2. mã nằm Top10 tháng trước suy yếu mạnh trong tháng hiện tại và có thể kéo danh mục đi xuống.

V78 thêm **tactical advisory layer**, không thay monthly C3 core.

## Current preview

Current preview dùng đúng ba component C3:

- `low_volatility`;
- `relative_strength_120`;
- `high_52_week`.

Trọng số dùng trọng số C3 của completed monthly signal hiện hành. Current-day eligibility giữ cùng contract:

- close >= MA250;
- ADV20 >= 5 tỷ VND;
- zero-volume60 <= 5.

Preview rank chỉ xếp các mã currently eligible. Tuy nhiên **mọi prior-month C3 Top10 vẫn phải hiện trong health table kể cả khi hiện tại mất eligibility**. Không được để một incumbent xấu biến mất khỏi màn hình vì fail filter.

## Incumbent health + actual current-period drag

Giữ semantics V72 đã nghiên cứu:

- R07: prior-month Top10 và drawdown20 <= -8%;
- R08: prior-month Top10 và drawdown60 <= -12%.

V78 dùng R07/R08 làm `WATCH` / `RISK_ALERT_R08`.

**Không auto-sell theo R07/R08.** V72 cho thấy các trim này có thể giảm cú April 2026 nhưng làm full-2026/lịch sử kém hơn ở nhiều sensitivity scope.

Ngoài R07/R08, prior-month Top10 cũng `WATCH` nếu current preview rank rơi >15 hoặc relative5 <= -2%. Đây là operating-health label, không phải rule tự giao dịch.

Quan trọng hơn, V78 không chỉ suy đoán từ rank/drawdown. Với từng prior-month C3 Top10, nó đo trực tiếp:

- `period_entry_day` = phiên thị trường đầu tiên sau completed monthly signal;
- `period_return` = current close / entry open - 1;
- `period_benchmark_return` = VNINDEX current close / VNINDEX entry open - 1 trên cùng calendar;
- `period_relative_return` = strategy return - benchmark return.

Contract của metric này là:

`NEXT_SESSION_OPEN_AFTER_MONTHLY_SIGNAL_TO_CURRENT_CLOSE_GROSS`

Một incumbent được gắn `dragging_current_period=true` khi đồng thời:

- `period_return < 0`;
- `period_relative_return < 0`.

Nếu incumbent đang kéo xuống và current preview rank đã rơi ngoài Top10, V78 có thể gắn `WATCH_MONTH_DRAG`. Đây vẫn là cảnh báo; **không auto-sell**.

Mục tiêu là trả lời trực tiếp câu hỏi: mã Top cao tháng trước có đang thực sự làm giảm NAV và thua VNINDEX trong tháng hiện tại hay không.

## Emerging leader / L15

Exact L15 trigger giữ nguyên V72:

- prior-month canonical rank >10;
- current preview rank <=5;
- prior-week preview rank <=10;
- relative5 >= +2%;
- volume ratio 5/20 >=1.

Nếu thiếu prior-week persistence thì chỉ `WATCH_EMERGING`, không được gọi L15 swap.

Nếu có exact L15 leader, V78 chọn:

- strongest leader theo preview rank/score;
- worst incumbent theo current preview rank/score;
- hiển thị advisory `L15_SWAP_OUT_CANDIDATE -> L15_SWAP_IN_CANDIDATE`, fraction 50% theo V72.

Đây vẫn là advisory; web không gửi lệnh.

V78 lưu current preview vào persistent state:

`du_lieu/v78-tactical-state/previews/`

Prior-week persistence lấy snapshot gần nhất thuộc ISO week trước. Không xóa state nếu muốn L15 persistence có ý nghĩa.

## Recent regime evidence

Thay vì mở model search mới, V78 đọc các monthly-return artifact đã tồn tại của V72/V76 và báo cố định:

- 6 tháng gần nhất;
- 12 tháng gần nhất;
- 18 tháng gần nhất.

V72 recent cards: frozen C3/no-overlay vs L15 và R08, GAP18_CLEAN, Equal, BASE_DNSE, immediate.

V76 recent cards: `C3_BASELINE` vs `V76_RIDGE_RANK`, GAP18_CLEAN, Equal, BASE_DNSE, nếu monthly artifact local còn tồn tại.

Không chọn cửa sổ sau khi nhìn kết quả; luôn báo đủ 6/12/18 khi data đủ. Đây chỉ là **regime evidence**, không thay long-run champion evidence.

## Existing approved web is frozen as the UI baseline

User đã xác nhận web local hiện hữu trong `vn_quant_local_system/` là giao diện đã hoàn thiện và được duyệt về trải nghiệm. V78 **không được thay giao diện này bằng web/NiceGUI mới**.

Baseline đã quan sát từ workstation archive:

- app: `VN Quant Local Workstation`;
- localhost: `http://127.0.0.1:8787`;
- static UI: `vn_quant_local_system/web/index.html` + các JS/CSS versioned hiện hữu;
- backend: `vn_quant_local_system/src/vn_quant_local/webapp.py`;
- baseline local package có data-integrity V55 semantics.

Known uploaded baseline hashes chỉ dùng để audit/diagnostic, không phải lý do ghi đè:

- `web/index.html`: `c4b26ce2d59cd92c1f2c2d1985eab34e7f9bf260f4562eed9de94476a461b1f5`;
- `src/vn_quant_local/webapp.py`: `99d1ec1ef6347280094c35e6ec737a77489078b2f909822eea4d35342096cc78`.

V78 integration phải **additive**:

- giữ nguyên layout/tabs/chức năng cũ;
- thêm `tactical_v78.js` và `tactical_v78.css` với CSS scoped;
- thêm một tab `Tactical` và một summary panel nhỏ ở Dashboard;
- thêm API read/refresh tactical hẹp vào backend cũ;
- `Chạy C3` có thể refresh tactical fail-soft, không được làm hỏng C3/web nếu tactical unavailable;
- backup `index.html` và `webapp.py` trước lần patch đầu;
- installer idempotent;
- tuyệt đối không đọc/ghi/xóa credentials, holdings, workstation SQLite, DNSE state hoặc V77 paper state.

Separate `web_console_app_v78.py`/port 8089 không còn là deployment contract và phải bị loại khỏi runner.

## Nội dung mới được thêm vào web cũ

Tab/panel Tactical hiển thị:

- C3 MAIN và current market regime;
- toàn bộ prior-month Top10, không chỉ mã đang cảnh báo;
- current preview rank;
- **P&L kỳ và Alpha kỳ của từng incumbent từ tradable next-open đến close hiện tại**;
- marker mã đang kéo xuống;
- leader intra-month / `WATCH_EMERGING`;
- exact L15 pair nếu có;
- Ridge confirmation;
- recent 6/12/18 backtest evidence C3 vs L15/R08/Ridge.

Stable snapshot vẫn ở:

`vn_quant_local_system/data/v78-c3-tactical/`

Web đọc/refresh qua bridge của repository nhưng tiếp tục phục vụ trên UI cũ tại `127.0.0.1:8787`.

## Safety

- no live orders;
- no broker order endpoint;
- no automatic champion replacement;
- no automatic R07/R08/period-drag sell;
- no L15 swap label nếu thiếu exact trigger;
- existing approved web không bị redesign/thay thế;
- existing credentials/state không được touched bởi installer;
- V77 paper state không bị sửa/xóa;
- data-lineage gates vẫn giữ fail-closed cho canonical/promotion/live.
