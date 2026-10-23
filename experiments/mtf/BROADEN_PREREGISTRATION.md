# MTF Broadened Search — Pre-Registration (frozen before any result look)

The frozen 24-cell MTF grid fixed one regime definition (`price_vs_sma`) and a
single 2-day hold, and surfaced the headline cell (1d trend gate + 15m RSI
counter-trend, PF 1.24) that fails DSR and the drawdown cap. This pre-registers a
broadened 15m-1d search asking a sharper question: **is any structurally-different
cell BETTER than the headline, or does any cell clear the deployable bar?** Frozen
here so the result cannot be rationalised after the fact. Paper research; promotes
nothing to live. The frozen `all_cells()`/`headline_cell()` spec, the two MTF
forward registrations, and the 4h Donchian Slice-3 strategy are untouched.

- **asof:** 2026-07-01
- **symbol / base:** BTCUSDT, 15m base (every HTF is a closed-bar resample)
- **window:** 2020-01-01 → end-of-data (START_MS 1_577_836_800_000, END_MS
  1_782_000_000_000); train_oos = first 80%, last 20% holdout read only inside
  stage-3 walk-forward (identical split to `mtf_search.py`).
- **grid (frozen):** `grid.broadened_cells()` = **72 cells** =
  2 HTF {4h, 1d} × 3 biases × 3 triggers × (2 exits × 2 holds).

### The new structural axes (the experiment)

1. **Regime DEFINITION** (was fixed to one): `price_vs_sma` (trend sign,
   reproduces the frozen headline as a control), `roc` (momentum sign — coded but
   never gridded), **`trend_strength`** (regime QUALITY: trade only when
   |close − SMA50| ≥ 1·σ, flat in chop). The hero hypothesis: skipping the chop
   removes the weak-trend whipsaw losers behind the 2022/2024 down years and so
   **lifts PF on the counter-trend entries**.
2. **Hold horizon** (was fixed to 2d): {1d, 2d} swings — the 15m–1d range floor.
3. Triggers narrowed to the diagnostic's three best (`rsi_reversion`,
   `ma_reclaim` counter-trend + `donchian_break` momentum); the dominated
   `atr_trail` exit and the `bb_breakout` trigger are dropped (PF<1 everywhere in
   the 24-cell run).

### Gates (frozen, identical ladder to the lane)

- **Stage 1** gross Stouffer |Z| ≥ 2.0 (diagnostic only — never kills here).
- **Stage 2** OOS deflated Sharpe **DSR ≥ 0.95**, deflated by the full
  **n_trials = 72** (honest multiple-comparison penalty for the wider grid).
- **Stage 3** econ walk-forward vs **ECON_BAR**
  (PF ≥ 1.2 / exp ≥ 0.05R / MAR ≥ 0.5 / MaxDD ≤ 30R@f=0.01 / robust ≥ 0.60).

### Decision rule (frozen)

| outcome | condition |
|---|---|
| **PROMOTE** (new paper candidate, own forward registration) | any cell clears DSR ≥ 0.95, OR any **non-headline** cell clears the full ECON_BAR |
| **BETTER-THAN-HEADLINE** (re-rank the lane's best, paper only) | a non-headline cell has, on the full single path, higher MAR **and** higher PF **and** robust_frac ≥ the headline's — without clearing ECON_BAR |
| **NEGATIVE** (expected) | no cell clears DSR or ECON_BAR and none beats the headline → broadening adds nothing; the headline stands as the lane's best and both forward registrations are unchanged |

**Kill rule:** a NEGATIVE closes the broadened grid — no per-cell parameter
rescue, no re-grid on the same data. The program's discipline (a failed grid is
closed, not re-tuned) is what kept 58 domains honest. A BETTER-THAN-HEADLINE only
re-ranks which cell the lane tracks forward; it does NOT authorise live capital.

### Prior (honest)

The program's strong prior is NEGATIVE: every prior grid expansion found nothing
and only deflated DSR, and the 24-cell diagnostic already placed the headline at
the top of its leaderboard. The `trend_strength` gate is the one genuinely new
mechanism with a specific, falsifiable reason to beat it (it targets the known
weak-trend failure mode). Expected result: trend_strength trades less and may
lift PF but cut robustness/total-R, and no cell clears the deployable bar — but
the test is cheap, frozen, and the right way to answer the user's "search wider."
