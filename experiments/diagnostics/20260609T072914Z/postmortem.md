# MoonFace Phase 2 Post-Mortem

- generated: 2026-06-09T07:29:14.635547+00:00
- setups analysed: 3602
- overall net R: -1380.1384

## Step 1 — MFE/MAE (entry vs exit)
- verdict: **mixed**
- losers: 2580, median loser MFE 0.5787R, share running >=1R 0.3019
- winner median MAE 0.4178R

## Step 2 — Gate ablation
| gate | kind | trades | net R | expectancy | Δnet R | Δexp | verdict |
|---|---|---|---|---|---|---|---|
| htf_bias | structural | 2204 | -868.6942 | -0.3941 | 511.4442 | -0.0106 | neutral |
| choch_displacement | structural | 564 | -160.1202 | -0.2839 | 1220.0182 | 0.0996 | value-adding |
| premium_discount | soft | 3599 | -1380.1384 | -0.3835 | 0.0 | 0.0 | neutral |
| poi_mitigation | soft | 1321 | -710.2551 | -0.5377 | 669.8833 | -0.1542 | edge-destroying |
| fib_zone | soft | 229 | -78.9953 | -0.345 | 1301.1431 | 0.0385 | value-adding |
| pinbar | soft | 169 | -36.3354 | -0.215 | 1343.803 | 0.1685 | value-adding |

## Step 3 — Segments (worst leaks / best edges)
- leak poi_type:OB: -1380.1384R over 3602 (win 0.2831)
- leak regime:trend: -1039.6437R over 2683 (win 0.2768)
- leak rr2:rr2_ge_3: -727.6043R over 1488 (win 0.197)
- leak market:bull: -706.0027R over 2029 (win 0.2944)
- leak side:BUY: -696.8029R over 1911 (win 0.2977)
- edge side_x_vol:BUY|high_vol: 17.4536R over 24 (win 0.5833)
- edge session:off_hours: -101.0746R over 417 (win 0.3077)
- edge weekday:2: -121.8287R over 569 (win 0.3111)
- edge weekday:4: -178.5112R over 553 (win 0.2935)
- edge weekday:1: -185.5576R over 490 (win 0.2761)

## Recommendation
**regime filter** — Segment 'side_x_vol:BUY|high_vol' earns 17.45R over 24 trades while the whole is -1380.14R.

