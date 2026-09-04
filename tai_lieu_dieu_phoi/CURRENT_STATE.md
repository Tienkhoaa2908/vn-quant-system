# CURRENT STATE — VN Quant System

Updated: 2026-09-04 (Vietnam time)

This is the single current operational snapshot. If older coordination documents, historical handoffs, chat memory, or stale PR descriptions conflict with this file, verify GitHub/current workstation evidence and update this file. Versioned research contracts/results remain historical evidence, not current-state authority.

## 1. Repository / active stack

Repository: `Tienkhoaa2908/vn-quant-system`.

Current infrastructure branch: `agent/v86-dnse-openapi-realtime-hardening`.

PR #62 (`V86: isolate and harden DNSE OpenAPI realtime`) is Open, Draft, mergeable, not merged. Do not merge without explicit user instruction.

The prior continuity HEAD `0b7fd1b1272f4985aa7d32d047982a6bde26fea6` completed both exact-head workflows successfully:

- `v86_dnse_openapi_realtime_hardening` run 17: success;
- `kiem_tra_tu_dong` run 930: success.

The 2026-09-04 broker-freshness patch/checkpoint is newer than that green anchor and must obtain its own exact-head CI before being called fully green.

Relevant stacked PRs remain open/unmerged:

- #54 V78 tactical web layer — Draft.
- #55 V79 tactical capital policy — Draft.
- #56 V80 forward-paper tactical registry — Ready.
- #57 V81 frozen historical tactical audit — Ready.
- #58 V82 profit/tactical dashboard — Ready.
- #59 V83 capital discipline + primary web — Draft.
- #60 V84 main daily operating dashboard — Ready.
- #61 V85 DNSE realtime forensic audit — Ready.
- #62 V86 DNSE OpenAPI realtime hardening — Draft.

Because later PRs are stacked, verify bases and merge order before any merge operation.

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

VPI recovery remains a concrete warning against one-shot auto-sell logic. Entry timing PRE-2026 also did not support replacing canonical T+1 with T+2/staged execution. Monitor forward rather than retuning from contaminated 2026 examples.

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
- REST/account path was generally working but is now known to have intermittent portfolio-read reliability by time of day;
- legacy SDK source carries the nonce/reconnect bug signatures for WebSocket use;
- localhost `GET /api/realtime` HTTP 200 is not evidence that the upstream realtime feed is healthy.

WebSocket close code `1000 (OK)` can be a normal closure. The defect was the legacy reconnect lifecycle/health semantics, not the numeric close code by itself.

## 9. V86 architecture

V86 isolates public realtime from the canonical REST runtime:

- canonical `.venv`: temporarily keeps `dnse==0.5.0` for EOD/account/portfolio REST;
- isolated `.venv-dnse-openapi-v86`: `dnse-sdk-openapi==1.4.6`;
- new read-only REST smoke pins API version `2026-05-07`;
- public market WebSocket uses official OpenAPI `TradingClient`, msgpack, authentication, heartbeat and reconnect/re-auth/re-subscribe capabilities;
- web process does not own a WebSocket;
- V59 compatibility wrapper no longer imports/starts/stops legacy market/private WS;
- `/api/realtime` and `/api/realtime/status` read V86 sidecar state;
- legacy realtime start/stop POST routes are disabled and network-inert;
- no OTP, Trading Token, private order stream, position stream or order mutation;
- `live_order_ready=false` throughout.

## 10. V86 real workstation smoke — 2026-09-01

User-provided run transcript for implementation head `57001d64096b25cc9044a432bc8b5b997d6c4bd3` completed with `V86_EXIT_CODE=0`.

Observed:

- isolated SDK `dnse-sdk-openapi==1.4.6` installed successfully;
- canonical `dnse==0.5.0` remained unchanged;
- WebSocket connected to `wss://ws-openapi.dnse.com.vn/v1/stream?encoding=msgpack`;
- authentication succeeded;
- 20-symbol public subscriptions accepted;
- server ping received and pong sent;
- `transport_connected=True`;
- `authenticated=True`;
- `subscriptions_active=True`;
- `heartbeat_healthy=True`;
- `reconnect_count=0`;
- read-only REST smoke `SUCCESS`;
- `live_order_ready=False`.

The smoke ran after market hours, therefore `IDLE_MARKET_CLOSED` and zero ticks were expected. V77/V80 digests remained unchanged. V86 installer reported no web-owned WebSocket, no live-order endpoint and no credential/trading-state mutation.

