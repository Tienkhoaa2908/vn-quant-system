# V81 contract — frozen tactical historical audit

## Purpose

V81 uses historical data to understand the behavior of the tactical policies that were already frozen after V79 and are being collected forward in V80. It is **not** a new model/threshold-selection round.

Operational champion remains `C3_STABLE_3_PAST_IC_SHRUNK`.

Frozen policy surface is exactly:

- `NO_OVERLAY`;
- `L15_SWAP25_WORST`;
- `L15_SWAP50_WORST`;
- `L15_CASH_ADD25_SLOT`.

No other tactical policy is eligible for V81 selection or tuning.

## Exact L15 remains frozen

V81 delegates the trigger to V72/V79; it does not reimplement a looser rule.

Exact L15 remains:

- canonical rank > 10;
- current preview rank <= 5;
- prior-week preview rank <= 10;
- relative 5-session return >= +2%;
- volume ratio 5/20 >= 1.

No threshold counterfactuals such as rank 6, volume 0.8, relative 1.5%, etc. are generated.

## Historical replay role

Historical results are post-selection diagnostics because the broad historical sample has already been inspected in earlier research. V81 may describe pre-2026 and 2026 separately, but it cannot claim a fresh unbiased selection test and cannot authorize promotion.

V81 answers behavior questions under the frozen policy:

1. How frequently exact-L15 appears by year/month/week.
2. Whether activity is concentrated in a few leaders or incumbents.
3. For actual simulated actions, how the leader performs versus the replaced incumbent after H5/H10/H20 and at the next monthly rebalance.
4. Replacement regret rate: `leader_return - incumbent_return < 0`.
5. Leader performance versus VNINDEX over the same execution-aligned horizon.
6. Causal market-regime diagnostics from trailing 60-session VNINDEX return.
7. Portfolio monthly delta versus `NO_OVERLAY`, including whether gains/losses are dominated by a few months.
8. Baseline behavior in months with no exact-L15 event.
9. Robustness under GROSS/BASE_DNSE/STRESS/SEVERE costs.
10. T+2 no-advance sensitivity.
11. Capital/capacity sensitivity at 100M/1B/10B VND.

## Causal execution

Historical event signals are V68 causal weekly states. Execution remains weekly close -> next market open, with monthly C3 rebalance precedence. V79/V72 execution primitives are reused.

H5/H10/H20 pair diagnostics start at the actual simulated trade-day open. A horizon that crosses the next monthly rebalance execution is censored; the monthly-boundary diagnostic uses that rebalance open.

## Regime diagnostic

Regime buckets are descriptive only and cannot alter trading behavior:

- `BULL_60D`: trailing 60-market-session VNINDEX return >= +5%;
- `BEAR_60D`: <= -5%;
- `SIDEWAYS_60D`: otherwise.

Only information available by the signal evaluation day is used for this bucket.

## Persistence safety

V81 is historical/read-only research. The workstation runner must verify before/after equality for:

- logical market `bars` fingerprint;
- `du_lieu/v77-paper-oos-state/` digest;
- `du_lieu/v80-tactical-paper-state/` digest.

The V80 forward registry must never be reset, rewritten or backfilled by V81.

Approved V78 local web modifications are preserved transactionally by the workstation wrapper and are outside the V81 research surface.

## Outputs

The one-shot V81 package emits:

- `v81_report.json`;
- `v81_signal_events.csv`;
- `v81_signal_frequency.csv`;
- `v81_action_horizons.csv`;
- `v81_horizon_summary.csv`;
- `v81_regime_summary.csv`;
- `v81_concentration.csv`;
- `v81_portfolio_delta_diagnostics.csv`;
- `v81_no_trigger_months.csv`;
- `v81_cost_robustness.csv`;
- `v81_t2_robustness.csv`;
- `v81_capital_robustness.csv`;
- `v81_backtest_summary.csv`;
- base-cost trade ledger and daily equity as gzipped CSV.

## Interpretation limits

V81 can strengthen or weaken our understanding of the frozen mechanism, but it does not itself change the frozen V80 rule. A future change to thresholds/policy would require a separate research decision with new evidence, not an automatic response to a V81 chart or near-miss.

No broker endpoint, live order, champion replacement, promotion authorization or data-gate closure is created by V81. PIT HOSE membership, price basis, corporate actions and PIT sector lineage remain fail-closed.
