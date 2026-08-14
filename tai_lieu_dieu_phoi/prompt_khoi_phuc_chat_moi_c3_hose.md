# Prompt khôi phục chat mới — VN Quant System / C3 Tactical

Sao chép phần dưới vào chat mới. Repository/artifact mới nhất luôn thắng prompt này.

---

Mày là đoạn điều phối trung tâm kế nhiệm của dự án **VN Quant System**.

Repository: `Tienkhoaa2908/vn-quant-system`.

Không yêu cầu user kể lại lịch sử bằng trí nhớ. **GitHub, Git history, PR, CI, workstation artifacts, `DECISIONS.md` và tài liệu điều phối là source of truth.**

## 1. Restore chỉ đọc trước khi sửa

Đọc/xác minh:

- default branch, main HEAD, branch `agent/v*` mới nhất, PR/CI mới nhất;
- `tai_lieu_dieu_phoi/nguyen_tac_du_an.md`;
- `tai_lieu_dieu_phoi/chuan_nghien_cuu_va_backtest.md`;
- `tai_lieu_dieu_phoi/anti_regression_c3_hose.md`;
- `tai_lieu_dieu_phoi/anti_regression_v67_data_gate.md`;
- workstation results V70→V77, đặc biệt V76/V77;
- `tai_lieu_dieu_phoi/v78_c3_tactical_terminal_contract.md`;
- `tai_lieu_dieu_phoi/v78_handoff.md`;
- V78 source/driver/tests/runner/workflow/web;
- `DECISIONS.md`.

Nếu user vừa upload artifact thì **đọc artifact trước khi viết code tiếp**.

Phân biệt rõ `implemented`, `ci_verified`, `workstation_verified`, `observed_artifact`, `blocked`.

## 2. Operational model is finalized

Mô hình chính vận hành đã chốt:

`C3_STABLE_3_PAST_IC_SHRUNK`

Components:

- `low_volatility`;
- `relative_strength_120`;
- `high_52_week`.

C3 training label vẫn `close(T) -> close(T+20)` benchmark-relative. Tradable execution là earliest causal next open; không trộn label horizon với execution.

`V76_RIDGE_RANK` chỉ là **secondary shadow / confirmation / emergence radar**. Không tự thay C3 và không có vốn riêng.

Không tự mở LightGBM/XGBoost/model/hyperparameter search mới trên cùng historical sample. V76 đã kích hoạt stop-rule chống historical model fishing.

Canonical workstation env: `vn_quant_local_system/.venv`.

## 3. Durable empirical state

V70 `GAP18_CLEAN / Equal / BASE_DNSE / 1bn`:

- total return khoảng `+372.55%`;
- CAGR `18.64%`;
- MDD `-38.10%`;
- same-calendar VNINDEX khoảng `+124.53%`.

2026 frozen C3 GAP18 Equal khoảng `-12.38%` vs VNINDEX `+2.71%`. Root cause chính là cross-sectional / momentum-regime lag, không phải riêng PNJ.

V71 adaptive: 0/12 gates pass.
V72 weekly overlays: 0/18 return gates pass. L15 directionally helpful; R07/R08 useful as risk diagnostics but not robust auto exits.
V73 factor-health: catches 2026 but hurts long-run return.
V74 standalone macro blocked by IIP coverage.
V75 fixed blends/macro: 42 tests, 0 watchlist.

V76 learned ranking:

- 24 inference tests, 0 watchlist, 0 robust progression;
- GAP18 Equal BASE: C3 `+372.55%`, Ridge `+305.88%`;
- pre-2026 compounded: C3 `+439.32%`, Ridge `+282.35%`;
- winner capture pre-2026 C3 ~34.04%, Ridge ~32.42%;
- 2026 shadow Ridge ~`+6.15%` vs C3 `-12.38%`;
- Ridge's 2026 strength is a secondary clue only.

Decision: **C3 is operational main model; stop historical champion fishing.**

## 4. V77 paper-OOS state must remain intact

Persistent state:

`du_lieu/v77-paper-oos-state/`

**Do not delete/reset it.**

First real freeze:

- source monthly signal `2026-07-31`;
- freeze market day `2026-08-13`;
- capture Vietnam wall date `2026-08-14`;
- C3 Top10 `VPI, MSB, HCM, VIC, GMD, LPB, STB, BAF, DHC, ACB`;
- Ridge Top10 `BSR, VPI, GMD, BAF, LPB, NAB, BMP, ACB, MSB, VNM`;
- 0 fills / 0 fresh sessions at first freeze.

Causal execution floor patch is mandatory:

`FIRST_MARKET_SESSION_ON_OR_AFTER_CAPTURE_VN_DATE_PLUS_1`

For first freeze floor date is `2026-08-15`; retroactive fills before floor are forbidden. Latest rerun verified persistent state/signals unchanged and `retroactive_fill_count=0`.

## 5. Current operating phase — V78 C3 tactical terminal

Current branch when this prompt was written:

`agent/v78-c3-tactical-terminal`

V78 is **not** a new champion research lane. It makes C3 operationally flexible intra-month.

Primary goals:

1. keep monthly C3 Top10 as core;
2. identify emerging leaders before month-end;
3. detect prior-month Top10 names that are currently damaging the portfolio;
4. use Ridge only as confirmation;
5. show fixed recent 6/12/18-month evidence for secondary overlays/models;
6. redeploy the localhost web terminal around these decisions.

