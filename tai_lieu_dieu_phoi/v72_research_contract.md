# V72 research contract — standalone weekly overlay deep backtest

## Why V72 exists

V70 showed that frozen C3 has strong long-run modeled-cost alpha but a severe relative failure in 2026, especially the April interval. V71 tested recent-IC adaptive C3 weights. No V71 adaptive candidate passed the pre-2026 selection gate, so expanding C3 remains champion. V71 EWMA-HL24 improved 2026 shadow materially but that period is already observed and cannot be used to promote the candidate.

V69 had previously surfaced three endogenous weekly mechanisms worth translating from signal research into actual portfolio actions:

- `R07_DD20_08` — canonical Top10 name down at least 8% from 20-session high;
- `R08_DD60_12` — canonical Top10 name down at least 12% from 60-session high;
- `L15_PERSIST_REL` — emerging leader moves from prior Preview Top10 into current Top5 with relative/volume confirmation.

V72 asks one clean question: **does acting on each frozen mechanism, by itself, improve a frozen-C3 portfolio after realistic execution mechanics?**

These mechanisms were surfaced historically before V72. V72 is therefore a **post-selected mechanism audit**, not a pristine independent holdout. Historical success cannot promote them directly.

## Frozen baseline

Champion remains `C3_STABLE_3_PAST_IC_SHRUNK`.

V72 does not change:

- the three C3 components;
- close(T) -> close(T+20) benchmark-relative weight-training label;
- monthly C3 ranking;
- MA250 eligibility/regime semantics;
- V70 next-open / actual-share / lot / cost primitives.

`NO_OVERLAY` must reproduce V70 equal and inverse-vol always-invested total return, CAGR and daily max drawdown within `1e-10`. Otherwise V72 fails before research interpretation.

## Predeclared standalone actions

No policies are combined in V72.

### `R07_TRIM50_CASH`

When a currently held canonical C3 Top10 name satisfies frozen `R07_DD20_08` at a completed weekly close:

- execute at next market open;
- sell 50% of current shares, rounded down to lot 100;
- leave proceeds in cash until the next monthly C3 rebalance;
- do not retrim the same symbol again in the same monthly cycle.

### `R08_TRIM50_CASH`

Same mechanics, using frozen `R08_DD60_12`.

### `L15_SWAP50_WORST`

At a completed weekly close:

- identify currently unheld symbols satisfying frozen `L15_PERSIST_REL`;
- choose the best by Preview rank then score;
- choose the currently held name with the worst Preview rank/score;
- next open, sell 50% of the worst position, lot-rounded;
- use that target notional to buy the leader, never exceeding the existing 15% single-name cap;
- at most one leader swap per weekly signal.

This is not a permanent new monthly ranking. The next monthly C3 rebalance restores the frozen monthly target universe/weights.

## Timing and collision rules

Weekly signal: after completed weekly close.

Earliest trade: next benchmark-market-session open.

If a weekly action and monthly C3 rebalance would execute on the same open, **monthly C3 rebalance has precedence** and the stale weekly action is suppressed.

Missing open is never replaced by a future price. V70 missing-price behavior applies.

## Portfolio mechanics

Each policy is backtested with:

- equal allocation and inverse-vol60 allocation;
- lot 100;
- max 15% per name;
- GROSS / BASE_DNSE / STRESS / SEVERE costs;
- immediate-cash research case plus BASE T+2/no-advance sensitivity;
- 100m / 1bn / 10bn VND capital sensitivity;
- daily NAV/drawdown;
- trade ledger, overlay action log, missing-price log, ADV participation and turnover.

No PIT sector cap is fabricated while PIT sector master is unavailable.

## Statistical selection boundary

Primary policy inference ends at `2025-12-31`.

2026 is excluded from:

- sign-flip tests;
- bootstrap selection CI;
- BH-FDR;
- annual consistency gate;
- policy threshold design.

2026 is reported only as observed stress/shadow, including April delta versus no-overlay frozen C3.

Paired return inference:

- same variant;
- same allocator;
- same monthly period;
- candidate policy minus `NO_OVERLAY`;
- BASE_DNSE, immediate settlement;
- contiguous two-calendar-month sign-flip blocks;
- block-bootstrap CI;
- BH-FDR within variant + allocator.

Return watch gate requires all:

1. mean monthly delta > 0;
2. BH q < 0.10;
3. bootstrap 95% CI lower bound > 0;
4. at least 60% of pre-2026 annual return deltas > 0.

Risk-trim policies also have a diagnostic risk-efficiency gate:

- daily max-drawdown improvement at least 2 percentage points pre-2026;
- CAGR delta no worse than -1 percentage point;
- pre-2026 p10 monthly return improves.

This risk gate is diagnostic only because R07/R08 are historically post-selected. It does not authorize promotion.

## Interpretation hierarchy

Report in this order:

1. P&L / benchmark / alpha / CAGR / drawdown;
2. pre-2026 policy-vs-base evidence;
3. turnover/cost/capacity/T+2 feasibility;
4. 2026 shadow and April attribution;
5. action frequency/concentration;
6. whether any mechanism merits a future paper holdout or only further research.

Do not select a policy because it performs well in 2026 if it fails the pre-2026 evidence gate.

## Deferred

V72 deliberately does **not**:

- combine R07 + R08 + L15;
- combine weekly overlay with V71 EWMA/rolling adaptive weights;
- add macro variables;
- alter C3 components;
- authorize paper/live capital.

Only after standalone evidence is known may a later package predeclare a small integration matrix. Macro remains a separate release-date point-in-time ablation if endogenous C3/allocation/weekly mechanisms remain insufficient.
