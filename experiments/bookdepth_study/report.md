# Book-depth imbalance mechanism study — pooled cross-asset verdict

- generated: 2026-06-12T13:20:39.198692+00:00
- **verdict: inconclusive** — pooled mean positive (0.000024) but p=0.7728 / Z=0.24 miss the frozen criteria
- evaluable assets: 16 (skipped for coverage: 0)
- co-primary: sign test p = 0.7727508544921875, Stouffer Z = 0.24128997293712467, pooled mean = 2.3685105335414993e-05

## Per-asset (confirmation set, primary endpoint h=6 bars, gross)

| asset | events | mean directional ret | t |
|---|---|---|---|
| BTCUSDT | 1063 | 0.000411 | 1.06 |
| ETHUSDT | 1072 | 0.000391 | 0.72 |
| SOLUSDT | 1072 | 0.000627 | 0.93 |
| 1000PEPEUSDT | 1090 | -0.000004 | -0.00 |
| PEOPLEUSDT | 1206 | -0.000215 | -0.24 |
| DOGEUSDT | 1028 | -0.000102 | -0.13 |
| BNBUSDT | 1036 | -0.000096 | -0.21 |
| 1000SHIBUSDT | 1174 | -0.000267 | -0.41 |
| 1000FLOKIUSDT | 1074 | 0.000127 | 0.13 |
| XRPUSDT | 1059 | 0.000284 | 0.37 |
| LINKUSDT | 1193 | -0.001001 | -1.40 |
| HIGHUSDT | 1202 | -0.000490 | -0.37 |
| NEARUSDT | 1130 | 0.000987 | 1.23 |
| JASMYUSDT | 1112 | -0.000989 | -1.13 |
| TRBUSDT | 1104 | 0.001478 | 1.33 |
| FILUSDT | 1127 | -0.000762 | -0.93 |

## Pre-registered descriptive analyses

```json
{
  "h_1": {
    "m": 16,
    "k": 13,
    "p_sign": 0.0106353759765625,
    "z": 2.0728535947395925,
    "pooled_mean": 0.00012516259983695865
  },
  "h_24": {
    "m": 16,
    "k": 4,
    "p_sign": 0.9893646240234375,
    "z": -2.6727140869749597,
    "pooled_mean": -0.0017418145266402878
  },
  "net_of_cost": {
    "m": 16,
    "k": 1,
    "p_sign": 0.9999847412109375,
    "z": -5.226283965982034,
    "pooled_mean": -0.0009763148946645856
  },
  "liquidity_upper_half": {
    "m": 8,
    "k": 3,
    "p_sign": 0.85546875,
    "z": 0.609069920902512,
    "pooled_mean": 9.299884735101148e-05
  },
  "liquidity_lower_half": {
    "m": 8,
    "k": 4,
    "p_sign": 0.63671875,
    "z": -0.2678343687101932,
    "pooled_mean": -4.562863668018149e-05
  },
  "leave_one_out_pooled_mean": {
    "min": -7.329581208720928e-05,
    "max": 9.19783562856437e-05
  },
  "time_first_half": {
    "m": 16,
    "k": 0,
    "p_sign": 1.0,
    "z": 0.0,
    "pooled_mean": 0.0
  },
  "time_second_half": {
    "m": 16,
    "k": 0,
    "p_sign": 1.0,
    "z": 0.0,
    "pooled_mean": 0.0
  }
}
```

## Discovery set (BTC/ETH/SOL — contaminated, excluded from evidence)

```json
[]
```

## Correction (2026-06-12, post-verdict)

The time-stability rows in the descriptive JSON above are an artifact: the
time-halves code path hardcoded the OI change-momentum generator instead of
dispatching to the registered level-follow generator, producing zero events
(all-zero rows). The primary endpoint and verdict used the correct dispatched
path throughout (per-asset event counts above) and are unaffected. The
corrected, pre-registered time-halves descriptive (recomputed from the same
cached data with the fixed dispatch; `correction_time_halves.json`):

- **first half** (2024-06 → 2025-06): m=16, k=13 positive, pooled mean
  +0.000390, Z = 1.20
- **second half** (2025-06 → 2026-06): m=16, k=7 positive, pooled mean
  −0.000305, Z = −0.83

The faint h=6 effect was present in the first year and absent/inverted in
the second — decaying through time, consistent with the overall verdict.
