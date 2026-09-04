# ROADMAP — current priorities

Updated: 2026-09-04

This roadmap supersedes the old generic `ke_hoach_tong_the.md`. It describes current priorities, not a historical milestone plan.

## Now — V86 public realtime + broker-state freshness hardening

Goal: make DNSE public market-data realtime and read-only broker state reliable, observable and isolated without enabling orders.

Current state:
- official OpenAPI SDK 1.4.6 sidecar smoke succeeded on real workstation;
- 2026-09-04 active-session screenshot showed `HEALTHY`, authenticated/subscribed public feed, about 0.6s tick age and reconnect count 0;
- legacy V59 WebSocket ownership has been removed from the web process;
- web remains port 8787;
- DNSE holdings/cash REST capture succeeded at 13:45 on 2026-09-04, but official local EOD valuation still ended 2026-08-21;
- user reports intermittent DNSE portfolio-read failures during market/open-session windows;
- order authority remains false.

Required next evidence/work:
1. Add broker sync health/freshness instrumentation and fail-closed protection for ambiguous empty market-hours position responses.
2. Separate three clocks in UI/API: holdings capture time, official EOD valuation day, public realtime tick age.
3. Add absolute EOD-age warning so two equally stale dates cannot render as ready.
4. Collect time-of-day broker REST success/failure/timing evidence over real sessions while preserving the last good snapshot.
5. Fix/investigate REST TLS certificate verification; no `InsecureRequestWarning` may remain as an accepted production state.
6. Run long-lived public sidecar across multiple real trading sessions and record transport/auth/subscription/heartbeat/tick freshness/reconnect behavior.
7. Audit the V86 upload ZIP when supplied.
8. In an isolated read-only experiment, verify whether the modern DNSE private position/account stream can provide reliable intraday broker-state updates. Do not request OTP/Trading Token or mutate orders merely for this test.

Exit criteria for V86 read-only infrastructure:
- HTTPS verification explicitly safe/fail-closed;
- public WS stable enough across multiple sessions with explained reconnects;
- health semantics correctly distinguish market closed vs stale/degraded feed;
- broker sync failures do not overwrite last-known-good holdings;
- holdings capture freshness and EOD valuation freshness are separately visible;
- materially stale EOD cannot render as operationally ready;
- no legacy V59 WS process ownership;
- canonical REST environment remains unchanged/healthy or has a separately verified migration path;
- V77/V80/market integrity preserved;
- no order mutation surface.

## Next — private broker event plumbing, still read-only

Only after or in a narrowly scoped parallel probe that does not weaken the V86 safety gates:

- verify isolated private DNSE position/account event observation on the real workstation;
- determine whether the private stream supplies a complete initial state or only change events;
- reconcile private stream observations against successful REST checkpoints;
- implement Trading Token lifecycle only as a separate security component when actually required; do not obtain/use it merely for read-only observation if HMAC auth is sufficient;
- build order/account/position REST reconciliation;
- define persistent idempotent intent/order state machine;
- define `UNKNOWN_SUBMIT_STATE -> RECONCILE_ONLY` behavior;
- build circuit breaker and unresolved-order gate;
- integrate DNSE security definition, working dates/session state and PPSE/preflight data.

This phase is infrastructure validation, not autonomous trading authority.

## Later — intraday indicative portfolio view

Keep `V55_FINAL_EOD_ONLY_VALUATION` as official valuation truth for planner/performance.

After broker quantities are proven fresh and V86 stores adequate per-symbol tick state, an additive intraday view may show:
- latest confirmed broker quantities/cash;
- public realtime mark-to-market price;
- clearly labeled `INDICATIVE_INTRADAY`, never confused with V55 official EOD;
- freshness/error state for every input.

Do not use a single global last tick as portfolio-wide mark-to-market truth; per-symbol freshness is required.

## Later — controlled paper execution state machine

After private event plumbing is stable:

- simulate complete order lifecycle without broker mutation;
- test duplicate prevention, partial fill, cancel/replace race, reconnect during uncertain submit, stale quote/feed, session transitions and rate-limit/backoff behavior;
- compare REST and WS state and fail closed on disagreement.

## Live-order promotion gate

Live orders require a separate explicit user decision and a documented promotion package. At minimum:

- data/research gates relevant to the live decision must be closed or explicitly scoped;
- public and private realtime health stable;
- TLS verified;
- broker holdings/cash reconciliation reliable across market hours;
- Trading Token lifecycle tested safely;
- idempotency/reconciliation/circuit breaker proven;
- preflight checks for account, cash, PPSE, lot, price bands, session/security status;
- bounded rate-limit-aware retries for safe reads only;
- no blind retry after uncertain mutation;
- kill switch/manual override;
- audit logging without secrets;
- paper/shadow observation period completed.

Until then: `LIVE_ORDER_READY=false`.

## Quant/research lane

- Keep `C3_STABLE_3_PAST_IC_SHRUNK` as champion.
- Continue V77/V80 fresh forward evidence without resetting state.
- Keep V83 capital-discipline overlays advisory; PRE-2026 tests did not improve profit.
- Monitor entry quality forward rather than retuning T+1/T+2 from contaminated 2026 examples.
- Do not reopen broad model/threshold fishing on the same historical sample under the V76 stop rule.
- Prioritize PIT HOSE membership, price basis, corporate actions and PIT sector truth if canonical/live claims require them.

## Product/web lane

- V84 remains the main daily operating dashboard at `http://127.0.0.1:8787`.
- V86 adds semantic public realtime health and broker freshness; no second user-facing web/port.
- Keep research history collapsed/secondary; daily operational information stays primary.
- Any future order UI must show fail-closed gate state and cannot infer permission from HTTP endpoint liveness alone.

## Documentation/continuity lane

Every project turn must:
- read current GitHub state first;
- append `CHAT_TURN_LOG.md` before answering;
- update current docs when durable state changes;
- verify the new head/CI after writes;
- keep historical evidence clearly versioned and avoid stale competing current-state files.