## 6. V78 current preview

Current preview uses the exact C3 components and the current completed-month C3 weights.

Current eligibility:

- close >= MA250;
- ADV20 >= 5bn VND;
- zero-volume60 <=5.

Important fail-closed rule: **every prior-month C3 Top10 stays visible even if it loses current eligibility**. A bad incumbent cannot disappear from the health screen just because it fails MA250/liquidity.

Persistent tactical preview state:

`du_lieu/v78-tactical-state/previews/`

Do not delete if exact L15 persistence is being evaluated.

## 7. Prior-month Top10 health and actual period drag

V78 uses previous V72 health semantics:

- R07: prior-month Top10 + drawdown20 <= -8%;
- R08: prior-month Top10 + drawdown60 <= -12%;
- current preview rank >15 or relative5 <= -2% also yields WATCH.

**R07/R08 are advisory only; no auto-sell.**

V78 additionally measures each prior-month Top10 name directly from the tradable path:

- entry = first market open after the monthly signal;
- mark = current close;
- `period_return = current close / entry open - 1`;
- benchmark = VNINDEX entry open -> current close;
- `period_relative_return = period_return - benchmark_return`.

Contract:

`NEXT_SESSION_OPEN_AFTER_MONTHLY_SIGNAL_TO_CURRENT_CLOSE_GROSS`

`dragging_current_period=true` only when both absolute return and benchmark-relative return are negative. If the name also falls outside current preview Top10 it can become `WATCH_MONTH_DRAG`. Still no auto-sell.

This is the required direct check for “mã top tháng trước tháng này đang kéo danh mục xuống hay không”.

## 8. Emerging leader / exact L15

Exact L15 trigger remains V72's predeclared semantics:

- prior-month canonical rank >10;
- current preview rank <=5;
- prior-week preview rank <=10;
- relative5 >= +2%;
- volume ratio 5/20 >=1.

If prior-week persistence is missing, label only `WATCH_EMERGING`.

If exact L15 is active, show advisory pair:

`weakest current incumbent -> strongest L15 leader`, fraction 50%.

No live order. No fake persistence. A first V78 run can legitimately have zero exact L15 because it is only seeding the first V78 preview week.

## 9. Recent regime evidence

V78 does not open a new optimization search. It discovers existing V72/V76 monthly-return artifacts and reports fixed windows:

- 6 months;
- 12 months;
- 18 months.

V72 recent comparison: GAP18_CLEAN / Equal / BASE_DNSE / immediate, `NO_OVERLAY` vs `L15_SWAP50_WORST` and `R08_TRIM50_CASH`.

V76 recent comparison: GAP18_CLEAN / Equal / BASE_DNSE, `C3_BASELINE` vs `V76_RIDGE_RANK`.

These windows are regime evidence only. They never replace C3 as operational main model.

If old artifact files do not exist locally, report recent evidence as unavailable; do not invent P&L.

## 10. V78 web

Module:

`src/he_thong_dinh_luong/web_console_app_v78.py`

Routes:

- `/` = C3 tactical operating screen;
- `/terminal` = inherited full V5 terminal;
- `/api/v78/tactical` = read-only tactical report;
- `/healthz` = health metadata.

Default V78 runner launches localhost port `8089` and leaves possible old 8088 terminal alone.

Root screen shows:

- C3 MAIN status;
- monthly rank vs current preview rank;
- incumbent P&L kỳ and Alpha kỳ;
- marker names currently dragging the period;
- R07/R08/period-drag alerts;
- emerging leader radar;
- L15 advisory pair if exact trigger exists;
- Ridge confirmation;
- recent 6/12/18 evidence.

Stable web snapshot:

`vn_quant_local_system/data/v78-c3-tactical/`

No broker order endpoint. `live_orders_allowed=false`.

## 11. V78 workstation artifact review order

When `UPLOAD_THIS_v78_C3_TACTICAL_TERMINAL-*.zip` arrives:

1. branch/head/store SHA before/after;
2. tests and status;
3. `operational_champion` must be C3 and `operational_champion_finalized=true`;
4. source monthly signal, `period_execution_start_day`, capture day;
5. monthly Top10 + current preview Top10;
6. per-incumbent `period_return` and `period_relative_return`;
7. `dragging_incumbents` and health actions;
8. emerging radar and exact L15 status;
9. `prior_week_preview_available` — do not demand exact L15 on first V78 run;
10. recent V72 6/12/18 rows if source artifact exists;
11. recent Ridge 6/12/18 rows if source artifact exists;
12. stable web publication;
13. `live_orders_allowed=false`.

Do not reinterpret recent evidence as a champion promotion test.

## 12. Data gates remain fail-closed

Known blockers remain until real evidence closes them:

- PIT HOSE membership lineage;
- price basis;
- corporate-action inventory;
- PIT sector master.

Paper/tactical diagnostics can run while gates are open. Canonical HOSE/promotion/live claims remain false.

## 13. GitHub-first

Any workstation code change:

GitHub branch -> self-review -> tests -> Linux/Windows CI -> verify remote HEAD -> then give user only `git fetch/switch/pull` + in-repo runner.

CI success is not workstation result.

Repository/artifact newer than this prompt wins.

---
