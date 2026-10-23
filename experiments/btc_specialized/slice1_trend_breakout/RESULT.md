# BTC-Specialized Practical Signal Optimization — Slice 1 (2h, 4h)

## Verdict: NEGATIVE

- asof: 2026-06-21T13:58:58.097710+00:00
- data_sha: 2h=8de450095ac5cf18, 4h=b3b004cb58258369
- gate: explore(wide, net-R) -> top-K freeze -> walk-forward robust_frac>=0.60 -> single SEALED-tail full econ bar (DSR reported, not gated)

| cell | tf | family | dsr | val_robust | val_total_r | seal_pf | seal_exp | verdict |
|---|---|---|---|---|---|---|---|---|
| 2h:atr_channel_break:k=2.5:donchian_trail:mb=84:atr_period=14,k_stop=2.0,trail_n=20:ap=20 | 2h | atr_channel_break | - | 0.538 | 52.536 | - | - | rejected |
| 2h:atr_channel_break:k=2.5:donchian_trail:mb=168:atr_period=14,k_stop=2.0,trail_n=20:ap=20 | 2h | atr_channel_break | - | 0.538 | 42.716 | - | - | rejected |
| 2h:atr_channel_break:k=1.0:donchian_trail:mb=84:atr_period=14,k_stop=2.0,trail_n=20:ap=14 | 2h | atr_channel_break | - | 0.462 | 28.365 | - | - | rejected |
| 4h:donchian_break:n=20.0:chandelier:mb=120:atr_mult=4.0,atr_period=14 | 4h | donchian_break | - | 0.615 | 29.903 | - | - | rejected |
| 2h:donchian_break:n=40.0:donchian_trail:mb=84:atr_period=14,k_stop=2.0,trail_n=20 | 2h | donchian_break | - | 0.692 | 68.715 | 1.602 | 0.709 | rejected |
| 2h:donchian_break:n=55.0:donchian_trail:mb=84:atr_period=14,k_stop=2.0,trail_n=20 | 2h | donchian_break | - | 0.615 | 53.860 | - | - | rejected |
| 4h:ma_cross:slow=100.0:donchian_trail:mb=60:atr_period=14,k_stop=2.0,trail_n=20 | 4h | ma_cross | - | 0.385 | 15.154 | - | - | rejected |
| 2h:ma_cross:slow=50.0:chandelier:mb=84:atr_mult=4.0,atr_period=14 | 2h | ma_cross | - | 0.692 | 54.647 | - | - | rejected |
| 2h:ma_cross:slow=50.0:chandelier:mb=168:atr_mult=4.0,atr_period=14 | 2h | ma_cross | - | 0.692 | 56.955 | - | - | rejected |

## Honest caveat

A NEGATIVE is the expected, valid outcome. Any accepted candidate is a single-asset BTC PAPER ONLY signal — it does NOT authorize live capital or automatic execution, must get its own frozen paper-forward protocol, and never inherits the live/Donchian slot. The frozen 4h Donchian Slice-3 strategy is untouched by this lane.
