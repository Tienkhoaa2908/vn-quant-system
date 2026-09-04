# CHAT TURN LOG

Append-only continuity log for project conversations. This is not a substitute for `CURRENT_STATE.md`; it records what each turn read/changed so a successor can reconstruct recent context.

## 2026-09-01 — continuity cleanup / V86 checkpoint

- User intent: persist the latest project state, lessons, known bugs, do/don't rules and recovery procedure to GitHub; remove clearly obsolete coordination documents; require GitHub read-back + update on every future project turn; provide two professional recovery/checkpoint prompts.
- GitHub read: V86 PR #62 metadata/current head, current-head CI, open PR stack, `tai_lieu_dieu_phoi/README.md`, stale top-level status/handoff docs, versioned V67-V86 coordination index, V86 plan, V86 sidecar/web runners and real launcher path.
- Workstation evidence read from user-provided V86 transcript: one-shot completed `V86_EXIT_CODE=0`; official OpenAPI SDK 1.4.6 connected/authenticated/subscribed; ping/pong healthy; REST smoke success; market closed -> `IDLE_MARKET_CLOSED`, event_count 0; reconnect_count 0; canonical dnse 0.5.0 unchanged; V77/V80 digests unchanged; installer disabled legacy V59 WS ownership; live order false; ZIP generated with SHA-256 `95ad8d4d9b84117659aeae4388340039322402c024094712e0b1433a703efb9e`.
- New unresolved issue captured: REST smoke emitted `InsecureRequestWarning` / unverified HTTPS to `openapi.dnse.com.vn`; must be fixed before order mutation.
- Important prior mistakes captured: wrong unrelated repo path `~/v31_mt5_40usd`; Windows PYTHONPATH separator; hidden `webapp_v59` legacy WS ownership; HTTP 200 != feed health; one-shot installer != long-lived service; SQLite WAL physical SHA false positive; V77 retroactive execution-floor risk; V83/2026 selection contamination.
- Durable changes in this checkpoint: establish `AGENTS.md`, `CURRENT_STATE.md`, `CHAT_OPERATING_PROTOCOL.md`, `KNOWN_ISSUES_AND_GUARDRAILS.md`, `ROADMAP.md`, `RESTORE_PROMPTS.md`; refresh coordination README; add V86 workstation result; prune clearly obsolete top-level current/handoff/prompt/marker files.
- Evidence class: CI + user-provided workstation transcript. V86 ZIP itself has not yet been uploaded/audited; multi-session live market tick stability has not yet been established; live order authority remains false.
- Next action: finish atomic GitHub cleanup commit, re-read new PR/head, wait/check current-head CI, then continue V86 TLS verification + long-lived multi-session public realtime observation.

## 2026-09-04 13:49 +07 — active-session screenshot / broker freshness hardening

- User intent: provide the requested web screenshots and report an additional operational problem: real DNSE portfolio reads are intermittently unavailable, especially during market/open-session windows, while they may work later in the evening.
- Mandatory read-back: `AGENTS.md`, `CURRENT_STATE.md`, `CHAT_OPERATING_PROTOCOL.md`, `KNOWN_ISSUES_AND_GUARDRAILS.md`, `ROADMAP.md`, PR #62, exact-head CI, V86 sidecar/web code, V59/V55/V49 broker paths and public `dnse-tech/dnse-py` docs/source.
- Exact pre-patch continuity head `0b7fd1b1272f4985aa7d32d047982a6bde26fea6`: dedicated V86 run 17 and full `kiem_tra_tu_dong` run 930 both completed/success.
- Screenshot evidence: V86 public feed was `HEALTHY` during an actual market session; transport connected, auth authenticated, subscriptions active for 20 symbols/msgpack, tick age about 0.6s, VIC tick visible, reconnect count 0, pong about 15s, SDK 1.4.6/API 2026-05-07.
- Broker screenshot distinction: DNSE cash/quantities were captured fresh at `2026-09-04T13:45:37+07:00`; `2026-08-21` was the V55 local final-EOD valuation day, not the holdings capture timestamp. Seven positions were displayed.
- UI defect found: V84 could show `DỮ LIỆU VẬN HÀNH SẴN SÀNG` when both latest local Market EOD and broker valuation day were equally stale at 2026-08-21. Relative equality of two stale dates is not freshness.
- Broker reliability finding: active V59 selected-account REST reconcile throws before snapshot persistence when balances/positions throws, but a successful-yet-empty positions response after a prior non-empty checkpoint remains ambiguous. User-observed time-of-day unreliability is therefore treated as an operational blocker.
- Upstream architecture evidence: current public DNSE Python SDK documents account/balance REST plus private read-only position/account/order WebSocket subscriptions. This is not yet workstation proof for the exact isolated 1.4.6 runtime and does not authorize order mutation.
- Durable code patch prepared: add V86 broker sync health file, holdings/EOD freshness API state, market-hours fail-closed non-empty -> empty guard, V86 UI broker freshness warning, dedicated tests/workflow coverage. V55 official final-EOD valuation semantics remain unchanged; no broker-price fallback and no order/private-stream mutation added.
- Durable documentation: update current state, guardrails, roadmap; add `v86_visual_and_broker_freshness_20260904.md`.
- Evidence class: real workstation visual evidence + user operational observation + current-head repository inspection + upstream public SDK architecture review. Active-session public realtime is one-session evidence, not multi-session reliability proof.
- Next action: commit the patch/checkpoint atomically, run/recheck exact-head CI, then deploy to workstation only after CI; collect broker-sync time-of-day failures with explicit degraded/last-good behavior and continue TLS verification.
