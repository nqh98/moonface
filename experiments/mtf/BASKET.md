# MTF Headline Signal — Equal-Weight Cross-Asset Basket

## Verdict: DOES NOT CLEAR ECON_BAR (thin edge, large drawdown)

- asof: 2026-06-30T19:06:21.586179+00:00
- data_sha: 544756e5130ebe12
- frozen cell: `1d:price_vs_sma|rsi_reversion|horizon_wide_stop`
- construction: equal 0.333 risk weight per asset (3 assets), single faithful merged equity path
- assets: BTCUSDT, ETHUSDT, SOLUSDT  (each gated by its OWN 1d trend)

## Single-asset books (full weight, for reference)

| book | n | L/S | pf | exp/trade | totalR | maxDD_R | MAR | positive |
|---|---|---|---|---|---|---|---|---|
| BTCUSDT | 973 | 520/453 | 1.2388 | +0.581 | +565.4 | -124.8 | 4.5305 | YES |
| BTCUSDT recent | 317 | 164/153 | 1.1401 | +0.357 | +113.2 | -113.65 | 0.9958 | YES |
| ETHUSDT | 966 | 512/454 | 1.0117 | +0.028 | +27.0 | -185.88 | 0.1452 | YES |
| ETHUSDT recent | 316 | 138/178 | 1.0826 | +0.205 | +64.6 | -89.31 | 0.7238 | YES |
| SOLUSDT | 874 | 439/435 | 1.1336 | +0.309 | +270.0 | -156.09 | 1.7296 | YES |
| SOLUSDT recent | 316 | 139/177 | 1.0946 | +0.225 | +71.0 | -79.75 | 0.8908 | YES |

## Equal-weight basket (single faithful path)

| book | n | L/S | pf | exp/trade | totalR | maxDD_R | MAR | positive |
|---|---|---|---|---|---|---|---|---|
| BASKET full | 2813 | 1471/1342 | 1.1286 | +0.102 | +287.5 | -107.11 | 2.6837 | YES |
| BASKET recent | 949 | 441/508 | 1.1063 | +0.087 | +83.0 | -70.32 | 1.1796 | YES |

## Drawdown diversification

- perfect-correlation reference DD (weighted sum of individual): -155.59R
- realized merged-path DD: -107.11R
- **drawdown cut from de-correlation: 31.2%**

## Per-year robustness (merged path)

| year | n | pf | exp/trade | totalR | maxDD_R | positive |
|---|---|---|---|---|---|---|
| 2020 | 287 | 1.0883 | +0.069 | +19.7 | -48.66 | YES |
| 2021 | 461 | 1.3372 | +0.251 | +115.5 | -31.45 | YES |
| 2022 | 469 | 0.9967 | -0.003 | -1.2 | -66.62 | no |
| 2023 | 458 | 1.3215 | +0.260 | +119.0 | -93.72 | YES |
| 2024 | 465 | 0.954 | -0.038 | -17.8 | -53.16 | no |
| 2025 | 459 | 1.1168 | +0.096 | +43.9 | -45.76 | YES |
| 2026 | 214 | 1.0484 | +0.039 | +8.4 | -70.32 | YES |

robust_frac = 0.7143 (single-asset BTC reference: 0.553)

## ECON_BAR check (full basket)

`PF>=1.2 / exp>=0.05R / MAR>=0.5 / MaxDD<=30R@f=0.01 / robust>=0.60`

PF 1.1286 FAIL | exp 0.1022 PASS | MAR 2.6837 PASS | DD -107.11 FAIL | robust 0.7143 PASS

## Honest reading

Equal-weight diversification de-correlates the loser-clustering that drives the single-asset wall, and lifts robustness above the 0.60 floor that the single-asset signal failed. But it does not thicken the edge: PF stays below 1.2 and the single-path drawdown still exceeds the 30R fixed-f cap (a sizing failure -- f~0.003 maps it to ~30% equity). The basket is a MORE ROBUST deployment of the same thin signal, not a deployable edge. Crypto majors share beta, so the assets are correlated confirmations, not independent ones (see the program's breadth-neutral finding). Paper only; promotes nothing to live.
