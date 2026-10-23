# Swing 4h Edge Search — FROZEN Pre-Registration

FROZEN pre-registration, committed before any run.
asof: 2026-06-19
data source: `fetch_perp_candles BTCUSDT 4h`, cache `.backtest_cache`

## Data bounds

| field | value |
|---|---|
| start_ms | 1718179200000 (2024-06-12T08:00Z) |
| end_ms | 1781251200000 (2026-06-12T08:00Z) |
| rows | 4380 |
| data_sha | 390b99ccdcefb4ee (cached at `.backtest_cache/BTCUSDT_4h.csv`) |

## Holdout split

- holdout_bars = 540 (~90 days)
- train+OOS = first 3840 bars (2024-06-12T08:00Z -> 2026-03-14T08:00Z)
- sealed holdout = last 540 bars (2026-03-14T08:00Z -> 2026-06-12T08:00Z)
- holdout opened only at stage 3

## Registered cell grid (4 cells, all is_retest=Y)

| label | family | params | exit | exit_params | h | test_bars | step_bars | is_retest |
|---|---|---|---|---|---|---|---|---|
| ma_cross_20_50 | ma_cross | {"fast": 20, "slow": 50} | atr_trail | {"atr_period": 14, "k_trail": 2.0, "max_bars": 24} | 12 | 540 | 540 | Y |
| donchian_break_n40 | donchian_break | {"n": 40, "long_only": true} | donchian_trail | {"atr_period": 14, "k_stop": 2.0, "trail_n": 20, "max_bars": 60} | 12 | 540 | 540 | Y |
| atr_channel_break_k1 | atr_channel_break | {"k": 1.0, "atr_period": 14} | atr_trail | {"atr_period": 14, "k_trail": 2.0, "max_bars": 24} | 12 | 540 | 540 | Y |
| reversion_in_range_30 | reversion_in_range | {"period": 30, "low": 0.15, "high": 0.85} | fixed_bracket | {"atr_period": 14, "k_stop": 2.0, "m_tp": 3.0} | 12 | 540 | 540 | Y |

### is_retest provenance (all cells re-test closed 4h ground)

- ma_cross_20_50: drift-screen closed (mechanism_does_not_exist)
- donchian_break_n40: deployable Slice-1/2 closed (robustness gate)
- atr_channel_break_k1: pathsig rung-0 curiosity (+24R/MAR 0.92, cap-clean)
- reversion_in_range_30: resrev closed (gross coin-flip, Z=-0.18)

## Frozen thresholds

- Z_FLOOR = 2.0 (stage 1: gross Stouffer Z on per-event forward R)
- DSR_FLOOR = 0.95 (stage 2: deflated Sharpe ratio)
- n_trials = TOTAL_CELLS = 9 (4 swing + 5 day; deflation denominator)
- ECON_BAR: PF >= 1.2 / expectancy >= 0.05R / MAR >= 0.5 / MaxDD <= 30R @ f=0.01 / robust_frac >= 0.60

## Kill rule

A cell failing any stage is CLOSED, not retried. Params are frozen per cell.
No per-window param search.
