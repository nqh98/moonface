# xsection_perp v1 — cross-sectional momentum/carry long-short

- generated: 2026-06-12T06:01:01.228112+00:00
- status: **closed_negative**
- symbols with data: 714 (funding fetched for 89)
- frozen window: 1686635234325 .. 1781243234325, fence 1762321634325

| construction | screen mean/d | s1 | holdout MAR | holdout DD | s2 | research Sharpe/d | DSR | s3 | tail MAR | tail DD | s4 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| mom_7 | 0.000926 | PASS | -0.124 | -0.514 | fail | 0.0282 | - | - | -0.987 | -0.901 | fail |
| mom_30 | 0.000532 | PASS | 3.193 | -0.229 | PASS | 0.0452 | 0.828498 | fail | -0.970 | -0.916 | fail |
| carry_7 | 0.001701 | PASS | -0.064 | -0.352 | fail | 0.0579 | - | - | 1.202 | -0.519 | fail |

## Decision

A construction is a survivor only if it clears every stage; the verdict above is final (one-touch tail).
