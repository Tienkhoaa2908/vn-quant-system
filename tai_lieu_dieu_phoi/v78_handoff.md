# V78 handoff — C3 tactical layer inside the approved local web

## Current decision

C3 is finalized as the operational main model:

`C3_STABLE_3_PAST_IC_SHRUNK`

No V78 champion search is allowed. `V76_RIDGE_RANK` remains shadow confirmation/emergence radar only.

V78 responds to the operational gap identified after V77: monthly C3 remains the portfolio core, while an advisory intra-month layer watches for emerging winners and deteriorating prior-month Top10 incumbents.

Read first:

1. `tai_lieu_dieu_phoi/v76_workstation_result_20260814.md`;
2. `tai_lieu_dieu_phoi/v77_workstation_result_20260814.md`;
3. `tai_lieu_dieu_phoi/v78_workstation_result_20260814.md`;
4. `tai_lieu_dieu_phoi/v78_c3_tactical_terminal_contract.md`;
5. this handoff;
6. V78 source/driver/bridge/installer/tests/runner/workflow.

## V78 branch

`agent/v78-c3-tactical-terminal`

V77 persistent workstation state remains:

`du_lieu/v77-paper-oos-state/`

Do not delete it.

V78 separate tactical persistence:

`du_lieu/v78-tactical-state/previews/`

Do not delete this if intra-month L15 persistence is being evaluated; prior-week preview is part of the exact L15 trigger.

## Real workstation result already observed

Artifact generated at HEAD `a53c7bbd62cd6ef4175364193d3e0bee9173a161` was successful with unchanged market-store SHA.

Observed current state:

- source monthly signal: `2026-07-31`;
- capture market day: `2026-08-13`;
- current-period entry: `2026-08-03`;
- risk_on=false;
- monthly Top10: `VPI, MSB, HCM, VIC, GMD, LPB, STB, BAF, DHC, ACB`;
- current preview Top10: `MSB, HCM, TLG, LPB, BAF, DHC, STB, BWE, KDC, GMD`;
- current dragging incumbents: `VPI, VIC`;
- current emerging radar: `TLG`;
- exact L15 inactive because first run had no prior-week V78 snapshot.

Read `v78_workstation_result_20260814.md` for exact P&L/alpha and recent 6/12/18 numbers.

## Operational semantics

Monthly C3 Top10 stays core. Current-day preview uses exact C3 components and the current completed-month C3 weights.

Incumbent health:

- R07 DD20 <= -8% => WATCH/health alert;
- R08 DD60 <= -12% => stronger RISK_ALERT_R08;
- current preview rank >15 or relative5 <= -2% => WATCH;
- no auto-sell from these health flags.

Important fail-closed behavior: a prior-month Top10 symbol remains visible even when it loses current eligibility. It cannot disappear from the health table merely because current MA250/liquidity eligibility fails.

### Actual current-period incumbent performance

V78 measures each prior-month Top10 name on the tradable path:

`monthly signal close -> next actual session open entry -> current close mark`

Reports:

- `period_entry_day`;
- `period_return`;
- `period_benchmark_return` using VNINDEX entry open -> current close;
- `period_relative_return`.

Metric contract:

`NEXT_SESSION_OPEN_AFTER_MONTHLY_SIGNAL_TO_CURRENT_CLOSE_GROSS`

`dragging_current_period=true` requires both absolute period return < 0 and benchmark-relative period return < 0. Still advisory only; no automatic sell.

## Emerging leader exact L15

- prior-month rank >10;
- current preview rank <=5;
- prior-week preview rank <=10;
- relative5 >=2%;
- volume ratio 5/20 >=1.

Without prior-week persistence, label only `WATCH_EMERGING`. With exact trigger, show advisory pair: weakest incumbent by current preview -> strongest L15 leader, 50% fraction, same V72 semantics. Still no live order.

A first V78 run normally has no prior V78 week and therefore cannot honestly produce an exact L15 persistence trigger. That first preview seeds the tactical state.

## Recent evidence

V78 discovers existing local V72/V76 monthly-return artifacts and reports fixed recent windows 6/12/18 months.

- V72: GAP18_CLEAN / Equal / BASE_DNSE / immediate, `NO_OVERLAY` vs L15 and R08.
- V76: GAP18_CLEAN / Equal / BASE_DNSE, `C3_BASELINE` vs `V76_RIDGE_RANK`.

