# V84 handoff — main daily operating dashboard

## Status

V84 is the current main-web completion track on top of V83.

- Branch: `agent/v84-main-web-operating-dashboard`
- PR: #60
- Workstation-verified implementation HEAD: `31f0b6c9d52cd9e8beb79b0d194e888788d29b0f`
- Workstation verification doc commit: `652f7908ac4ea3eed2bac121233de7802501547c`
- Approved web: `http://127.0.0.1:8787`

## Product role

V84 is the primary daily operating view. It is web-only and does not reopen model/threshold/overlay research.

The dashboard joins existing read-only sources to show:

- real DNSE EOD NAV, stock value, safe cash and position P&L;
- current C3 regime and monthly signal;
- real holdings joined to C3 rank/current rank/Rel5 health;
- advisory `ADD REVIEW`, `SEVERE WATCH`, `RECOVERED` states;
- current entry-gap monitoring;
- stale capital-plan guard;
- current-plan conflict warning if a buy plan proposes adding to a watched name.

## Evidence language

Do not interpret V83/V84 advisory labels as automatic trading rules.

- Historical V83 did not show `NO_ADD_UNDERWATER` or persistent-severe trim rules outperforming C3 on the pre-2026 selection sample.
- C3 remains champion.
- `ADD REVIEW` means review before incremental capital; it is not an automatic block.
- `SEVERE WATCH` means persistent/severe deterioration watch; it is not an automatic sell.
- `RECOVERED` preserves evidence such as the VPI drag-to-recovery case.
- T+1 open remains canonical; entry gap is monitoring only.

## Workstation verification 2026-08-22

Real screenshot + audit ZIP verified:

- market EOD and DNSE valuation both `2026-08-21`;
- V77/V80 persistent digests unchanged before/after;
- market logical fingerprint unchanged before/after;
- no new API endpoint;
- no live-order endpoint;
- no credentials/state mutation;
- stale plan from market day `2026-08-17` is correctly rejected for current operational interpretation;
- Daily Operating Dashboard renders successfully.

Full detail: `tai_lieu_dieu_phoi/v84_workstation_result_20260822.md`.

## Next operating cadence

Use V84 as the main workstation web. Refresh/sync DNSE when the dashboard reports a stale broker valuation. Recreate a capital plan whenever the dashboard reports `PLAN CŨ — TẠO LẠI`.

Do not start another historical threshold matrix by default. Future quant work should be triggered by fresh evidence, data-truth improvements, or a concrete operational defect found through daily use.

No merge/live authority is implied by this handoff.
