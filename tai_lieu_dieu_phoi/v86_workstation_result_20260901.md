# V86 workstation result — 2026-09-01

Status: `SMOKE_PASS_WITH_TLS_WARNING`.

Evidence source: user-provided terminal transcript from the canonical Windows workstation. The generated ZIP was reported by the runner but had not yet been uploaded/audited in chat at the time of this document.

## Provenance

- branch: `agent/v86-dnse-openapi-realtime-hardening`
- implementation HEAD: `57001d64096b25cc9044a432bc8b5b997d6c4bd3`
- canonical workstation repo: `D:\VNQuant\vn-quant-system`
- canonical Git Bash path: `/d/VNQuant/vn-quant-system`

## Environment isolation

Before/after canonical DNSE distribution:

`dnse==0.5.0`

Isolated sidecar environment:

`vn_quant_local_system/.venv-dnse-openapi-v86`

Installed/verified:

- `dnse-sdk-openapi==1.4.6`
- `websockets==17.1`
- `msgpack==1.2.2`
- `tzdata==2025.2`

Runner reported `CANONICAL_ENV_ISOLATION=PASS` and verified the sidecar environment did not contain the legacy `dnse` distribution.

Pinned read-only OpenAPI REST date version:

`2026-05-07`

## Subscription set

The runner built a 20-symbol public realtime set from the existing approved portfolio/preview logic:

`BAF,GMD,STB,ACB,MSB,HCM,LPB,VPI,SAB,KDC,TLG,SBT,DHC,VNM,HDB,SSB,VIC,HNG,OCB,BMP`

No private order or position stream was enabled.

## Contract tests

14 V86 tests passed on the workstation, covering:

- sanitized atomic state;
- pinned SDK/API version;
- market-open vs market-closed freshness semantics;
- HEALTHY requirements;
- symbol normalization/limits;
- stale bridge fail-closed behavior;
- actual V59 web wrapper sidecar-only ownership;
- health-only frontend/no order mutation;
- installer idempotence;
- Windows web runner ownership contract.

## Real DNSE OpenAPI smoke

Observed around 19:58 Vietnam time:

- WebSocket connect: success.
- Session ID assigned by DNSE.
- HMAC authentication: success.
- Public tick subscriptions accepted for the symbol set.
- Server ping received; client sent pong.
- Smoke disconnected cleanly after the configured ~20 second read-only window.

Final active-state values reported by runner:

```text
V86_SMOKE_STATUS=IDLE_MARKET_CLOSED
V86_TRANSPORT_CONNECTED=True
V86_AUTHENTICATED=True
V86_SUBSCRIPTIONS_ACTIVE=True
V86_HEARTBEAT_HEALTHY=True
V86_EVENT_COUNT=0
V86_RECONNECT_COUNT=0
V86_REST_SMOKE=SUCCESS
V86_LIVE_ORDER_READY=False
```

Because the smoke ran after Vietnamese market hours, `IDLE_MARKET_CLOSED` and zero trade events are expected. This is not evidence of a stale feed during an active session.

## Web integration

Installer returned `SUCCESS` with:

- existing user-facing port: 8787;
- endpoint: `/api/realtime-v86`;
- `isolated_sidecar_required=true`;
- `web_process_owns_websocket=false`;
- `legacy_v59_wrapper_ws_disabled=true`;
- `canonical_rest_runtime_replaced=false`;
- `credentials_or_trading_state_touched=false`;
- `live_order_endpoint_added=false`;
- `trading_token_requested=false`.

The old V59 wrapper is now compatibility-only and cannot own/start legacy market/private WebSockets under the V86 contract.

## Persistent-state integrity

V77 digest before/after:

`f7f961a202d386815efad18e11d01713ad5eddc2d68297c06bca468b8d85fdc8`

V80 digest before/after:

`8f3fcc0ef22d8b40ac2470691159374a2e7c4b32d21dbd75ddff3fd9218b8c89`

Canonical `dnse==0.5.0` also remained unchanged after the upgrade/smoke.

The runner's logical-market integrity assertion did not fail. The pasted transcript did not include the actual before/after logical fingerprint values, so this document does not invent them.

## Generated artifact

Runner reported:

`artifacts/UPLOAD_THIS_v86_DNSE_OPENAPI_REALTIME-20260901-195512.zip`

SHA-256:

`95ad8d4d9b84117659aeae4388340039322402c024094712e0b1433a703efb9e`

The ZIP still requires independent upload/audit if artifact-level verification is needed.

## Important operational clarification

The one-shot upgrade is intentionally finite. It installs/tests/patches and exits; it does not keep the sidecar or web running.

Long-lived observation requires two terminals:

1. `bash scripts/run_v86_dnse_openapi_realtime_sidecar_gitbash.sh`
2. `cd vn_quant_local_system && bash scripts/run_web_gitbash.sh`

This separation is intentional: the web process must not own the realtime WebSocket.

## New blocker found during smoke: TLS verification

The REST smoke emitted:

`InsecureRequestWarning: Unverified HTTPS request is being made to host 'openapi.dnse.com.vn'`

This did not prevent the read-only REST smoke from succeeding, but it is not acceptable as a production/order-mutation security posture.

Required follow-up:

- identify whether the official SDK defaults to `verify=False` or the current wrapper/runtime disables verification;
- make certificate verification explicit and fail-closed;
- add regression/smoke evidence that the warning is gone and server identity is verified;
- do not enable order mutation before this is resolved.

## Decision

V86 public realtime architecture is validated at short read-only smoke level. It is not yet proven across active trading sessions and is not live-order ready.

Next evidence should be:

1. TLS verification hardening;
2. long-lived active-session market tick/reconnect telemetry over multiple sessions;
3. V86 health UI visual verification;
4. only then private order/position event plumbing as a read-only infrastructure phase.
