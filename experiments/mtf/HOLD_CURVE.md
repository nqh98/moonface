# MTF hold horizon — derived from the entry's forward-return path

- asof: 2026-07-01T03:57:47.452839+00:00
- data_sha: 544756e5130ebe12
- gate+entry fixed to broaden_best; only the HOLD length is set by the forward path E[R(h)]
- hold rule: smallest horizon where marginal E[R] per day <= 0 (drift exhausted), on the TRAIN window, confirmed against RECENT OOS
- E[R(h)] traced over ONE fixed non-overlapping trade set (constant n); z = mean / (std/sqrt n)

## Chosen holds

| symbol | exhaustion hold (train) | E[R] | z | significant |
|---|---|---|---|---|
| BTCUSDT | 1.5 d | +0.783 | +0.91 | no |
| ETHUSDT | 1.5 d | +1.149 | +1.72 | yes |
| SOLUSDT | 0.25 d | +0.411 | +1.98 | yes |

## BTCUSDT

### Forward-return path — TRAIN (entries < 2024-06, selection)

| hold (days) | n | E[R] | z (t) | marginal R/day |
|---|---|---|---|---|
| 0.25 | 220 | +0.013 | +0.06 | +0.052 |
| 0.5 | 220 | -0.148 | -0.41 | -0.644 |
| 0.75 | 220 | -0.016 | -0.03 | +0.526 |
| 1.0 | 220 | +0.243 | +0.39 | +1.036 |
| 1.5 | 220 | +0.783 | +0.91 | +1.080 |
| 2.0 | 220 | +0.598 | +0.65 | -0.370 |
| 3.0 | 220 | +0.590 | +0.52 | -0.008 |
| 4.0 | 220 | -0.436 | -0.26 | -1.026 |
| 5.0 | 220 | +0.306 | +0.17 | +0.742 |
| 6.0 | 220 | +1.148 | +0.38 | +0.842 |

### Forward-return path — RECENT OOS (entries >= 2024-06, confirm)

| hold (days) | n | E[R] | z (t) | marginal R/day |
|---|---|---|---|---|
| 0.25 | 104 | +0.221 | +0.62 | +0.886 |
| 0.5 | 104 | +0.311 | +0.53 | +0.357 |
| 0.75 | 104 | +0.768 | +1.03 | +1.828 |
| 1.0 | 104 | +0.961 | +1.15 | +0.775 |
| 1.5 | 104 | +1.643 | +1.59 | +1.364 |
| 2.0 | 104 | +2.163 | +1.90 | +1.039 |
| 3.0 | 104 | +2.245 | +1.55 | +0.082 |
| 4.0 | 104 | +1.803 | +1.00 | -0.442 |
| 5.0 | 104 | +1.200 | +0.66 | -0.604 |
| 6.0 | 104 | +2.212 | +1.15 | +1.013 |

**Risk-adjusted-optimal hold (train): 1.5 d** (max z = per-trade Sharpe peak); E[R]=+0.783, z=+0.91, NOT significant. Raw-E[R] peak at 6.0 d (+1.148R, noisy tail).

deployment — incumbent 2d (single path):

| window | n | pf | exp/trade | totalR | maxDD_R | MAR |
|---|---|---|---|---|---|---|
| full | 731 | 1.24 | +0.897 | +655.6 | -135.61 | 4.8346 |
| recent | 237 | 1.4059 | +1.413 | +334.9 | -103.83 | 3.2257 |

robust_frac=1.0 | ECON MAR floor 0.5, DD cap 30.0R

deployment — derived 1.5d (single path):

| window | n | pf | exp/trade | totalR | maxDD_R | MAR |
|---|---|---|---|---|---|---|
| full | 888 | 1.0978 | +0.322 | +286.2 | -172.45 | 1.6594 |
| recent | 282 | 1.319 | +0.950 | +268.0 | -104.13 | 2.5736 |

robust_frac=0.8571 | ECON MAR floor 0.5, DD cap 30.0R

## ETHUSDT

### Forward-return path — TRAIN (entries < 2024-06, selection)

| hold (days) | n | E[R] | z (t) | marginal R/day |
|---|---|---|---|---|
| 0.25 | 227 | +0.055 | +0.23 | +0.219 |
| 0.5 | 227 | +0.276 | +0.75 | +0.883 |
| 0.75 | 227 | +0.515 | +1.23 | +0.956 |
| 1.0 | 227 | +0.649 | +1.32 | +0.537 |
| 1.5 | 227 | +1.149 | +1.72 | +1.002 |
| 2.0 | 227 | +1.191 | +1.42 | +0.083 |
| 3.0 | 227 | +1.259 | +1.18 | +0.068 |
| 4.0 | 227 | +0.769 | +0.62 | -0.490 |
| 5.0 | 227 | +1.968 | +1.41 | +1.199 |
| 6.0 | 227 | +1.196 | +0.78 | -0.772 |

### Forward-return path — RECENT OOS (entries >= 2024-06, confirm)

