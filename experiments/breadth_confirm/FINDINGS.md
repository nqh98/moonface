# BTC Breadth Confirm (net_new_highs on disjoint universes)

## Verdict: MECHANISM_UNCONFIRMED

- asof: 2026-06-28T13:50:05.889399+00:00
- data_sha: b3b004cb58258369
- bonferroni_alpha: 0.025
- discovery_xcheck_ok: True

| slice | status | val_exp | seal_exp | pooled_n | pooled_exp | boot_lo | p_le0 |
|---|---|---|---|---|---|---|---|
| [20, 40] | mechanism_unconfirmed | 0.037 | 0.033 | 241 | 0.035 | -0.231 | 0.4055 |
| [40, 60] | mechanism_unconfirmed | -0.089 | -0.132 | 251 | -0.110 | -0.324 | 0.8424 |

Paper-only, BTC futures only. Disjoint-slice confirmation cures the winner's-curse selection bias; the top-20 discovery is reported (x-check ok=True), never re-gated. mechanism_unconfirmed at thin-slice n is the expected underpowered outcome — resolution defers to forward time.
