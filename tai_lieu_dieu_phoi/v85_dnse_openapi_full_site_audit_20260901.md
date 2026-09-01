# V85 — DNSE OpenAPI full-site integration audit — 2026-09-01

Status: RESEARCH / ARCHITECTURE AUDIT ONLY. No live-order authority.

## Scope

Official/current sources reviewed:

- https://developers.dnse.com.vn/
- current OpenAPI platform, registration, authentication, FAQ, error codes, rate limits, API/SDK versioning;
- current Market Data WebSocket and Trading Data WebSocket documentation;
- current REST endpoint docs for accounts, balances, positions, OHLC, loan packages, corporate-action history, working dates;
- official `dnse-tech/openapi-sdk` repository and its Python WebSocket client/examples;
- PyPI metadata for `dnse-sdk-openapi` and legacy `dnse`;
- official DNSE LightSpeed registration/product/terms pages and older V1 documentation, only to distinguish generations.

Repository surfaces compared:

- `src/he_thong_dinh_luong/nguon_dnse.py`
- `src/he_thong_dinh_luong/dnse_portfolio.py`
- `vn_quant_local_system/src/vn_quant_local/data_sources.py`
- `vn_quant_local_system/src/vn_quant_local/v59_market_stream.py`
- `vn_quant_local_system/src/vn_quant_local/v59_fast_realtime.py`
- V85 workstation forensic evidence.

## Executive conclusion

The project is not using DNSE completely incorrectly. The REST/EOD/account integration is mostly aligned with current OpenAPI endpoint semantics and is empirically healthy on the workstation. However, it is pinned to the legacy `dnse==0.5.0` client and does not explicitly pin the OpenAPI date-version or surface rate-limit metadata. That makes the REST integration backward-compatible by accident/default rather than explicit contract.

The realtime integration is not production-grade under current DNSE documentation. It uses legacy `DnseMarketStream` / `DnseTradingStream`, and V85 proved the installed 0.5.0 source has both the nonce-type bug and reconnect-without-close/reset bug. Local `/api/realtime` HTTP 200 is not a valid feed-health signal.

The current official WebSocket contract requires explicit connection/auth/subscription health, PING/PONG liveness, awareness of the server-enforced maximum 8-hour session, and reconnection/re-subscription behavior. The newer official OpenAPI SDK implements these concerns in `TradingClient` and should be evaluated in an isolated runtime rather than installed over the canonical `.venv`.

## Current OpenAPI generation vs old LightSpeed V1

Do not mix the old V1 docs with current OpenAPI.

Current OpenAPI:

- REST base: `https://openapi.dnse.com.vn`
- auth: API Key + API Secret HMAC signature + Date/Nonce
- optional-but-recommended date-based `version` header
- trading mutation also requires an 8-hour Trading Token obtained via the configured OTP method
- WebSocket base: `wss://ws-openapi.dnse.com.vn`

Old V1 docs still indexed on DNSE support pages describe username/password login, JWT and older hosts/datafeed plumbing. They are legacy references, not the contract to build new code against.

## Authentication findings

Current REST requests require `x-api-key`, `x-Signature`, and RFC1123 UTC `Date`. The signing nonce is a fresh UUID4 hex string of 32 characters per request. DNSE rejects excessive clock skew; the documented tolerance is ±1 minute.

Trading mutations (place/replace/cancel/close position) additionally require `trading-token`. The token is obtained after OTP verification and is valid for 8 hours. Smart OTP is manual and short-lived; Email OTP can be integrated but still remains a second-factor workflow.

Implication for this project:

- clock synchronization becomes a hard infrastructure dependency for live trading;
- API credentials and Trading Token must have separate lifecycles;
- no trading token should be persisted in browser code;
- any future auto-order service must fail closed when trading-token validity is unknown.

## API versioning findings

DNSE uses date-based API versioning via header `version: YYYY-MM-DD`.

- requests with no version currently fall back to `2026-05-07`;
- DNSE explicitly recommends pinning a version in code;
- version `2026-07-23` added/changed order functionality, including conditional order support and some breaking order-id behavior;
- old versions currently have no automatic sunset, but clients can miss newer behavior/features if they rely on the default.

Current repo gap:

`DnseRestSource` and `DnseReadOnlyClient` instantiate legacy `DnseClient` without a visible explicit OpenAPI date-version. The fact that REST works is therefore not the same as having a deliberate version contract.

Required correction in the eventual migration:

- choose and pin one API version explicitly;
- record it in reports/logs;
- add compatibility regression tests around any version upgrade;
- parse responses forward-compatibly (ignore unknown added fields).

## Rate-limit findings

Limits are per API Key and per endpoint. Important current values include:

- accounts: 1,000/hour, 10,000/day
- balances: 10,000/hour, 100,000/day
- positions: 10,000/hour, 100,000/day
- OHLC: 50,000/hour, 100,000/day
- latest trade/quote: 10,000/hour, 100,000/day
- working dates / security definition / corporate-action history: 1,000/hour, 10,000/day
- place/replace/cancel order: 50,000/hour, 100,000/day each
- email OTP / trading-token creation: 100/hour, 1,000/day

