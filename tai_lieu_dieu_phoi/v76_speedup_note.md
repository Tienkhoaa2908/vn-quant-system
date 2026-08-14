# V76 speed-up note

V76 is the first learned-ranking package after the V75 stop decision on manual factor blends.

To reduce workstation time, `scripts/run_v76_learned_ranking_gitbash.sh` treats unchanged V68/V70 output as a verified cache. It reuses the newest local V75 V68/V70 output only if all of the following match:

1. the V75 bundle and corresponding output directory both exist;
2. the bundle-recorded market-store SHA256 equals the current market-store SHA256;
3. V68 report status is SUCCESS and champion is frozen C3;
4. V70 report status is SUCCESS, champion is frozen C3 and deep backtest completed.

If a check fails, V76 automatically rebuilds V68 and V70. No user intervention is required.

The V76 upload bundle copies compact V68/V70 report provenance into `reference/` and records `reference_source.txt`, so a later chat can distinguish verified-cache reuse from a fresh baseline rebuild.

This cache may never be used to reuse V76 model predictions, model fits or candidate P&L. Those are recomputed in every V76 workstation run.