# BTC Breadth Internal Lane 2 (high-frequency, block-bootstrap)

## Verdict: FORWARD_CANDIDATE

- asof: 2026-06-28T09:43:18.942100+00:00  block_len: 8
- overlap_xcheck_ok: True  block_xcheck_ok: True
- bonferroni_alpha: 0.016666666666666666

| signal | val_exp | seal_exp | pooled_n | pooled_exp | boot_lo | p_le0 | verdict |
|---|---|---|---|---|---|---|---|
| breadth_oscillator | -0.037 | -0.176 | 449 | -0.106 | -0.364 | 0.7953 | negative |
| breadth_momentum | 0.165 | 0.142 | 653 | 0.154 | -0.070 | 0.0743 | forward_candidate |
| breadth_accel | -0.026 | 0.040 | 832 | 0.006 | -0.197 | 0.4831 | negative |

Paper-only, BTC futures only. Overlapping trades inflate n but not the effective sample; the block bootstrap keeps CIs honest.
