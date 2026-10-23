# MTF broaden_best cell — Equal-Weight Cross-Asset Basket

## Verdict: DOES NOT CLEAR ECON_BAR (thin edge, large drawdown)

- asof: 2026-06-30T19:33:01.028131+00:00
- data_sha: 544756e5130ebe12
- frozen cell: `4h:trend_strength|rsi_reversion|horizon_hold@2d` (broaden_best)
- construction: equal 0.333 risk weight per asset (3 assets), single faithful merged equity path
- assets: BTCUSDT, ETHUSDT, SOLUSDT  (each gated by its OWN 1d trend)

## Single-asset books (full weight, for reference)

| book | n | L/S | pf | exp/trade | totalR | maxDD_R | MAR | positive |
|---|---|---|---|---|---|---|---|---|
| BTCUSDT | 731 | 391/340 | 1.24 | +0.897 | +655.6 | -135.61 | 4.8346 | YES |
| BTCUSDT recent | 237 | 121/116 | 1.4059 | +1.413 | +334.9 | -103.83 | 3.2257 | YES |
| ETHUSDT | 741 | 394/347 | 1.0501 | +0.214 | +158.9 | -174.97 | 0.9082 | YES |
| ETHUSDT recent | 227 | 109/118 | 1.047 | +0.226 | +51.3 | -174.97 | 0.2932 | YES |
| SOLUSDT | 669 | 332/337 | 1.3439 | +1.222 | +817.2 | -112.99 | 7.2321 | YES |
| SOLUSDT recent | 232 | 113/119 | 1.3095 | +1.125 | +261.0 | -99.5 | 2.623 | YES |

## Equal-weight basket (single faithful path)

| book | n | L/S | pf | exp/trade | totalR | maxDD_R | MAR | positive |
|---|---|---|---|---|---|---|---|---|
| BASKET full | 2141 | 1117/1024 | 1.1971 | +0.254 | +543.9 | -93.67 | 5.8065 | YES |
| BASKET recent | 696 | 343/353 | 1.2346 | +0.310 | +215.7 | -71.21 | 3.0297 | YES |

## Drawdown diversification

- perfect-correlation reference DD (weighted sum of individual): -141.18R
- realized merged-path DD: -93.67R
- **drawdown cut from de-correlation: 33.7%**

## Per-year robustness (merged path)

| year | n | pf | exp/trade | totalR | maxDD_R | positive |
|---|---|---|---|---|---|---|
| 2020 | 251 | 1.1408 | +0.182 | +45.7 | -72.44 | YES |
| 2021 | 358 | 1.2594 | +0.295 | +105.8 | -47.57 | YES |
| 2022 | 340 | 0.9641 | -0.049 | -16.7 | -93.67 | no |
| 2023 | 347 | 1.38 | +0.489 | +169.6 | -80.82 | YES |
| 2024 | 361 | 1.2652 | +0.358 | +129.2 | -70.94 | YES |
| 2025 | 328 | 1.1822 | +0.235 | +77.2 | -50.64 | YES |
| 2026 | 156 | 1.1606 | +0.213 | +33.2 | -57.44 | YES |

robust_frac = 0.8571 (single-asset BTC reference: 0.553)

## ECON_BAR check (full basket)

`PF>=1.2 / exp>=0.05R / MAR>=0.5 / MaxDD<=30R@f=0.01 / robust>=0.60`

PF 1.1971 FAIL | exp 0.254 PASS | MAR 5.8065 PASS | DD -93.67 FAIL | robust 0.8571 PASS

## Honest reading

Equal-weight diversification de-correlates the loser-clustering that drives the single-asset wall, and lifts robustness above the 0.60 floor that the single-asset signal failed. But it does not thicken the edge: PF stays below 1.2 and the single-path drawdown still exceeds the 30R fixed-f cap (a sizing failure -- f~0.003 maps it to ~30% equity). The basket is a MORE ROBUST deployment of the same thin signal, not a deployable edge. Crypto majors share beta, so the assets are correlated confirmations, not independent ones (see the program's breadth-neutral finding). Paper only; promotes nothing to live.
