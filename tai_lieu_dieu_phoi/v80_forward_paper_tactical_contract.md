# V80 contract — frozen tactical opportunity forward paper

## Purpose

V80 is the post-V79 forward-paper phase. It does **not** search historical thresholds, factors, models or architectures. The operational champion remains `C3_STABLE_3_PAST_IC_SHRUNK`.

V80 freezes exactly three tactical opportunity challengers selected by V79:

- `L15_SWAP25_WORST`;
- `L15_SWAP50_WORST`;
- `L15_CASH_ADD25_SLOT`.

Autonomous incumbent sell rules remain rejected. Incumbent health/drag may only rank the replacement source; it cannot create a paper trade without independently qualified exact L15.

## Observation contract

Each workstation run refreshes the current V78 tactical observation without touching the approved web layout. The target is built from the V78 report plus tactical rows and revalidates exact L15 through the frozen V72 trigger semantics.

An observation is identified by `source_monthly_signal_day + capture_market_day`. On first capture V80 stores:

- immutable target hash;
- exact tactical rows used to form the target;
- Vietnam wall-clock capture time;
- causal execution floor;
- the three frozen policy records.

A rerun of the same observation with a different target is `V80_TARGET_DRIFT` and fails closed. Frozen tactical-row drift also fails closed.

Persistent state lives at `du_lieu/v80-tactical-paper-state/` and must never be deleted/reset to obtain a cleaner result.

## Causal execution floor

A target observed after the workstation wall-clock capture cannot use an earlier open, even if that bar is later added to the local store.

Execution contract:

`FIRST_MARKET_SESSION_ON_OR_AFTER_CAPTURE_VN_DATE_PLUS_1`

Paper execution is at that legal session open. If the next monthly C3 rebalance execution has precedence, an unfilled tactical action is cancelled rather than backfilled.

## Counterfactual portfolio basis

Every event is evaluated independently on a normalized current-cycle C3 portfolio:

- initial NAV: 1,000,000,000 VND;
- monthly C3 Top10 Equal;
- current monthly signal -> next-session-open baseline construction;
- V70 lot size / cap / execution primitives;
- `BASE_DNSE` fees, sell tax, transfer fee and slippage;
- immediate settlement for this event counterfactual;
- no leverage.

This is an **event counterfactual**, not a claim about the user's actual brokerage holdings.

`SWAP25/50` removes 25%/50% of the simulated weakest incumbent **position shares after lot rounding**, not 25%/50% of account NAV, and uses the V79 rotation mechanics to buy the exact-L15 leader.

`CASH_ADD25` is eligible only when the V78 monthly signal is risk-on. It calls the V79 cash-add mechanics and can spend only the simulated idle cash actually left after the C3 baseline construction; its maximum slot is 25% of the normal 10% base slot (2.5% NAV before lot/cap/cost constraints).

## Outcome contract

After a paper fill V80 records baseline and challenger counterfactual NAV at:

- 5 market sessions;
- 10 market sessions;
- 20 market sessions;
- next monthly rebalance execution open.

A fixed-horizon observation that would occur after the monthly rebalance boundary is censored by that boundary. Existing fills/outcomes are immutable; later market-data revisions that alter them fail closed instead of silently rewriting evidence.

## Safety / lineage

- C3 champion unchanged;
- exact L15 unchanged;
- no historical model or threshold search;
- no autonomous R07/R08/drag sell;
- no broker endpoint;
- no live order;
- no promotion authorization;
- V77 persistent state must be byte-identical before/after V80;
- V78 preview state is reused and may append only through V78's own immutable persistence contract;
- market data is read-only and protected by the WAL-safe logical `bars` fingerprint from V79; physical SQLite SHA is audit metadata only;
- PIT HOSE membership, price basis, corporate actions and PIT sector master remain fail-closed.
