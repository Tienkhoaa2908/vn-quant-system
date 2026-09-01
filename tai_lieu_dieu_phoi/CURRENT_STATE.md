# CURRENT STATE — VN Quant System

Updated: 2026-09-01 (Vietnam time)

This is the single current operational snapshot. If older coordination documents, historical handoffs, chat memory, or stale PR descriptions conflict with this file, verify GitHub/current workstation evidence and update this file. Versioned research contracts/results remain historical evidence, not current-state authority.

## 1. Repository / active stack

Repository: `Tienkhoaa2908/vn-quant-system`.

Current infrastructure branch: `agent/v86-dnse-openapi-realtime-hardening`.

V86 implementation head verified by CI before this continuity-cleanup checkpoint: `57001d64096b25cc9044a432bc8b5b997d6c4bd3`.

PR #62 (`V86: isolate and harden DNSE OpenAPI realtime`) is Open, Draft, mergeable, not merged. At implementation head `57001d...`, dedicated V86 Ubuntu/Windows and full `kiem_tra_tu_dong` Ubuntu/Windows including HTTP smoke completed successfully.

Relevant stacked PRs remain open/unmerged:

- #54 V78 tactical web layer — Draft.
- #55 V79 tactical capital policy — Draft.
- #56 V80 forward-paper tactical registry — Ready.
- #57 V81 frozen historical tactical audit — Ready.
- #58 V82 profit/tactical dashboard — Ready.
- #59 V83 capital discipline + primary web — Draft.
- #60 V84 main daily operating dashboard — Ready.
- #61 V85 DNSE realtime forensic audit — Ready.
- #62 V86 DNSE OpenAPI realtime hardening — Draft pending full workstation/long-lived verification.

Do not merge any PR without explicit user instruction. Because the later PRs are stacked, verify bases and merge order before any merge operation.

## 2. Frozen quant champion / research stop rule

Operational champion/default remains `C3_STABLE_3_PAST_IC_SHRUNK`.

Frozen factor weights:

- `low_volatility = 0.24031440995977327`
- `relative_strength_120 = 0.3678235312634722`
- `high_52_week = 0.3918620587767545`

`V76_RIDGE_RANK` remains shadow/diagnostic only.

V76 stop rule remains active: do not reopen LightGBM/XGBoost/model-architecture/hyperparameter or threshold fishing on the same repeatedly inspected historical sample merely to find a winner. New model work requires materially new truth data, fresh OOS evidence, or a separately justified research question.

C3 label/execution contract remains close(T) -> close(T+20) for the C3 label, with tradable execution no earlier than next-session open.

## 3. Data/research gates

The following data-lineage gates remain fail-closed for canonical/live/promotion claims:

- PIT HOSE membership lineage;
- price-basis confirmation;
- corporate-action inventory/reconstruction;
- PIT sector master.

Diagnostics and paper collection may continue where contracts explicitly allow them. Open gates must never be silently treated as resolved.

## 4. Persistent forward states — never reset

- V77 persistent state: `du_lieu/v77-paper-oos-state/` — never delete/reset.
- V80 persistent state: `du_lieu/v80-tactical-paper-state/` — never delete/reset.
- V78 preview state is append-only under its contract.

V80 current product role is forward evidence collection, not live trading. Incumbent health/drag alone cannot trigger an automatic sell. Exact L15 remains required for the frozen opportunity policies; no exact L15 means no tactical action.

## 5. V83 capital-discipline result

Canonical policy selection is PRE-2026 only because the V83 direction was formed after observing 2026 behavior. 2026 is shadow/contaminated for selection.

Reference: GAP18_CLEAN / BASE_DNSE / Equal / 1bn, through 2025-12-31.

- `C3_BASE`: ending NAV ~5.578800bn; net profit ~4.578800bn; total return +457.88%; CAGR ~22.43%; MDD ~-37.46%.
- `NO_ADD_UNDERWATER`: about -7.093m VND vs C3; slightly lower turnover/MDD, but lower profit.
- `PERSIST2_SEVERE_TRIM50`: about -19.523m VND vs C3; only ~0.106pp MDD improvement, lower profit.
- combined policy: about -30.438m VND vs C3.

Decision: none of these automatic capital-discipline rules is promoted. Web labels remain advisory (`ADD REVIEW`, `SEVERE WATCH`, recovery/entry diagnostics), not executable instructions.

VPI recovery is a concrete warning against one-shot auto-sell logic: transient drag can recover. Do not infer that every deteriorating position should be held indefinitely; use the frozen evidence/health contracts and fresh observations.

Entry timing PRE-2026 also did not support replacing canonical T+1 with T+2/staged execution. 2026 shadow moved the other way, so execution quality should be monitored forward rather than retroactively retuned.

## 6. V84 approved main web

The approved user-facing workstation web remains:

`http://127.0.0.1:8787`

V84 is the main daily operating dashboard. It joins real DNSE portfolio/NAV/cash/positions with C3 health, capital-discipline advisory, stale-plan detection and entry-gap context.

Do not redesign into a separate app/port unless the user explicitly changes this constraint.

## 7. DNSE API commercial finding

DNSE public material reviewed on 2026-09-01 did not expose a separate current LightSpeed/OpenAPI subscription/usage fee in the public service-fee material reviewed, and official API FAQ material states API-submitted orders follow normal transaction fees rather than an added API-order surcharge.

Canonical wording: `NO_SEPARATE_PUBLIC_API_FEE_FOUND` as of 2026-09-01. This is not a `FREE_FOREVER` guarantee. Any account-specific contract, Entrade X charge, or later DNSE fee-policy update overrides the public-doc observation and must be recorded as local TCO evidence.

