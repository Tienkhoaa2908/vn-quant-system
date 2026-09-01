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
