# V83 capital discipline contract

## Product decision

V83 stops treating new-leader/L15 discovery as the primary product direction. V80/V81 remain immutable archived evidence; they are not deleted or rewritten.

Operational champion remains `C3_STABLE_3_PAST_IC_SHRUNK`.

Primary question: how to allocate less capital to C3 incumbents that are already deteriorating without selling transient losers such as the observed VPI recovery case.

## Fixed research surface

No threshold grid and no model search.

Policies:

1. `C3_BASE` — frozen C3 Equal baseline.
2. `NO_ADD_UNDERWATER` — at a monthly rebalance, if a symbol is already held and its prior-cycle return from next-open entry to the current monthly signal close is both negative absolute and negative relative to VNINDEX, any *incremental buy* is blocked. Existing shares are not sold by this rule.
3. `PERSIST2_SEVERE_TRIM50` — reuse existing V79 `SEVERE_DRAG` semantics and require the condition at two consecutive weekly checkpoints in the same monthly cycle before one 50% trim-to-cash research action. This is deliberately stricter than the rejected one-shot autonomous cut families.
4. `NO_ADD_PLUS_PERSIST2_TRIM50` — combine 2 and 3.

2026 is contaminated by design discussion and therefore **cannot be used for selection**. Canonical selection evidence is truncated at `2025-12-31`. 2026/all-sample results may be shown only as shadow/diagnostic context.

## Entry-quality audit

For brand-new monthly C3 names only, compare:

- T+1 open (current causal baseline),
- T+2 open,
- 50/50 notional staged T+1/T+2 effective entry.

This audit does not promote a delayed/staged execution rule automatically. It measures whether the current T+1 entry is systematically expensive before any execution contract changes.

## Web contract

Existing approved workstation remains `http://127.0.0.1:8787`.

Primary web surface becomes Capital Discipline:

- `KHÔNG MUA THÊM` — current C3 incumbents dragging or health-alerted;
- `CUT WATCH` — strict persistent severe deterioration only;
- `RECOVERED` — prior forward-snapshot drag that has recovered now;
- `ENTRY GAP` — signal close to T+1 open gap for current monthly C3 names;
- V83 historical P&L appears after workstation audit.

Leader/L15, V80 and V81 move into a collapsed Research Archive. They remain accessible but are no longer the main operating recommendation surface.

## Safety / authority

V83 is advisory/research only.

- no broker endpoint;
- no live order;
- no promotion authority;
- no V77/V80 reset or mutation;
- logical market bars must be unchanged by the research/install phase;
- no leader purchase rule is opened by V83.
