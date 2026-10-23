# Donchian Walk-Forward Result — Slice-2 (robustness-only) — BTCUSDT 4h

## Verdict: PASS (promote to paper — NOT live)

- aggregate gates from non-overlapping yearly run: 4 windows
- robustness from overlapping 1-year windows (quarterly step): 14 windows
- expectancy_r: 0.4442
- profit_factor: 1.7543 (floor 1.2)
- MAR: 4.6755 (floor 0.5)
- max drawdown: -7.7908R (tol 30.0R @ f=0.01)
- robust fraction: 0.7857 (floor 0.6)

## Reasons

- all thresholds met

## Honest caveat

Overlapping windows are autocorrelated (consecutive 1-year windows share ~3/4 of their data), so robust_frac here is a smoother estimate of the same quantity, not independent trials. A FAIL remains a valid, informative result and cheaper to learn now than with live capital.

## Chosen params (clean-run mode)

- entry_n/trail_n mode = 40/20
