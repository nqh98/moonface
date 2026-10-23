# Liqladder liquidation-ladder magnet verdict

- generated: 2026-07-02T16:31:49.886706+00:00
- **verdict: mechanism_does_not_exist** - net pooled mean continuation is non-positive
- evaluable assets: 16 (skipped: 0)
- co-primary: k_positive = 3, Stouffer Z = -1.9004349960975828, pooled mean = -0.0006388059072359321

## Per-asset (h=6 bars, net of cost)

| asset | events | mean net continuation | t |
|---|---|---|---|
| 1000PEPEUSDT | 842 | -0.000406 | -0.33 |
| BNBUSDT | 236 | -0.001472 | -1.12 |
| PEOPLEUSDT | 867 | 0.000418 | 0.31 |
| DOGEUSDT | 614 | -0.000791 | -0.60 |
| XRPUSDT | 480 | -0.001112 | -0.74 |
| HIGHUSDT | 821 | -0.001950 | -1.06 |
| 1000FLOKIUSDT | 845 | -0.000280 | -0.23 |
| AVAXUSDT | 626 | -0.000016 | -0.02 |
| 1000SHIBUSDT | 567 | -0.002643 | -2.17 |
| JASMYUSDT | 770 | -0.000771 | -0.61 |
| FILUSDT | 572 | -0.000305 | -0.20 |
| CRVUSDT | 913 | -0.000470 | -0.43 |
| INJUSDT | 889 | 0.000037 | 0.03 |
| ENSUSDT | 623 | 0.000296 | 0.22 |
| UNIUSDT | 693 | -0.000407 | -0.34 |
| FETUSDT | 983 | -0.000348 | -0.31 |

## Robustness

```json
{
  "time_first_half": {
    "m": 16,
    "k_positive": 4,
    "p_sign": 0.9893646240234375,
    "stouffer_z": -1.3658190951321096,
    "pooled_mean": -0.0006364769326707587
  },
  "time_second_half": {
    "m": 16,
    "k_positive": 6,
    "p_sign": 0.8949432373046875,
    "stouffer_z": -1.422533621887968,
    "pooled_mean": -0.0006755944178652146
  },
  "leave_one_out_pooled_mean": {
    "min": -0.0007092596008903287,
    "max": -0.0005051648131659863
  }
}
```
