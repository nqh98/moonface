# Donchian Walk-Forward Result — BTCUSDT 4h

## Verdict: FAIL

- windows (test-only): 1
- entry_n/trail_n mode = 40/20
- expectancy_r: -0.5285
- profit_factor: 0.2773 (floor 1.2)
- MAR: 0.9829 (floor 0.5)
- max drawdown: -12.9054R (tol 30.0R @ f=0.01)
- robust fraction: 0.0 (floor 0.6)

## Reasons

- expectancy -0.5285 < 0.05
- profit factor 0.2773 < 1.2
- robust in 0% of windows < 60%

## Honest caveat

Most likely outcome is no deployable edge; a FAIL is a valid, informative result and cheaper to learn now than with live capital.

## Read this carefully — what this 3y cut is and is NOT

- **N=1 test window.** The walk-forward needs 2y train + 1y test; a 3y span yields exactly ONE non-overlapping test window. The "test" period is just the most recent year (~2025-06-20 → 2026-06-20), trained on 2023-06-20 → 2025-06-20. This is a single realised year, not a robustness measurement.
- It does NOT supersede the frozen 6.5y revalidation
  (`DONCHIAN_REVALIDATION_RESULT.md`, 2026-06-20), which over 4 windows is
  `INCONCLUSIVE / PAPER-SUSPENDED` — passing PF/exp/MAR/maxDD aggregate gates and
  missing only robust_frac 0.5<0.60 (a quantization artifact per Slice-2's 14-window 0.7857).
- The most recent 1y was a poor regime for the deployed 40/20 config (PF 0.277,
  expectancy −0.53R). That is information, not a verdict.
- **This must NOT trigger re-tuning.** The strategy config is byte-frozen under the
  Slice-3 forward paper registration (`DONCHIAN_SLICE3_FORWARD_REGISTRATION.md`).
  Re-cutting windows and adjusting params off a bad recent year is exactly the
  post-hoc overfitting that registration forbids. Resolution comes from forward
  paper evidence, not from re-slicing the historical path.