## 8. V85 realtime root cause

Workstation forensic evidence established:

- canonical runtime `dnse==0.5.0`;
- REST/account path healthy;
- legacy SDK source carries the nonce/reconnect bug signatures (integer nonce pattern and reconnect without closing/resetting the old socket first);
- localhost `GET /api/realtime` HTTP 200 is not evidence that the upstream realtime feed is healthy.

WebSocket close code `1000 (OK)` can be a normal closure. The defect was the legacy reconnect lifecycle/health semantics, not the numeric close code by itself.

## 9. V86 architecture

V86 isolates realtime from the canonical REST runtime:

- canonical `.venv`: temporarily keeps `dnse==0.5.0` for working EOD/account/portfolio REST;
- isolated `.venv-dnse-openapi-v86`: `dnse-sdk-openapi==1.4.6`;
- new read-only REST smoke pins API version `2026-05-07`;
- market WebSocket uses official OpenAPI `TradingClient`, msgpack, authentication, heartbeat and reconnect/re-auth/re-subscribe capabilities;
- web process does not own a WebSocket;
- V59 compatibility wrapper no longer imports/starts/stops legacy market/private WS;
- `/api/realtime` and `/api/realtime/status` read V86 sidecar state;
- legacy realtime start/stop POST routes are disabled and network-inert;
- no OTP, Trading Token, private order stream, position stream or order mutation;
- `live_order_ready=false` throughout.

## 10. V86 real workstation smoke — 2026-09-01

User-provided run transcript for implementation head `57001d...` completed with `V86_EXIT_CODE=0`.

Observed real OpenAPI smoke:

- isolated SDK `dnse-sdk-openapi==1.4.6` installed successfully;
- canonical `dnse==0.5.0` remained unchanged;
- 20-symbol public market subscription set built;
- WebSocket connected successfully to `wss://ws-openapi.dnse.com.vn/v1/stream?encoding=msgpack`;
- authentication succeeded;
- subscriptions were accepted across the SDK's public tick channels for the symbol set;
- server ping was received and pong sent;
- `transport_connected=True`;
- `authenticated=True`;
- `subscriptions_active=True`;
- `heartbeat_healthy=True`;
- `reconnect_count=0`;
- read-only REST smoke `SUCCESS`;
- `live_order_ready=False`.

Smoke ran around 19:58 Vietnam time, outside market hours, so `IDLE_MARKET_CLOSED` and `event_count=0` are expected and are not evidence of failure.

V77 and V80 digests remained unchanged before/after. V86 installer reported `web_process_owns_websocket=false`, `legacy_v59_wrapper_ws_disabled=true`, no live-order endpoint, no credential/trading-state mutation.

Generated workstation ZIP path from the run:
`artifacts/UPLOAD_THIS_v86_DNSE_OPENAPI_REALTIME-20260901-195512.zip`

Reported SHA-256:
`95ad8d4d9b84117659aeae4388340039322402c024094712e0b1433a703efb9e`

The transcript is sufficient to establish a successful smoke. The ZIP itself had not yet been uploaded/audited in chat at this checkpoint, and long-lived next-session tick freshness has not yet been proven.

## 11. Current V86 runtime procedure

The one-shot upgrade intentionally exits after install/smoke. It does not keep the web or sidecar alive.

For normal read-only V86 observation use two Git Bash terminals:

Terminal A — long-lived realtime sidecar:

```bash
cd /d/VNQuant/vn-quant-system
git switch agent/v86-dnse-openapi-realtime-hardening
bash scripts/run_v86_dnse_openapi_realtime_sidecar_gitbash.sh
```

Terminal B — approved web:

```bash
cd /d/VNQuant/vn-quant-system/vn_quant_local_system
bash scripts/run_web_gitbash.sh
```

Keep both terminals open. Outside market hours the semantic state may be `IDLE_MARKET_CLOSED`; during a real session the target state is `HEALTHY` with fresh ticks and bounded reconnect behavior.

## 12. Current blockers / next evidence

1. V86 REST smoke emitted `InsecureRequestWarning` for an unverified HTTPS request. TLS certificate verification must be investigated and made fail-closed before any order-mutation work.
2. Run the long-lived sidecar through multiple actual market sessions and record tick freshness, heartbeat, reconnect count/reasons and recovery behavior.
3. Verify the V86 realtime health panel visually on web 8787.
4. Only after stable public market-data sessions: design private order/position stream + REST reconciliation state machine. Still no order mutation at that stage unless separately approved and gated.
5. Before any future auto-order authority, require idempotent intent/order identity, uncertain-submit reconciliation, circuit breaker, REST account/order reconciliation, private order/position stream health and Trading Token lifecycle.

## 13. Workstation path and command safety

Canonical Git Bash repo path is `/d/VNQuant/vn-quant-system`.

A previous assistant command accidentally used `~/v31_mt5_40usd`, which belongs to another project and caused immediate script exit. Never reuse that path for VN Quant.

On Windows CPython launched from Git Bash, multi-entry `PYTHONPATH` must use Windows semantics (`;`) with `cygpath -w`; this has caused earlier path/import issues and is now explicitly guarded in current runners.

## 14. Evidence discipline

Always distinguish:

- CI green: code/contracts compile and tests pass;
- workstation smoke: the real local environment performed the tested action;
- historical research evidence: may be selected/contaminated and is not fresh OOS;
- forward-paper evidence: fresh observations under frozen policy;
- live authority: currently false.

Never promote a policy or auto-order capability because a UI renders, an HTTP endpoint returns 200, or one shadow observation looks favorable.
