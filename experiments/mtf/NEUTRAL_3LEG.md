# MTF broaden_best — BTC-Beta-Hedged (Market-Neutral) Falsification

## Verdict: DOES NOT SURVIVE BTC HEDGE — cross-asset edge is crypto beta

- asof: 2026-07-01T04:47:14.355205+00:00
- data_sha: 544756e5130ebe12
- frozen cell: `4h:trend_strength|rsi_reversion|horizon_hold@2d` (broaden_best)
- hedge asset: BTCUSDT (crypto-beta proxy); alts hedged, BTC carries raw
- beta: point-in-time trailing 90-day daily cov/var, unit-beta fallback
- assets: BTCUSDT, ETHUSDT, SOLUSDT


## Per-leg: does the edge survive removing BTC beta?

| asset | mean beta | raw exp/trade | hedged exp/trade | beta contrib | raw exp recent | hedged exp recent | edge |
|---|---|---|---|---|---|---|---|
| BTCUSDT | - | +0.897 | +0.897 | - | +1.413 | +1.413 | kept |
| ETHUSDT | +1.114 | +0.214 | +0.226 | -0.012 | +0.226 | -0.268 | lost |
| SOLUSDT | +1.268 | +1.222 | +0.651 | +0.571 | +1.125 | -0.205 | lost |

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
| RAW basket full | 2141 | 1117/1024 | 1.1971 | +0.254 | +543.9 | -93.67 | 5.8065 | YES |
| RAW basket recent | 696 | 343/353 | 1.2346 | +0.310 | +215.7 | -71.21 | 3.0297 | YES |
| HEDGED basket full | 2141 | 1117/1024 | 1.2069 | +0.196 | +419.5 | -54.68 | 7.6722 | YES |
| HEDGED basket recent | 696 | 343/353 | 1.1144 | +0.108 | +75.5 | -49.64 | 1.5209 | YES |
| MKT-NEUTRAL alts full | 1410 | 726/684 | 1.1799 | +0.214 | +301.5 | -82.67 | 3.6467 | YES |
| MKT-NEUTRAL alts recent | 459 | 222/237 | 0.9062 | -0.118 | -54.2 | -82.67 | 0.6558 | no |

- hedged basket robust_frac: 0.8571  |  market-neutral alt robust_frac: 0.7143
- hedged-basket DD de-correlation cut: 54.9% (merged -54.68R vs ref -121.35R)

## Honest reading

The MTF basket's ETH/SOL/DOGE legs 'confirm' the BTC signal, but crypto majors share beta. This test removes the BTC-beta component of each non-BTC trade's PnL over its actual holding window (point-in-time beta, no look-ahead; beta=0 reproduces raw exactly). If the market-neutral alt book keeps a positive edge, the cross-asset transfer is genuine beta-residual alpha. If it collapses or flips sign, the transfer was crypto-beta timing — the same outcome the breadth cross-asset leads met (`breadth_neutral`): a real crypto-beta timing overlay, NOT market-neutral alpha. BTC's own directional edge is untouched (un-hedgeable against itself). Paper only; promotes nothing to live.
