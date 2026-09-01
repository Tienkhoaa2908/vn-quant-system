# ROADMAP — current priorities

Updated: 2026-09-01

This roadmap supersedes the old generic `ke_hoach_tong_the.md`. It describes current priorities, not a historical milestone plan.

## Now — V86 public realtime hardening

Goal: make DNSE public market-data realtime reliable, observable and isolated without enabling orders.

Current state:
- official OpenAPI SDK 1.4.6 sidecar smoke succeeded on real workstation;
- authentication/subscription/heartbeat succeeded;
- legacy V59 WebSocket ownership has been removed from the web process;
- web remains port 8787;
- order authority remains false.

Required next evidence:
1. Fix/investigate REST TLS certificate verification; no `InsecureRequestWarning` may remain as an accepted production state.
2. Run long-lived sidecar across multiple real trading sessions.
3. Record per-session transport/auth/subscription/heartbeat/tick freshness/reconnect observations.
4. Visually verify V86 health UI on 8787.
5. Audit the V86 upload ZIP when supplied.

Exit criteria for V86:
- HTTPS verification explicitly safe/fail-closed;
- public WS stable enough across multiple sessions with explained reconnects;
- health semantics correctly distinguish market closed vs stale/degraded feed;
- no legacy V59 WS process ownership;
- canonical REST environment remains unchanged/healthy;
- V77/V80/market integrity preserved;
- no order mutation surface.

## Next — private broker event plumbing, still read-only

Only after V86 exit criteria:

- design isolated private Trading WebSocket order/position event observation;
- implement Trading Token lifecycle as a separate security component, but do not submit orders merely to test it unless explicitly approved;
- build order/account/position REST reconciliation;
- define persistent idempotent intent/order state machine;
- define `UNKNOWN_SUBMIT_STATE -> RECONCILE_ONLY` behavior;
- build circuit breaker and unresolved-order gate;
- integrate DNSE security definition, working dates/session state and PPSE/preflight data.

This phase is infrastructure validation, not autonomous trading authority.

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
- V86 adds semantic realtime health; no second user-facing web/port.
- Keep research history collapsed/secondary; daily operational information stays primary.
- Any future order UI must show fail-closed gate state and cannot infer permission from HTTP endpoint liveness alone.

## Documentation/continuity lane

Every project turn must:
- read current GitHub state first;
- append `CHAT_TURN_LOG.md` before answering;
- update current docs when durable state changes;
- verify the new head/CI after writes;
- keep historical evidence clearly versioned and avoid stale competing current-state files.
