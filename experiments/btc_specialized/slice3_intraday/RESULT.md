# BTC-Specialized Practical Signal Optimization — Slice 1 (2h, 4h)

## Verdict: NEGATIVE

- asof: 2026-07-02T10:09:14.980548+00:00
- data_sha: 15m=9a0cac3893c6251f, 30m=8b91172ad369662d
- gate: explore(wide, net-R) -> top-K freeze -> walk-forward robust_frac>=0.60 -> single SEALED-tail full econ bar (DSR reported, not gated)

| cell | tf | family | dsr | val_robust | val_total_r | seal_pf | seal_exp | verdict |
|---|---|---|---|---|---|---|---|---|
| 15m:vol_compression_breakout:squeeze_n=64.0:donchian_trail:mb=48:atr_period=14,k_stop=2.0,trail_n=10 | 15m | vol_compression_breakout | - | 0.385 | -1.899 | - | - | rejected |
| 15m:vol_compression_breakout:squeeze_n=64.0:donchian_trail:mb=48:atr_period=14,k_stop=2.0,trail_n=20 | 15m | vol_compression_breakout | - | 0.462 | -0.149 | - | - | rejected |
| 15m:vol_compression_breakout:squeeze_n=64.0:donchian_trail:mb=96:atr_period=14,k_stop=2.0,trail_n=10 | 15m | vol_compression_breakout | - | 0.385 | -1.899 | - | - | rejected |

## Honest caveat

A NEGATIVE is the expected, valid outcome. Any accepted candidate is a single-asset BTC PAPER ONLY signal — it does NOT authorize live capital or automatic execution, must get its own frozen paper-forward protocol, and never inherits the live/Donchian slot. The frozen 4h Donchian Slice-3 strategy is untouched by this lane.
