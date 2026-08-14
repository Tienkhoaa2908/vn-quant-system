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
- workstation results V70→V78, đặc biệt `v78_workstation_result_20260814.md`;
- `tai_lieu_dieu_phoi/v78_c3_tactical_terminal_contract.md`;
- `tai_lieu_dieu_phoi/v78_handoff.md`;
- V78 source/driver/bridge/installer/tests/runner/workflow/assets;
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

For first freeze floor date is `2026-08-15`; retroactive fills before floor are forbidden.

## 5. Current operating phase — V78 C3 tactical inside the approved local web

Current branch when this prompt was written:

`agent/v78-c3-tactical-terminal`

V78 is **not** a new champion research lane. It makes C3 operationally flexible intra-month.

Primary goals:

1. keep monthly C3 Top10 as core;
2. identify emerging leaders before month-end;
3. detect prior-month Top10 names that are currently damaging the portfolio;
4. use Ridge only as confirmation;
5. show fixed recent 6/12/18-month evidence for secondary overlays/models;
6. **add those results to the existing approved `VN Quant Local Workstation` UI, never replace/redesign it.**

## 6. V78 current preview

Current preview uses exact C3 components and current completed-month C3 weights.

Eligibility:

- close >= MA250;
- ADV20 >= 5bn VND;
- zero-volume60 <=5.

Important fail-closed rule: **every prior-month C3 Top10 stays visible even if it loses current eligibility**.

Persistent tactical preview state:

`du_lieu/v78-tactical-state/previews/`

Do not delete if exact L15 persistence is being evaluated.

## 7. Prior-month Top10 health and actual period drag

V78 retains V72 health semantics:

- R07: prior-month Top10 + drawdown20 <= -8%;
- R08: prior-month Top10 + drawdown60 <= -12%;
- current preview rank >15 or relative5 <= -2% also yields WATCH.

**R07/R08 are advisory only; no auto-sell.**

V78 additionally measures each prior-month Top10 directly:

- entry = first market open after monthly signal;
- mark = current close;
- `period_return = current close / entry open - 1`;
- benchmark = VNINDEX entry open -> current close;
- `period_relative_return = period_return - benchmark_return`.

Contract:

`NEXT_SESSION_OPEN_AFTER_MONTHLY_SIGNAL_TO_CURRENT_CLOSE_GROSS`

`dragging_current_period=true` only when both absolute return and benchmark-relative return are negative. Still no auto-sell.

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

No live order. No fake persistence.

## 9. First real V78 workstation result — observed 2026-08-14

Read `tai_lieu_dieu_phoi/v78_workstation_result_20260814.md` before interpreting V78.

Observed research artifact provenance:

- artifact HEAD `a53c7bbd62cd6ef4175364193d3e0bee9173a161`;
- store SHA unchanged `2959f8cce0c11e8e4186fcb49ae75bf7babf86b84afe64ca3b843a7470d58b1a`;
- capture day `2026-08-13`;
- source monthly signal `2026-07-31`;
- current-period tradable entry `2026-08-03`;
- risk_on=false.

Monthly Top10:

`VPI, MSB, HCM, VIC, GMD, LPB, STB, BAF, DHC, ACB`

Current preview Top10:

`MSB, HCM, TLG, LPB, BAF, DHC, STB, BWE, KDC, GMD`

Current-period dragging incumbents:

- VPI: period about `-4.71%`, alpha about `-5.89pp`, rank 1 -> current 13;
- VIC: period about `-3.75%`, alpha about `-4.93pp`, rank 4 -> current 14.

Emerging radar:

- TLG current preview rank 3;
- period about `+9.18%`;
- alpha about `+8.00pp`;
- relative5 about `+10.15%`;
- volume ratio about `1.79`;
- action `WATCH_EMERGING` because first V78 run had no prior-week V78 preview.

Exact L15 correctly remained inactive on first run.

## 10. Recent regime evidence already observed

Fixed 6/12/18 months; diagnostic only.

L15 delta vs frozen C3/no-overlay:

- 6m `+0.576pp`;
- 12m `+2.485pp`;
- 18m `+3.745pp`.