DNSE exposes `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset`; 429 must be handled with wait/backoff rather than blind retry.

Current repo gap:

The wrappers consume `.json()` and do not promote rate-limit headers into operational telemetry. Ordinary EOD sync is unlikely to hit quotas, but using REST polling as a realtime substitute is wasteful and can become dangerous once order/status polling is added.

Required correction:

- capture and expose rate-limit headers;
- cache low-change REST resources;
- use WebSocket push for realtime prices/order/position events;
- classify 429 separately and wait until reset.

## Market Data WebSocket contract

Current official contract:

- base `wss://ws-openapi.dnse.com.vn`;
- a WebSocket connection is valid for at most 8 hours; server will disconnect it afterward;
- server PING every ~3 minutes;
- client must answer PONG within 1 minute or it is disconnected;
- client may send proactive keepalive;
- `msgpack` is recommended for production efficiency; JSON is simpler for debug;
- symbols must be uppercase.

Useful channels for this project:

- `Trade`: realtime match price/volume; preferred for simple live-price display;
- `Quotes`: depth only when the UI/execution layer actually needs it;
- `Market Index`: ~5-second index updates;
- `Expected Price`: ATO/ATC only;
- `Security Definition`: BOD/EOD metadata including reference/ceiling/floor/status/listing fields;
- `OHLC` / `OHLC Closed`: realtime/formally closed candle use cases.

DNSE explicitly states Trade Extra has extra derived information and plain Trade is preferable when those fields are not required, for speed/bandwidth.

Current repo problem:

V59 declares a thread `RUNNING` immediately after creating `DnseMarketStream`; it does not prove transport connected, authentication succeeded, subscriptions are active, heartbeat is healthy, or ticks are fresh. V85 additionally proved the installed legacy stream has known auth/reconnect defects.

## Trading Data WebSocket contract

Current documented private realtime channels are:

- `order.{market_type}.{encoding}` — updates when an order is created, status changes, or fills change;
- `position.{market_type}.{encoding}` — updates when a position changes.

FAQ distinguishes:

- `accountNo`: REST trading endpoint identifier;
- `investorId`: Trading WebSocket identity.

Current V59 private stream subscribes to positions, orders and opportunistically `account` if available in the old SDK. The current public Trading Data docs center on documented order/position channels. Future code must not depend on an undocumented account-stream behavior; use REST balance/account reconciliation for account cash and documented WS channels for order/position changes.

For future automated execution the correct reconciliation shape is:

REST place/replace/cancel -> Trading WS order event -> REST order-detail/order-book reconciliation -> position/account reconciliation.

A missing WS event must never cause a blind duplicate order.

## REST endpoint audit against current repo

### EOD OHLC

Current DNSE endpoint remains `GET /price/ohlc`.

The repo uses exactly `/price/ohlc`, STOCK/INDEX type, `resolution=1D`, `from`, `to`. Its pagination/cursor de-duplication and fail-closed duplicate-day handling are stronger than a naive client and should be preserved.

Assessment: endpoint usage is conceptually correct; migrate SDK/versioning/telemetry, not the research semantics.

### Accounts / balances / positions

Current endpoints:

- `GET /accounts`
- `GET /accounts/:accountNo/balances`
- `GET /accounts/:accountNo/positions`

The repo uses these paths and correctly uses account number for REST. The explicit read-only endpoint allowlist is good safety design.

Assessment: conceptually correct.

### Working dates

DNSE supplies `GET /market/working-dates`, returning trading days over roughly the next/current one-year scope with weekends/holidays removed.

Current project should integrate this as a source for near-term market-calendar truth rather than infer all future sessions only from weekdays/local bars. Historical research still requires its own complete historical session lineage.

### Corporate actions

Current documented endpoint is `GET /accounts/:accountNo/corporate-action-history`: it is account-specific rights-event history, not a universal historical corporate-action master for every symbol.

It can help reconcile actual account cash/rights, but it does NOT by itself close the project's market-wide corporate-action inventory/price-basis gate.

### Security Definition / Instruments

Current API/WS provides security metadata and trading status. This can strengthen current-session venue/status validation and price-band/order validation. It does not automatically prove PIT historical HOSE membership, so it must not be used to falsely close the PIT-HOSE lineage gate.

## Order API implications

Current API requires:

- accountNo
- marketType / orderCategory
- symbol uppercase
- loanPackageId
- side NB/NS
- orderType
- quantity
- price (0 for non-LO where documented)
- trading-token header.

For STOCK, valid quantities are either round lots in multiples of 100 or odd lots 1-99; values such as 101 are invalid. Buy/sell quantity must also respect PPSE/qmax. LO prices must respect floor/ceiling and tick-size rules.

The current official error taxonomy is rich enough to build deterministic handling:

