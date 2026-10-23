# BTC Classic (from-scratch re-analysis)

## Verdict: FORWARD_CANDIDATE

- asof: 2026-06-28T19:18:05.938953+00:00
- data_sha: d3163358136570f1
- bonferroni_alpha: 0.008333333333333333

| signal | val_exp | seal_exp | pooled_n | pooled_exp | boot_lo | p_le0 | verdict |
|---|---|---|---|---|---|---|---|
| trend | 0.174 | 0.140 | 68 | 0.157 | -0.404 | 0.2703 | forward_candidate |
| breakout | 0.393 | -0.168 | 294 | 0.107 | -0.171 | 0.1866 | negative |
| momentum | 0.154 | -0.053 | 550 | 0.040 | -0.181 | 0.3392 | negative |
| channel | 0.201 | 0.003 | 250 | 0.104 | -0.213 | 0.2273 | forward_candidate |
| meanrev | -0.193 | -0.115 | 594 | -0.153 | -0.369 | 0.9499 | negative |
| funding_fade | 0.392 | -0.275 | 129 | 0.082 | -0.392 | 0.3540 | negative |

Paper-only, BTC futures only. forward_candidate at n<30 is the expected underpowered outcome, not a failure.
