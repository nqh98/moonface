# OI-build mechanism study — pooled cross-asset verdict

- generated: 2026-06-12T07:29:35.397922+00:00
- **verdict: mechanism_does_not_exist** — equal-weight pooled mean directional return is non-positive (-0.006373) on fresh assets
- evaluable assets: 16 (skipped for coverage: 1)
- co-primary: sign test p = 0.5981903076171875, Stouffer Z = -1.0240920214752438, pooled mean = -0.006373412315166312

## Per-asset (confirmation set, primary endpoint h=24 bars, gross)

| asset | events | mean directional ret | t |
|---|---|---|---|
| 1000PEPEUSDT | 63 | 0.002165 | 0.11 |
| PEOPLEUSDT | 52 | -0.028509 | -1.42 |
| DOGEUSDT | 59 | -0.006760 | -0.50 |
| BNBUSDT | 64 | 0.008305 | 1.39 |
| 1000SHIBUSDT | 63 | -0.002323 | -0.22 |
| 1000FLOKIUSDT | 63 | -0.009669 | -0.67 |
| XRPUSDT | 56 | 0.012999 | 0.73 |
| LINKUSDT | 62 | 0.002190 | 0.19 |
| HIGHUSDT | 61 | -0.059834 | -1.75 |
| NEARUSDT | 59 | -0.014603 | -0.86 |
| JASMYUSDT | 66 | -0.004410 | -0.28 |
| TRBUSDT | 48 | 0.013524 | 0.68 |
| FILUSDT | 58 | 0.000673 | 0.05 |
| ARBUSDT | 58 | 0.003407 | 0.23 |
| AVAXUSDT | 68 | 0.002292 | 0.23 |
| ETCUSDT | 62 | -0.021422 | -2.01 |

## Pre-registered descriptive analyses

```json
{
  "h_6": {
    "m": 16,
    "k": 9,
    "p_sign": 0.4018096923828125,
    "z": -0.07377455304325503,
    "pooled_mean": 0.00037354691759272375
  },
  "h_48": {
    "m": 16,
    "k": 5,
    "p_sign": 0.9615936279296875,
    "z": -2.4699254376343767,
    "pooled_mean": -0.016448267319908276
  },
  "lookback_24": {
    "m": 16,
    "k": 7,
    "p_sign": 0.7727508544921875,
    "z": -0.7665996282914767,
    "pooled_mean": -0.004534861763151088
  },
  "net_of_cost": {
    "m": 16,
    "k": 7,
    "p_sign": 0.7727508544921875,
    "z": -1.3185926550181173,
    "pooled_mean": -0.007373412315166312
  },
  "liquidity_upper_half": {
    "m": 8,
    "k": 4,
    "p_sign": 0.63671875,
    "z": -0.13436877950637968,
    "pooled_mean": -0.002700228121622318
  },
  "liquidity_lower_half": {
    "m": 8,
    "k": 4,
    "p_sign": 0.63671875,
    "z": -1.313916046381989,
    "pooled_mean": -0.010046596508710304
  },
  "leave_one_out_pooled_mean": {
    "min": -0.007699889568432936,
    "max": -0.002809370985318684
  },
  "time_first_half": {
    "m": 16,
    "k": 9,
    "p_sign": 0.4018096923828125,
    "z": -0.13467235667099298,
    "pooled_mean": -0.0007332923173086151
  },
  "time_second_half": {
    "m": 16,
    "k": 8,
    "p_sign": 0.5981903076171875,
    "z": -1.4039577421036389,
    "pooled_mean": -0.011139940464811251
  }
}
```

## Discovery set (BTC/ETH/SOL — contaminated, excluded from evidence)

```json
[
  {
    "sym": "BTCUSDT",
    "n": 69,
    "mean": 0.004404961642622311,
    "t": 0.7826626893730555
  },
  {
    "sym": "ETHUSDT",
    "n": 68,
    "mean": -0.006580296391832828,
    "t": -0.6636223518246495
  },
  {
    "sym": "SOLUSDT",
    "n": 71,
    "mean": 0.01727749558305021,
    "t": 1.7901398049707413
  }
]
```
