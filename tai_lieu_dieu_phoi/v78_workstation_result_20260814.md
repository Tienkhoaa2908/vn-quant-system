# V78 workstation result — 2026-08-14

## Provenance

Observed upload: `UPLOAD_THIS_v78_C3_TACTICAL_TERMINAL-*` from real Windows workstation.

- branch: `agent/v78-c3-tactical-terminal`;
- artifact HEAD: `a53c7bbd62cd6ef4175364193d3e0bee9173a161`;
- Python: 3.12.13 canonical `vn_quant_local_system/.venv`;
- scikit-learn: 1.9.0;
- store SHA before/after: `2959f8cce0c11e8e4186fcb49ae75bf7babf86b84afe64ca3b843a7470d58b1a` unchanged;
- V78 report status: `SUCCESS`.

This result was generated before the follow-up existing-web integration fix. Research/tactical outputs remain valid; only the deployment UI contract was corrected afterward to preserve the user's approved V55 local web.

## Operational model decision

Main operational model remains finalized:

`C3_STABLE_3_PAST_IC_SHRUNK`

Secondary:

`V76_RIDGE_RANK` = shadow confirmation/emergence radar only.

No champion replacement. No live orders.

## Current signal state

- capture market day: `2026-08-13`;
- completed monthly source signal: `2026-07-31`;
- tradable current-period entry day: `2026-08-03`;
- market regime: `risk_on=false`;
- C3 weights:
  - low-volatility `0.24031441`;
  - RS120 `0.36782353`;
  - high-52-week `0.39186206`.

Monthly C3 Top10:

`VPI, MSB, HCM, VIC, GMD, LPB, STB, BAF, DHC, ACB`

Current intra-month preview Top10:

`MSB, HCM, TLG, LPB, BAF, DHC, STB, BWE, KDC, GMD`

This is the operational distinction V78 was designed to surface: TLG/BWE/KDC have moved into the current preview while VPI/VIC/ACB have weakened relative to their month-start position.

## Incumbent drag audit

Two prior-month Top10 names are simultaneously negative in absolute return and negative versus VNINDEX from next-session open after the monthly signal to current close:

### VPI

- monthly rank: 1;
- current preview rank: 13;
- current-period return: `-4.7096%`;
- VNINDEX same-period return: `+1.1788%`;
- relative return / alpha: `-5.8883pp`;
- relative 5-session: `-3.6990%`;
- DD20/DD60: `-6.6154%`;
- volume ratio 5/20: `1.5628`;
- action: `WATCH`;
- `dragging_current_period=true`.

### VIC

- monthly rank: 4;
- current preview rank: 14;
- current-period return: `-3.7500%`;
- VNINDEX same-period return: `+1.1788%`;
- relative return / alpha: `-4.9288pp`;
- relative 5-session: `-5.0299%`;
- DD20 `-5.5000%`, DD60 `-9.8048%`;
- volume ratio 5/20: `1.1801`;
- action: `WATCH`;
- `dragging_current_period=true`.

Neither name hit the exact R07/R08 thresholds yet. Therefore this is a real-period drag alert, not an automatic sell signal.

Other prior-month Top10 names remained non-dragging under the same metric. Examples:

- HCM: `+2.5948%`, alpha `+1.4161pp`, preview rank 2;
- LPB: `+3.2630%`, alpha `+2.0842pp`, preview rank 4;
- BAF: `+5.9022%`, alpha `+4.7234pp`, preview rank 5;
- DHC: `+7.1104%`, alpha `+5.9317pp`, preview rank 6;
- GMD: `+2.7487%`, alpha `+1.5699pp`, preview rank 10.

This confirms the required operating behavior: do not treat every rank fall as equivalent; measure actual current-period P&L and relative drag name by name.

## Emerging leader audit

### TLG

TLG is the only emitted emerging-radar row in this first V78 run:

- prior monthly canonical rank: outside recorded ranked set (`>10` semantics);
- current preview rank: 3;
- current-period return: `+9.1837%`;
- VNINDEX: `+1.1788%`;
- relative return: `+8.0049pp`;
- relative 5-session: `+10.1475%`;
- DD20/DD60: `0%`;
- volume ratio 5/20: `1.7948`;
- Ridge monthly Top10: false;
- action: `WATCH_EMERGING`.

`prior_week_preview_available=false` on the first V78 run, therefore exact L15 persistence cannot be proven yet. V78 correctly did **not** fabricate an L15 swap.

Current exact L15 pair:

`active=false`

This is expected behavior. The persistent preview created by this run becomes evidence for later-week persistence checks.

## Recent-regime evidence

Fixed windows are 6/12/18 months. They are diagnostic regime evidence only, not a champion-selection sample.

### L15 vs frozen C3/no-overlay

- 6m: baseline `-16.5477%`, L15 `-15.9715%`, delta `+0.5762pp`, monthly win rate `66.7%`;
- 12m: baseline `-10.4682%`, L15 `-7.9836%`, delta `+2.4846pp`, monthly win rate `66.7%`;
- 18m: baseline `+25.8581%`, L15 `+29.6029%`, delta `+3.7448pp`, monthly win rate `61.1%`.

Interpretation: L15 is directionally useful in the recent windows and is the right tactical opportunity clue to surface on the web, but V72 long-run paired inference still did not pass promotion gates. Keep advisory.

### R08 trim vs frozen C3/no-overlay

- 6m delta `-1.3120pp`;
- 12m delta `-0.9430pp`;
- 18m delta `-3.0054pp`.

Interpretation: recent evidence does not support converting R08 into an automatic trim rule. Keep R08 as health alert only.

### Ridge vs frozen C3

- 6m: frozen `-16.5477%`, Ridge `-6.1163%`, delta `+10.4314pp`;
- 12m: frozen `-10.4682%`, Ridge `+2.4959%`, delta `+12.9641pp`;
- 18m: frozen `+25.8581%`, Ridge `+17.5230%`, delta `-8.3351pp`.

Interpretation: Ridge has been materially better over the most recent 6/12 months but worse over 18 months and failed V76 promotion evidence. This supports its assigned role as **recent-regime confirmation/radar**, not replacement of C3.

## Web decision after user clarification

The uploaded workstation archive also established that the user-approved web already exists as `VN Quant Local Workstation` under `vn_quant_local_system/`, serving `127.0.0.1:8787` with the V55-era static UI/backend.

The initially implemented separate NiceGUI V78 web is therefore a deployment mistake, not a research mistake.

Correct follow-up contract:

- preserve the existing approved web and its visual/operational layout;
- add V78 only as an additive Tactical tab + compact Dashboard summary;
- reuse existing port 8787;
- no replacement web on 8089;
- backup local `index.html`/`webapp.py` before additive patch;
- never touch credentials/state during installation.

The branch was subsequently amended to implement this additive integration.

## Final interpretation

V78 real workstation evidence supports the intended operational architecture:

1. C3 remains the main monthly model;
2. VPI and VIC are current real-period drag names requiring attention, not automatic sells;
3. TLG is a strong current emerging leader but first-run persistence is not yet available, so only `WATCH_EMERGING` is valid;
4. L15 deserves tactical display/advisory treatment; R08 should stay warning-only;
5. Ridge is useful as recent-regime confirmation but not champion;
6. the newly researched information should be added to the existing approved web rather than replacing that web.

Data-lineage/canonical/live-capital gates remain unchanged. `automatic_live_orders_allowed=false`.
