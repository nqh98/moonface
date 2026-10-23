# MTF broaden_best — BTCUSDT standalone edge characterization

- asof: 2026-07-01T04:52:33.550227+00:00
- data_sha: 7b8ea8ba0826e1b0
- frozen cell: `4h:trend_strength|rsi_reversion|horizon_hold@2d` (broaden_best)
- the one signal that survived the BTC-beta hedge (see NEUTRAL.md)
- descriptive decomposition of the single faithful trade stream; no selection, no gate, no new cell

## Side attribution — long book vs short book

| book | n | L/S | pf | exp/trade | win_rate | totalR | maxDD_R | MAR | +ve |
|---|---|---|---|---|---|---|---|---|---|
| WHOLE full | 731 | 391/340 | 1.24 | +0.897 | 0.501 | +655.6 | -135.61 | 4.8346 | YES |
| LONG full | 391 | 391/0 | 1.5725 | +1.942 | 0.560 | +759.2 | -87.53 | 8.6739 | YES |
| SHORT full | 340 | 0/340 | 0.9263 | -0.305 | 0.432 | -103.6 | -260.94 | 0.3971 | no |
| WHOLE recent | 237 | 121/116 | 1.4059 | +1.413 | 0.481 | +334.9 | -103.83 | 3.2257 | YES |
| LONG recent | 121 | 121/0 | 1.4388 | +1.689 | 0.512 | +204.4 | -78.43 | 2.6059 | YES |
| SHORT recent | 116 | 0/116 | 1.3634 | +1.125 | 0.448 | +130.6 | -100.47 | 1.2994 | YES |

Long book = counter-trend dip-buys inside a 4h up-regime; short book = rip-sells inside a 4h down-regime. A balanced, both-sides-profitable split is what makes this a directional L/S edge rather than disguised long-only beta.

## Return distribution

- full:   win_rate 0.501 | avg_win +9.255R | avg_loss -7.484R | payoff 1.24 | skew +1.04 | kurt +9.85 | best +81.7R | worst -66.9R
- recent: win_rate 0.481 | avg_win +10.175R | avg_loss -6.708R | payoff 1.52 | skew +1.92 | kurt +12.47 | best +81.7R | worst -32.9R

## Outlier dependence (is the edge carried by a few trades?)

- full sample: n=731, total +655.6R; top 36 trades (top 5%) carry 39.0% of gross profit
- drop top 1 winner(s): expectancy +0.786R, total +573.9R (still positive)
- drop top 3 winner(s): expectancy +0.607R, total +441.6R (still positive)
- drop top 5 winner(s): expectancy +0.451R, total +327.4R (still positive)
- drop top 10 winner(s): expectancy +0.106R, total +76.7R (still positive)

- recent window: top 11 trades carry 36.1% of gross profit; drop-top-1 +; drop-top-3 +; drop-top-5 +; drop-top-10 NEG

## Adverse / favorable excursion (why the dip-buy needs room)

- median MAE -5.519R, median MFE 6.318R
- median MAE of WINNERS -2.726R vs LOSERS -9.612R

Winners that first run materially underwater (MAE << 0) before paying are the mechanism reason a tight stop destroys this edge and a 2-day hold is load-bearing (confirms the wide-stop and hold-curve findings).

## Per-year robustness

| year | n | pf | exp/trade | totalR | maxDD_R | positive |
|---|---|---|---|---|---|---|
| 2020 | 112 | 1.437 | +1.475 | +165.2 | -112.48 | YES |
| 2021 | 116 | 1.1158 | +0.410 | +47.6 | -119.71 | YES |
| 2022 | 105 | 1.0449 | +0.177 | +18.6 | -105.43 | YES |
| 2023 | 113 | 1.29 | +1.182 | +133.5 | -135.61 | YES |
| 2024 | 118 | 1.3721 | +1.493 | +176.2 | -128.11 | YES |
| 2025 | 115 | 1.0972 | +0.358 | +41.2 | -103.83 | YES |
| 2026 | 52 | 1.4312 | +1.409 | +73.2 | -64.13 | YES |

robust_frac = 1.0

## Honest reading

This is a descriptive x-ray of the one edge that survived beta-hedging, not a new result. It answers: does the edge come from both sides or one; is it broad or a handful of outliers; what is the win/payoff shape; and how much heat does a winning trade take. Read the outlier-dependence and the short-book columns hardest -- an edge that needs its short book AND survives dropping its top winners is the real, deployable-shape article; one that doesn't is beta or noise in disguise. Paper only.
