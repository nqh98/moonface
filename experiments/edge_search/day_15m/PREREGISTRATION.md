# Day 15m Edge Search — FROZEN Pre-Registration

FROZEN pre-registration, committed before any run.
asof: 2026-06-19
data source: `fetch_perp_candles BTCUSDT 15m`, cache `.backtest_cache`
(backfilled by tools/backfill_15m.py in Task 9)

## Data bounds

| field | value |
|---|---|
| start_ms | 1749686400000 (2025-06-12T00:00Z) |
| end_ms | 1781222400000 (2026-06-12T00:00Z) |
| rows | ~35040 (backfilled; feasibility gate MIN_15M_ROWS=20000) |
| data_sha | TBD (recorded by Task 9 backfill output / RESULT.md after the run) |

## Holdout split

- holdout_bars = 2880 (~30 days)
- train+OOS = first ~32160 bars
- sealed holdout = last 2880 bars (~30 days)
- holdout opened only at stage 3

## Registered cell grid (5 cells, all is_retest=N)

| label | family | params | exit | exit_params | h | test_bars | step_bars | is_retest |
|---|---|---|---|---|---|---|---|---|
| ma_cross_20_50 | ma_cross | {"fast": 20, "slow": 50} | atr_trail | {"atr_period": 14, "k_trail": 2.0, "max_bars": 24} | 12 | 2880 | 2880 | N |
| donchian_break_n40 | donchian_break | {"n": 40, "long_only": true} | donchian_trail | {"atr_period": 14, "k_stop": 2.0, "trail_n": 20, "max_bars": 60} | 12 | 2880 | 2880 | N |
| atr_channel_break_k1 | atr_channel_break | {"k": 1.0, "atr_period": 14} | atr_trail | {"atr_period": 14, "k_trail": 2.0, "max_bars": 24} | 12 | 2880 | 2880 | N |
| reversion_in_range_30 | reversion_in_range | {"period": 30, "low": 0.15, "high": 0.85} | fixed_bracket | {"atr_period": 14, "k_stop": 2.0, "m_tp": 3.0} | 12 | 2880 | 2880 | N |
| seasonality_hour | seasonality | {"hours": [13, 14, 15], "trend_n": 50} | horizon_hold | {"atr_period": 14, "n_bars": 12} | 12 | 2880 | 2880 | N |

### is_retest provenance

All 5 cells are is_retest=N (fresh 15m ground, never tested before).
seasonality_hour is the only family not present on the 4h grid.

## Frozen thresholds

- Z_FLOOR = 2.0 (stage 1: gross Stouffer Z on per-event forward R)
- DSR_FLOOR = 0.95 (stage 2: deflated Sharpe ratio)
- n_trials = TOTAL_CELLS = 9 (4 swing + 5 day; deflation denominator)
- ECON_BAR: PF >= 1.2 / expectancy >= 0.05R / MAR >= 0.5 / MaxDD <= 30R @ f=0.01 / robust_frac >= 0.60

## Kill rule

A cell failing any stage is CLOSED, not retried. Params are frozen per cell.
No per-window param search.
