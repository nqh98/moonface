# BTC Long/Short Tournament

## Verdict: NEGATIVE

- asof: 2026-06-27T10:10:40.647467+00:00
- data_sha: 2h=8de450095ac5cf18, 4h=b3b004cb58258369
- gate: train practical bar + twin beat -> validate and sealed practical bar with same expectancy sign + twin beat on both

| cell | tf | long | short | train_r | train_twin | val_r | val_twin | seal_r | seal_twin | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| 4h:core_donchian_break:n=100:long=donchian_break(n=100):short=donchian_break(n=100):atr_trail:atr_period=14,k_trail=2.0,max_bars=120 | 4h | donchian_break | donchian_break | 74.517 | 63.568 | 10.739 | 6.373 | -10.600 | -6.352 | negative |

## Honest caveat

A negative outcome is expected and valid. Any accepted candidate is paper-only, BTC futures only, and does not authorize live capital or promotion.
