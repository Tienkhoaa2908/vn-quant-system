# V85 — DNSE realtime connectivity forensic audit

## Trigger

Workstation web on 2026-08-24 repeatedly logged successful localhost polling:

`GET /api/realtime HTTP/1.1 200`

while the upstream streaming layer repeatedly logged reconnect failures ending in WebSocket close code `1000 (OK)`.

HTTP 200 from localhost proves only that the local endpoint answers. It does not prove the upstream DNSE WebSocket is authenticated, subscribed, fresh, or stable.

## Repository/runtime fact before V85

The approved workstation currently hard-pins the legacy Python distribution `dnse==0.5.0` in `vn_quant_local_system/src/vn_quant_local/data_sources.py`. REST/EOD and read-only portfolio flows are already working on that runtime and must not be broken by an in-place package swap.

Upstream DNSE evidence relevant to the failure mode:

- `dnse-tech/dnse-py` issue #1 reports two defects in package 0.5.0: WebSocket auth nonce sent as integer rather than string, and reconnect calling connect without first closing/resetting the previous socket. The reported reconnect failure family is consistent with the workstation screenshot.
- DNSE now publishes a separate official OpenAPI SDK distribution, `dnse-sdk-openapi`; PyPI latest observed during V85 design is 1.4.6, released 2026-07-01.
- That newer SDK exposes `TradingClient` with heartbeat, automatic reconnect, re-authentication and re-subscription. It imports under the same top-level Python module name `dnse`, therefore it must not be installed over the canonical legacy runtime without a deliberate REST migration.

These upstream facts are hypotheses about the workstation until V85 fingerprints the actually installed source.

## V85 scope

V85 is forensic/read-only only. It does **not**:

- install or upgrade any Python package;
- modify the approved web;
- create a trading token or request OTP;
- subscribe to private order channels;
- send/cancel/replace any order;
- change C3/V83/V84 policy;
- mutate V77/V80 or market bars.

The one-shot audit captures:

1. canonical Python/platform;
2. installed `dnse`, `dnse-sdk-openapi` and `websockets` distribution versions;
3. `dnse.__file__` origin plus hashes of candidate stream/auth/connection source files;
4. source signatures for integer-vs-string nonce and old-socket reconnect cleanup;
5. local realtime integration matches by relative path/hash/line number/marker only — no source copy and no credentials;
6. several sanitized samples from `http://127.0.0.1:8787/api/realtime` while the web is running;
7. existing read-only DNSE REST smoke, summarized without credentials/account identifiers;
8. logical market fingerprint and full V77/V80 state digest before/after.

## Decision labels

`LEGACY_SDK_RECONNECT_BUG_SIGNATURE=true` means the actual installed source matches at least one known legacy defect signature.

`REST_OK_WS_UNSTABLE=true` means REST is operational while the WebSocket layer remains at risk/unhealthy; localhost HTTP 200 alone cannot clear this gate.

`LOCAL_REALTIME_DIRTY_OR_UNTRACKED=true` means the `/api/realtime` implementation is coming from approved local-only/dirty web code rather than the branch source of truth and must be recovered before a durable fix.

`MIGRATION_RECOMMENDED=true` does not authorize installation or trading. It means the next implementation should isolate the streaming runtime.

`LIVE_ORDER_READY` is hard-coded `false` in V85.

## Preferred next architecture if the artifact confirms the legacy defect

Do **not** replace `dnse==0.5.0` inside the canonical workstation `.venv` immediately.

Use an isolated streaming sidecar environment/process with pinned `dnse-sdk-openapi==1.4.6`, while keeping the current REST/EOD/portfolio runtime unchanged until separately migrated and regression-tested.

The approved web remains the only user-facing service on port 8787. The sidecar should expose state to the parent process through localhost IPC or atomic local state, not a second user-facing dashboard.

Before any future automatic order capability can be considered, the execution infrastructure must fail closed on at least:

- streaming transport connected and authenticated;
- subscription acknowledgement and resubscription after reconnect;
- heartbeat/freshness threshold;
- REST account/order reconciliation;
- order-event stream health;
- idempotent client-order identity;
- bounded reconnect/backoff and circuit breaker;
- post-order reconciliation before another action.

V85 does not implement those live-order functions. It only establishes the evidence needed to build the streaming foundation safely.

## Workstation entrypoint

```bash
bash scripts/run_v85_dnse_realtime_connectivity_audit_gitbash.sh
```

Expected upload artifact:

`artifacts/UPLOAD_THIS_v85_DNSE_REALTIME_CONNECTIVITY_AUDIT-*.zip`

Run with the existing web server still running when possible so `/api/realtime` can be sampled in the same failure state shown in the screenshot.
