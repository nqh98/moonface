# Bollinger Band breakout decomposition — RESEARCH-ONLY

> Diagnostic, not a strategy. No edge is claimed; the WAIT stance and
> `experiments/PROGRAM_CONCLUSION.md` are unchanged. Exit-free forward-path
> scoring (declumped events, 6/12/18/30-bar horizons) with a single-asset
> bootstrap 95% CI on mean_ret_r — not a promotion gate. This is the
> momentum mirror of the bb_revert (mean-reversion) decomposition.

## BTC/USDT:USDT 4h  (bars=14200)

| variant | params | h | n | win_rate | mean_ret_r | ci95 |
|---|---|---|---|---|---|---|
| bb_breakout | {"mult": 2.0, "period": 20} | 6 | 533 | 0.50 | 0.240 | [0.035, 0.453] |
| bb_breakout | {"mult": 2.0, "period": 20} | 12 | 532 | 0.50 | 0.330 | [0.037, 0.633] |
| bb_breakout | {"mult": 2.0, "period": 20} | 18 | 532 | 0.51 | 0.340 | [-0.007, 0.700] |
| bb_breakout | {"mult": 2.0, "period": 20} | 30 | 532 | 0.50 | 0.682 | [0.207, 1.181] |
| bb_breakout | {"mult": 2.5, "period": 20} | 6 | 371 | 0.51 | 0.192 | [-0.066, 0.450] |
| bb_breakout | {"mult": 2.5, "period": 20} | 12 | 370 | 0.51 | 0.351 | [-0.012, 0.724] |
| bb_breakout | {"mult": 2.5, "period": 20} | 18 | 370 | 0.51 | 0.384 | [-0.046, 0.827] |
| bb_breakout | {"mult": 2.5, "period": 20} | 30 | 370 | 0.51 | 0.599 | [-0.023, 1.237] |
| bb_breakout | {"mult": 3.0, "period": 20} | 6 | 182 | 0.52 | 0.280 | [-0.114, 0.680] |
| bb_breakout | {"mult": 3.0, "period": 20} | 12 | 182 | 0.52 | 0.627 | [0.064, 1.219] |
| bb_breakout | {"mult": 3.0, "period": 20} | 18 | 182 | 0.49 | 0.559 | [-0.109, 1.250] |
| bb_breakout | {"mult": 3.0, "period": 20} | 30 | 182 | 0.52 | 0.979 | [0.025, 1.986] |
| bb_breakout | {"mult": 2.0, "period": 50} | 6 | 344 | 0.51 | 0.288 | [0.051, 0.533] |
| bb_breakout | {"mult": 2.0, "period": 50} | 12 | 344 | 0.52 | 0.560 | [0.225, 0.898] |
| bb_breakout | {"mult": 2.0, "period": 50} | 18 | 344 | 0.49 | 0.538 | [0.123, 0.963] |
| bb_breakout | {"mult": 2.0, "period": 50} | 30 | 344 | 0.49 | 0.641 | [0.069, 1.230] |
| bb_breakout | {"mult": 2.5, "period": 50} | 6 | 218 | 0.56 | 0.333 | [0.042, 0.630] |
| bb_breakout | {"mult": 2.5, "period": 50} | 12 | 218 | 0.52 | 0.513 | [0.087, 0.955] |
| bb_breakout | {"mult": 2.5, "period": 50} | 18 | 218 | 0.51 | 0.541 | [0.006, 1.093] |
| bb_breakout | {"mult": 2.5, "period": 50} | 30 | 218 | 0.49 | 0.629 | [-0.154, 1.497] |
| bb_breakout | {"mult": 3.0, "period": 50} | 6 | 127 | 0.50 | 0.221 | [-0.191, 0.647] |
| bb_breakout | {"mult": 3.0, "period": 50} | 12 | 127 | 0.50 | 0.460 | [-0.096, 1.040] |
| bb_breakout | {"mult": 3.0, "period": 50} | 18 | 127 | 0.49 | 0.398 | [-0.286, 1.123] |
| bb_breakout | {"mult": 3.0, "period": 50} | 30 | 127 | 0.52 | 0.639 | [-0.290, 1.607] |

