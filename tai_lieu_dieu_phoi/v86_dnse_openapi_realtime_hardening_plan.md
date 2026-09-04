# V86 — DNSE OpenAPI realtime hardening

Status: implementation candidate, no live-order authority.

## Commercial gate

Official/public DNSE material reviewed on 2026-09-01 does not expose a separate current LightSpeed API subscription/usage fee in the public service fee schedule or LightSpeed terms. DNSE's official API FAQ states API-submitted orders use the normal transaction fee schedule rather than an added API-order surcharge. LightSpeed is nevertheless a registered service and DNSE can change commercial terms; therefore the project records the conclusion as **no separate public API fee found at this date**, not `FREE_FOREVER`.

Any account-specific signed contract/Entrade X charge overrides this public-doc observation and belongs in account-local TCO evidence, never hard-coded research truth.

## Scope approved by user

V86 hardens the connectivity layer without enabling order mutation.

1. Keep the canonical workstation `.venv` on legacy `dnse==0.5.0` temporarily so healthy EOD/account/portfolio REST is not broken by a namespace collision.
2. Create a separate `.venv-dnse-openapi-v86` containing `dnse-sdk-openapi==1.4.6` plus its explicit runtime dependencies.
3. Pin the new-SDK read-only REST smoke to OpenAPI date-version `2026-05-07`, matching the compatibility contract selected after the full-site audit.
4. Run Market Data WebSocket through the new official `TradingClient`, msgpack, auto reconnect/re-auth/re-subscribe, heartbeat tracking.
5. Subscribe only to public Trade market data for the first rollout. Do not obtain a Trading Token and do not subscribe to private order/position channels.
6. Write sanitized atomic sidecar state under workstation `data/state`.
7. Make the existing web `:8787` read that state. Local HTTP 200 is never interpreted as feed health.
8. Preserve market store, V77 and V80 state exactly.

## Semantic realtime health

V86 exposes independent dimensions:

- sidecar process freshness;
- transport connected;
- HMAC WebSocket authenticated;
- subscriptions active;
- heartbeat/PONG healthy;
- last-tick age during the approximate market window;
- reconnect count and last reconnect timestamp;
- pinned new-SDK REST/account smoke status and latency.

Possible semantic states include `HEALTHY`, `IDLE_MARKET_CLOSED`, `DEGRADED_*`, `ERROR`, `STOPPED` and stale-process-state at the web bridge.

The first rollout intentionally uses a local-clock market-window approximation only for tick-staleness classification. It is explicitly not an exchange-calendar truth claim. DNSE working-dates/session/security-definition integration is a later hardening increment after the sidecar itself is proven stable.

## Legacy V59 ownership closure

The final architecture review found a critical compatibility path: the approved workstation launcher still starts `vn_quant_local.webapp_v59`. Historically that wrapper imported and started the old private and market WebSocket implementations, including automatic startup during web-server launch and broker refresh.

V86 therefore changes the historical `webapp_v59` module into a compatibility shell rather than leaving it untouched:

- fast legacy REST/account/plan behavior is preserved;
- the web process imports no V59 realtime transport module;
- the web process performs no legacy realtime start/stop call;
- `/api/realtime` and `/api/realtime/status` read V86 sidecar health only;
- legacy POST realtime start/stop endpoints return `DISABLED_V86_SIDECAR_OWNED` and perform no network mutation;
- root HTML no longer injects the V59 realtime JavaScript/CSS transport UI;
- `serve_web_gitbash.sh` explicitly declares `WEB_PROCESS_OWNS_WEBSOCKET=false` and uses a Windows-native semicolon-separated `PYTHONPATH`.

The V86 installer now fails closed unless this compatibility wrapper contains the V86 disable marker and contains none of the legacy WebSocket ownership imports/calls. Dedicated CI checks the same contract on Ubuntu and Windows.

## Safety contract

Hard false throughout V86:

- private order stream;
- private position stream;
- Trading Token request;
- OTP request;
- place/replace/cancel/close order;
- live-order readiness;
- model/research policy changes.

The legacy `/api/realtime` GET route, if present in the approved dirty workstation web, is replaced only as a read-only health surface. The web process no longer owns/starts the legacy realtime WebSocket.

## Workstation evidence required

The one-shot upgrade must prove:

- canonical environment remains `dnse==0.5.0` before/after;
- sidecar environment is exactly `dnse-sdk-openapi==1.4.6` and does not contain legacy distribution `dnse`;
- real read-only REST smoke succeeds on explicitly pinned API version;
- real WebSocket connects, authenticates, records subscriptions, and reports heartbeat healthy;
- active sidecar state is sanitized and `live_order_ready=false`;
- market logical bars, V77 and V80 digests are unchanged;
- web installer adds no order endpoint;
- the actual launcher path `serve_web_gitbash.sh -> vn_quant_local.webapp_v59` cannot create or own a legacy V59 WebSocket.

After the one-shot is audited, run the long-lived sidecar through multiple real sessions before any private Trading WebSocket or order-state-machine work is permitted.
