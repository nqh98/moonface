# BTC Breadth Internal v2

## Verdict: FORWARD_CANDIDATE

- asof: 2026-06-28T07:27:44.741974+00:00
- data_sha: b3b004cb58258369
- bonferroni_alpha: 0.0125
- s1_xcheck_ok: True

| signal | val_exp | seal_exp | pooled_n | pooled_exp | boot_lo | p_le0 | verdict |
|---|---|---|---|---|---|---|---|
| breadth_thrust | 0.215 | 0.212 | 23 | 0.213 | -0.722 | 0.3253 | forward_candidate |
| net_new_highs | 0.532 | 0.259 | 66 | 0.400 | -0.187 | 0.0684 | forward_candidate |
| breadth_divergence | 0.581 | -0.652 | 51 | -0.096 | -0.567 | 0.6737 | negative |
| dispersion_regime | -0.235 | 0.272 | 40 | 0.069 | -0.611 | 0.4361 | negative |

Paper-only, BTC futures only. forward_candidate at n<30 is the expected underpowered outcome, not a failure.
