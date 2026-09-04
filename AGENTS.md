# VN Quant System — mandatory agent continuity protocol

This repository is the durable source of truth for project coordination. Chat memory is secondary.

## Before every project-related answer

1. Read `tai_lieu_dieu_phoi/CURRENT_STATE.md`.
2. Read `tai_lieu_dieu_phoi/CHAT_OPERATING_PROTOCOL.md`.
3. Read `tai_lieu_dieu_phoi/KNOWN_ISSUES_AND_GUARDRAILS.md`.
4. Inspect the active GitHub branch/PR and current-head CI. If the task touches a versioned work package, also read its contract/result files.
5. Resolve contradictions in favor of newer verified GitHub evidence. Never revive a superseded top-level status document from history.

## Mandatory GitHub checkpoint on every turn

For every user prompt in this project, perform a GitHub continuity action before the final answer. At minimum append a concise entry to `tai_lieu_dieu_phoi/CHAT_TURN_LOG.md` describing what was read, what changed (or `NO_STATE_CHANGE`), evidence/CI state, and next action. If the turn changes project state, decisions, bugs, commands, architecture, evidence, or priorities, update the relevant current-state/guardrail/roadmap document in the same checkpoint.

If GitHub write access is unavailable or fails, state that explicitly in the answer; never pretend a checkpoint was written.

## Repository safety

- No direct edits to `main`; use an appropriate branch/PR.
- Do not merge any PR unless the user explicitly orders a merge.
- Do not claim CI is green until checks on the final/current head are actually green.
- Preserve immutable workstation states such as V77/V80 and do not reset/delete them.
- Never commit credentials, API keys/secrets, OTPs, Trading Tokens, private account data, or raw sensitive broker responses.
- Distinguish CI success, workstation smoke evidence, historical research evidence, and fresh forward evidence.
- Research outputs must report profit when available and must not overstate promotion/live authority.

## Workstation anchor

Canonical Windows repository path: `/d/VNQuant/vn-quant-system` in Git Bash (`D:\VNQuant\vn-quant-system` native Windows). Do not use paths from unrelated projects.
