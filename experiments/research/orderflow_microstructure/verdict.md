# orderflow_microstructure v1 — verdict

- **Status:** CLOSED_NEGATIVE
- **Domain:** orderflow_microstructure (intraday order-flow microstructure on BTC/USDT:USDT 15m vs donchian_break control)
- **Construction:** oi_flush_reversal / taker_flow_momentum / liquidity_sweep_reclaim + fixed_bracket{k_stop:2.0,m_tp:1.0,atr_period:14}.
- **Promotion requires >=1 treatment spec to clear stages 1, 2, 3.5, DSR(>=0.95, n_trials=10), and 4 AND strictly dominate its donchian_break control on MAR & Sharpe at holdout, WF aggregate, and lockbox tail.

| family | final stage | screen n | holdout trt MAR | WF folds | DSR | tail trt MAR |
|---|---|---:|---:|---:|---:|---:|
| oi_flush_reversal | rejected_stage1 | 5480 | -1.000 | - | - | - |
| taker_flow_momentum | rejected_stage1 | 4724 | -1.000 | - | - | - |
| oi_flush_reversal | rejected_stage1 | 2793 | -0.998 | - | - | - |
| taker_flow_momentum | rejected_stage1 | 2442 | -0.998 | - | - | - |
| oi_flush_reversal | rejected_stage1 | 4475 | -1.000 | - | - | - |
| taker_flow_momentum | rejected_stage1 | 4571 | -1.000 | - | - | - |
| oi_flush_reversal | rejected_stage1 | 2557 | -0.997 | - | - | - |
| taker_flow_momentum | rejected_stage1 | 2435 | -0.999 | - | - | - |
| liquidity_sweep_reclaim | rejected_stage1 | 5934 | -1.000 | - | - | - |
| liquidity_sweep_reclaim | rejected_stage1 | 3660 | -1.000 | - | - | - |

Closed by the pre-committed kill rule if negative: no v2, no added family, no gate/exit relaxation. The intraday-horizon + reversal-exit lever is terminal for these families on a closed-negative verdict.