- auth/permission/input errors: do not retry blindly;
- 429: respect reset headers;
- 500/503/TIMEOUT: exponential backoff, bounded retries;
- session/order-state errors: reconcile state before another mutation.

No auto-order implementation should be approved until these codes are mapped into fail-closed state transitions.

## Fees / commercial terms

The public developer pages reviewed do not state a definitive current LightSpeed API subscription price. Registration is a service enrollment/contract flow. The user reports that the service is paid; that may be an account-specific/current commercial term visible inside Entrade X or the signed service proposal and cannot be contradicted by public pages we can crawl.

Official older DNSE Ami X FAQ says orders sent via API do not incur an additional API-specific transaction surcharge and are charged under the normal trading fee schedule; it also describes Ami X data as free for DNSE customers. This must not be generalized into a claim that current LightSpeed OpenAPI subscription/service access is free.

Normal trading economics still apply. DNSE loan-package/order/account data includes brokerage buying/selling fees, exchange transfer fees and order fee/tax fields. The quant simulator should continue modeling transaction costs independently of any LightSpeed service subscription fee.

Action: if an exact recurring LightSpeed fee is needed for TCO, capture the current Entrade X LightSpeed registration/contract price from the user's logged-in page or contract and store it as account-local configuration/evidence, not hard-coded research truth.

## SDK generation and packaging

Legacy project runtime:

- package: `dnse==0.5.0`
- top-level module: `dnse`
- V85 confirmed known legacy WS nonce/reconnect bug signatures.

New official SDK line:

- PyPI project: `dnse-sdk-openapi`
- observed latest release: `1.4.6` (2026-07-01)
- official repo: `dnse-tech/openapi-sdk`
- top-level import also uses `dnse` (`DNSEClient`, `TradingClient`).

The official repo/PyPI documentation itself currently contains an installation naming inconsistency (`pip install openapi-sdk` is shown while PyPI project is `dnse-sdk-openapi`); an open official GitHub issue documents that discrepancy.

Because old and new distributions share the `dnse` import namespace, installing the new package directly over the canonical `.venv` is unsafe. Use a separate realtime/migration environment first.

## Recommended architecture

### Phase A — current production-safe read-only state

Keep canonical `.venv` REST/EOD/account reader unchanged while introducing observability:

- explicit REST API-version telemetry;
- clock-skew check;
- rate-limit telemetry;
- distinguish local HTTP health from upstream REST and WS health.

### Phase B — isolated Market Data sidecar

Separate Python environment pinned to a verified `dnse-sdk-openapi` wheel/hash.

One sidecar process owns Market Data WS and exposes only local state to the 8787 web process. Prefer msgpack in production. Subscribe only to channels needed by the product (Trade + Market Index initially; Quotes/Expected Price only when needed).

Health state must include at least:

- process_alive
- transport_connected
- authenticated
- subscription_acked/active
- last_pong_at / heartbeat_age
- last_market_event_at / tick_age
- reconnect_count / last_reconnect_at
- session_started_at / proactive 8h restart deadline
- last_error
- subscribed symbols/channels

`/api/realtime` should return semantic state such as HEALTHY / STALE / DEGRADED / DISCONNECTED, not merely HTTP 200.

### Phase C — private/order sidecar extension

Only after market-data stability has been demonstrated across multiple real sessions:

- documented Trading WS order/position channels;
- REST balance/order reconciliation;
- Trading Token lifecycle;
- explicit error-code state machine;
- rate-limit/circuit-breaker/idempotency controls.

### Phase D — automated-order gate

Auto-order remains BLOCKED until all critical gates are true:

- REST auth/version/clock healthy
- trading token valid
- market WS authenticated + subscribed + fresh
- order WS authenticated + subscribed + healthy
- position stream healthy
- PPSE/loan package/current session/security status checked
- rate-limit remaining safe
- no unresolved previous order
- deterministic client intent/idempotency key persisted
- REST post-submit reconciliation completed
- circuit breaker armed

Any uncertain outcome after submitting an order must transition to `RECONCILE_ONLY`, never resend blindly.

## Data-lineage opportunities from DNSE current API

- Working Dates can improve operational trading-calendar truth.
- Security Definition can improve current-session symbol status, venue/product group and price-band validation.
- Corporate Action History can reconcile rights events actually affecting the account.
- None of these automatically closes market-wide PIT HOSE membership, historical price-basis or universal corporate-action inventory gates. Those claims remain fail-closed until dedicated lineage evidence exists.

## Decision

1. Do not suppress the current legacy reconnect logs and call the problem fixed.
2. Do not in-place upgrade the canonical `.venv`.
3. Keep EOD/portfolio REST behavior temporarily, but migrate toward explicit API-version and rate-limit contracts.
4. Replace the legacy realtime implementation with an isolated current-OpenAPI WebSocket sidecar.
5. Treat port 8787 HTTP liveness, upstream REST health, market WS health and private/order WS health as independent dimensions.
6. Keep all automated order authority blocked until market-data sidecar and later private-stream/reconciliation gates have real workstation evidence.
