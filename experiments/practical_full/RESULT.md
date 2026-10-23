# BTC Practical FULL Re-Evaluation

## Verdict: NEGATIVE

- asof: 2026-06-25T15:30:03.384522+00:00
- data_sha: 2h=8de450095ac5cf18, 4h=b3b004cb58258369
- gate: explore(wide) -> selection(+2x/3x cost) -> dual replication (validate AND sealed); DSR reported, NOT gated

| cell | tf | family | dsr | val_pf | val_exp | seal_pf | seal_exp | v_2x | v_3x | s_2x | s_3x | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 4h:donchian_break:n=100:atr_trail:atr_period=14,k_trail=2.0 | 4h | donchian_break | - | 1.407 | 0.370 | 0.639 | -0.331 | True | True | False | False | rejected |
| 4h:atr_channel_break:k=2.0:atr_trail:atr_period=14,k_trail=2.0 | 4h | atr_channel_break | - | 1.429 | 0.354 | 0.869 | -0.108 | True | True | False | False | rejected |
| 4h:vol_expansion:mult=3.0:atr_trail:atr_period=14,k_trail=2.0 | 4h | vol_expansion | - | 1.923 | 0.555 | 0.565 | -0.319 | True | True | False | False | rejected |

## Honest caveat

A NEGATIVE is the expected, valid outcome. Any accepted candidate is a single-asset BTC PAPER ONLY signal — it does NOT authorize live capital or automatic execution, must get its own frozen paper-forward protocol, and never inherits the live/Donchian slot. The frozen 4h Donchian Slice-3 strategy is untouched by this lane.
