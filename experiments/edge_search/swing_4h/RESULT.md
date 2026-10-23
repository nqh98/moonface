# Price-Only Edge Search — BTC 4h

## Verdict: NEGATIVE

- asof: 2026-06-19T17:16:17.983949+00:00
- data_sha: 390b99ccdcefb4ee
- gate: Z_FLOOR=2.0 -> DSR_FLOOR=0.95 (n_trials=9) -> economic bar

| cell | retest | n | z | dsr | pf | mar | ddR | robust | verdict |
|---|---|---|---|---|---|---|---|---|---|
| ma_cross_20_50 | Y | 80 | 0.766 | - | - | - | - | - | negative |
| donchian_break_n40 | Y | 60 | 1.101 | - | - | - | - | - | negative |
| atr_channel_break_k1 | Y | 186 | 1.320 | - | - | - | - | - | negative |
| reversion_in_range_30 | Y | 177 | -1.330 | - | - | - | - | - | negative |

## Honest caveat

A NEGATIVE is the expected, valid outcome given the program's 58 closed domains; it is cheaper to learn here than with live capital. Single-asset BTC evidence — any EDGE is paper-only and needs cross-asset transfer confirmation before live consideration.