| hold (days) | n | E[R] | z (t) | marginal R/day |
|---|---|---|---|---|
| 0.25 | 102 | -0.063 | -0.17 | -0.251 |
| 0.5 | 102 | -0.287 | -0.51 | -0.899 |
| 0.75 | 102 | -0.062 | -0.09 | +0.903 |
| 1.0 | 102 | +0.106 | +0.14 | +0.673 |
| 1.5 | 102 | -0.097 | -0.09 | -0.407 |
| 2.0 | 102 | -0.249 | -0.19 | -0.304 |
| 3.0 | 102 | -1.128 | -0.72 | -0.879 |
| 4.0 | 102 | -0.775 | -0.36 | +0.353 |
| 5.0 | 102 | -0.509 | -0.22 | +0.266 |
| 6.0 | 102 | +0.247 | +0.09 | +0.757 |

**Risk-adjusted-optimal hold (train): 1.5 d** (max z = per-trade Sharpe peak); E[R]=+1.149, z=+1.72, significant. Raw-E[R] peak at 5.0 d (+1.968R, noisy tail).

deployment — incumbent 2d (single path):

| window | n | pf | exp/trade | totalR | maxDD_R | MAR |
|---|---|---|---|---|---|---|
| full | 741 | 1.0501 | +0.214 | +158.9 | -174.97 | 0.9082 |
| recent | 227 | 1.047 | +0.226 | +51.3 | -174.97 | 0.2932 |

robust_frac=0.5714 | ECON MAR floor 0.5, DD cap 30.0R

deployment — derived 1.5d (single path):

| window | n | pf | exp/trade | totalR | maxDD_R | MAR |
|---|---|---|---|---|---|---|
| full | 895 | 0.9929 | -0.025 | -22.5 | -286.1 | 0.0788 |
| recent | 272 | 0.8933 | -0.442 | -120.2 | -231.46 | 0.5193 |

robust_frac=0.2857 | ECON MAR floor 0.5, DD cap 30.0R

## SOLUSDT

### Forward-return path — TRAIN (entries < 2024-06, selection)

| hold (days) | n | E[R] | z (t) | marginal R/day |
|---|---|---|---|---|
| 0.25 | 192 | +0.411 | +1.98 | +1.645 |
| 0.5 | 192 | +0.237 | +0.70 | -0.699 |
| 0.75 | 192 | +0.429 | +1.02 | +0.769 |
| 1.0 | 192 | +0.528 | +1.14 | +0.398 |
| 1.5 | 192 | +0.900 | +1.47 | +0.743 |
| 2.0 | 192 | +1.362 | +1.71 | +0.924 |
| 3.0 | 192 | +1.288 | +1.23 | -0.073 |
| 4.0 | 192 | +1.684 | +1.28 | +0.396 |
| 5.0 | 192 | +2.037 | +1.31 | +0.353 |
| 6.0 | 192 | +2.221 | +1.29 | +0.184 |

### Forward-return path — RECENT OOS (entries >= 2024-06, confirm)

| hold (days) | n | E[R] | z (t) | marginal R/day |
|---|---|---|---|---|
| 0.25 | 104 | +0.111 | +0.29 | +0.445 |
| 0.5 | 104 | +0.551 | +0.96 | +1.759 |
| 0.75 | 104 | +0.968 | +1.44 | +1.669 |
| 1.0 | 104 | +1.552 | +1.75 | +2.333 |
| 1.5 | 104 | +1.298 | +1.24 | -0.508 |
| 2.0 | 104 | +1.239 | +1.10 | -0.117 |
| 3.0 | 104 | +0.365 | +0.31 | -0.875 |
| 4.0 | 104 | +0.760 | +0.54 | +0.396 |
| 5.0 | 104 | +1.533 | +0.90 | +0.773 |
| 6.0 | 104 | +1.326 | +0.71 | -0.207 |

**Risk-adjusted-optimal hold (train): 0.25 d** (max z = per-trade Sharpe peak); E[R]=+0.411, z=+1.98, significant. Raw-E[R] peak at 6.0 d (+2.221R, noisy tail).

deployment — incumbent 2d (single path):

| window | n | pf | exp/trade | totalR | maxDD_R | MAR |
|---|---|---|---|---|---|---|
| full | 669 | 1.3439 | +1.222 | +817.2 | -112.99 | 7.2321 |
| recent | 232 | 1.3095 | +1.125 | +261.0 | -99.5 | 2.623 |

robust_frac=0.8571 | ECON MAR floor 0.5, DD cap 30.0R

deployment — derived 0.25d (single path):

| window | n | pf | exp/trade | totalR | maxDD_R | MAR |
|---|---|---|---|---|---|---|
| full | 1925 | 1.0277 | +0.034 | +65.9 | -147.08 | 0.4481 |
| recent | 649 | 0.9228 | -0.104 | -67.6 | -117.78 | 0.5741 |

robust_frac=0.4286 | ECON MAR floor 0.5, DD cap 30.0R

