# MTF Confluence — BTC 15m entry + HTF bias (momentum vs counter-trend)

## Verdict: NEGATIVE (no cell clears the deployable ECON_BAR)

- asof: 2026-06-30T18:27:18.609781+00:00
- data_sha: 9a0cac3893c6251f
- base_tf: 15m
- diagnostic: econ walk-forward computed for ALL 24 cells (not DSR-gated)
- ECON_BAR: PF>=1.2/exp>=0.05R/MAR>=0.5/MaxDD<=30R@f=0.01/robust>=0.60
- DSR gate (academic, n_trials=24): >=0.95

| cell | n | z | dsr | pf | mar | ddR | robust | econ | strict |
|---|---|---|---|---|---|---|---|---|---|
| 1d:price_vs_sma|rsi_reversion|horizon_hold | 774 | 2.815 | 0.261 | 1.220 | 4.164 | -294.664 | 0.553 | - | negative |
| 1d:price_vs_sma|rsi_reversion|horizon_wide_stop | 774 | 2.815 | 0.086 | 1.255 | 3.992 | -203.470 | 0.526 | - | negative |
| 1d:price_vs_sma|donchian_break|horizon_hold | 646 | 2.578 | 0.278 | 1.239 | 3.967 | -268.365 | 0.539 | - | negative |
| 1d:price_vs_sma|ma_reclaim|horizon_wide_stop | 793 | 2.470 | 0.009 | 1.207 | 2.868 | -244.425 | 0.474 | - | negative |
| 1d:price_vs_sma|ma_reclaim|horizon_hold | 793 | 2.470 | 0.149 | 1.156 | 2.416 | -389.261 | 0.592 | - | negative |
| 1d:price_vs_sma|bb_breakout|horizon_hold | 792 | 1.813 | 0.041 | 1.144 | 2.196 | -412.672 | 0.513 | - | negative |
| 4h:price_vs_sma|rsi_reversion|horizon_wide_stop | 794 | -0.126 | 0.004 | 1.085 | 1.505 | -363.523 | 0.513 | - | negative |
| 4h:price_vs_sma|donchian_break|horizon_hold | 707 | 1.007 | 0.011 | 1.067 | 1.161 | -600.358 | 0.592 | - | negative |
| 4h:price_vs_sma|donchian_break|horizon_wide_stop | 707 | 1.007 | 0.024 | 1.077 | 1.086 | -425.337 | 0.553 | - | negative |
| 1d:price_vs_sma|bb_breakout|atr_trail | 792 | 1.813 | 0.000 | 0.786 | 0.892 | -447.264 | 0.303 | - | negative |
| 1d:price_vs_sma|ma_reclaim|atr_trail | 793 | 2.470 | 0.000 | 0.734 | 0.886 | -554.388 | 0.276 | - | negative |
| 4h:price_vs_sma|ma_reclaim|atr_trail | 802 | 0.865 | 0.000 | 0.756 | 0.875 | -1009.663 | 0.237 | - | negative |
| 4h:price_vs_sma|bb_breakout|atr_trail | 812 | 0.664 | 0.001 | 0.757 | 0.815 | -1110.325 | 0.210 | - | negative |
| 1d:price_vs_sma|donchian_break|horizon_wide_stop | 646 | 2.578 | 0.017 | 1.063 | 0.772 | -224.655 | 0.474 | - | negative |
| 4h:price_vs_sma|rsi_reversion|atr_trail | 794 | -0.126 | 0.001 | 0.846 | 0.686 | -789.756 | 0.329 | - | negative |
| 1d:price_vs_sma|donchian_break|atr_trail | 646 | 2.578 | 0.007 | 0.881 | 0.661 | -267.163 | 0.368 | - | negative |
| 4h:price_vs_sma|donchian_break|atr_trail | 707 | 1.007 | 0.003 | 0.858 | 0.636 | -711.733 | 0.342 | - | negative |
| 1d:price_vs_sma|rsi_reversion|atr_trail | 774 | 2.815 | 0.000 | 0.921 | 0.560 | -245.750 | 0.447 | - | negative |
| 4h:price_vs_sma|bb_breakout|horizon_wide_stop | 812 | 0.664 | 0.003 | 0.957 | 0.340 | -921.791 | 0.342 | - | negative |
| 4h:price_vs_sma|ma_reclaim|horizon_hold | 802 | 0.865 | 0.004 | 0.969 | 0.328 | -1246.014 | 0.447 | - | negative |
| 4h:price_vs_sma|ma_reclaim|horizon_wide_stop | 802 | 0.865 | 0.004 | 0.976 | 0.237 | -710.847 | 0.487 | - | negative |
| 4h:price_vs_sma|bb_breakout|horizon_hold | 812 | 0.664 | 0.002 | 1.019 | 0.220 | -1112.811 | 0.526 | - | negative |
| 1d:price_vs_sma|bb_breakout|horizon_wide_stop | 792 | 1.813 | 0.001 | 0.998 | 0.013 | -443.060 | 0.408 | - | negative |
| 4h:price_vs_sma|rsi_reversion|horizon_hold | 794 | -0.126 | 0.000 | 1.001 | 0.008 | -1090.506 | 0.526 | - | negative |

## Reading this

Momentum triggers (donchian_break/bb_breakout) buy strength; counter-trend triggers (rsi_reversion/ma_reclaim) buy weakness inside the HTF trend (buy-the-dip / sell-the-rip). Compare their drawdown (ddR) and MAR columns to see whether better entry price cuts the path drawdown. Single-asset BTC; any paper candidate needs cross-asset transfer before live consideration.
