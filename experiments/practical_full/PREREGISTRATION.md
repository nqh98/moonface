# BTC Practical FULL Re-Evaluation — PREREGISTRATION (frozen)

- asof: 2026-06-25T13:59:45.745172+00:00
- timeframes: 2h, 4h
- configs (reported DSR n_trials): 132
- families: atr_channel_break, donchian_break, liquidity_sweep_reclaim, ma_cross, price_vs_ma, reversion_in_range, roc_sign, trend_pullback, vol_compression_breakout, vol_expansion, vol_regime
- exits: atr_trail, chandelier, fixed_bracket, mean_revert_reclaim
- split: chronological Explore/Validate/Sealed 60/20/20 per timeframe (Sealed = most-recent holdout)
- selection gates: net-R>0, PF>=1.15, expectancy>0, |DD|<=30R@f=0.01, trades>=30, parameter-island, outlier-dependence, +5bps cost-stress, recent-period, AND 2x AND 3x multiplicative cost
- accept: dual replication on Validate AND Sealed (same thresholds + same sign + 2x/3x cost on both); DSR reported, NOT a gate; output PAPER ONLY
- isolation: Donchian / promotion / journal untouched; EXIT_REGISTRY unchanged

## Per-timeframe data fingerprint

| timeframe | bars | data_sha |
|---|---|---|
| 2h | 28356 | 8de450095ac5cf18 |
| 4h | 14178 | b3b004cb58258369 |
