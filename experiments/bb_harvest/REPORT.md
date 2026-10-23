# Bollinger-Breakout Harvest — BTC/USDT:USDT 4h

## Verdict: NEGATIVE

> Does the CI-clean exit-free bb_breakout drift survive an exit + cost +
> OOS split + drawdown budget? Frozen 3-stage gate (gross Z>=2.0 ->
> net DSR>=0.95, n_trials=12 -> economic bar). A NEGATIVE
> reproduces the standing 'drift real, path unharvestable' wall and does
> NOT change the WAIT stance.

- bars: 14200  (holdout last 2190 reserved for stage 3 only)

| cell | n | z | dsr | pf | mar | ddR | robust | verdict |
|---|---|---|---|---|---|---|---|---|
| bb_breakout p50m2.0:horizon_hold | 226 | 1.229 | - | - | - | - | - | negative |
| bb_breakout p50m2.0:atr_trail | 226 | 1.229 | - | - | - | - | - | negative |
| bb_breakout p50m2.0:breakeven_horizon | 226 | 1.229 | - | - | - | - | - | negative |
| bb_breakout p50m2.0:horizon_wide_stop | 226 | 1.229 | - | - | - | - | - | negative |
| bb_breakout p50m2.5:horizon_hold | 166 | 1.060 | - | - | - | - | - | negative |
| bb_breakout p50m2.5:atr_trail | 166 | 1.060 | - | - | - | - | - | negative |
| bb_breakout p50m2.5:breakeven_horizon | 166 | 1.060 | - | - | - | - | - | negative |
| bb_breakout p50m2.5:horizon_wide_stop | 166 | 1.060 | - | - | - | - | - | negative |
| bb_breakout p20m2.0:horizon_hold | 319 | 1.725 | - | - | - | - | - | negative |
| bb_breakout p20m2.0:atr_trail | 319 | 1.725 | - | - | - | - | - | negative |
| bb_breakout p20m2.0:breakeven_horizon | 319 | 1.725 | - | - | - | - | - | negative |
| bb_breakout p20m2.0:horizon_wide_stop | 319 | 1.725 | - | - | - | - | - | negative |

## Reconciliation with the exit-free decomposition

The `experiments/bb_breakout` diagnostic showed CI-clean positive drift; this
harvest gate kills every cell at **stage 1** (gross `|Z| < 2.0`). Both are
correct — they measure different things:

- **Window.** The diagnostic used all 14200 bars; stage 1 here runs on
  `train_oos` (the last ~1y / 2190 bars are held out), removing recent history
  that flattered the full-sample mean.
- **Estimator.** The diagnostic bootstrapped a 95% CI on `mean_ret_r` at each of
  four horizons (6/12/18/30) — four looks, and a CI excluding zero is only
  `|z|≈1.96`. Stage 1 uses one frozen horizon (h=24), a single Stouffer Z on
  **non-overlapping** events, gated at the program's cost-first floor of 2.0.
- **Result.** Under the honest, OOS-aware, single-horizon, non-overlapping test
  the strongest entry lands at `z=1.725` (`p20m2.0`, n=319) — below 2.0. The
  drift is real-ish but **too weak to clear the gross gate**, so exit/cost/DSR
  are never reached. The diagnostic's positive CIs were the in-sample,
  full-history, multi-horizon-peeking version of the same data.

**Takeaway:** the bb_breakout drift is not a harvestable long/short edge on BTC
4h. The standing drawdown/edge wall holds; WAIT stance unchanged. The exit knob
was never the bottleneck — the entry has no OOS-robust gross drift to begin with.
