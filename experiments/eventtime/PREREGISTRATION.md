# eventtime - is the drawdown wall a clock artifact? (H1) - PRE-REGISTRATION

Frozen 2026-07-06T05:17:25.684000+00:00 BEFORE any data read. Spec:
`docs/research-log/specs/2026-07-06-freedata-addendum-design.md` (H1).

**Not a new signal.** The program's one replicated finding - positive
fixed-horizon drift exists but no bounded-risk exit harvests it within budget -
was established entirely in clock time. H1 attacks the measurement basis:
dollar bars homogenize per-bar risk, so a per-bar-sized bracket may bound the
cascade tail the clock-ATR bracket could not.

## Frozen design

```json
{
  "symbol": "BTCUSDT",
  "exchange": "binanceusdm",
  "entry": {
    "family": "donchian_break",
    "params": {
      "n": 55
    }
  },
  "exit_rows": [
    [
      "horizon_hold",
      {
        "n_bars": 12,
        "atr_period": 14
      }
    ],
    [
      "horizon_hold",
      {
        "n_bars": 24,
        "atr_period": 14
      }
    ],
    [
      "horizon_hold",
      {
        "n_bars": 48,
        "atr_period": 14
      }
    ],
    [
      "atr_trail",
      {
        "k_trail": 2.0,
        "max_bars": 48,
        "atr_period": 14
      }
    ],
    [
      "atr_trail",
      {
        "k_trail": 3.0,
        "max_bars": 48,
        "atr_period": 14
      }
    ],
    [
      "horizon_wide_stop",
      {
        "n_bars": 24,
        "k_stop": 2.5,
        "atr_period": 14
      }
    ],
    [
      "horizon_wide_stop",
      {
        "n_bars": 24,
        "k_stop": 3.0,
        "atr_period": 14
      }
    ],
    [
      "breakeven_horizon",
      {
        "n_bars": 24,
        "k_stop": 3.0,
        "atr_period": 14
      }
    ],
    [
      "fixed_bracket",
      {
        "k_stop": 1.0,
        "m_tp": 4.0,
        "atr_period": 14
      }
    ],
    [
      "fixed_bracket",
      {
        "k_stop": 2.0,
        "m_tp": 4.0,
        "atr_period": 14
      }
    ]
  ],
  "calib_start_ms": 1577836800000,
  "calib_end_ms": 1672531200000,
  "test_start_ms": 1672531200000,
  "clock_timeframe": "4h",
  "bar_size_window_min": 240,
  "fence_fraction": 0.75,
  "fraction": 0.1,
  "grid_size": 10,
  "min_improve": 0.5,
  "kill_rule": "KILL unless (>=1 exit dollar-bar MaxDD/net-R ratio improves >=50% vs its clock twin, dollar net-R > 0) AND the dollar-bar ladder clears stage1->stage4",
  "test_end_ms": 1783315045684,
  "registered_utc": "2026-07-06T05:17:25.684000+00:00"
}
```

## Frozen entry x the frozen exit rows

Entry: `donchian_break` `{"n": 55}` (two-sided, no search).
Frozen exit rows (`EXIT_REGISTRY` snapshot):

- `horizon_hold` {'n_bars': 12, 'atr_period': 14}
- `horizon_hold` {'n_bars': 24, 'atr_period': 14}
- `horizon_hold` {'n_bars': 48, 'atr_period': 14}
- `atr_trail` {'k_trail': 2.0, 'max_bars': 48, 'atr_period': 14}
- `atr_trail` {'k_trail': 3.0, 'max_bars': 48, 'atr_period': 14}
- `horizon_wide_stop` {'n_bars': 24, 'k_stop': 2.5, 'atr_period': 14}
- `horizon_wide_stop` {'n_bars': 24, 'k_stop': 3.0, 'atr_period': 14}
- `breakeven_horizon` {'n_bars': 24, 'k_stop': 3.0, 'atr_period': 14}
- `fixed_bracket` {'k_stop': 1.0, 'm_tp': 4.0, 'atr_period': 14}
- `fixed_bracket` {'k_stop': 2.0, 'm_tp': 4.0, 'atr_period': 14}

## Both arms (same test window 1672531200000 -> 1783315045684)

- **Control (clock):** 4h fapi klines, recomputed fresh this run.
- **Treatment (event-time):** dollar bars at one procedurally-frozen size - the
  median trailing-4h dollar volume over the pre-2023 calibration window. No
  bar-size search.

## Verdict rule (frozen)

**KILL unless (>=1 exit dollar-bar MaxDD/net-R ratio improves >=50% vs its clock twin, dollar net-R > 0) AND the dollar-bar ladder clears stage1->stage4**

- ratio = abs(research MaxDD in R) / research net R; "improves >=50%" means
  dollar_ratio <= 0.5 * clock_ratio on the same exit row.
- Ladder = stage1 screen -> stage2 holdout -> stage3 DSR (>=0.95, grid_size 10)
  -> stage4 one-touch lockbox tail (last 25%).
- **KILL** => the wall is sampling-invariant; the entire time-sampling axis
  (dollar bars, volume bars, tick bars, imbalance bars) closes forever.
- **PASS is research-only** - event-time bars close at unpredictable clock
  times; promotion would need a separately registered event-driven executor.
