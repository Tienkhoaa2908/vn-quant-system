# V76 consolidated research plan

Question: can a causal learned cross-sectional ranking model improve the frozen C3 portfolio before 2026 and capture emerging leaders better, without increasing future-loser contamination?

V76 is one consolidated work package, not four separate workstation experiments. It trains/evaluates Ridge rank, Ridge context, HGB context and bottom-tail Logistic under one frozen feature/target/walk-forward contract, then deep-backtests every candidate under the same V70 mechanics.

Primary research selection ends 2025-12-31. 2026 is stress/shadow. The answer is based first on execution P&L and matched inference, then on rank IC and winner/loser diagnostics.

No manual factor blend, exposure threshold, macro threshold, or 2026-specific rule is tuned in V76. No LightGBM dependency is introduced.

If V76 does not produce a robust progression model, the historical search stop rule activates: move the project toward fresh paper OOS and data-lineage completion instead of opening V77 as another architecture-search round.