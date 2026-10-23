# Portfolio Tournament PREREGISTRATION (frozen)

- asof: 2026-06-25T09:18:59.787506+00:00
- window: 1577836800000..1782000000000
- timeframes: 1h, 4h
- n_trials (pooled): 8
- split: chronological Train-OOS / Validate / Sealed 60/20/20 per timeframe

## Components (frozen system_cells centers)

- 1h:roc_sign:period=24 family=roc_sign exit=atr_trail tf=1h h=24
- 1h:atr_channel_break:k=1.5 family=atr_channel_break exit=atr_trail tf=1h h=24
- 1h:trend_pullback:pull_atr=1.0 family=trend_pullback exit=atr_trail tf=1h h=24
- 1h:vol_expansion:mult=2.0 family=vol_expansion exit=atr_trail tf=1h h=24
- 1h:vol_regime:window=48 family=vol_regime exit=atr_trail tf=1h h=24
- 4h:ma_cross:slow=100 family=ma_cross exit=atr_trail tf=4h h=24
- 4h:donchian_break:n=55 family=donchian_break exit=atr_trail tf=4h h=24
- 4h:atr_channel_break:k=1.5 family=atr_channel_break exit=horizon_wide_stop tf=4h h=24
- 4h:vol_regime:window=48 family=vol_regime exit=horizon_wide_stop tf=4h h=24

## Operator grid (frozen)

- vote_2: vote {'k': 2}
- vote_majority: vote {'k': 'majority'}
- vol_target_vote_24: vol_target {'base': 'vote_majority', 'vol_lookback': 24, 'target_vol': 1.0}
- vol_target_vote_48: vol_target {'base': 'vote_majority', 'vol_lookback': 48, 'target_vol': 1.0}
- vol_target_lsn_24: vol_target {'base': 'long_short_net', 'vol_lookback': 24, 'target_vol': 1.0}
- vol_target_lsn_48: vol_target {'base': 'long_short_net', 'vol_lookback': 48, 'target_vol': 1.0}
- regime_switch: regime_switch {'floor': 0.1, 'lookback': 50}
- long_short_net: long_short_net {}

## Per-timeframe data fingerprint

| timeframe | bars | data_sha |
|---|---|---|
| 1h | pending | sha:1h:pending |
| 4h | pending | sha:4h:pending |
