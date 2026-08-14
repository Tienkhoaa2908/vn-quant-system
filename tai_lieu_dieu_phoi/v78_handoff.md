# V78 handoff — C3 tactical operating terminal

## Current decision

C3 is finalized as the operational main model:

`C3_STABLE_3_PAST_IC_SHRUNK`

No V78 champion search is allowed. `V76_RIDGE_RANK` remains shadow confirmation/emergence radar only.

V78 responds to the operational gap identified after V77: monthly C3 remains the portfolio core, while an advisory intra-month layer watches for emerging winners and deteriorating prior-month Top10 incumbents.

Read first:

1. `tai_lieu_dieu_phoi/v76_workstation_result_20260814.md`;
2. `tai_lieu_dieu_phoi/v77_workstation_result_20260814.md`;
3. `tai_lieu_dieu_phoi/v78_c3_tactical_terminal_contract.md`;
4. this handoff;
5. V78 source/driver/tests/runner/workflow.

## V78 branch

`agent/v78-c3-tactical-terminal`

It was branched from the latest V77 result-doc state, preserving V77 paper state semantics. V77 persistent workstation state remains:

`du_lieu/v77-paper-oos-state/`

Do not delete it.

V78 adds separate tactical persistence:

`du_lieu/v78-tactical-state/previews/`

Do not delete this if intra-month L15 persistence is being evaluated; prior-week preview is part of the exact L15 trigger.

## Operational semantics

Monthly C3 Top10 stays core. Current-day preview uses exact C3 components and the current completed-month C3 weights.

Incumbent health:

- R07 DD20 <= -8% => WATCH/health alert;
- R08 DD60 <= -12% => stronger RISK_ALERT_R08;
- current preview rank >15 or relative5 <= -2% => WATCH;
- no auto-sell from these health flags.

Important fail-closed behavior: a prior-month Top10 symbol remains visible even when it loses current eligibility. It cannot disappear from the health table merely because current MA250/liquidity eligibility fails.

### Actual current-period incumbent performance

V78 now measures each prior-month Top10 name on the tradable path instead of inferring damage only from rank:

`monthly signal close -> next actual session open entry -> current close mark`

For every incumbent it reports:

- `period_entry_day`;
- `period_return`;
- `period_benchmark_return` using VNINDEX entry open -> current close;
- `period_relative_return`.

Metric contract:

`NEXT_SESSION_OPEN_AFTER_MONTHLY_SIGNAL_TO_CURRENT_CLOSE_GROSS`

`dragging_current_period=true` requires both absolute period return < 0 and benchmark-relative period return < 0. When such a name has also fallen outside current preview Top10, it may be labeled `WATCH_MONTH_DRAG`. Still advisory only; no automatic sell.

This is the direct answer to whether a high-ranked prior-month name is currently pulling the portfolio down.

## Emerging leader exact L15

- prior-month rank >10;
- current preview rank <=5;
- prior-week preview rank <=10;
- relative5 >=2%;
- volume ratio 5/20 >=1.

Without prior-week persistence, label only `WATCH_EMERGING`. With exact trigger, show advisory pair: weakest incumbent by current preview -> strongest L15 leader, 50% fraction, same V72 semantics. Still no live order.

A first V78 run normally has no prior V78 week and therefore cannot honestly produce an exact L15 persistence trigger. That first preview seeds the tactical state; subsequent prior-week snapshots make exact L15 possible.

## Recent evidence

V78 does not rerun a new model search. It discovers existing local V72/V76 monthly-return artifacts and reports fixed recent windows 6/12/18 months.

- V72: GAP18_CLEAN / Equal / BASE_DNSE / immediate, `NO_OVERLAY` vs L15 and R08.
- V76: GAP18_CLEAN / Equal / BASE_DNSE, `C3_BASELINE` vs `V76_RIDGE_RANK`.

If old artifact files are not present locally, recent cards are explicitly unavailable but current tactical preview still runs. Do not invent recent P&L.

These windows are regime evidence only. They do not replace C3 as operational main model.

## Web

New web module:

`src/he_thong_dinh_luong/web_console_app_v78.py`

Root `/` = tactical screen. `/terminal` = inherited full V5 terminal. API `/api/v78/tactical` is read-only. No trade endpoint.

The tactical page shows:

- C3 MAIN status;
- monthly Top10 and current preview rank;
- actual current-period P&L and alpha per incumbent;
- marker for names currently dragging the period;
- R07/R08/period-drag alerts;
- emerging leader radar;
- exact L15 advisory pair when causal persistence exists;
- Ridge confirmation;
- fixed recent 6/12/18 evidence.

Stable web files are published by runner to:

`vn_quant_local_system/data/v78-c3-tactical/`

Default local port from V78 runner is 8089, so it does not need to kill/replace a possibly-running older terminal on 8088.

## Workstation runner

`scripts/run_v78_c3_tactical_terminal_gitbash.sh`

The runner:

- verifies canonical `.venv`;
- pins/validates sklearn 1.9.0 and NiceGUI 3.14.0;
- compiles/tests V78;
- reads the existing V77 freeze;
- computes current C3 tactical preview;
- measures incumbent next-open-to-current-close performance;
- persists preview state;
- summarizes recent V72/V76 evidence if artifacts exist;
- publishes stable web snapshot;
- bundles upload artifact;
- launches localhost tactical web on port 8089 by default.

Set `V78_LAUNCH_WEB=0` only when a non-interactive run is desired.

## Result interpretation

The workstation artifact must be read in this order:

1. provenance and store SHA before/after;
2. operational champion must be C3 and finalized=true;
3. source monthly signal, tradable period entry day and capture day;
4. prior-month Top10 actual `period_return` / `period_relative_return`;
5. `dragging_incumbents` and health actions;
6. current preview Top10 and emerging radar;
7. exact L15 trigger and prior-week persistence availability;
8. recent 6/12/18 V72 evidence if found;
9. recent 6/12/18 Ridge evidence if found;
10. web snapshot publication;
11. `live_orders_allowed=false`.

## No regression

V78 must not:

- replace C3 based on recent windows;
- re-open LightGBM/XGBoost/hyperparameter fishing;
- auto-sell R07/R08/period-drag names;
- call an emerging name L15 without persistence+relative+volume conditions;
- hide a weak prior-month Top10 because current eligibility failed;
- mutate/reset V77 paper evidence;
- enable live broker orders.
