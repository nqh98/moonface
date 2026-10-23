# MTF Headline Signal — Cross-Asset Transfer Test

## Verdict: TRANSFERS (sign holds + recent-positive on every non-BTC asset)

- asof: 2026-06-30T18:33:13.400380+00:00
- frozen cell: `1d:price_vs_sma|rsi_reversion|horizon_wide_stop`
- recent window: entries >= 1717200000000 (2024-06, out-of-sample)
- BTC = in-sample control; ETH/SOL = transfer targets

| asset | period | n | L/S | pf | exp/trade | totalR | maxDD_R | MAR | positive |
|---|---|---|---|---|---|---|---|---|---|
| BTCUSDT | full | 973 | 520/453 | 1.2388 | +0.581 | +565.4 | -124.8 | 4.5305 | YES |
| BTCUSDT | recent | 317 | 164/153 | 1.1401 | +0.357 | +113.2 | -113.65 | 0.9958 | YES |
| ETHUSDT | full | 966 | 512/454 | 1.0117 | +0.028 | +27.0 | -185.88 | 0.1452 | YES |
| ETHUSDT | recent | 316 | 138/178 | 1.0826 | +0.205 | +64.6 | -89.31 | 0.7238 | YES |
| SOLUSDT | full | 874 | 439/435 | 1.1336 | +0.309 | +270.0 | -156.09 | 1.7296 | YES |
| SOLUSDT | recent | 316 | 139/177 | 1.0946 | +0.225 | +71.0 | -79.75 | 0.8908 | YES |

## Caveat

Crypto majors share beta, so ETH/SOL are correlated confirmations, not independent ones. Each asset is gated by its OWN 1d trend, so this tests mechanism generalisation; a market-neutral claim would need a BTC hedge (see the program's breadth-neutral finding).
