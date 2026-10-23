# MTF Confluence — BTC 15m entry + HTF bias (momentum vs counter-trend)

## Verdict: NEGATIVE (no cell clears the deployable ECON_BAR)

- asof: 2026-06-30T19:22:47.932654+00:00
- data_sha: 9a0cac3893c6251f
- base_tf: 15m
- diagnostic: econ walk-forward computed for ALL 72 cells (not DSR-gated)
- ECON_BAR: PF>=1.2/exp>=0.05R/MAR>=0.5/MaxDD<=30R@f=0.01/robust>=0.60
- DSR gate (academic, n_trials=72): >=0.95

| cell | n | z | dsr | pf | mar | ddR | robust | econ | strict |
|---|---|---|---|---|---|---|---|---|---|
| 4h:trend_strength|rsi_reversion|horizon_hold@2d | 583 | 2.159 | 0.376 | 1.188 | 4.685 | -294.661 | 0.539 | - | negative |
| 1d:price_vs_sma|rsi_reversion|horizon_hold@2d | 774 | 2.815 | 0.494 | 1.220 | 4.164 | -294.664 | 0.553 | - | negative |
| 1d:price_vs_sma|rsi_reversion|horizon_wide_stop@2d | 774 | 2.815 | 0.253 | 1.255 | 3.992 | -203.470 | 0.526 | - | negative |
| 1d:price_vs_sma|donchian_break|horizon_hold@2d | 646 | 2.578 | 0.507 | 1.239 | 3.967 | -268.365 | 0.539 | - | negative |
| 1d:roc|rsi_reversion|horizon_wide_stop@2d | 777 | 0.880 | 0.054 | 1.167 | 2.886 | -178.904 | 0.553 | - | negative |
| 1d:price_vs_sma|ma_reclaim|horizon_wide_stop@2d | 793 | 2.470 | 0.040 | 1.207 | 2.868 | -244.425 | 0.474 | - | negative |
| 4h:roc|rsi_reversion|horizon_wide_stop@2d | 796 | 1.156 | 0.108 | 1.165 | 2.533 | -416.670 | 0.579 | - | negative |
| 1d:trend_strength|ma_reclaim|horizon_wide_stop@2d | 492 | 1.504 | 0.147 | 1.246 | 2.523 | -204.416 | 0.408 | - | negative |
| 1d:price_vs_sma|ma_reclaim|horizon_hold@2d | 793 | 2.470 | 0.331 | 1.156 | 2.416 | -389.261 | 0.592 | - | negative |
| 4h:trend_strength|donchian_break|horizon_wide_stop@1d | 718 | 1.827 | 0.103 | 1.111 | 2.326 | -245.288 | 0.579 | - | negative |
| 4h:trend_strength|donchian_break|horizon_hold@2d | 507 | 1.785 | 0.312 | 1.190 | 2.231 | -526.048 | 0.618 | - | negative |
| 1d:trend_strength|donchian_break|horizon_wide_stop@1d | 577 | 2.309 | 0.353 | 1.182 | 2.228 | -172.634 | 0.500 | - | negative |
| 1d:roc|donchian_break|horizon_hold@2d | 635 | 1.766 | 0.200 | 1.190 | 1.958 | -402.939 | 0.579 | - | negative |
| 4h:trend_strength|rsi_reversion|horizon_wide_stop@2d | 583 | 2.159 | 0.393 | 1.175 | 1.901 | -422.529 | 0.526 | - | negative |
| 1d:price_vs_sma|donchian_break|horizon_wide_stop@1d | 989 | 1.766 | 0.125 | 1.095 | 1.864 | -187.907 | 0.539 | - | negative |
| 1d:trend_strength|rsi_reversion|horizon_wide_stop@2d | 502 | 1.169 | 0.145 | 1.198 | 1.705 | -230.746 | 0.474 | - | negative |
| 4h:trend_strength|donchian_break|horizon_hold@1d | 718 | 1.827 | 0.125 | 1.122 | 1.685 | -484.473 | 0.526 | - | negative |
| 4h:roc|rsi_reversion|horizon_hold@2d | 796 | 1.156 | 0.040 | 1.112 | 1.605 | -791.321 | 0.658 | - | negative |
| 4h:trend_strength|ma_reclaim|horizon_hold@2d | 553 | 1.538 | 0.198 | 1.108 | 1.562 | -548.696 | 0.513 | - | negative |
| 1d:trend_strength|donchian_break|horizon_hold@2d | 398 | 1.822 | 0.420 | 1.211 | 1.507 | -378.075 | 0.487 | - | negative |
| 4h:price_vs_sma|rsi_reversion|horizon_wide_stop@2d | 794 | -0.126 | 0.021 | 1.085 | 1.505 | -363.523 | 0.513 | - | negative |
| 4h:roc|donchian_break|horizon_hold@2d | 679 | 1.437 | 0.104 | 1.079 | 1.363 | -574.847 | 0.592 | - | negative |
| 4h:price_vs_sma|donchian_break|horizon_hold@2d | 707 | 1.007 | 0.043 | 1.067 | 1.161 | -600.358 | 0.592 | - | negative |
| 1d:price_vs_sma|ma_reclaim|horizon_hold@1d | 1416 | 3.118 | 0.095 | 1.086 | 1.141 | -550.235 | 0.579 | - | negative |
| 4h:price_vs_sma|donchian_break|horizon_wide_stop@2d | 707 | 1.007 | 0.086 | 1.077 | 1.086 | -425.337 | 0.553 | - | negative |
| 1d:roc|rsi_reversion|horizon_hold@2d | 777 | 0.880 | 0.023 | 1.073 | 1.029 | -410.993 | 0.500 | - | negative |
| 1d:trend_strength|rsi_reversion|horizon_hold@2d | 502 | 1.169 | 0.135 | 1.088 | 0.941 | -332.227 | 0.474 | - | negative |
| 4h:roc|rsi_reversion|horizon_hold@1d | 1368 | -0.493 | 0.000 | 0.900 | 0.865 | -1652.635 | 0.342 | - | negative |
| 4h:roc|ma_reclaim|horizon_wide_stop@1d | 1428 | 0.046 | 0.000 | 0.897 | 0.837 | -1354.855 | 0.355 | - | negative |
| 1d:price_vs_sma|donchian_break|horizon_wide_stop@2d | 646 | 2.578 | 0.061 | 1.063 | 0.772 | -224.655 | 0.474 | - | negative |
| 4h:price_vs_sma|rsi_reversion|horizon_hold@1d | 1365 | 0.018 | 0.000 | 0.908 | 0.764 | -1696.738 | 0.355 | - | negative |
| 4h:price_vs_sma|ma_reclaim|horizon_wide_stop@1d | 1425 | 0.545 | 0.000 | 0.910 | 0.722 | -1385.185 | 0.434 | - | negative |
| 1d:trend_strength|ma_reclaim|horizon_hold@2d | 492 | 1.504 | 0.231 | 1.091 | 0.713 | -513.881 | 0.539 | - | negative |
| 4h:roc|ma_reclaim|horizon_wide_stop@2d | 806 | 0.714 | 0.001 | 0.857 | 0.703 | -1435.576 | 0.408 | - | negative |
| 4h:trend_strength|ma_reclaim|horizon_wide_stop@1d | 844 | 1.934 | 0.001 | 0.894 | 0.693 | -949.652 | 0.342 | - | negative |
| 4h:trend_strength|ma_reclaim|horizon_hold@1d | 844 | 1.934 | 0.071 | 1.051 | 0.655 | -613.151 | 0.553 | - | negative |
| 4h:roc|donchian_break|horizon_hold@1d | 1039 | 0.022 | 0.000 | 0.926 | 0.627 | -1361.102 | 0.434 | - | negative |
| 1d:roc|donchian_break|horizon_wide_stop@1d | 974 | 1.555 | 0.075 | 1.048 | 0.588 | -288.124 | 0.553 | - | negative |
| 4h:roc|ma_reclaim|horizon_hold@1d | 1428 | 0.046 | 0.000 | 0.925 | 0.578 | -2047.470 | 0.434 | - | negative |
| 1d:trend_strength|donchian_break|horizon_hold@1d | 577 | 2.309 | 0.362 | 1.089 | 0.560 | -474.672 | 0.474 | - | negative |
| 4h:trend_strength|ma_reclaim|horizon_wide_stop@2d | 553 | 1.538 | 0.118 | 1.059 | 0.552 | -494.829 | 0.539 | - | negative |
| 4h:price_vs_sma|rsi_reversion|horizon_wide_stop@1d | 1365 | 0.018 | 0.000 | 0.936 | 0.530 | -1167.856 | 0.461 | - | negative |
| 1d:price_vs_sma|ma_reclaim|horizon_wide_stop@1d | 1416 | 3.118 | 0.006 | 1.041 | 0.516 | -423.045 | 0.434 | - | negative |
| 1d:roc|ma_reclaim|horizon_hold@2d | 796 | 0.857 | 0.021 | 0.951 | 0.472 | -668.914 | 0.539 | - | negative |
| 4h:price_vs_sma|ma_reclaim|horizon_hold@1d | 1425 | 0.545 | 0.000 | 0.948 | 0.468 | -1744.307 | 0.447 | - | negative |
| 1d:roc|ma_reclaim|horizon_hold@1d | 1426 | 1.881 | 0.005 | 1.034 | 0.436 | -578.541 | 0.553 | - | negative |
| 4h:price_vs_sma|donchian_break|horizon_hold@1d | 1090 | 0.335 | 0.000 | 0.958 | 0.425 | -1153.523 | 0.447 | - | negative |
| 4h:trend_strength|rsi_reversion|horizon_wide_stop@1d | 894 | 1.466 | 0.050 | 1.033 | 0.416 | -481.380 | 0.474 | - | negative |
| 1d:trend_strength|rsi_reversion|horizon_hold@1d | 811 | 0.686 | 0.006 | 0.953 | 0.402 | -486.125 | 0.487 | - | negative |
| 4h:roc|donchian_break|horizon_wide_stop@1d | 1039 | 0.022 | 0.007 | 1.025 | 0.332 | -591.536 | 0.513 | - | negative |
| 4h:roc|rsi_reversion|horizon_wide_stop@1d | 1368 | -0.493 | 0.001 | 0.970 | 0.330 | -883.900 | 0.461 | - | negative |
| 4h:price_vs_sma|ma_reclaim|horizon_hold@2d | 802 | 0.865 | 0.019 | 0.969 | 0.328 | -1246.014 | 0.447 | - | negative |
| 1d:trend_strength|ma_reclaim|horizon_hold@1d | 849 | 0.890 | 0.008 | 0.947 | 0.327 | -773.327 | 0.487 | - | negative |
| 4h:roc|donchian_break|horizon_wide_stop@2d | 679 | 1.437 | 0.022 | 0.977 | 0.283 | -470.628 | 0.500 | - | negative |
| 1d:price_vs_sma|rsi_reversion|horizon_hold@1d | 1333 | 1.652 | 0.005 | 0.984 | 0.249 | -448.637 | 0.539 | - | negative |
| 1d:roc|donchian_break|horizon_wide_stop@2d | 635 | 1.766 | 0.008 | 0.974 | 0.246 | -285.513 | 0.408 | - | negative |
| 4h:price_vs_sma|donchian_break|horizon_wide_stop@1d | 1090 | 0.335 | 0.005 | 1.015 | 0.240 | -505.363 | 0.487 | - | negative |
| 1d:roc|ma_reclaim|horizon_wide_stop@1d | 1426 | 1.881 | 0.001 | 0.978 | 0.239 | -477.247 | 0.395 | - | negative |
| 4h:price_vs_sma|ma_reclaim|horizon_wide_stop@2d | 802 | 0.865 | 0.022 | 0.976 | 0.237 | -710.847 | 0.487 | - | negative |
| 1d:trend_strength|donchian_break|horizon_wide_stop@2d | 398 | 1.822 | 0.051 | 1.035 | 0.232 | -259.401 | 0.329 | - | negative |
| 4h:trend_strength|donchian_break|horizon_wide_stop@2d | 507 | 1.785 | 0.030 | 0.971 | 0.195 | -611.772 | 0.395 | - | negative |
| 1d:price_vs_sma|rsi_reversion|horizon_wide_stop@1d | 1333 | 1.652 | 0.000 | 0.987 | 0.191 | -329.678 | 0.447 | - | negative |
| 1d:roc|ma_reclaim|horizon_wide_stop@2d | 796 | 0.857 | 0.030 | 0.984 | 0.165 | -326.305 | 0.355 | - | negative |
| 4h:roc|ma_reclaim|horizon_hold@2d | 806 | 0.714 | 0.014 | 1.011 | 0.135 | -1001.495 | 0.513 | - | negative |
| 1d:trend_strength|ma_reclaim|horizon_wide_stop@1d | 849 | 0.890 | 0.014 | 1.013 | 0.132 | -305.860 | 0.447 | - | negative |
| 1d:roc|rsi_reversion|horizon_wide_stop@1d | 1335 | 1.064 | 0.000 | 0.990 | 0.128 | -360.222 | 0.447 | - | negative |
| 1d:trend_strength|rsi_reversion|horizon_wide_stop@1d | 811 | 0.686 | 0.004 | 1.006 | 0.080 | -204.398 | 0.421 | - | negative |
| 4h:trend_strength|rsi_reversion|horizon_hold@1d | 894 | 1.466 | 0.025 | 0.998 | 0.024 | -745.979 | 0.434 | - | negative |
| 1d:price_vs_sma|donchian_break|horizon_hold@1d | 989 | 1.766 | 0.038 | 1.002 | 0.018 | -537.417 | 0.447 | - | negative |
| 4h:price_vs_sma|rsi_reversion|horizon_hold@2d | 794 | -0.126 | 0.001 | 1.001 | 0.008 | -1090.506 | 0.526 | - | negative |
| 1d:roc|donchian_break|horizon_hold@1d | 974 | 1.555 | 0.024 | 1.001 | 0.007 | -456.596 | 0.434 | - | negative |
| 1d:roc|rsi_reversion|horizon_hold@1d | 1335 | 1.064 | 0.001 | 1.000 | 0.005 | -389.764 | 0.526 | - | negative |

## Reading this

Momentum triggers (donchian_break/bb_breakout) buy strength; counter-trend triggers (rsi_reversion/ma_reclaim) buy weakness inside the HTF trend (buy-the-dip / sell-the-rip). Compare their drawdown (ddR) and MAR columns to see whether better entry price cuts the path drawdown. Single-asset BTC; any paper candidate needs cross-asset transfer before live consideration.
