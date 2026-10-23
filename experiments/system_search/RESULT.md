# BTC System-Level Strategy Search

## Verdict: NEGATIVE

- asof: 2026-06-20T20:52:20.153219+00:00
- data_sha: 15m=6fb05db9b2b5ba60, 1h=b2f301ea165544c8, 2h=7c2e1ed9ee96cc1e, 30m=a770d73ccfba2f1d, 4h=390b99ccdcefb4ee
- n_trials (pooled): 72
- gate: gross(diagnostic) -> DSR>=0.95 -> ECON_BAR -> battery -> plateau

| cell | tf | retest | gross_z | dsr | pf | mar | ddR | robust | battery | plateau | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 4h:atr_channel_break:k=2.0 | 4h | Y | 0.766 | 0.401 | - | - | - | - | - | N | negative |
| 4h:ma_cross:slow=100 | 4h | Y | 1.433 | 0.327 | - | - | - | - | - | N | negative |
| 4h:donchian_break:n=55 | 4h | Y | 1.060 | 0.268 | - | - | - | - | - | N | negative |
| 4h:ma_cross:slow=50 | 4h | Y | 0.121 | 0.153 | - | - | - | - | - | N | negative |
| 2h:atr_channel_break:k=2.0 | 2h | Y | 1.741 | 0.061 | - | - | - | - | - | N | negative |
| 4h:vol_regime:window=48 | 4h | Y | 0.582 | 0.041 | - | - | - | - | - | N | negative |
| 15m:vol_compression_breakout:squeeze_n=32 | 15m | N | -0.180 | 0.030 | - | - | - | - | - | N | negative |
| 4h:donchian_break:n=20 | 4h | Y | 1.012 | 0.022 | - | - | - | - | - | N | negative |
| 4h:atr_channel_break:k=1.5 | 4h | Y | 0.659 | 0.014 | - | - | - | - | - | N | negative |
| 4h:atr_channel_break:k=1.0 | 4h | Y | 0.459 | 0.007 | - | - | - | - | - | N | negative |
| 2h:vol_expansion:mult=2.5 | 2h | N | 1.736 | 0.006 | - | - | - | - | - | N | negative |
| 4h:vol_regime:window=24 | 4h | Y | 0.221 | 0.005 | - | - | - | - | - | N | negative |
| 4h:vol_regime:window=96 | 4h | Y | 0.022 | 0.004 | - | - | - | - | - | N | negative |
| 2h:atr_channel_break:k=1.5 | 2h | Y | 2.265 | 0.003 | - | - | - | - | - | N | negative |
| 2h:trend_pullback:pull_atr=1.0 | 2h | N | -0.487 | 0.002 | - | - | - | - | - | N | negative |
| 30m:vol_compression_breakout:squeeze_n=32 | 30m | N | -0.028 | 0.002 | - | - | - | - | - | N | negative |
| 2h:vol_regime:window=96 | 2h | Y | 1.340 | 0.001 | - | - | - | - | - | N | negative |
| 15m:vol_compression_breakout:squeeze_n=24 | 15m | N | 0.524 | 0.000 | - | - | - | - | - | N | negative |
| 1h:atr_channel_break:k=2.0 | 1h | Y | 0.271 | 0.000 | - | - | - | - | - | N | negative |
| 2h:trend_pullback:pull_atr=1.5 | 2h | N | -1.217 | 0.000 | - | - | - | - | - | N | negative |
| 2h:roc_sign:period=48 | 2h | Y | 1.536 | 0.000 | - | - | - | - | - | N | negative |
| 2h:trend_pullback:pull_atr=0.5 | 2h | N | -0.407 | 0.000 | - | - | - | - | - | N | negative |
| 2h:vol_regime:window=48 | 2h | Y | 0.471 | 0.000 | - | - | - | - | - | N | negative |
| 2h:vol_expansion:mult=2.0 | 2h | N | 2.805 | 0.000 | - | - | - | - | - | N | negative |
| 1h:trend_pullback:pull_atr=1.5 | 1h | N | 1.465 | 0.000 | - | - | - | - | - | N | negative |
| 1h:vol_regime:window=48 | 1h | Y | 1.756 | 0.000 | - | - | - | - | - | N | negative |
| 2h:atr_channel_break:k=1.0 | 2h | Y | 2.303 | 0.000 | - | - | - | - | - | N | negative |
| 1h:vol_regime:window=96 | 1h | Y | 0.388 | 0.000 | - | - | - | - | - | N | negative |
| 2h:vol_expansion:mult=1.5 | 2h | N | 0.914 | 0.000 | - | - | - | - | - | N | negative |
| 1h:vol_expansion:mult=2.5 | 1h | N | 1.384 | 0.000 | - | - | - | - | - | N | negative |
| 1h:trend_pullback:pull_atr=1.0 | 1h | N | 0.174 | 0.000 | - | - | - | - | - | N | negative |
| 2h:roc_sign:period=24 | 2h | Y | -0.559 | 0.000 | - | - | - | - | - | N | negative |
| 2h:vol_regime:window=24 | 2h | Y | 0.355 | 0.000 | - | - | - | - | - | N | negative |
| 1h:trend_pullback:pull_atr=0.5 | 1h | N | 1.037 | 0.000 | - | - | - | - | - | N | negative |
| 1h:atr_channel_break:k=1.5 | 1h | Y | -0.207 | 0.000 | - | - | - | - | - | N | negative |
| 30m:vol_compression_breakout:squeeze_n=24 | 30m | N | 1.635 | 0.000 | - | - | - | - | - | N | negative |
| 2h:roc_sign:period=12 | 2h | Y | -0.686 | 0.000 | - | - | - | - | - | N | negative |
| 1h:vol_regime:window=24 | 1h | Y | 1.566 | 0.000 | - | - | - | - | - | N | negative |
| 15m:reversion_in_range:period=21 | 15m | Y | -1.161 | 0.000 | - | - | - | - | - | N | negative |
| 1h:vol_expansion:mult=2.0 | 1h | N | 0.231 | 0.000 | - | - | - | - | - | N | negative |
| 30m:reversion_in_range:period=21 | 30m | Y | -1.035 | 0.000 | - | - | - | - | - | N | negative |
| 1h:roc_sign:period=48 | 1h | Y | -1.547 | 0.000 | - | - | - | - | - | N | negative |
| 1h:roc_sign:period=24 | 1h | Y | -2.611 | 0.000 | - | - | - | - | - | N | negative |
| 15m:vol_compression_breakout:squeeze_n=16 | 15m | N | 0.415 | 0.000 | - | - | - | - | - | N | negative |
| 30m:vol_compression_breakout:squeeze_n=16 | 30m | N | 0.964 | 0.000 | - | - | - | - | - | N | negative |
| 1h:atr_channel_break:k=1.0 | 1h | Y | -0.788 | 0.000 | - | - | - | - | - | N | negative |
| 15m:seasonality:trend_n=100 | 15m | N | 1.151 | 0.000 | - | - | - | - | - | N | negative |
| 1h:roc_sign:period=12 | 1h | Y | -1.214 | 0.000 | - | - | - | - | - | N | negative |
| 1h:vol_expansion:mult=1.5 | 1h | N | -0.434 | 0.000 | - | - | - | - | - | N | negative |
| 15m:donchian_break:n=48 | 15m | Y | -0.097 | 0.000 | - | - | - | - | - | N | negative |
| 15m:reversion_in_range:period=14 | 15m | Y | -0.974 | 0.000 | - | - | - | - | - | N | negative |
| 15m:seasonality:trend_n=20 | 15m | N | 0.724 | 0.000 | - | - | - | - | - | N | negative |
| 15m:seasonality:trend_n=50 | 15m | N | 0.596 | 0.000 | - | - | - | - | - | N | negative |
| 15m:reversion_in_range:period=10 | 15m | Y | -2.001 | 0.000 | - | - | - | - | - | N | negative |
| 15m:donchian_break:n=20 | 15m | Y | 0.544 | 0.000 | - | - | - | - | - | N | negative |
| 15m:donchian_break:n=30 | 15m | Y | 0.813 | 0.000 | - | - | - | - | - | N | negative |
| 15m:liquidity_sweep_reclaim:swing_n=16 | 15m | N | -1.230 | 0.000 | - | - | - | - | - | N | negative |
| 15m:liquidity_sweep_reclaim:swing_n=24 | 15m | N | -0.839 | 0.000 | - | - | - | - | - | N | negative |
| 15m:liquidity_sweep_reclaim:swing_n=32 | 15m | N | -0.654 | 0.000 | - | - | - | - | - | N | negative |
| 30m:reversion_in_range:period=10 | 30m | Y | 0.930 | 0.000 | - | - | - | - | - | N | negative |
| 30m:reversion_in_range:period=14 | 30m | Y | -1.284 | 0.000 | - | - | - | - | - | N | negative |
| 30m:donchian_break:n=20 | 30m | Y | -0.166 | 0.000 | - | - | - | - | - | N | negative |
| 30m:donchian_break:n=30 | 30m | Y | -0.205 | 0.000 | - | - | - | - | - | N | negative |
| 30m:donchian_break:n=48 | 30m | Y | 0.328 | 0.000 | - | - | - | - | - | N | negative |
| 30m:seasonality:trend_n=20 | 30m | N | 0.124 | 0.000 | - | - | - | - | - | N | negative |
| 30m:seasonality:trend_n=50 | 30m | N | 0.699 | 0.000 | - | - | - | - | - | N | negative |
| 30m:seasonality:trend_n=100 | 30m | N | 0.851 | 0.000 | - | - | - | - | - | N | negative |
| 30m:liquidity_sweep_reclaim:swing_n=16 | 30m | N | -0.860 | 0.000 | - | - | - | - | - | N | negative |
| 30m:liquidity_sweep_reclaim:swing_n=24 | 30m | N | -0.072 | 0.000 | - | - | - | - | - | N | negative |
| 30m:liquidity_sweep_reclaim:swing_n=32 | 30m | N | -0.559 | 0.000 | - | - | - | - | - | N | negative |
| 4h:ma_cross:slow=200 | 4h | Y | -0.085 | 0.000 | - | - | - | - | - | N | negative |
| 4h:donchian_break:n=100 | 4h | Y | 0.953 | 0.000 | - | - | - | - | - | N | negative |

## Honest caveat

A NEGATIVE is the expected, valid outcome given the program's 58 closed domains. Any EDGE is a single-asset BTC PAPER candidate only — it does NOT authorize live capital and must later get its own frozen paper-forward protocol. The frozen 4h Donchian Slice-3 strategy is untouched by this lane.
