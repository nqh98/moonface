# Swing Slice-2 — Frozen Design (robustness-only)

**Status: FROZEN before running.** Authored 2026-06-18, ahead of the network run.

## Why Slice-2 exists

Slice-1 walk-forward returned **FAIL on the robustness gate only**: `robust_frac`
0.50 (2 of 4 windows) vs the 0.60 floor, while the other four economic gates
cleared comfortably (PF 1.75, expectancy 0.44R, MAR 4.68, maxDD −7.79R). With
only **N=4 non-overlapping yearly windows**, the 0.60 floor is quantised — it
effectively demands 3/4 = 75%, so a single weak deployment year flips the verdict.
Slice-2 re-estimates robustness on a finer grid of windows to tell whether the
two weak windows were isolated years or a pervasive failure.

## Locked invariants (NOT changed)

- **Strategy / params / Donchian construction:** unchanged. The runner imports
  the exact `_BASE` and `_GRID` objects from `tools/swing_donchian.py` — no
  re-declaration, so strategy identity is guaranteed at the object level.
- **Engine & sim:** `backtest/engine.py` and `trend_sim.py` byte-unchanged.
- **Economic gates:** `ECON_BAR` unchanged (PF≥1.2, exp≥0.05R, MAR≥0.5,
  MaxDD≤30R@f=0.01, robust≥0.60). No floor weakened.
- **No filters, exits, regime overlays, or variants added.**
- **Data:** BTCUSDT 4h, 2020-01-01 → ~2026-06 (14,159 bars ≈ 6.46y). This is
  essentially all of Binance's BTCUSDT perp history; it **cannot be extended**,
  which is why densification (not more history) is the only lever.
- The Slice-1 FAIL is **not** reinterpreted as a PASS. Slice-2 is its own verdict.

## The single lever: walk-forward step

Each deployment window keeps `train = 2 years`, `test = 1 year` — the **same
deployment-style criteria** as Slice-1 (a full forward year evaluated OOS). The
only change is the cadence at which windows are advanced:

- **Aggregate gates (PF, expectancy, MAR, maxDD):** taken from the original
  **non-overlapping yearly run** (`step = 1 year`), i.e. identical to Slice-1.
  This avoids corrupting the pooled R series — overlapping windows would
  double-count trades and make pooled MAR/maxDD meaningless.
- **Robustness gate (`robust_frac`):** recomputed over **overlapping 1-year
  windows advanced one quarter at a time** (`step = 1 quarter = 547 bars`),
  yielding ~14 windows instead of 4. Each window is still a full, untouched
  1-year holdout; only the start dates are denser.

Mechanically: `evaluate_econ(res_dense.test_summaries, res_clean.aggregated)` —
the four aggregate gates read `res_clean.aggregated` (uncorrupted), `robust_frac`
reads `res_dense.test_summaries` (denser). Exact existing `evaluate_econ`, no edit.

## Pre-registered caveats (honest)

- Overlapping windows are **autocorrelated**: consecutive 1-year windows share
  ~3/4 of their data, so the effective sample size is well below the nominal ~14.
  `robust_frac` here is a smoother estimate of the same quantity, not 14
  independent trials. The result will report nominal window count alongside.
- A PASS would mean **"promote to paper — NOT live"**, identical to Slice-1's
  verdict string. It does not authorise capital.
- Most likely outcome remains no deployable edge; a FAIL is a valid result.

## Pre-registered decision rule

Run once. Report `res_clean` aggregate gates + `res_dense` robust_frac through
the unchanged `ECON_BAR`. PASS iff all five gates clear. No re-runs, no
post-hoc step tuning. Output: `experiments/deployable/DONCHIAN_SLICE2_RESULT.md`.
