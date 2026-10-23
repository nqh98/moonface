# funding_fade_voltarget v1 — verdict

- **Status:** CLOSED_NEGATIVE
- **Domain:** funding_fade_voltarget (vol/risk-targeted sizing vs fixed-fractional)
- **Construction:** funding_fade {'window': 60, 'z_thr': 1.5} + fixed_bracket {'atr_period': 14, 'k_stop': 2.0, 'm_tp': 4.0}
- **Promotion requires BOTH assets to clear stages 1-4 and dominate the control on MAR & Sharpe at holdout, WF aggregate, and lockbox tail.

| asset | final stage | screen n | holdout trt MAR | WF folds | DSR | tail trt MAR |
|---|---|---:|---:|---:|---:|---:|
| ETH/USDT:USDT | rejected_stage1 | 330 | 1.906 | - | - | - |
| SOL/USDT:USDT | rejected_stage2 | 281 | -0.267 | - | - | - |

Closed by the pre-committed kill rule if negative: no v2, no fraction grid, no budget relaxation. The vol/risk-targeting lever is terminal for funding_fade + fixed_bracket on a closed-negative verdict.### RUN_LOG ###

- Run: `python tools/research.py voltarget` on full backfilled ETH/SOL perp history (2020-01-01 → run date).
- First run returned 0 trades (closed_negative) due to a partial perp-history cache (`*_USDT:USDT_4h.csv` held only ~600 recent candles; fetch_history forward-appends only and never backfills the tail). After removing the partial caches so the network path paginated the full 2020+ history, the run produced real trade counts (ETH 330 / SOL 281 screen trades) and the verdict above.
- Lockbox tail was NEVER spent (both assets rejected before stage 4); pristine.
