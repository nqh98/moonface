# Bollinger Band mean-reversion decomposition — RESEARCH-ONLY

> Diagnostic, not a strategy. No edge is claimed; the WAIT stance and
> `experiments/PROGRAM_CONCLUSION.md` are unchanged. Exit-free forward-path
> scoring (declumped events, 6/12/18/30-bar horizons) with a single-asset
> bootstrap 95% CI on mean_ret_r — not a promotion gate.

## BTC/USDT:USDT 4h  (bars=14200)

| variant | params | h | n | win_rate | mean_ret_r | ci95 |
|---|---|---|---|---|---|---|
| bb_revert | {"mult": 2.0, "period": 20} | 6 | 533 | 0.50 | -0.240 | [-0.453, -0.035] |
| bb_revert | {"mult": 2.0, "period": 20} | 12 | 532 | 0.50 | -0.330 | [-0.632, -0.037] |
| bb_revert | {"mult": 2.0, "period": 20} | 18 | 532 | 0.49 | -0.340 | [-0.699, 0.007] |
| bb_revert | {"mult": 2.0, "period": 20} | 30 | 532 | 0.50 | -0.682 | [-1.181, -0.206] |
| bb_revert | {"mult": 2.5, "period": 20} | 6 | 371 | 0.49 | -0.192 | [-0.450, 0.066] |
| bb_revert | {"mult": 2.5, "period": 20} | 12 | 370 | 0.49 | -0.351 | [-0.723, 0.012] |
| bb_revert | {"mult": 2.5, "period": 20} | 18 | 370 | 0.49 | -0.384 | [-0.826, 0.046] |
| bb_revert | {"mult": 2.5, "period": 20} | 30 | 370 | 0.49 | -0.599 | [-1.235, 0.023] |
| bb_revert | {"mult": 3.0, "period": 20} | 6 | 182 | 0.48 | -0.280 | [-0.680, 0.114] |
| bb_revert | {"mult": 3.0, "period": 20} | 12 | 182 | 0.48 | -0.627 | [-1.218, -0.063] |
| bb_revert | {"mult": 3.0, "period": 20} | 18 | 182 | 0.51 | -0.559 | [-1.250, 0.109] |
| bb_revert | {"mult": 3.0, "period": 20} | 30 | 182 | 0.48 | -0.979 | [-1.985, -0.025] |
| bb_revert | {"mult": 2.0, "period": 50} | 6 | 344 | 0.49 | -0.288 | [-0.532, -0.051] |
| bb_revert | {"mult": 2.0, "period": 50} | 12 | 344 | 0.48 | -0.560 | [-0.898, -0.225] |
| bb_revert | {"mult": 2.0, "period": 50} | 18 | 344 | 0.51 | -0.538 | [-0.963, -0.123] |
| bb_revert | {"mult": 2.0, "period": 50} | 30 | 344 | 0.51 | -0.641 | [-1.230, -0.069] |
| bb_revert | {"mult": 2.5, "period": 50} | 6 | 218 | 0.44 | -0.333 | [-0.630, -0.042] |
| bb_revert | {"mult": 2.5, "period": 50} | 12 | 218 | 0.48 | -0.513 | [-0.955, -0.087] |
| bb_revert | {"mult": 2.5, "period": 50} | 18 | 218 | 0.49 | -0.541 | [-1.092, -0.005] |
| bb_revert | {"mult": 2.5, "period": 50} | 30 | 218 | 0.51 | -0.629 | [-1.497, 0.154] |
| bb_revert | {"mult": 3.0, "period": 50} | 6 | 127 | 0.50 | -0.221 | [-0.647, 0.191] |
| bb_revert | {"mult": 3.0, "period": 50} | 12 | 127 | 0.50 | -0.460 | [-1.040, 0.097] |
| bb_revert | {"mult": 3.0, "period": 50} | 18 | 127 | 0.51 | -0.398 | [-1.123, 0.286] |
| bb_revert | {"mult": 3.0, "period": 50} | 30 | 127 | 0.48 | -0.639 | [-1.607, 0.291] |

