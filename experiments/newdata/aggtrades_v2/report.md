# Aggressor Trades Rung-0 Non-Lockbox Report (v2)

- status: killed
- provider/data class: Binance Vision futures um daily aggTrades (per-second side counts)
- universe: BTCUSDT perpetual
- feature: excitation asymmetry (lag-1 autocorrelation of per-second buy prints minus sell prints, 6h trailing window)
- bucket: 5 minutes
- horizon: next 5-minute bucket
- lockbox_touched: false

No strategy backtest was run.
No sealed lockbox evaluation was run.
This is not a trading result.

## Gate Failures
- median fold Spearman IC must be > 0.015
- Newey-West t-statistic must be >= 2.0
- highest excitation-asymmetry bucket must beat lowest excitation-asymmetry bucket

## JSON Result

```json
{
  "status": "killed",
  "audit": {
    "status": "ready",
    "failures": [],
    "checks": {
      "symbols": [
        "BTCUSDT"
      ],
      "history_days": 180,
      "cadence_ms": 300000,
      "coverage_ratio": 1.0,
      "monotonic_timestamps": true,
      "duplicate_timestamp_ratio": 0.0,
      "fields": [
        "ts_ms",
        "symbol",
        "buy_count",
        "sell_count",
        "last_price"
      ]
    }
  },
  "bucket_count": 51768,
  "nonlockbox_bucket_count": 41414,
  "sealed_lockbox_bucket_count": 10354,
  "lockbox_touched": false,
  "verdict": {
    "status": "killed",
    "failures": [
      "median fold Spearman IC must be > 0.015",
      "Newey-West t-statistic must be >= 2.0",
      "highest excitation-asymmetry bucket must beat lowest excitation-asymmetry bucket"
    ],
    "score": {
      "fold_count": 6,
      "fold_spearman_ic": [
        -0.00950080696795373,
        0.000407023760987102,
        0.009347726176641417,
        0.018408022598804114,
        0.013318569272485668,
        -0.008194917237615071
      ],
      "positive_fold_count": 4,
      "median_spearman_ic": 0.00487737496881426,
      "newey_west_t": -0.012506243712515571,
      "monotonic_bucket_check": false,
      "trimmed_effect_positive": true,
      "lockbox_touched": false
    }
  }
}
```