Generated ZIP reported by the runner:
`artifacts/UPLOAD_THIS_v86_DNSE_OPENAPI_REALTIME-20260901-195512.zip`

Reported SHA-256:
`95ad8d4d9b84117659aeae4388340039322402c024094712e0b1433a703efb9e`

The ZIP itself has not yet been independently uploaded/audited in chat.

## 11. Active-session V86 visual verification — 2026-09-04

User screenshots around `2026-09-04 13:45 +07:00` showed the approved web with actual market-session public feed state:

- semantic `HEALTHY`;
- transport `CONNECTED`;
- auth `AUTHENTICATED`;
- subscriptions `ACTIVE` for 20 symbols / msgpack;
- tick freshness about `0.6s`;
- visible last tick `VIC 253`;
- reconnect count `0`;
- pong age about `15.0s`;
- contract `1.4.6`, API date `2026-05-07`.

This is real active-session evidence that the public sidecar can receive fresh ticks. It is still only one observed trading session; multi-session reconnect/recovery reliability remains unproven.

Full durable note: `tai_lieu_dieu_phoi/v86_visual_and_broker_freshness_20260904.md`.

## 12. DNSE broker-state freshness finding — 2026-09-04

The same screenshots showed:

- DNSE holdings/cash captured at `2026-09-04T13:45:37+07:00`;
- official V55 EOD valuation day `2026-08-21`;
- 7 positions;
- available cash about 59,566 VND;
- official EOD NAV about 543,618 VND.

Important distinction: `2026-08-21` is the local final-EOD valuation day, not the holdings capture timestamp. The holdings/cash REST call in this screenshot was fresh at 13:45.

However the user separately reports intermittent inability to obtain the real DNSE portfolio during some windows, especially market/open-session periods, with better success later in the evening. This is now an operational blocker.

Current active V59 fast REST reconcile reads account -> balances -> positions before persisting. A thrown balance/positions error therefore fails before snapshot write. The dangerous ambiguous case is a successful-but-empty positions response after a previously non-empty checkpoint.

The 2026-09-04 V86 broker-freshness patch adds:

- broker sync health state separate from last good snapshot;
- market-hours fail-closed protection for sudden non-empty -> empty holdings transitions;
- separate API freshness fields for holdings capture age and EOD valuation age;
- conservative absolute EOD-age warning;
- V86 UI correction so stale EOD cannot remain labeled operationally ready simply because broker valuation day equals the equally stale local market day.

V55 final-EOD-only official valuation remains unchanged. No broker market-price fallback is introduced.

## 13. Current V86 runtime procedure

The one-shot upgrade intentionally exits after install/smoke. It does not keep the web or sidecar alive.

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

## 14. Current blockers / next evidence

1. Obtain exact-head CI for the 2026-09-04 broker-freshness patch before workstation rollout.
2. Then rerun/install the V86 web patch and verify the broker freshness warning visually.
3. Collect time-of-day broker REST sync success/failure evidence; a failed read must retain/display last-known-good holdings with explicit degraded state.
4. V86 REST smoke emitted `InsecureRequestWarning` for an unverified HTTPS request. TLS certificate verification must be made fail-closed before any order-mutation work.
5. Continue long-lived public sidecar through multiple actual market sessions and record tick freshness, heartbeat, reconnect count/reasons and recovery behavior.
6. In an isolated read-only experiment, verify modern DNSE private position/account stream semantics and whether it provides initial state versus change-only events. No order mutation.
7. Before any future auto-order authority, require idempotency, uncertain-submit reconciliation, circuit breaker, REST reconciliation, private event health, Trading Token lifecycle and explicit promotion approval.

## 15. Workstation path and command safety

Canonical Git Bash repo path is `/d/VNQuant/vn-quant-system`.

A previous assistant command accidentally used `~/v31_mt5_40usd`, which belongs to another project and caused immediate script exit. Never reuse that path for VN Quant.

On Windows CPython launched from Git Bash, multi-entry `PYTHONPATH` must use Windows semantics (`;`) with `cygpath -w`.

## 16. Evidence discipline

Always distinguish:

- CI green: code/contracts compile and tests pass;
- workstation smoke/visual evidence: the real local environment performed/displayed the tested state;
- historical research evidence: may be selected/contaminated and is not fresh OOS;
- forward-paper evidence: fresh observations under frozen policy;
- live authority: currently false.

Never promote a policy or auto-order capability because a UI renders, an HTTP endpoint returns 200, one market session looks healthy, or one shadow observation looks favorable.
