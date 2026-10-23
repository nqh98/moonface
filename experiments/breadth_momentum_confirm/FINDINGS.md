# BTC Breadth Momentum Confirm (breadth_momentum on disjoint universes)

## Verdict: MECHANISM_UNCONFIRMED

- asof: 2026-06-28T14:12:30.204788+00:00
- data_sha: b3b004cb58258369
- bonferroni_alpha: 0.025
- block_len: 8
- discovery_xcheck_ok: True

| slice | status | val_exp | seal_exp | pooled_n | pooled_exp | boot_lo | p_le0 |
|---|---|---|---|---|---|---|---|
| [20, 40] | mechanism_unconfirmed | -0.023 | 0.011 | 528 | -0.005 | -0.217 | 0.5310 |
| [40, 60] | mechanism_unconfirmed | 0.125 | -0.004 | 554 | 0.058 | -0.134 | 0.2872 |

Paper-only, BTC futures only. Disjoint-slice confirmation cures the winner's-curse selection bias; the top-20 discovery is reported (x-check ok=True), never re-gated. The block bootstrap (block_len=8) keeps CIs honest under overlapping holds. mechanism_unconfirmed at thin-slice n is the expected underpowered outcome — resolution defers to forward time.
