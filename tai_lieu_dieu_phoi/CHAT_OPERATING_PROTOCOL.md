# CHAT OPERATING PROTOCOL

Updated: 2026-09-01

This protocol exists so a new conversation can resume the project without relying on chat memory and without repeating already-solved mistakes.

## A. Mandatory start-of-turn read

For every prompt in this project, before giving a substantive answer:

1. Read `AGENTS.md`.
2. Read `tai_lieu_dieu_phoi/CURRENT_STATE.md`.
3. Read `tai_lieu_dieu_phoi/KNOWN_ISSUES_AND_GUARDRAILS.md`.
4. Read the latest entries in `tai_lieu_dieu_phoi/CHAT_TURN_LOG.md`.
5. Inspect the active branch/PR metadata and current-head CI on GitHub.
6. If the prompt touches a specific version/work package, read that version's contract and most recent workstation result/evidence.

Do not answer from chat memory alone when GitHub can resolve the state.

## B. Mandatory end-of-turn GitHub checkpoint

Before the final response to every project prompt, perform a GitHub write on the active project branch.

Minimum requirement: append one concise entry to `CHAT_TURN_LOG.md` containing:

- timestamp (Vietnam time when known);
- user intent;
- GitHub documents/PR/CI read;
- actions/research performed;
- state change, or explicit `NO_STATE_CHANGE`;
- evidence distinction (CI / workstation / historical / forward / live);
- unresolved blocker;
- exact next action.

If the turn changes durable project state, also update the appropriate file:

- `CURRENT_STATE.md` for operational/project status;
- `KNOWN_ISSUES_AND_GUARDRAILS.md` for a new failure mode, lesson, or do/don't rule;
- `ROADMAP.md` for priorities or next phases;
- a `vXX_*` contract/result file for work-package evidence;
- `RESTORE_PROMPTS.md` if the recovery procedure changes.

A project turn should not finish with important state existing only in chat.

If GitHub mutation is impossible because a connector/write fails, state this clearly in the final answer and preserve a copyable checkpoint payload for the next turn. Never falsely claim it was saved.

## C. Read-after-write verification

After each GitHub checkpoint:

1. Re-read the branch/PR head to confirm the intended commit landed.
2. Re-read changed files when practical to catch malformed or stale content.
3. Check CI triggered on the new/current head.
4. Never say `CI green` for a documentation/current-state head until the checks for that exact head are green; distinguish a previously green implementation head from a newer docs-only head.

## D. Source-of-truth precedence

Use this order when facts conflict:

1. Real immutable workstation artifact/log tied to exact commit and audited integrity.
2. GitHub current-head code, contracts and CI.
3. `CURRENT_STATE.md` after it has been updated from the above.
4. Versioned historical result/contract documents.
5. PR descriptions/comments.
6. Chat memory.

A stale file named `current`, `status`, `handoff`, etc. must never outrank newer verified evidence just because of its filename.

## E. Branch / merge discipline

- No direct `main` edits.
- Prefer one focused branch/PR for a coherent work package.
- No merge unless the user explicitly requests it.
- Check stacked PR bases before merging; merging a later stacked PR into its parent branch is not the same as merging into `main`.
- Never force-reset or delete workstation state simply to make a runner pass.
- Preserve approved dirty workstation web files when a runner contract permits them.

## F. Research discipline

- No future data leakage; signals after close T, tradable order no earlier than allowed T+1/session contract.
- Time-based split only, no random split for causal research.
- No historical-universe survivorship shortcut.
- C3 remains frozen champion unless a separately valid promotion decision is made.
- V76 stop rule prohibits repeated architecture/hyperparameter/threshold fishing on the same inspected sample.
- 2026 V83 observations are contaminated for V83 policy selection; use forward monitoring rather than retroactive tuning.
- Data gates remain fail-closed until explicitly closed by evidence.
- Report actual profit when research outputs provide it.
- Separate historical diagnostics from genuinely fresh forward evidence.

## G. Broker/realtime discipline

- `HTTP 200` from localhost does not imply upstream realtime health.
- WebSocket transport, authentication, subscriptions, heartbeat and tick freshness are separate health dimensions.
- V86 public market sidecar is read-only. No OTP, Trading Token, private order/position stream or order mutation in current authority.
- Never install `dnse-sdk-openapi` into the canonical `.venv` while legacy `dnse` is retained; both use the top-level `dnse` namespace.
- Treat uncertain order-submit state as reconciliation-only, never blind resend, when order mutation is eventually developed.
- TLS verification warning is an unresolved blocker before order mutation.

## H. Workstation command discipline

Correct repo path in Git Bash:

`/d/VNQuant/vn-quant-system`

Do not use unrelated project paths such as `~/v31_mt5_40usd`.

For Windows Python invoked from Git Bash, use `cygpath -w` and Windows `PYTHONPATH` separator `;` for multiple paths.

Do not assume an installer keeps services alive. V86 currently has a one-shot installer and a separate long-lived sidecar runner.

## I. Documentation hygiene

Top-level coordination directory should contain only clear current indexes/protocols and explicit versioned evidence. Remove or replace documents that call themselves current but are materially stale. Keep versioned contracts/results where they remain useful as audit history.

When a historical handoff becomes redundant, prefer deleting it only after its unique durable facts are captured in a contract/result/index. Do not delete evidence merely to make the tree look clean.