R08 delta:

- 6m `-1.312pp`;
- 12m `-0.943pp`;
- 18m `-3.005pp`.

Ridge delta vs C3:

- 6m `+10.431pp`;
- 12m `+12.964pp`;
- 18m `-8.335pp`.

Interpretation:

- L15 = useful tactical opportunity clue, still advisory;
- R08 = warning-only, not automatic trim;
- Ridge = useful recent-regime confirmation/radar, not champion;
- C3 stays main.

## 11. Critical UI rule — preserve the user-approved web

User supplied the actual workstation archive and explicitly confirmed that this web is already finished and approved.

Approved baseline:

- title: `VN Quant Local Workstation`;
- root: `vn_quant_local_system/`;
- frontend: `vn_quant_local_system/web/index.html` + existing versioned JS/CSS;
- backend: `vn_quant_local_system/src/vn_quant_local/webapp.py`;
- URL: `http://127.0.0.1:8787`;
- existing tabs/layout/features must remain intact.

**Do not revive or deploy `web_console_app_v78.py`, NiceGUI replacement UI, port 8089, or any separate V78 web.** That earlier direction was corrected and the replacement module was removed.

V78 web integration is additive only through:

- `src/he_thong_dinh_luong/local_workstation_v78_bridge.py`;
- `src/he_thong_dinh_luong/existing_web_v78_installer.py`;
- `web_extensions/v78/tactical_v78.js`;
- `web_extensions/v78/tactical_v78.css`.

Installer contract:

- backup existing `web/index.html` and `src/vn_quant_local/webapp.py` before first patch;
- idempotent narrow anchors;
- add a compact Tactical summary on Dashboard;
- add one `Tactical` tab before Docs;
- add read/refresh tactical API bridge to existing backend;
- existing `Chạy C3` refreshes tactical fail-soft;
- no global redesign;
- no credentials, holdings, account state, workstation DB, DNSE state, V77 state mutation.

Tactical tab shows:

- all prior-month Top10;
- current preview rank;
- period P&L, VNINDEX, alpha;
- drag marker;
- rel5/DD20/DD60;
- emerging leader radar;
- exact L15 state;
- Ridge confirmation;
- recent 6/12/18 evidence.

Stable tactical snapshot:

`vn_quant_local_system/data/v78-c3-tactical/`

## 12. Current V78 runner

Runner:

`scripts/run_v78_c3_tactical_terminal_gitbash.sh`

It must:

1. use canonical `.venv`;
2. compute current tactical + recent evidence;
3. publish stable tactical snapshot;
4. install additive Tactical extension into the approved existing web;
5. create web backup/audit;
6. preserve store SHA;
7. use/open existing `127.0.0.1:8787`;
8. never automatically kill a pre-existing old web process;
9. if restart is required, tell user to Ctrl+C old server then run `bash vn_quant_local_system/scripts/run_web_gitbash.sh`;
10. keep live orders false.

When a **post-integration** V78 ZIP arrives, review in this order:

1. branch/head/store SHA before/after;
2. V78 report and actual tactical outputs;
3. web integration report;
4. `existing_layout_replaced=false`;
5. `credentials_or_state_touched=false`;
6. backup directory exists on first patch;
7. existing web bridge imports successfully;
8. approved web remains port 8787;
9. no NiceGUI/8089 deployment;
10. `live_orders_allowed=false`.

The first research V78 ZIP at HEAD `a53c7...` validates tactical calculations but predates the approved-web integration correction; a new workstation run is required to verify the final web integration.

## 13. Data gates remain fail-closed

Known blockers remain until real evidence closes them:

- PIT HOSE membership lineage;
- price basis;
- corporate-action inventory;
- PIT sector master.

Paper/tactical diagnostics can run while gates are open. Canonical HOSE/promotion/live claims remain false.

## 14. GitHub-first

Any workstation code change:

GitHub branch -> self-review -> tests -> Linux/Windows CI -> verify remote HEAD -> then give user only `git fetch/switch/pull` + in-repo runner.

CI success is not workstation result.

Repository/artifact newer than this prompt wins.

---
