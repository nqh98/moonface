# BTC-Specialized Signal Optimization — Slice 3 PREREGISTRATION (frozen)

- asof: 2026-07-02T09:32:33.479112+00:00
- timeframes (slice 3): 15m, 30m
- pooled n_trials (reported DSR): 264
- split: chronological Explore/Validate/Sealed 55/25/20 per timeframe
- TF max-hold bars: {'15m': [24, 48, 96], '30m': [12, 24, 48], '1h': [24, 48, 96], '2h': [36, 84, 168], '4h': [30, 60, 120]}
- exits: per-family — TF-scaled trend exits (atr_trail/donchian_trail/chandelier, max hold 1d) for vol_compression_breakout; fixed_bracket (k_stop x m_tp) for the fade families (liquidity_sweep_reclaim, bb_revert). fixed_bracket keeps its frozen internal 96-bar safety cap (1d at 15m; 2d worst case at 30m, reached only when neither bracket leg fills)
- selection: parameter-island filter + top-3/family by net total R
- validation: walk-forward robust_frac>=0.6 on VALIDATE, then the single best (by validate net R) opened ONCE on SEALED under the locked econ bar (PF>=1.2/exp>=0.05R/MAR>=0.5/DD<=30R@f=0.01/robust>=0.60) + positive net R both segments + trade-count floor {'15m': 100, '30m': 80, '1h': 60, '2h': 40, '4h': 30} + outlier(top-1/top-3) + +15bps cost-stress + recent-period
- accept: every gate on clean OOS -> PAPER ONLY (own forward protocol; never the Donchian slot; live disabled)
- DSR reported, NOT a gate; isolation: Donchian/promotion/journal untouched; EXIT_REGISTRY unchanged

## Per-timeframe data fingerprint

| timeframe | bars | data_sha |
|---|---|---|
| 15m | 226848 | 9a0cac3893c6251f |
| 30m | 113424 | 8b91172ad369662d |
