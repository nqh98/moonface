# liqprem v1 — cross-sectional Amihud illiquidity premium

- generated: 2026-07-28T17:34:00.645960+00:00
- status: **closed_negative**
- symbols with data: 772 (viability members 434, funding fetched for 434)
- frozen window: 1690651625589 .. 1785259625589, fence 1766338025589
- punitive costs: 25 bps/side illiquid leg, 5 bps/side liquid leg
- viability floor: listed >= 365d AND trailing-30d median dollar volume >= $1,000,000

Cost-first pre-screen (research window, before the ladder):

| construction | gross mean/d | gross Z | net mean/d | net Z | cost-first |
|---|---|---|---|---|---|
| liqprem_1 | -0.00010666 | -0.280 | -0.00015442 | -0.406 | fail |

Ladder (only constructions that clear cost-first):

| construction | screen mean/d | s1 | holdout MAR | holdout DD | s2 | research Sharpe/d | DSR | s3 | tail MAR | tail DD | s4 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| liqprem_1 | — cost-dead, ladder skipped — | | | | | | | | | | |

## Decision

- `liqprem_1` kill branch **no_premium**: gross Stouffer Z <= 0 — **no liquidity premium exists in this cross-section**.

A construction is a survivor only if it clears the cost-first pre-screen and then every ladder stage; the verdict above is final (one-touch tail).

Per the free-data addendum, EITHER kill branch closes the entire cross-sectional space permanently — every documented premium class will then have been tested and killed.
