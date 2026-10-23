# BTC Multi-Timeframe Trend Playbook — PREREGISTRATION (frozen)

- asof: 2026-06-22T08:04:16.172072+00:00
- timeframes: 4h regime / 2h confirm / 1h trigger
- n_trials (reported DSR, NOT gated): 12
- split: chronological Explore/Validate/Sealed 60/20/20 per timeframe
- selection gates: PF>=1.15, expectancy>0, |DD|<=30.0R@f=0.01, trades>=30, outlier-dependence, +5bps cost-stress, recent-period
- accept: dual replication on Validate AND Sealed (same thresholds + same expectancy sign); DSR reported, NOT a gate; output PAPER ONLY
- isolation: Donchian Slice-3 / promotion / journal untouched; EXIT_REGISTRY unchanged (lane adds no executable exit)

## Frozen configs

| label | exit |
|---|---|
| slope10:don20:atr_trail | atr_trail |
| slope10:don20:chandelier | chandelier |
| slope10:don20:donchian_trail | donchian_trail |
| slope10:don55:atr_trail | atr_trail |
| slope10:don55:chandelier | chandelier |
| slope10:don55:donchian_trail | donchian_trail |
| slope20:don20:atr_trail | atr_trail |
| slope20:don20:chandelier | chandelier |
| slope20:don20:donchian_trail | donchian_trail |
| slope20:don55:atr_trail | atr_trail |
| slope20:don55:chandelier | chandelier |
| slope20:don55:donchian_trail | donchian_trail |

## Per-timeframe data fingerprint

| timeframe | bars | data_sha |
|---|---|---|
| 1h | 56712 | 13ff327d94d966dd |
| 2h | 28356 | 8de450095ac5cf18 |
| 4h | 14178 | b3b004cb58258369 |
