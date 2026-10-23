# BTC-Specialized Signal Optimization — Slice 1 PREREGISTRATION (frozen)

- asof: 2026-06-21T13:37:51.880334+00:00
- timeframes (slice 1): 2h, 4h
- pooled n_trials (reported DSR): 684
- split: chronological Explore/Validate/Sealed 55/25/20 per timeframe
- TF max-hold bars: {'2h': [36, 84, 168], '4h': [30, 60, 120]}
- selection: parameter-island filter + top-3/family by net total R
- validation: walk-forward robust_frac>=0.6 on VALIDATE, then the single best (by validate net R) opened ONCE on SEALED under the locked econ bar (PF>=1.2/exp>=0.05R/MAR>=0.5/DD<=30R@f=0.01/robust>=0.60) + positive net R both segments + trade-count floor {'2h': 40, '4h': 30} + outlier(top-1/top-3) + +5bps cost-stress + recent-period
- accept: every gate on clean OOS -> PAPER ONLY (own forward protocol; never the Donchian slot; live disabled)
- DSR reported, NOT a gate; isolation: Donchian/promotion/journal untouched; EXIT_REGISTRY unchanged

## Per-timeframe data fingerprint

| timeframe | bars | data_sha |
|---|---|---|
| 2h | 28356 | 8de450095ac5cf18 |
| 4h | 14178 | b3b004cb58258369 |
