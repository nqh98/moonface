# BTC System-Level Strategy Search -- PREREGISTRATION (frozen)

- asof: 2026-06-20T17:53:17.597788+00:00
- timeframes: 15m, 30m, 1h, 2h, 4h
- pooled n_trials (DSR): 72
- split: chronological train/OOS/sealed-holdout 60 / 20 / 20 per timeframe
- gate: gross drift = DIAGNOSTIC ONLY (never kills) -> DSR>=0.95 -> ECON_BAR(PF>=1.2/exp>=0.05R/MAR>=0.5/MaxDD<=30R@f=0.01/robust>=0.60) -> robustness battery -> plateau
- kill rule: a family failing any stage is CLOSED (no param rescue, no v2)
- exits: EXIT_REGISTRY only (deploy-only trailing exit excluded; Donchian Slice-3 untouched)

## Per-timeframe data fingerprint

| timeframe | bars | data_sha |
|---|---|---|
| 15m | 35040 | 6fb05db9b2b5ba60 |
| 30m | 52596 | a770d73ccfba2f1d |
| 1h | 17520 | b2f301ea165544c8 |
| 2h | 13149 | 7c2e1ed9ee96cc1e |
| 4h | 4380 | 390b99ccdcefb4ee |

## Frozen cells

| timeframe | family | swept grid |
|---|---|---|
| 15m | reversion_in_range | [10.0, 14.0, 21.0] |
| 15m | donchian_break | [20.0, 30.0, 48.0] |
| 15m | vol_compression_breakout | [16.0, 24.0, 32.0] |
| 15m | seasonality | [20.0, 50.0, 100.0] |
| 15m | liquidity_sweep_reclaim | [16.0, 24.0, 32.0] |
| 30m | reversion_in_range | [10.0, 14.0, 21.0] |
| 30m | donchian_break | [20.0, 30.0, 48.0] |
| 30m | vol_compression_breakout | [16.0, 24.0, 32.0] |
| 30m | seasonality | [20.0, 50.0, 100.0] |
| 30m | liquidity_sweep_reclaim | [16.0, 24.0, 32.0] |
| 1h | roc_sign | [12.0, 24.0, 48.0] |
| 1h | atr_channel_break | [1.0, 1.5, 2.0] |
| 1h | trend_pullback | [0.5, 1.0, 1.5] |
| 1h | vol_expansion | [1.5, 2.0, 2.5] |
| 1h | vol_regime | [24.0, 48.0, 96.0] |
| 2h | roc_sign | [12.0, 24.0, 48.0] |
| 2h | atr_channel_break | [1.0, 1.5, 2.0] |
| 2h | trend_pullback | [0.5, 1.0, 1.5] |
| 2h | vol_expansion | [1.5, 2.0, 2.5] |
| 2h | vol_regime | [24.0, 48.0, 96.0] |
| 4h | ma_cross | [50.0, 100.0, 200.0] |
| 4h | donchian_break | [20.0, 55.0, 100.0] |
| 4h | atr_channel_break | [1.0, 1.5, 2.0] |
| 4h | vol_regime | [24.0, 48.0, 96.0] |
