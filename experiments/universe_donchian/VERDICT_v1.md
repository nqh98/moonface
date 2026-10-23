# universe_donchian v1 — verdict

- **Status:** CLOSED_NEGATIVE
- **Domain:** universe_donchian (frozen Donchian engine on a dynamic top-5 alt universe by abnormal 24h quote-volume expansion, vs a static broad-basket control)
- **Construction:** simulate_donchian(entry_n=40, trail_n=20 @ 4h, long_only=False) on universe_data alt perps; COST_FRACTION=0.001 round-trip + funding; top-5/30d-ratio screener default.
- **Promotion requires >=1 treatment spec to clear stages 1, 2, 3.5, DSR(>=0.95, n_trials=4), and 4 AND strictly dominate its static-basket control on portfolio MAR & Sharpe at holdout, WF aggregate, and lockbox tail.
- **BTC/USDT deployed reference (non-gating):** full MAR 0.420, tail MAR -0.895, tail DD -0.230.

| screener | final stage | screen n | holdout trt MAR | WF folds | DSR | tail trt MAR |
|---|---|---:|---:|---:|---:|---:|
| 5x30d-ratio | rejected_stage1 | 560 | -0.847 | - | - | - |
| 5x60d-ratio | rejected_stage1 | 590 | -0.859 | - | - | - |
| 10x30d-ratio | rejected_stage2 | 1200 | -0.918 | - | - | - |
| 5x30d-zscore | rejected_stage1 | 547 | -0.975 | - | - | - |

Closed by the pre-committed kill rule if negative: no v2 universe rule, no filter relaxation, no long-only flip, no exit change, no top-N re-tuning. The universe-expansion lever is terminal for the frozen Donchian engine on a closed-negative verdict.