# Breadth-internal leads — cross-asset transfer confirmation (ETH/SOL)

## Verdict: MECHANISM_UNCONFIRMED

- asof: 2026-06-28T14:22:00.047399+00:00
- bonferroni_alpha: 0.0125
- anchor_ok (BTC discovery reproduced): True

| asset | lead | status | val_exp | seal_exp | pooled_n | pooled_exp | boot_lo | p_le0 |
|---|---|---|---|---|---|---|---|---|
| ETHUSDT | net_new_highs | transfers_unconfirmed | 0.631 | 0.307 | 66 | 0.474 | -0.126 | 0.0403 |
| ETHUSDT | breadth_momentum | transfers_unconfirmed | 0.162 | 0.224 | 653 | 0.193 | -0.060 | 0.0449 |
| SOLUSDT | net_new_highs | transfers_unconfirmed | 0.383 | 0.432 | 60 | 0.407 | -0.164 | 0.0594 |
| SOLUSDT | breadth_momentum | transfers_unconfirmed | 0.072 | 0.113 | 587 | 0.093 | -0.131 | 0.1840 |

Paper-only. Cross-asset transfer is an independent robustness axis (different traded leg, identical BTC-excluded breadth state). The BTC discovery is anchor-x-checked (ok=True), never re-gated. mechanism_unconfirmed is the pre-committed expected outcome given both leads already failed the disjoint-universe cure.
