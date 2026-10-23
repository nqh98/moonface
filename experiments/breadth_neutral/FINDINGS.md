# Breadth-internal leads — market-neutral (BTC-hedged) falsification

## Verdict: RESIDUAL_SURVIVES

- asof: 2026-06-28T17:17:59.891650+00:00
- market factor: BTCUSDT   beta_window: 500 bars
- bonferroni_alpha: 0.0125
- raw anchor_ok (beta=0 reproduces cross-asset): True

| asset | lead | status | raw_exp | hedged_exp | beta_contrib | mean_beta | pooled_n | boot_lo | p_le0 |
|---|---|---|---|---|---|---|---|---|---|
| ETHUSDT | net_new_highs | beta_explained | 0.474 | -0.049 | 0.523 | 1.152 | 66 | -0.454 | 0.6068 |
| ETHUSDT | breadth_momentum | residual_positive | 0.193 | 0.043 | 0.150 | 1.158 | 653 | -0.129 | 0.2922 |
| SOLUSDT | net_new_highs | beta_explained | 0.407 | -0.020 | 0.427 | 1.351 | 60 | -0.474 | 0.5377 |
| SOLUSDT | breadth_momentum | beta_explained | 0.093 | -0.044 | 0.136 | 1.355 | 587 | -0.216 | 0.7170 |

Paper-only. Each ETH/SOL breadth trade is hedged against BTC over its holding window (rolling trailing beta, no look-ahead). `beta_contrib` = raw_exp − hedged_exp is how much of the edge was crypto beta. If hedged_exp collapses to ~0/negative, the cross-asset confirmation was a single beta bet, not an independent breadth edge.
