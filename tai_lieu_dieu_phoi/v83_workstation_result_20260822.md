# V83 workstation result — 2026-08-22

## Provenance and integrity

- Branch: `agent/v83-capital-discipline-main-web`
- Artifact HEAD: `f518b9b084f1f403fb8dd8653a730476d980c580`
- Uploaded ZIP SHA256: `2085e68a0b83ba77f95fa7944593a9ca8e2364144bb957454bb9c7b975520f25`
- Market bars: first `2015-06-29`, last `2026-08-21`, rows `301259`, logical SHA256 `7f48a06841fd33de3bf1688d371c13edd5a7a15d896f18ebc32d4fdd0eaf8cad`; unchanged through the V83 research phase.
- V77 digest before/after: `f7f961a202d386815efad18e11d01713ad5eddc2d68297c06bca468b8d85fdc8`.
- V80 digest before/after: `8f3fcc0ef22d8b40ac2470691159374a2e7c4b32d21dbd75ddff3fd9218b8c89`.
- V83 tests: 7 PASS.
- Existing workstation web install: SUCCESS; port remains 8787; endpoint `/api/dashboard-v83`; no live-order endpoint added; credentials/state untouched.

The workstation did not find reusable V81 causal outputs and therefore rebuilt V68 and V70 successfully before V83.

## Selection isolation

V83 policy direction was formed after observing 2026 forward behavior. Therefore canonical policy selection is hard-truncated at `2025-12-31`. The 2026/all-sample replay is shadow diagnostic only and must not be used to promote a rule.

## Canonical PRE-2026 selection result

Reference: `GAP18_CLEAN`, `BASE_DNSE`, EQUAL C3, initial capital 1,000,000,000 VND.

| Policy | Ending NAV | Net profit | Incremental NAV vs C3 | Total return | CAGR | MDD | Discipline events | Trades |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `C3_BASE` | 5,578,800,169 | 4,578,800,169 | 0 | +457.8800% | 22.4257% | -37.4595% | 0 | 1418 |
| `NO_ADD_UNDERWATER` | 5,571,706,908 | 4,571,706,908 | **-7,093,260** | +457.1707% | 22.4073% | -37.4301% | 59 | 1356 |
| `PERSIST2_SEVERE_TRIM50` | 5,559,276,923 | 4,559,276,923 | **-19,523,245** | +455.9277% | 22.3752% | -37.3535% | 16 | 1434 |
| `NO_ADD_PLUS_PERSIST2_TRIM50` | 5,548,361,703 | 4,548,361,703 | **-30,438,466** | +454.8362% | 22.3469% | -37.3689% | 78 | 1371 |

Interpretation:

- None of the three capital-discipline policies improves canonical pre-2026 P&L versus frozen C3.
- `NO_ADD_UNDERWATER` reduces turnover/trades and slightly improves MDD, but the economic effect is negative: about -7.09m VND incremental NAV and -0.7093pp total-return uplift over the selection sample.
- `PERSIST2_SEVERE_TRIM50` improves MDD only about +0.1060pp but loses about -19.52m VND versus C3; this is insufficient evidence to promote a cut rule.
- The combined policy is worst on P&L, about -30.44m VND versus C3.
- Therefore V83 does **not** authorize automatic no-add or automatic trim/exit. Current web labels must remain advisory only.

## 2026 shadow diagnostic — not selection evidence

On the all-sample replay through `2026-08-21`, `PERSIST2_SEVERE_TRIM50` ends about **+5.40m VND** above C3 and improves MDD about +0.1060pp. This reverses its pre-2026 deficit of about -19.52m VND, meaning the 2026 segment contributed a large relative swing in favor of the trim rule.

This observation is interesting for fresh forward monitoring but is contaminated for V83 selection and must not be used to promote the rule.

2026 reference discipline events include only two persistent severe trims in GAP18/BASE_DNSE (`FRT`, `PC1`). `VPI` appears in the 2026 no-add shadow event set but was not sold by that rule.

## Entry timing audit

Canonical pre-2026 `GAP18_CLEAN` entry sample: 463 new-name entries.

- Mean T+1 open gap from signal close: **+0.3101%**.
- Mean T+2 price improvement versus T+1: **-0.2929%** (negative means T+2 was more expensive on average).
- Median T+2 price improvement versus T+1: **-0.2490%**.
- T+2 was cheaper than T+1 only **40.17%** of entries.
- 50/50 staged T+1/T+2 was cheaper only **40.60%** of entries.
- Mean return to monthly boundary: T+1 **+1.9630%**, T+2 **+1.6031%**, staged **+1.7830%**.
- Delaying to T+2 reduced mean boundary return by about **-0.3600pp**; staged reduced it by about **-0.1800pp** versus canonical T+1.

Thus the clean historical selection sample does **not** support changing canonical entry from T+1 to T+2 or staged execution.

The 2026 shadow reverses direction: T+2 was cheaper in about 65.5% of 29 observations, with mean T+2 price improvement about +0.6122% and mean boundary-return improvement about +0.3473pp versus T+1. This is fresh-regime context only, not selection evidence. The correct next step is forward entry-quality monitoring, not retroactive rule promotion.

## Product decision

1. Frozen C3 remains champion.
2. Do not promote `NO_ADD_UNDERWATER` as an automatic capital rule from V83.
3. Do not promote `PERSIST2_SEVERE_TRIM50` or the combined rule.
4. Keep V83 Capital Discipline as the main workstation operating view, but label `KHÔNG MUA THÊM` and `CUT WATCH` as advisory diagnostics rather than executable instructions.
5. Keep T+1 open as canonical historical execution. Track 2026/future entry gaps forward because the current regime may differ from the pre-2026 sample.
6. New-leader/L15 research remains non-primary/archived; no broker/live authority is added.
