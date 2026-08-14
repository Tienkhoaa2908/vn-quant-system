# V74 workstation result — 2026-08-14

Observed workstation artifact from `agent/v74-macro-pit-ablation` at HEAD `ffb78150f33ef5976a0514750417005e7f171a94`.

Store SHA256: `2959f8cce0c11e8e4186fcb49ae75bf7babf86b84afe64ca3b843a7470d58b1a`.
Canonical workstation Python: `vn_quant_local_system/.venv/Scripts/python.exe`, Python 3.12.13.

## Structural status

- V74 regression tests: 6/6 PASS;
- V68 frozen-C3/data phase: SUCCESS;
- V70 deep baseline phase: SUCCESS;
- V74 macro phase: **BLOCKED before backtest**;
- champion remains `C3_STABLE_3_PAST_IC_SHRUNK`;
- market store was not mutated;
- no promotion/live authorization.

## Macro collection result

Official NSO collector obtained first-release coverage:

- CPI: 111 unique reference months;
- IIP: 59 unique reference months.

V74 contract required at least 80 months for both series, therefore the macro lane failed closed with:

`V74_MACRO_COVERAGE_INSUFFICIENT:{'CPI': 111, 'IIP': 59}`

No V74 macro P&L was produced and no macro conclusion is authorized.

## Interpretation

This is a data-coverage/collector limitation, not evidence that macro does or does not help C3. The dedicated official IIP archive is historically sparse/heterogeneous in older years; spending additional workstation cycles on collector-only probes is not justified.

## Research decision

1. do not rerun standalone V74 merely to test collector changes;
2. the next package must be consolidated and must continue stock-selection research even if macro coverage remains partial;
3. macro becomes an optional, publication-date-PIT late-era lane when sufficient observations are available; macro failure must not block factor-selection research;
4. next package should attack the observed C3 failure directly: winner capture, loser avoidance, fast-relative/fresh-breakout/anti-exhaustion features, causal walk-forward scoring, and mandatory V70 deep backtest;
5. 2026 remains shadow/stress only and may not select thresholds or candidates;
6. profit-first reporting remains mandatory.

Historical results remain research-only. PIT HOSE membership, price-basis/corporate-action and PIT-sector blockers still prevent canonical/live claims.
