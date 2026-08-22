# V84 workstation result — 2026-08-22

## Provenance

- Branch: `agent/v84-main-web-operating-dashboard`
- Implementation HEAD: `31f0b6c9d52cd9e8beb79b0d194e888788d29b0f`
- Uploaded audit ZIP SHA256: `8c5aa965fb9e08143a7992c0a157eb22887c703c4f35efc752cb891af1281e7e`
- Approved workstation URL: `http://127.0.0.1:8787`

## Installer / integrity

Audit bundle reports:

- install status `SUCCESS`
- mode `MAIN_DAILY_OPERATING_DASHBOARD`
- existing port `8787`
- consumed only read-only endpoints `/api/status`, `/api/dashboard-v83`, `/api/tactical-v78`
- `new_api_endpoint_added=false`
- `live_order_endpoint_added=false`
- `research_policy_changed=false`
- `credentials_or_state_touched=false`

Market bars were byte-logically unchanged before/after:

- first day `2015-06-29`
- last day `2026-08-21`
- row count `301259`
- logical SHA256 `7f48a06841fd33de3bf1688d371c13edd5a7a15d896f18ebc32d4fdd0eaf8cad`

Persistent state was unchanged:

- V77 before/after: `f7f961a202d386815efad18e11d01713ad5eddc2d68297c06bca468b8d85fdc8`
- V80 before/after: `8f3fcc0ef22d8b40ac2470691159374a2e7c4b32d21dbd75ddff3fd9218b8c89`

## Screenshot verification

The real workstation screenshot confirms the V84 Daily Operating Dashboard renders successfully and joins DNSE + C3 + V83 advisory state.

Visible operating snapshot:

- market EOD `2026-08-21`
- DNSE valuation `2026-08-21`
- DNSE capture `2026-08-22T23:17:13+07:00`
- `DỮ LIỆU VẬN HÀNH SẴN SÀNG`
- NAV EOD about `543.6 nghìn VND`
- stock value about `484.1 nghìn VND`
- exposure `89.04%`
- safe cash about `59.6 nghìn VND` / `10.96% NAV`
- aggregate EOD position P&L about `+5.0 nghìn VND` / `+1.04%`
- C3 regime `RISK OFF`
- monthly signal `2026-07-31`
- capital advisory `3 / 0 / 1` = add-review / severe / recovered

Real-holding × C3 health table visibly classifies:

- `LPB`: ADD REVIEW, current rank 15, Rel5 about -6.84%, real EOD P&L about -5.30%
- `MSB`: ADD REVIEW, current rank 3, Rel5 about -3.81%, real EOD P&L about -1.55%
- `STB`, `GMD`, `ACB`, `HCM`, `BAF`: C3 HOLD in the visible viewport

The panel also correctly detects that the saved capital plan is stale:

- plan signal `2026-07-31`
- plan market day `2026-08-17`
- current EOD `2026-08-21`
- UI emits `PLAN CŨ — TẠO LẠI TRƯỚC KHI DÙNG`

Entry-quality summary renders:

- mean Top10 T+1 gap about `+0.30%`
- largest chase gap `MSB +0.94%`
- `7/10` names had positive gap
- T+1 remains canonical; no automatic delay is introduced.

## Conclusion

V84 workstation integration is verified. The main operational web now provides one primary daily view for real DNSE NAV/P&L, C3 regime/health, capital-discipline advisory, stale-plan guarding and entry-gap monitoring.

V84 does not promote a new research policy and does not add live-order authority. C3 remains champion. V83 capital-discipline labels remain advisory only.
