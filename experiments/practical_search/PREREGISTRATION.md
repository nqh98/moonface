# BTC Practical Signal Discovery — PREREGISTRATION (frozen)

- asof: 2026-06-21T07:17:44.198413+00:00
- timeframes (slice): 1h, 4h
- pooled n_trials (reported DSR): 72
- split: chronological Explore/Validate/Sealed 60/20/20 per timeframe
- TF max-hold bars: {'1h': [24, 48, 96], '4h': [30, 60, 120]}
- selection gates: PF>=1.15, expectancy>0, |DD|<=30.0R@f=0.01, trades>=30, parameter-island, outlier-dependence, +5bps cost-stress, recent-period
- accept: dual replication on Validate AND Sealed (same thresholds + same sign); DSR reported, NOT a gate; output PAPER ONLY
- isolation: Donchian Slice-3 / promotion / journal untouched; EXIT_REGISTRY unchanged

## Per-timeframe data fingerprint

| timeframe | bars | data_sha |
|---|---|---|
| 1h | 26304 | b8ce2d692e60cafc |
| 4h | 6576 | b7bf22be1d054cd0 |

## Frozen explore groups

| timeframe | family | exit | axis grid |
|---|---|---|---|
| 1h | reversion_in_range | mean_revert_reclaim | [10.0, 14.0, 21.0] |
| 1h | atr_channel_break | atr_trail | [1.0, 1.5, 2.0] |
| 4h | reversion_in_range | mean_revert_reclaim | [10.0, 14.0, 21.0] |
| 4h | atr_channel_break | atr_trail | [1.0, 1.5, 2.0] |
