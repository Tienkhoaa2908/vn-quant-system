# KNOWN ISSUES AND GUARDRAILS

Updated: 2026-09-04

This file records failure modes already encountered so future chats/agents do not repeat them.

## 1. Wrong repository path can terminate scripts immediately

Observed mistake: a VN Quant command was accidentally given with `~/v31_mt5_40usd`, an unrelated project path. Because the block used `cd ... || exit 1`, the Git Bash window could close immediately.

Do:
- use `/d/VNQuant/vn-quant-system` in Git Bash;
- when debugging, keep the shell open and print exit code/error before closing.

Avoid:
- copying paths from other projects;
- using `exit 1` in a double-clicked shell without preserving visible diagnostics.

## 2. Stale coordination docs created false current state

Old top-level files still claimed PR #20-30 / July 2026 state as current after the project had reached V83-V86.

Do:
- treat `CURRENT_STATE.md` as the single current snapshot;
- update it every time durable state changes;
- keep historical evidence versioned by Vxx/date.

Avoid:
- maintaining multiple files named current/status/handoff with conflicting dates;
- assuming a filename implies freshness.

## 3. CI green is not research evidence

Do:
- state whether evidence is CI, workstation smoke, historical research, fresh paper OOS, or live.

Avoid:
- treating tests passing as proof of alpha/profit/production readiness.

## 4. SQLite WAL physical SHA can produce a false mutation alarm

V79 showed that WAL/checkpoint behavior can change the physical SQLite main-file hash without changing logical market bars.

Do:
- use deterministic logical `bars` fingerprint as the mutation invariant;
- retain physical SHA as audit metadata only.

Avoid:
- failing a research run solely because checkpointing changes physical `.sqlite3` SHA while logical content is identical.

## 5. V77 causal execution-floor bug was caught before fills

A stale local store plus evening target capture could have allowed a future sync to retroactively use an open that occurred before target capture.

Do:
- preserve the frozen state;
- enforce the V77 causal execution-floor contract;
- require zero retroactive fills.

Avoid:
- deleting/resetting `du_lieu/v77-paper-oos-state/` to simplify replays.

## 6. Windows Git Bash + Windows Python path semantics

Windows native Python does not use POSIX `:` for multi-entry `PYTHONPATH`.

Do:
- convert paths with `cygpath -w`;
- separate Windows Python paths with `;`.

Avoid:
- reusing Linux path syntax in Windows CPython runners.

## 7. DNSE legacy WebSocket SDK 0.5.0 is not production-safe for realtime

V85 workstation forensic evidence found legacy nonce/reconnect bug signatures in the installed `dnse==0.5.0` stream implementation while REST/account remained healthy.

Do:
- keep legacy SDK temporarily only for the currently working canonical REST path;
- use isolated V86 realtime env with `dnse-sdk-openapi==1.4.6`;
- preserve namespace isolation.

Avoid:
- installing the new SDK into the same `.venv` as legacy `dnse`; both use import namespace `dnse`;
- suppressing reconnect logs instead of fixing architecture.

## 8. `HTTP 200` is not realtime health

The old localhost `/api/realtime` could return HTTP 200 while upstream WebSocket repeatedly disconnected/reconnected.

Do:
- evaluate process freshness, transport, auth, subscription state, heartbeat and tick freshness separately;
- expose semantic `HEALTHY/IDLE/DEGRADED/...` state.

Avoid:
- using endpoint liveness as feed-health or auto-order permission.

## 9. WebSocket close `1000 (OK)` is not itself the defect

`1000` is a normal WebSocket closure code. The observed problem was legacy reconnect lifecycle and inadequate health semantics.

Do:
- classify why/how often closures happen and whether re-auth/re-subscribe/tick freshness recover.

Avoid:
- treating every code 1000 as a network failure;
- conversely, treating a normal close code as proof the overall feed is healthy.

## 10. Actual V59 launcher still owned legacy WebSockets until explicitly closed

A first V86 pass patched the base web route but architecture review found `serve_web_gitbash.sh` actually launched `vn_quant_local.webapp_v59`, which historically auto-started private + market V59 streams.

Do:
- keep V59 wrapper as a compatibility shell only;
- fail CI/installer if legacy realtime transport imports/start/stop calls return;
- keep `WEB_PROCESS_OWNS_WEBSOCKET=false`.

Avoid:
- patching only the visible route without tracing the real launcher/import path.

## 11. V86 one-shot installer does not keep web or sidecar alive

The successful V86 one-shot ends after smoke/install/integrity and therefore does not automatically leave a browser/web/sidecar running.

Do:
- start the long-lived sidecar in one terminal;
- start web 8787 in another terminal;
- keep both open.

Avoid:
- interpreting normal one-shot exit as installation failure.

## 12. V86 REST TLS verification warning is unresolved

Real V86 REST smoke on 2026-09-01 emitted `InsecureRequestWarning: Unverified HTTPS request` for `openapi.dnse.com.vn`.

Do:
- investigate SDK/client certificate verification behavior;
- make TLS verification explicit/fail-closed before any order mutation;
- add regression evidence after fixing.

