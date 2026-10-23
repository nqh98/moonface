# BTC Breadth-Thrust Timing

## Verdict: NEGATIVE

| cell | val_R | val_exp | seal_R | seal_exp | econ | verdict |
|---|---|---|---|---|---|---|
| (no train survivors) | - | - | - | - | - | negative |

Paper-only. A negative outcome is expected and valid.

## Closest miss (train, in-sample — NOT a result)

Recorded for the lineage, per program convention. These are TRAIN-slice,
selection-biased numbers from `explore_leaderboard.json`; the sealed window was
never opened. No cell reached the DSR ≥ 0.95 gate, so `select` froze zero
candidates and the verdict above is NEGATIVE.

| cell (train) | n | total_R | exp_R | PF | maxDD_R | DSR |
|---|---|---|---|---|---|---|
| breadth_thrust:6 | 21 | 25.82 | 1.229 | 2.85 | -6.80 | **0.848** |
| breadth_thrust:12 | 23 | 24.51 | 1.066 | 2.61 | -8.10 | 0.805 |
| breadth_thrust:3 | 14 | 15.21 | 1.086 | 2.51 | -5.76 | 0.706 |
| pct_above_ma:50 | 37 | 26.31 | 0.711 | 2.01 | -8.79 | 0.621 |
| breadth_momentum:12 | 67 | 33.68 | 0.503 | 1.73 | -15.27 | 0.552 |

The `breadth_thrust` family is the standout: genuine in-sample edge (PF 2.5–2.85,
expectancy > 1R, tight drawdown), DSR up to 0.848 — among the stronger in-sample
signals the program has produced, but still short of the deflated 0.95 bar, and
never tested OOS. Per the kill rule the breadth/market-internal axis is closed:
no v2, no band/threshold rescue. The deflation gate did its job — it refused an
in-sample-only signal before the holdout was spent.

