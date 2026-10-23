# New-data readiness verdict

- status: ready
- provider: ExampleVendor
- data class: aggressor_trades

No signal tests, return tests, or strategy backtests were run.

## Gate Failures
- none

## Checks

```json
{
  "symbols": [
    "BTCUSDT"
  ],
  "history_days": 365,
  "cadence_ms": 1000,
  "coverage_ratio": 0.98,
  "monotonic_timestamps": true,
  "duplicate_timestamp_ratio": 0.002,
  "fields": [
    "price",
    "side",
    "size",
    "symbol",
    "ts_ms"
  ]
}
```
