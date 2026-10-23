# bab v1 — betting-against-beta cross-sectional long-short

- generated: 2026-06-17T06:44:50.052094+00:00
- status: **closed_negative**
- symbols with data: 714 (funding fetched for 92)
- frozen window: 1687070670212 .. 1781678670212, fence 1762757070212

| construction | screen mean/d | s1 | holdout MAR | holdout DD | s2 | research Sharpe/d | DSR | s3 | tail MAR | tail DD | s4 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| bab_60 | 0.001638 | PASS | -0.481 | -0.450 | fail | 0.0400 | - | - | -0.943 | -0.692 | fail |

## Decision

A construction is a survivor only if it clears every stage; the verdict above is final (one-touch tail).
