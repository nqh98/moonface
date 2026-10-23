# MTF broaden_best cell — Equal-Weight Cross-Asset Basket

## Verdict: DOES NOT CLEAR ECON_BAR (thin edge, large drawdown)

- asof: 2026-06-30T19:40:31.933191+00:00
- data_sha: 8ac31ffcc0941cc9
- frozen cell: `4h:trend_strength|rsi_reversion|horizon_hold@2d` (broaden_best)
- construction: equal 0.250 risk weight per asset (4 assets), single faithful merged equity path
- assets: BTCUSDT, ETHUSDT, SOLUSDT, DOGEUSDT  (each gated by its OWN 1d trend)

## Single-asset books (full weight, for reference)

| book | n | L/S | pf | exp/trade | totalR | maxDD_R | MAR | positive |
|---|---|---|---|---|---|---|---|---|
| BTCUSDT | 731 | 391/340 | 1.24 | +0.897 | +655.6 | -135.61 | 4.8346 | YES |
| BTCUSDT recent | 237 | 121/116 | 1.4059 | +1.413 | +334.9 | -103.83 | 3.2257 | YES |
| ETHUSDT | 741 | 394/347 | 1.0501 | +0.214 | +158.9 | -174.97 | 0.9082 | YES |
| ETHUSDT recent | 227 | 109/118 | 1.047 | +0.226 | +51.3 | -174.97 | 0.2932 | YES |
| SOLUSDT | 669 | 332/337 | 1.3439 | +1.222 | +817.2 | -112.99 | 7.2321 | YES |
| SOLUSDT recent | 232 | 113/119 | 1.3095 | +1.125 | +261.0 | -99.5 | 2.623 | YES |
| DOGEUSDT | 643 | 295/348 | 1.1356 | +0.489 | +314.5 | -151.39 | 2.0772 | YES |
| DOGEUSDT recent | 233 | 100/133 | 1.1572 | +0.628 | +146.4 | -101.34 | 1.4443 | YES |

## Equal-weight basket (single faithful path)

| book | n | L/S | pf | exp/trade | totalR | maxDD_R | MAR | positive |
|---|---|---|---|---|---|---|---|---|
| BASKET full | 2784 | 1412/1372 | 1.1836 | +0.175 | +486.5 | -78.12 | 6.2281 | YES |
| BASKET recent | 929 | 443/486 | 1.2151 | +0.214 | +198.4 | -71.46 | 2.7764 | YES |

## Drawdown diversification

- perfect-correlation reference DD (weighted sum of individual): -143.74R
- realized merged-path DD: -78.12R
- **drawdown cut from de-correlation: 45.6%**

## Per-year robustness (merged path)

| year | n | pf | exp/trade | totalR | maxDD_R | positive |
|---|---|---|---|---|---|---|
| 2020 | 291 | 1.2002 | +0.183 | +53.2 | -54.33 | YES |
| 2021 | 465 | 1.197 | +0.172 | +79.9 | -48.64 | YES |
| 2022 | 448 | 1.0562 | +0.055 | +24.8 | -78.12 | YES |
| 2023 | 455 | 1.2822 | +0.260 | +118.4 | -66.53 | YES |
| 2024 | 475 | 1.2549 | +0.250 | +118.6 | -76.27 | YES |
| 2025 | 440 | 1.106 | +0.111 | +48.7 | -51.32 | YES |
| 2026 | 210 | 1.2234 | +0.204 | +42.8 | -44.28 | YES |

robust_frac = 1.0 (single-asset BTC reference: 0.553)

## ECON_BAR check (full basket)

`PF>=1.2 / exp>=0.05R / MAR>=0.5 / MaxDD<=30R@f=0.01 / robust>=0.60`

PF 1.1836 FAIL | exp 0.1748 PASS | MAR 6.2281 PASS | DD -78.12 FAIL | robust 1.0 PASS

## Honest reading

Equal-weight diversification de-correlates the loser-clustering that drives the single-asset wall, and lifts robustness above the 0.60 floor that the single-asset signal failed. But it does not thicken the edge: PF stays below 1.2 and the single-path drawdown still exceeds the 30R fixed-f cap (a sizing failure -- f~0.003 maps it to ~30% equity). The basket is a MORE ROBUST deployment of the same thin signal, not a deployable edge. Crypto majors share beta, so the assets are correlated confirmations, not independent ones (see the program's breadth-neutral finding). Paper only; promotes nothing to live.
