# vrp_measure — BTC Variance Risk Premium (frozen measurement run)

Measurement lane: descriptive accounting over pinned data. Nothing is
predicted. There is no verdict here and no trading rule. See
`experiments/vrp_measure/SPEC.md`.

- commit: `5effcbe52e48410ce6526a84d39faeff44bc9e4f`
- dvol: `cache/exogenous/dvol_BTC_43200_full.csv` sha256 `2b6ef133b30b8fb7298dce012fe83f7c390afcd515915229d21e666a2936089a`
- spot: `.backtest_cache/BTC_USDT_1h.csv` sha256 `ca8f20222017a0fb8f2314c0a94c4c59bb61369c1dda2cea89924b555d4b859f`

## Q1 — data integrity

- window: 2021-03-24 00:00 → 2026-05-31 12:00 UTC
- DVOL bars: 3790
- hourly returns: 46188
- returns excluded at splice boundaries: 10

## Q2 — the spread, full window (annualized variance)

- mean (overlapping, primary): +0.094904
- median: +0.078530
- fraction of windows positive: 0.7451
- block-bootstrap 95% CI: [+0.053134, +0.137323]
- disjoint cross-check (n=64): mean +0.126238, CI [+0.062877, +0.189598]

## Q3 — year by year

| year | mean spread | n |
|---|---|---|
| 2021 | +0.239471 | 566 |
| 2022 | +0.152202 | 730 |
| 2023 | +0.064546 | 730 |
| 2024 | +0.067095 | 732 |
| 2025 | +0.025616 | 730 |
| 2026 | -0.006273 | 302 |

## Q4 — null calibration (the gate)

| null | seeds | mean | p2.5 | p50 | p97.5 |
|---|---|---|---|---|---|
| null_gaussian | 500 | +0.004400 | -0.001387 | +0.004535 | +0.010004 |
| null_student_t | 500 | +0.004319 | -0.019292 | +0.005491 | +0.020192 |

- real mean − gaussian null mean: +0.090504
- clause 1 (above both null p97.5): True
- clause 2 (both CIs above zero): True
- clause 3 (≥5 of 6 buckets positive): True (5 of 6)

**Continuation (SPEC §6): True** — this decides
only whether a Stage-1 spec is written. It is not a verdict.

## Q5 — tail behavior (descriptive, not part of §6)

| window start (UTC) | realized variance | spread |
|---|---|---|
| 2021-05-12 12:00 | 1.747740 | -1.053018 |
| 2021-05-12 00:00 | 1.744724 | -1.000473 |
| 2021-05-11 12:00 | 1.737689 | -0.976084 |
| 2021-05-11 00:00 | 1.734409 | -0.919722 |
| 2021-05-10 12:00 | 1.718350 | -0.913202 |

## Q6 — vol-point spread (descriptive secondary)

- mean DVOL − realized vol: +8.1108 vol points

Jensen caveat: E[σ]² ≠ E[σ²], so this is biased relative to the
variance-space claim in Q2. It is reported because vol points are how
volatility is read, and is not part of any threshold.
