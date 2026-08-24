# V85 workstation result — 2026-08-24

## Status

PASS — read-only forensic audit completed. This is connectivity evidence only; `live_order_ready=false` remains mandatory.

Artifact implementation HEAD: `61c9b330547c6ce036e4deeac65630434e7a8b83`.

## Canonical runtime

- Windows 11, Python `3.12.13`.
- Canonical interpreter: `vn_quant_local_system/.venv/Scripts/python.exe`.
- Installed `dnse` distribution: `0.5.0`.
- `dnse-sdk-openapi` distribution: not installed in canonical runtime.
- `websockets`: `17.0.1`.

Installed legacy stream source fingerprint conclusively matches both V85 risk signatures:

- auth nonce is emitted as integer (`nonce_integer_signature=true`, string signature false);
- reconnect implementation exists but neither closes nor resets the old socket before reconnect (`reconnect_closes_old_socket_before_connect=false`, `reconnect_resets_old_socket_before_connect=false`).

Therefore `legacy_sdk_reconnect_bug_signature=true`.

## REST vs WebSocket separation

Existing DNSE REST/account smoke is healthy:

- market data `SUCCESS`, latest day `2026-08-24`, 16 rows in smoke range;
- portfolio/account read `SUCCESS`, account count 1;
- overall REST smoke `SUCCESS`.

The existing local realtime implementation is present and tracked under V59 (`v59_market_stream.py`, `v59_fast_realtime.py`, `webapp_v59.py`, realtime JS/CSS). It uses legacy `DnseMarketStream` and `DnseTradingStream` from the installed `dnse==0.5.0` runtime.

The audit sampled `http://127.0.0.1:8787/api/realtime` eight times while the web process was not accepting connections; every sample received WinError 10061 connection refused. This does not contradict the earlier screenshot in which `/api/realtime` returned HTTP 200 while the upstream WebSocket repeatedly logged reconnect failures. It proves localhost HTTP liveness and upstream feed health must be treated as separate gates.

Conclusion flags:

- `rest_connectivity_ok=true`;
- `rest_ok_ws_unstable=true`;
- `migration_recommended=true`;
- recommended architecture: `ISOLATED_DNSE_OPENAPI_WEBSOCKET_SIDECAR_KEEP_CANONICAL_REST_UNCHANGED`;
- `live_order_ready=false`.

## Integrity / safety

Market logical bars were byte-identical before/after:

- first day `2015-06-29`;
- last day `2026-08-21`;
- rows `301259`;
- logical SHA256 `7f48a06841fd33de3bf1688d371c13edd5a7a15d896f18ebc32d4fdd0eaf8cad`.

Persistent states unchanged:

- V77 digest `f7f961a202d386815efad18e11d01713ad5eddc2d68297c06bca468b8d85fdc8` before/after;
- V80 digest `8f3fcc0ef22d8b40ac2470691159374a2e7c4b32d21dbd75ddff3fd9218b8c89` before/after.

No packages were installed/upgraded, no web files modified, no trading token requested, no credentials emitted, and no orders sent.

## Decision

Do not patch/suppress the legacy reconnect log and do not upgrade the canonical `.venv` in place. Build V86 as an isolated OpenAPI realtime sidecar runtime, then expose its explicit transport/auth/subscription/tick-freshness health to the existing port-8787 web. Private order-event streaming and order placement remain out of scope until market-data sidecar stability is proven first.