Observed first V78 run:

- L15 delta vs baseline: +0.576pp / +2.485pp / +3.745pp over 6/12/18m;
- R08 delta: -1.312pp / -0.943pp / -3.005pp;
- Ridge delta: +10.431pp / +12.964pp / -8.335pp.

Interpretation remains: L15 advisory clue; R08 warning-only; Ridge recent-regime confirmation only. C3 remains main.

## Critical web correction

User supplied the actual workstation archive and explicitly confirmed the existing web is already finished and approved.

The approved web is:

- `vn_quant_local_system/web/index.html` + existing versioned JS/CSS;
- backend `vn_quant_local_system/src/vn_quant_local/webapp.py`;
- local URL `http://127.0.0.1:8787`;
- UI title `VN Quant Local Workstation`;
- current local data-integrity semantics through V55.

Therefore **do not build or deploy a separate V78 web**. `web_console_app_v78.py` was removed from the branch and port 8089 is no longer the contract.

## Additive web integration

Repository files:

- `src/he_thong_dinh_luong/local_workstation_v78_bridge.py`;
- `src/he_thong_dinh_luong/existing_web_v78_installer.py`;
- `web_extensions/v78/tactical_v78.js`;
- `web_extensions/v78/tactical_v78.css`;
- `tests/test_existing_web_v78_installer.py`.

The installer patches only two existing local files with narrow anchors:

- `vn_quant_local_system/web/index.html`;
- `vn_quant_local_system/src/vn_quant_local/webapp.py`.

Before first patch it creates a backup under:

`vn_quant_local_system/validation/v78_web_backup/<timestamp>/`

It then copies the two scoped V78 assets. Installer is idempotent.

Explicit invariants:

- existing layout replaced = false;
- credentials/state touched = false;
- no modification to `data/state/dnse_credentials.json` or other credential files;
- no reset of holdings/account/workstation DB;
- no reset of V77/V78 persistent research state;
- no broker order endpoint.

## What appears in the existing web

The old tabs/layout remain. V78 adds:

1. a compact Tactical C3 summary on Dashboard;
2. one new `Tactical` tab before Docs.

The Tactical tab displays:

- C3 MAIN + regime + dates;
- **all prior-month Top10**, not just alert names;
- current preview rank;
- period P&L, VNINDEX and alpha from tradable next-open to current close;
- drag marker;
- relative5/DD20/DD60;
- emerging-leader radar;
- exact L15 state;
- Ridge confirmation;
- fixed recent 6/12/18 C3 vs L15/R08/Ridge evidence.

Backend integration adds read/refresh tactical endpoints to the existing `vn_quant_local.webapp`. The existing `Chạy C3` path refreshes tactical fail-soft, so a tactical failure cannot invalidate the C3 refresh itself.

Stable tactical data remain:

`vn_quant_local_system/data/v78-c3-tactical/`

## Workstation runner

`scripts/run_v78_c3_tactical_terminal_gitbash.sh`

Current runner:

- verifies canonical `.venv`;
- validates sklearn 1.9.0 only; NiceGUI is no longer required by V78;
- compiles/tests V78 including installer tests;
- reads existing V77 freeze;
- computes tactical preview/current-period P&L;
- persists preview state;
- summarizes recent V72/V76 evidence;
- publishes stable snapshot;
- installs the additive extension into the existing approved web with backup;
- verifies patched existing web imports;
- bundles V78 output + web-integration audit;
- uses/open existing web URL `127.0.0.1:8787`.

If the old 8787 Python process is already running with pre-patch code, the runner deliberately does not kill it. It prints `WEB_RESTART_REQUIRED=true`; stop the old web terminal with Ctrl+C and run:

`bash vn_quant_local_system/scripts/run_web_gitbash.sh`

This reloads the same approved web with V78 additions.

## No regression

V78 must not:

- replace/redesign the approved local web;
- revive separate NiceGUI V78 deployment;
- replace C3 based on recent windows;
- re-open LightGBM/XGBoost/hyperparameter fishing;
- auto-sell R07/R08/period-drag names;
- call an emerging name L15 without persistence+relative+volume conditions;
- hide a weak prior-month Top10 because current eligibility failed;
- touch credentials/local account state during web install;
- mutate/reset V77 paper evidence;
- enable live broker orders.
