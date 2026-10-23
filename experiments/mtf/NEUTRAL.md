# MTF broaden_best — BTC-Beta-Hedged (Market-Neutral) Falsification

## Verdict: DOES NOT SURVIVE BTC HEDGE — cross-asset edge is crypto beta

- asof: 2026-07-01T04:47:05.065938+00:00
- data_sha: 8ac31ffcc0941cc9
- frozen cell: `4h:trend_strength|rsi_reversion|horizon_hold@2d` (broaden_best)
- hedge asset: BTCUSDT (crypto-beta proxy); alts hedged, BTC carries raw
- beta: point-in-time trailing 90-day daily cov/var, unit-beta fallback
- assets: BTCUSDT, ETHUSDT, SOLUSDT, DOGEUSDT


## Per-leg: does the edge survive removing BTC beta?

| asset | mean beta | raw exp/trade | hedged exp/trade | beta contrib | raw exp recent | hedged exp recent | edge |
|---|---|---|---|---|---|---|---|
| BTCUSDT | - | +0.897 | +0.897 | - | +1.413 | +1.413 | kept |
| ETHUSDT | +1.114 | +0.214 | +0.226 | -0.012 | +0.226 | -0.268 | lost |
| SOLUSDT | +1.268 | +1.222 | +0.651 | +0.571 | +1.125 | -0.205 | lost |
| DOGEUSDT | +1.296 | +0.489 | +0.023 | +0.466 | +0.628 | -0.312 | lost |

`beta contrib` = raw − hedged expectancy (the crypto-beta share of the per-trade edge). `edge=lost` means the leg goes non-positive once beta is removed — the confirmation was market beta, not alpha.

## Basket books (equal-weight single faithful path)

| book | n | L/S | pf | exp/trade | totalR | maxDD_R | MAR | positive |
|---|---|---|---|---|---|---|---|---|
| BTCUSDT raw | 731 | 391/340 | 1.24 | +0.897 | +655.6 | -135.61 | 4.8346 | YES |
| BTCUSDT market (raw) | 731 | 391/340 | 1.24 | +0.897 | +655.6 | -135.61 | 4.8346 | YES |
| ETHUSDT raw | 741 | 394/347 | 1.0501 | +0.214 | +158.9 | -174.97 | 0.9082 | YES |
| ETHUSDT hedged | 741 | 394/347 | 1.1022 | +0.226 | +167.7 | -113.77 | 1.4737 | YES |
| SOLUSDT raw | 669 | 332/337 | 1.3439 | +1.222 | +817.2 | -112.99 | 7.2321 | YES |
| SOLUSDT hedged | 669 | 332/337 | 1.2545 | +0.651 | +435.3 | -114.68 | 3.7955 | YES |
| DOGEUSDT raw | 643 | 295/348 | 1.1356 | +0.489 | +314.5 | -151.39 | 2.0772 | YES |
| DOGEUSDT hedged | 643 | 295/348 | 1.0088 | +0.023 | +14.9 | -210.25 | 0.0709 | YES |
| RAW basket full | 2784 | 1412/1372 | 1.1836 | +0.175 | +486.5 | -78.12 | 6.2281 | YES |
| RAW basket recent | 929 | 443/486 | 1.2151 | +0.214 | +198.4 | -71.46 | 2.7764 | YES |
| HEDGED basket full | 2784 | 1412/1372 | 1.1637 | +0.114 | +318.4 | -87.18 | 3.6518 | YES |
| HEDGED basket recent | 929 | 443/486 | 1.0595 | +0.041 | +38.4 | -87.18 | 0.4407 | YES |
| MKT-NEUTRAL alts full | 2053 | 1021/1032 | 1.1224 | +0.100 | +205.9 | -116.78 | 1.7635 | YES |
| MKT-NEUTRAL alts recent | 692 | 322/370 | 0.8968 | -0.087 | -60.4 | -116.78 | 0.5173 | no |

- hedged basket robust_frac: 0.8571  |  market-neutral alt robust_frac: 0.7143
- hedged-basket DD de-correlation cut: 39.3% (merged -87.18R vs ref -143.57R)

## Honest reading

The MTF basket's ETH/SOL/DOGE legs 'confirm' the BTC signal, but crypto majors share beta. This test removes the BTC-beta component of each non-BTC trade's PnL over its actual holding window (point-in-time beta, no look-ahead; beta=0 reproduces raw exactly). If the market-neutral alt book keeps a positive edge, the cross-asset transfer is genuine beta-residual alpha. If it collapses or flips sign, the transfer was crypto-beta timing — the same outcome the breadth cross-asset leads met (`breadth_neutral`): a real crypto-beta timing overlay, NOT market-neutral alpha. BTC's own directional edge is untouched (un-hedgeable against itself). Paper only; promotes nothing to live.
