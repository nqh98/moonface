# resrev v1 — cross-sectional short-term residual reversal

- generated: 2026-06-17T07:33:17.674133+00:00
- status: **closed_negative**
- symbols with data: 714 (funding fetched for 88)
- frozen window: 1687073580610 .. 1781681580610, fence 1762759980610

Cost-first pre-screen (research window, before the ladder):

| construction | gross mean/d | gross Z | net mean/d | net Z | cost-first |
|---|---|---|---|---|---|
| resrev_1 | -0.000318 | -0.178 | -0.001255 | -0.709 | fail |

Ladder (only constructions that clear cost-first):

| construction | screen mean/d | s1 | holdout MAR | holdout DD | s2 | research Sharpe/d | DSR | s3 | tail MAR | tail DD | s4 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| resrev_1 | — cost-dead, ladder skipped — | | | | | | | | | | |

## Decision

A construction is a survivor only if it clears the cost-first pre-screen and then every ladder stage; the verdict above is final (one-touch tail).
