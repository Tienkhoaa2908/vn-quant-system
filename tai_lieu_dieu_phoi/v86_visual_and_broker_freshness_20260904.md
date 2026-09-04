# V86 active-session visual verification + DNSE broker freshness finding — 2026-09-04

Capture time supplied by user: approximately `2026-09-04 13:45 +07:00` during an active Vietnam market session.

This document records what the screenshots prove, what they do not prove, and the broker-state freshness defect discovered while reviewing the current V59/V55/V86 runtime.

## 1. Public realtime visual evidence

The approved web at `http://127.0.0.1:8787` visibly showed the V86 isolated sidecar as:

- semantic status `HEALTHY`;
- transport `CONNECTED`;
- authentication `AUTHENTICATED`;
- subscriptions `ACTIVE` for 20 symbols using msgpack;
- tick freshness about `0.6s`;
- last visible tick `VIC 253`;
- reconnect count `0`;
- pong age about `15.0s`;
- SDK contract `1.4.6`, API compatibility date `2026-05-07`;
- web message explicitly states the web only reads sidecar state and does not own the WebSocket;
- live-order authority remains blocked.

This is stronger than the 2026-09-01 after-hours smoke because it demonstrates actual fresh public ticks during a live session. It is still one observed session, not multi-session reliability proof.

## 2. Broker portfolio screenshot semantics

The portfolio panel showed:

- DNSE cash/quantity capture timestamp `2026-09-04T13:45:37+07:00`;
- official EOD valuation day `2026-08-21`;
- version `V55_FINAL_EOD_ONLY_VALUATION`;
- 7 positions;
- available cash about `59,566 VND`;
- withdrawable cash about `59,565 VND`;
- official EOD NAV about `543,618 VND`;
- official EOD stock value about `484,050 VND`.

Therefore the date `2026-08-21` in this screenshot is the local final-EOD valuation date, not the DNSE holdings capture timestamp. The current REST holdings/cash request itself completed at 13:45 on 2026-09-04.

V55 intentionally treats DNSE as authoritative for account selection, cash, quantity and sellable quantity while using local final EOD close as the sole official valuation price. Broker `marketPrice` remains excluded because its timestamp/semantics are not verified. This contract is retained.

## 3. User-reported intermittent broker-state problem

The user separately reports that current DNSE portfolio information is intermittently unavailable, especially around market-open/market-hours windows, while the same read may work later in the evening.

This is treated as a real operational reliability blocker even though the specific 13:45 screenshot happened to show a successful fresh holdings capture.

The active V59 selected-account reconcile performs synchronous REST reads in this order:

1. account identity;
2. balances;
3. `/accounts/{account}/positions`;
4. normalize positions;
5. only then persist a broker snapshot.

A thrown balance/positions exception therefore stops the current V59 fast reconcile before its snapshot write. However a successful HTTP response that is transiently empty can still be ambiguous. A previous non-empty portfolio must not be silently replaced by an empty market-hours response without a fail-closed guard.

## 4. UI freshness defect

V84 currently marks the daily dashboard ready when `broker.market_day` is not older than the latest local market day. That comparison is insufficient when both values are stale together.

Observed screenshot:

- latest local Market EOD: `2026-08-21`;
- DNSE official valuation day: `2026-08-21`;
- current date: `2026-09-04`;
- dashboard still displayed `DỮ LIỆU VẬN HÀNH SẴN SÀNG`.

This is a false-ready presentation state. Freshness must separate at least three clocks:

1. DNSE holdings/cash capture time;
2. official EOD valuation/market-data day;
3. public realtime tick age.

A healthy public realtime feed does not make stale EOD valuation current, and a fresh EOD database does not prove broker holdings are fresh.

## 5. Patch direction frozen from this finding

V86 broker-state hardening must:

- preserve V55 final-EOD official valuation semantics;
- record broker sync success/failure separately from the last good snapshot;
- fail closed during market hours if a previously non-empty portfolio suddenly reads as empty;
- keep the previous completed snapshot available instead of silently treating an ambiguous empty response as operational truth;
- expose broker holdings capture age and EOD valuation age separately;
- mark materially old EOD data as degraded even when broker valuation day equals the local market DB day;
- keep all order mutation disabled.

The first absolute-age UI guard uses a conservative calendar-day warning and explicitly does not claim exchange-calendar truth. A later refinement should use verified DNSE working dates/session state.

## 6. Modern DNSE SDK architectural evidence

The public `dnse-tech/dnse-py` documentation/source reviewed on 2026-09-04 shows:

- account list and balances in the modern resource API;
- private read-only WebSocket event subscriptions for positions/account/orders;
- WebSocket authentication built from API key/secret HMAC;
- order mutations remain a separate OTP/trading-token concern.

This is architectural evidence only. It is not yet proof that the exact isolated `dnse-sdk-openapi==1.4.6` workstation runtime provides identical private-stream behavior or an initial complete position snapshot. Any migration/probe must be isolated, read-only and verified on the real workstation before becoming broker-state truth.

## 7. Evidence classification

- Public realtime screenshot: real workstation, active-session visual evidence.
- Broker timestamp/portfolio screenshot: real workstation visual evidence.
- Intermittent market-hours portfolio failure: user-observed operational evidence; exact failure payload/timing still needs instrumentation.
- Code-path findings: current-head repository inspection.
- Modern SDK private-stream observation: public upstream source/docs; not workstation proof.
- Live-order authority: `false`.
