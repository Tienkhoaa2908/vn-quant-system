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

Emerging leader exact L15:

- prior-month rank >10;
- current preview rank <=5;
- prior-week preview rank <=10;
- relative5 >=2%;
- volume ratio 5/20 >=1.

Without prior-week persistence, label only `WATCH_EMERGING`. With exact trigger, show advisory pair: weakest incumbent by current preview -> strongest L15 leader, 50% fraction, same V72 semantics. Still no live order.

## Recent evidence

V78 does not rerun a new model search. It discovers existing local V72/V76 monthly-return artifacts and reports fixed recent windows 6/12/18 months.

If old artifact files are not present locally, recent cards are explicitly unavailable but live tactical preview still runs. Do not invent recent P&L.

## Web

New web module:

`src/he_thong_dinh_luong/web_console_app_v78.py`

Root `/` = tactical screen. `/terminal` = inherited full V5 terminal. API `/api/v78/tactical` is read-only. No trade endpoint.

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
3. source monthly signal/capture day/current preview;
4. prior-month Top10 health table;
5. exact L15 trigger and prior-week persistence availability;
6. recent 6/12/18 V72 evidence if found;
7. recent 6/12/18 Ridge evidence if found;
8. web snapshot publication;
9. live_orders_allowed=false.

A first V78 run can have no exact L15 because there is no prior-week V78 preview yet. That is correct; it must not fabricate persistence.

## No regression

V78 must not:

- replace C3 based on recent windows;
- re-open LightGBM/XGBoost/hyperparameter fishing;
- auto-sell R07/R08 names;
- call an emerging name L15 without persistence+relative+volume conditions;
- hide a weak prior-month Top10 because current eligibility failed;
- mutate/reset V77 paper evidence;
- enable live broker orders.
