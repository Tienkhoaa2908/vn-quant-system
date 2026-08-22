# V83 handoff — capital discipline + main web

## Current direction

- Champion remains `C3_STABLE_3_PAST_IC_SHRUNK`.
- New-leader/L15 expansion is stopped as a primary research direction.
- V80 forward registry and V81 historical L15 audit remain immutable archived evidence.
- V83 focuses on incumbent capital discipline and entry quality.

## Fixed policies

- `C3_BASE`
- `NO_ADD_UNDERWATER`
- `PERSIST2_SEVERE_TRIM50`
- `NO_ADD_PLUS_PERSIST2_TRIM50`

Do not add another cut fraction, persistence length, drawdown level or rank threshold after seeing V83 output. Any future change must be a separately justified research question.

## Selection isolation

V83 was initiated after observing 2026 forward behavior including VPI recovery. Therefore selection evidence is hard-truncated at `2025-12-31` by `capital_discipline_selection_v83.py`.

2026/all-sample tables are shadow diagnostics only and must not be used to choose a V83 policy.

## Main web

Branch: `agent/v83-capital-discipline-main-web`

Approved URL remains `http://127.0.0.1:8787`.

Primary surface:

- no-add list;
- cut-watch list;
- recovered-from-drag list;
- current C3 entry-gap table;
- pre-2026 V83 profit table after workstation run.

Existing leader/L15/recent-regime/V80/V81 sections are moved into a collapsed Research Archive rather than deleted.

## Workstation

Canonical one-shot runner:

`scripts/run_v83_capital_discipline_main_web_gitbash.sh`

The runner:

1. allows only approved tracked web modifications;
2. preserves V77 and V80 by digest guard;
3. reuses the latest audited V81 V68/V70 outputs when present, otherwise rebuilds them;
4. runs all-sample diagnostic plus pre-2026-only selection audit;
5. publishes `vn_quant_local_system/data/v83-capital-discipline/LATEST.json` with **pre-2026 selection rows as the primary web rows**;
6. installs the V83 endpoint/assets into the existing 8787 web;
7. checks logical market bars and V77/V80 unchanged;
8. emits `artifacts/UPLOAD_THIS_v83_CAPITAL_DISCIPLINE_MAIN_WEB-*.zip`.

No live order or promotion is authorized before workstation evidence is audited.
