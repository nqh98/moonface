# BTC-Specialized Practical Signal Optimization — Slice 1 (2h, 4h)

## Verdict: NEGATIVE

- asof: 2026-06-22T02:20:11.062887+00:00
- data_sha: 1h=13ff327d94d966dd
- gate: explore(wide, net-R) -> top-K freeze -> walk-forward robust_frac>=0.60 -> single SEALED-tail full econ bar (DSR reported, not gated)

| cell | tf | family | dsr | val_robust | val_total_r | seal_pf | seal_exp | verdict |
|---|---|---|---|---|---|---|---|---|
| 1h:ma_cross:slow=96.0:chandelier:mb=96:atr_mult=4.0,atr_period=14 | 1h | ma_cross | - | 0.462 | 11.743 | - | - | rejected |
| 1h:ma_cross:slow=144.0:chandelier:mb=24:atr_mult=3.0,atr_period=14 | 1h | ma_cross | - | 0.615 | 18.334 | - | - | rejected |
| 1h:ma_cross:slow=144.0:donchian_trail:mb=24:atr_period=14,k_stop=2.0,trail_n=20 | 1h | ma_cross | - | 0.615 | 5.727 | - | - | rejected |
| 1h:trend_pullback:ma=48.0:chandelier:mb=96:atr_mult=4.0,atr_period=14:pull=1.0 | 1h | trend_pullback | - | 0.615 | 40.957 | 0.555 | -0.705 | rejected |
| 1h:trend_pullback:ma=48.0:atr_trail:mb=24:atr_period=14,k_trail=3.0:pull=1.0 | 1h | trend_pullback | - | 0.385 | -44.100 | - | - | rejected |
| 1h:trend_pullback:ma=144.0:chandelier:mb=48:atr_mult=4.0,atr_period=14:pull=1.5 | 1h | trend_pullback | - | 0.231 | -49.762 | - | - | rejected |
| 1h:vol_expansion:mult=3.0:fixed_bracket:atr_period=14,k_stop=1.0,m_tp=3.0:lb=24 | 1h | vol_expansion | - | 0.308 | -8.847 | - | - | rejected |
| 1h:vol_expansion:mult=3.0:fixed_bracket:atr_period=14,k_stop=1.0,m_tp=3.0:lb=48 | 1h | vol_expansion | - | 0.308 | -8.468 | - | - | rejected |
| 1h:vol_expansion:mult=3.0:fixed_bracket:atr_period=14,k_stop=1.0,m_tp=4.0:lb=24 | 1h | vol_expansion | - | 0.385 | -0.985 | - | - | rejected |

## Honest caveat

A NEGATIVE is the expected, valid outcome. Any accepted candidate is a single-asset BTC PAPER ONLY signal — it does NOT authorize live capital or automatic execution, must get its own frozen paper-forward protocol, and never inherits the live/Donchian slot. The frozen 4h Donchian Slice-3 strategy is untouched by this lane.