Avoid:
- suppressing the warning as the final fix;
- enabling order mutation while HTTPS server identity is not being verified correctly.

## 13. Public API fee finding must not be overstated

Current public DNSE review found no separate public LightSpeed/OpenAPI fee and no API-order surcharge beyond normal trading fees.

Do:
- use wording `NO_SEPARATE_PUBLIC_API_FEE_FOUND` with date;
- treat account-specific contracts/charges as stronger evidence;
- recheck fee policy before material production rollout.

Avoid:
- saying `free forever`.

## 14. VPI recovery argues against one-shot automatic cuts

VPI moved from a weak/dragging state to recovery/rank strength without an automatic sell. V83 PRE-2026 capital-discipline variants also did not improve profit over C3.

Do:
- keep current no-add/cut labels advisory;
- use fresh forward evidence before changing policy.

Avoid:
- converting a temporary drag alert directly into an autonomous sell rule.

## 15. 2026 contamination / repeated sample inspection

V83 direction was influenced by 2026 observations; V76 already triggered a stop rule for repeated historical model fishing.

Do:
- use PRE-2026 selection where declared;
- treat 2026 as shadow where contaminated;
- prioritize frozen forward collection and data truth improvements.

Avoid:
- selecting a new threshold/model because it happens to fix known 2026 examples.

## 16. Persistent state integrity

Do:
- hash/check V77/V80 before/after any runner that should be read-only to them;
- preserve append-only semantics.

Avoid:
- reset/delete state to repair a failed run;
- rewrite historical observations after future information arrives.

## 17. Stale capital plan can conflict with current market state

V84 correctly detected a saved plan using older signal/EOD state.

Do:
- regenerate a stale plan before operational use;
- compare planned adds with current advisory health.

Avoid:
- interpreting an old plan as today's recommendation.

## 18. Auto-order readiness remains blocked

Even with V86 public realtime smoke successful, order mutation is not ready.

Required before any future live authority includes at least:
- verified TLS;
- stable public market stream across multiple sessions;
- private order/position stream health;
- Trading Token lifecycle;
- preflight security/session/PPSE/cash/lot checks;
- idempotent client intent/order identity;
- uncertain-submit reconciliation instead of blind retry;
- REST order/account/position reconciliation;
- circuit breaker and unresolved-order gate.

Until separately approved and proven: `AUTO_ORDER = BLOCKED`.

## 19. Holdings capture freshness and EOD valuation freshness are different clocks

The 2026-09-04 screenshot showed DNSE cash/quantities captured at `13:45:37+07:00` while official local EOD valuation remained `2026-08-21`.

Do:
- display and reason about DNSE holdings capture time, EOD valuation day and public tick age separately;
- keep V55 final-EOD valuation as the official valuation contract until a separately validated intraday layer exists.

Avoid:
- calling the holdings snapshot stale merely because its valuation day is old;
- conversely, calling the whole operating state fresh because the holdings request or public ticks are fresh.

## 20. V84 had a false-ready state when both market DB and broker valuation were equally stale

V84 only compared `broker.market_day < latest local market day`. On 2026-09-04 both values were `2026-08-21`, so the UI displayed `DỮ LIỆU VẬN HÀNH SẴN SÀNG` despite a roughly two-week-old EOD basis.

Do:
- include an absolute-age freshness guard in addition to relative broker-vs-market comparison;
- label calendar-age guards as conservative approximations until verified exchange working-date logic is wired into the UI.

Avoid:
- inferring freshness from equality of two stale timestamps.

## 21. DNSE positions REST is intermittently unreliable during market hours

User operational observation: the real portfolio read can fail or become unavailable in some time windows, especially around/open market hours, while the same read may work later in the evening.

Current active V59 fast reconcile reads balances then the legacy `/accounts/{account}/positions` endpoint before writing a snapshot. A thrown positions/balance exception currently stops before snapshot persistence, which is good. The remaining ambiguous case is a successful-but-empty positions response after a previously non-empty checkpoint.

Do:
- record broker sync success/failure/timing separately from the last good snapshot;
- fail closed on a sudden non-empty -> empty transition during market hours;
- retain the prior completed snapshot for operational display rather than silently replacing it with an ambiguous empty response;
- collect time-of-day failure evidence before replacing the REST source.

Avoid:
- turning an empty transient response into an authoritative zero-holdings state during market hours;
- overwriting last-known-good broker state merely because the HTTP request itself returned successfully.

## 22. Public realtime market health is not broker-position truth

The 2026-09-04 active-session screenshot showed V86 public market realtime `HEALTHY` with about `0.6s` tick age and zero reconnects while broker/EOD freshness remained a separate concern.

Do:
- use public ticks only as market-price evidence;
- require an independently reliable broker account/position source for quantities/cash;
- investigate the modern isolated DNSE private position/account stream read-only before considering it authoritative.

Avoid:
- using a healthy public market WebSocket to infer that DNSE holdings are current;
- enabling private/order mutation merely to solve a read-only portfolio freshness problem.
