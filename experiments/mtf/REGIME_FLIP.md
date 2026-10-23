# MTF regime-flip exit — head-to-head vs fixed-hold / wide-stop

- asof: 2026-07-01T03:43:37.640190+00:00
- data_sha: 544756e5130ebe12
- gate+entry fixed to broaden_best (`4h:trend_strength|rsi_reversion`); only the EXIT varies
- faithful single-path (non-overlapping, per-trade R); recent window >= 2024-06-01
- regime_flip is a parallel follow-up cell (not in the frozen 72-grid, no DSR deflation); promotes nothing to live

## Head-to-head summary (recent OOS = the trust anchor)

| symbol | exit | full pf | full MAR | full DD | recent pf | recent exp | recent n |
|---|---|---|---|---|---|---|---|
| BTCUSDT | horizon_hold (fixed 2d, champion) | 1.24 | 4.8346 | -135.61 | 1.4059 | +1.413 | 237 |
| BTCUSDT | horizon_wide_stop (3xATR) | 1.2211 | 2.2771 | -166.82 | 1.0422 | +0.105 | 237 |
| BTCUSDT | regime_flip (structural, NEW) | 1.3136 | 4.636 | -110.01 | 1.1693 | +0.406 | 237 |
| ETHUSDT | horizon_hold (fixed 2d, champion) | 1.0501 | 0.9082 | -174.97 | 1.047 | +0.226 | 227 |
| ETHUSDT | horizon_wide_stop (3xATR) | 1.1259 | 1.1521 | -191.21 | 1.2147 | +0.532 | 227 |
| ETHUSDT | regime_flip (structural, NEW) | 1.1575 | 2.1504 | -119.48 | 1.0961 | +0.242 | 227 |
| SOLUSDT | horizon_hold (fixed 2d, champion) | 1.3439 | 7.2321 | -112.99 | 1.3095 | +1.125 | 232 |
| SOLUSDT | horizon_wide_stop (3xATR) | 1.0926 | 0.8537 | -166.42 | 0.9683 | -0.076 | 232 |
| SOLUSDT | regime_flip (structural, NEW) | 1.1795 | 3.0465 | -84.45 | 1.0287 | +0.062 | 232 |

## BTCUSDT

### horizon_hold (fixed 2d, champion)

| window | n | L/S | pf | exp/trade | totalR | maxDD_R | MAR | win | +ve |
|---|---|---|---|---|---|---|---|---|---|
| full | 731 | 391/340 | 1.24 | +0.897 | +655.6 | -135.61 | 4.8346 | 0.5007 | YES |
| recent (>=2024-06) | 237 | 121/116 | 1.4059 | +1.413 | +334.9 | -103.83 | 3.2257 | 0.481 | YES |

per-year positive: 7/7  (robust_frac = 1.0)

ECON_BAR: `PF>=1.2 / exp>=0.05R / MAR>=0.5 / MaxDD<=30R@f=0.01 / robust>=0.60`

**DOES NOT CLEAR ECON_BAR** — PF 1.24 PASS | exp 0.897 PASS | MAR 4.8346 PASS | DD -135.61 FAIL | robust 1.0 PASS

### horizon_wide_stop (3xATR)

| window | n | L/S | pf | exp/trade | totalR | maxDD_R | MAR | win | +ve |
|---|---|---|---|---|---|---|---|---|---|
| full | 731 | 391/340 | 1.2211 | +0.520 | +379.9 | -166.82 | 2.2771 | 0.2791 | YES |
| recent (>=2024-06) | 237 | 121/116 | 1.0422 | +0.105 | +25.0 | -166.82 | 0.1498 | 0.2405 | YES |

per-year positive: 5/7  (robust_frac = 0.7143)

ECON_BAR: `PF>=1.2 / exp>=0.05R / MAR>=0.5 / MaxDD<=30R@f=0.01 / robust>=0.60`

**DOES NOT CLEAR ECON_BAR** — PF 1.2211 PASS | exp 0.52 PASS | MAR 2.2771 PASS | DD -166.82 FAIL | robust 0.7143 PASS

### regime_flip (structural, NEW)

| window | n | L/S | pf | exp/trade | totalR | maxDD_R | MAR | win | +ve |
|---|---|---|---|---|---|---|---|---|---|
| full | 731 | 391/340 | 1.3136 | +0.698 | +510.0 | -110.01 | 4.636 | 0.3297 | YES |
| recent (>=2024-06) | 237 | 121/116 | 1.1693 | +0.406 | +96.3 | -69.14 | 1.3932 | 0.2996 | YES |

per-year positive: 5/7  (robust_frac = 0.7143)

ECON_BAR: `PF>=1.2 / exp>=0.05R / MAR>=0.5 / MaxDD<=30R@f=0.01 / robust>=0.60`

**DOES NOT CLEAR ECON_BAR** — PF 1.3136 PASS | exp 0.698 PASS | MAR 4.636 PASS | DD -110.01 FAIL | robust 0.7143 PASS

## ETHUSDT

### horizon_hold (fixed 2d, champion)

| window | n | L/S | pf | exp/trade | totalR | maxDD_R | MAR | win | +ve |
|---|---|---|---|---|---|---|---|---|---|
| full | 741 | 394/347 | 1.0501 | +0.214 | +158.9 | -174.97 | 0.9082 | 0.475 | YES |
| recent (>=2024-06) | 227 | 109/118 | 1.047 | +0.226 | +51.3 | -174.97 | 0.2932 | 0.4493 | YES |

