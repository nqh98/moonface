# stack_path — stage-0 drawdown-aware drift screen

- **VERDICT: mechanism_does_not_exist**
- reason: drift gate not cleared (p=0.9616, Z=-0.84, pooled_ret_r=-0.0618)
- identity_hash: `b5c4f5fe9700cc657461832a0f245be59e2a2b4023444d2c8e76cab27d2d1bb2`
- registered: 2026-07-16T03:59:42.597176+00:00

## Frozen construction

- params: `{'lookback_bars': 20, 'penalty_factor': 1.0, 'stack_threshold': 1, 'slope_threshold': 0.01, 'long_only': False, 'atr_period': 14, 'k_stop': 2.0}`
- params provenance: **UNKNOWN — strategy + test arrived untracked**
- primary horizon h=24 (4h bars), atr_period=14, floor=0.1319
- universe: 16 fresh assets (discovery ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'] excluded)
- design inherited verbatim from `experiments/drift_screen/registration.json` (frozen 2026-06-16T02:25:37.286384+00:00)
- kill rule: mechanism_does_not_exist => stack_path closed at stage 0; no parameter rescue, no v2, no re-run

## Primary gate (binding)

- evaluable assets: 16 (min 8)
- total non-overlapping events: 2785
- assets with positive mean_ret_r: 5/16
- sign test p = 0.9616 (need <= 0.05)
- Stouffer Z = -0.8352 (need >= 1.645)
- pooled mean_ret_r = -0.0618
- pooled mean_abs_mae_r = 2.7880
- **path ratio = -0.0222** (floor 0.1319)

## Per-asset evidence

| asset | n | mean_ret_r | mean_abs_mae_r | mean_mfe_r | sign_rate | t |
|---|---|---|---|---|---|---|
| 1000FLOKIUSDT | 174 | -0.1762 | 2.7571 | 2.8730 | 0.4828 | -0.5855 |
| 1000PEPEUSDT | 175 | -0.0188 | 2.8296 | 3.0084 | 0.4686 | -0.0592 |
| 1000SHIBUSDT | 173 | -0.0944 | 2.7117 | 2.9892 | 0.4740 | -0.3696 |
| ARBUSDT | 174 | -0.2490 | 2.8547 | 2.9575 | 0.4828 | -0.8522 |
| AVAXUSDT | 173 | -0.0975 | 2.7841 | 3.0445 | 0.4913 | -0.3420 |
| BNBUSDT | 174 | 0.1232 | 2.6802 | 3.1791 | 0.5115 | 0.4443 |
| DOGEUSDT | 173 | -0.1240 | 2.9038 | 3.1863 | 0.4740 | -0.3838 |
| ETCUSDT | 174 | -0.0971 | 2.7418 | 2.9598 | 0.4598 | -0.3752 |
| FILUSDT | 174 | 0.1210 | 2.7401 | 2.9129 | 0.5057 | 0.4459 |
| HIGHUSDT | 175 | -0.1488 | 2.9863 | 3.1159 | 0.4743 | -0.4297 |
| JASMYUSDT | 174 | 0.1931 | 2.4903 | 3.0171 | 0.5172 | 0.7705 |
| LINKUSDT | 174 | 0.0128 | 2.8378 | 2.8942 | 0.4655 | 0.0481 |
| NEARUSDT | 174 | -0.2041 | 2.8255 | 2.8855 | 0.4885 | -0.7116 |
| PEOPLEUSDT | 175 | -0.2845 | 2.7964 | 2.8835 | 0.4057 | -1.1103 |
| TRBUSDT | 175 | -0.0446 | 2.8725 | 3.0861 | 0.4057 | -0.1551 |
| XRPUSDT | 174 | 0.1007 | 2.7965 | 3.3703 | 0.4138 | 0.3246 |

## Horizon curve (DESCRIPTIVE — not a gate)

| h | m | n | pooled_ret_r | pooled_abs_mae_r | ratio | p_sign | Z |
|---|---|---|---|---|---|---|---|
| 6 | 16 | 9835 | 0.0314 | 1.2750 | 0.0246 | 0.1051 | 1.4700 |
| 12 | 16 | 5362 | 0.0077 | 1.8693 | 0.0041 | 0.4018 | 0.2225 |
| 24 | 16 | 2785 | -0.0618 | 2.7880 | -0.0222 | 0.9616 | -0.8352 |
| 48 | 16 | 1412 | -0.2396 | 4.3777 | -0.0547 | 0.9616 | -1.6646 |
