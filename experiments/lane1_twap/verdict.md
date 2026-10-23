# lane1_twap (Track A) — verdict

- **Status:** CLOSED NEGATIVE
- **Lane:** Exchange Liquidation TWAP, Track A proxy pre-screen (BTC/USDT:USDT 1h, in-sample, gross, no lockbox).
- **Reason:** failed: floor, robust
- **treat_mean(R)@h=2:** 0.1023 vs **ctrl_mean:** 0.0860
- **null_max_effect_z:** 0.75 (must be < 3.0)

| condition | pass |
|---|---|
| sign_positive | PASS |
| floor | fail |
| robust | fail |
| treatment_gt_control | PASS |
| null_fails | PASS |

| k | h | n | mean_ret_r | effect_z |
|---:|---:|---:|---:|---:|
| 1.5 | 1 | 100 | 0.0386 | 0.38 |
| 1.5 | 2 | 98 | 0.1023 | 0.81 |
| 1.5 | 3 | 96 | -0.0003 | -0.00 |
| 1.5 | 4 | 96 | -0.0025 | -0.02 |
| 2.0 | 1 | 55 | 0.1078 | 1.03 |
| 2.0 | 2 | 55 | 0.1105 | 0.80 |
| 2.0 | 3 | 55 | 0.0577 | 0.44 |
| 2.0 | 4 | 55 | 0.0703 | 0.45 |

Kill rule (fired if CLOSED NEGATIVE): no grid expansion, no direction flip (continuation<->reversal is Setup 3), no proxy swap, no multi-asset, no Track B without a NEW pre-registration.