per-year positive: 4/7  (robust_frac = 0.5714)

ECON_BAR: `PF>=1.2 / exp>=0.05R / MAR>=0.5 / MaxDD<=30R@f=0.01 / robust>=0.60`

**DOES NOT CLEAR ECON_BAR** — PF 1.0501 FAIL | exp 0.214 PASS | MAR 0.9082 PASS | DD -174.97 FAIL | robust 0.5714 FAIL

### horizon_wide_stop (3xATR)

| window | n | L/S | pf | exp/trade | totalR | maxDD_R | MAR | win | +ve |
|---|---|---|---|---|---|---|---|---|---|
| full | 741 | 394/347 | 1.1259 | +0.297 | +220.3 | -191.21 | 1.1521 | 0.2591 | YES |
| recent (>=2024-06) | 227 | 109/118 | 1.2147 | +0.532 | +120.7 | -98.89 | 1.2202 | 0.2335 | YES |

per-year positive: 3/7  (robust_frac = 0.4286)

ECON_BAR: `PF>=1.2 / exp>=0.05R / MAR>=0.5 / MaxDD<=30R@f=0.01 / robust>=0.60`

**DOES NOT CLEAR ECON_BAR** — PF 1.1259 FAIL | exp 0.297 PASS | MAR 1.1521 PASS | DD -191.21 FAIL | robust 0.4286 FAIL

### regime_flip (structural, NEW)

| window | n | L/S | pf | exp/trade | totalR | maxDD_R | MAR | win | +ve |
|---|---|---|---|---|---|---|---|---|---|
| full | 741 | 394/347 | 1.1575 | +0.347 | +256.9 | -119.48 | 2.1504 | 0.3455 | YES |
| recent (>=2024-06) | 227 | 109/118 | 1.0961 | +0.242 | +54.8 | -113.3 | 0.4841 | 0.326 | YES |

per-year positive: 5/7  (robust_frac = 0.7143)

ECON_BAR: `PF>=1.2 / exp>=0.05R / MAR>=0.5 / MaxDD<=30R@f=0.01 / robust>=0.60`

**DOES NOT CLEAR ECON_BAR** — PF 1.1575 FAIL | exp 0.347 PASS | MAR 2.1504 PASS | DD -119.48 FAIL | robust 0.7143 PASS

## SOLUSDT

### horizon_hold (fixed 2d, champion)

| window | n | L/S | pf | exp/trade | totalR | maxDD_R | MAR | win | +ve |
|---|---|---|---|---|---|---|---|---|---|
| full | 669 | 332/337 | 1.3439 | +1.222 | +817.2 | -112.99 | 7.2321 | 0.5097 | YES |
| recent (>=2024-06) | 232 | 113/119 | 1.3095 | +1.125 | +261.0 | -99.5 | 2.623 | 0.5129 | YES |

per-year positive: 6/7  (robust_frac = 0.8571)

ECON_BAR: `PF>=1.2 / exp>=0.05R / MAR>=0.5 / MaxDD<=30R@f=0.01 / robust>=0.60`

**DOES NOT CLEAR ECON_BAR** — PF 1.3439 PASS | exp 1.222 PASS | MAR 7.2321 PASS | DD -112.99 FAIL | robust 0.8571 PASS

### horizon_wide_stop (3xATR)

| window | n | L/S | pf | exp/trade | totalR | maxDD_R | MAR | win | +ve |
|---|---|---|---|---|---|---|---|---|---|
| full | 669 | 332/337 | 1.0926 | +0.212 | +142.1 | -166.42 | 0.8537 | 0.2646 | YES |
| recent (>=2024-06) | 232 | 113/119 | 0.9683 | -0.076 | -17.6 | -134.34 | 0.1307 | 0.25 | no |

per-year positive: 3/7  (robust_frac = 0.4286)

ECON_BAR: `PF>=1.2 / exp>=0.05R / MAR>=0.5 / MaxDD<=30R@f=0.01 / robust>=0.60`

**DOES NOT CLEAR ECON_BAR** — PF 1.0926 FAIL | exp 0.212 PASS | MAR 0.8537 PASS | DD -166.42 FAIL | robust 0.4286 FAIL

### regime_flip (structural, NEW)

| window | n | L/S | pf | exp/trade | totalR | maxDD_R | MAR | win | +ve |
|---|---|---|---|---|---|---|---|---|---|
| full | 669 | 332/337 | 1.1795 | +0.385 | +257.3 | -84.45 | 3.0465 | 0.3453 | YES |
| recent (>=2024-06) | 232 | 113/119 | 1.0287 | +0.062 | +14.4 | -75.48 | 0.1913 | 0.3319 | YES |

per-year positive: 4/7  (robust_frac = 0.5714)

ECON_BAR: `PF>=1.2 / exp>=0.05R / MAR>=0.5 / MaxDD<=30R@f=0.01 / robust>=0.60`

**DOES NOT CLEAR ECON_BAR** — PF 1.1795 FAIL | exp 0.385 PASS | MAR 3.0465 PASS | DD -84.45 FAIL | robust 0.5714 FAIL

