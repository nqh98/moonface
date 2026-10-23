# Liqrev liquidation-cascade reversion verdict

- generated: 2026-06-17T09:37:34.148199+00:00
- **verdict: inconclusive** - positive pooled effect misses the frozen Z or breadth gate
- evaluable assets: 16 (skipped: 0)
- co-primary: k_positive = 9, Stouffer Z = 0.9183259023217205, pooled mean = 0.0022891927252154916

## Per-asset (h=6 bars, net of cost)

| asset | events | mean net reversion | t |
|---|---|---|---|
| 1000PEPEUSDT | 52 | 0.005254 | 0.66 |
| PEOPLEUSDT | 44 | 0.015152 | 1.55 |
| DOGEUSDT | 44 | -0.002306 | -0.23 |
| BNBUSDT | 37 | -0.002035 | -0.35 |
| XRPUSDT | 47 | 0.005988 | 1.08 |
| 1000SHIBUSDT | 36 | 0.004410 | 0.35 |
| 1000FLOKIUSDT | 35 | -0.002172 | -0.20 |
| HIGHUSDT | 43 | -0.006367 | -0.86 |
| JASMYUSDT | 38 | 0.007136 | 0.61 |
| LINKUSDT | 44 | -0.001464 | -0.18 |
| FILUSDT | 41 | -0.016548 | -1.99 |
| UNIUSDT | 47 | -0.001216 | -0.16 |
| AVAXUSDT | 48 | 0.009000 | 1.05 |
| ARBUSDT | 32 | 0.005235 | 0.48 |
| NEARUSDT | 42 | 0.006962 | 0.69 |
| ETCUSDT | 49 | 0.009599 | 1.17 |

## Robustness

```json
{
  "time_first_half": {
    "m": 16,
    "k_positive": 11,
    "p_sign": 0.1050567626953125,
    "stouffer_z": 1.2768673657921363,
    "pooled_mean": 0.00424829505790364
  },
  "time_second_half": {
    "m": 16,
    "k_positive": 8,
    "p_sign": 0.5981903076171875,
    "stouffer_z": -0.2754927355399116,
    "pooled_mean": 0.0001173797456165325
  },
  "leave_one_out_pooled_mean": {
    "min": 0.0014316453068996995,
    "max": 0.0035450155943373956
  }
}
```
