# V85 handoff

V85 is complete forensic evidence. It does not modify runtime behavior.

Confirmed on the canonical Windows workstation:

- REST/account connectivity is healthy on `dnse==0.5.0`;
- legacy WebSocket source contains the known nonce integer and reconnect-without-close/reset signatures;
- local realtime V59 code uses `DnseMarketStream` / `DnseTradingStream` from that legacy runtime;
- `live_order_ready=false`;
- market/V77/V80 state remained unchanged.

Do not upgrade the canonical `.venv` in place. Next branch is V86: isolated `dnse-sdk-openapi==1.4.6` realtime sidecar for market-data health/ticks first, with the existing 8787 web as the only user-facing UI. Order-event/private stream and any order API stay blocked until sidecar market-data stability is proven.
