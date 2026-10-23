# Stage 1 Audit — BTCUSDT 4h

## A. Reconciliation (engine correctness)

- trades reconciled: 1209
- max abs R diff vs `simulate_trade`: 0.000000
- engine (`backtest/engine.py`) is **unchanged**; funding + trailing live only in the new sim.

## B. Cost-sensitivity sweep

| fee | slippage | expectancy_r | profit_factor | MAR |
|---|---|---|---|---|
| 0.0 | 0.0 | 0.3472 | 1.7466 | 8.9947 |
| 0.0 | 0.0003 | 0.3234 | 1.6741 | 8.0024 |
| 0.0 | 0.0005 | 0.3076 | 1.628 | 7.3887 |
| 0.0 | 0.001 | 0.2679 | 1.5199 | 5.9124 |
| 0.0002 | 0.0 | 0.3314 | 1.6978 | 8.3232 |
| 0.0002 | 0.0003 | 0.3076 | 1.628 | 7.389 |
| 0.0002 | 0.0005 | 0.2917 | 1.5835 | 6.8097 |
| 0.0002 | 0.001 | 0.2521 | 1.4796 | 5.3672 |
| 0.00045 | 0.0 | 0.3116 | 1.6394 | 7.5393 |
| 0.00045 | 0.0003 | 0.2878 | 1.5727 | 6.6535 |
| 0.00045 | 0.0005 | 0.2719 | 1.5303 | 6.0556 |
| 0.00045 | 0.001 | 0.2323 | 1.4314 | 4.6847 |
| 0.00075 | 0.0 | 0.2878 | 1.5727 | 6.6538 |
| 0.00075 | 0.0003 | 0.264 | 1.5098 | 5.7734 |
| 0.00075 | 0.0005 | 0.2482 | 1.4698 | 5.2372 |
| 0.00075 | 0.001 | 0.2086 | 1.3764 | 3.6792 |
| 0.001 | 0.0 | 0.268 | 1.5201 | 5.9136 |
| 0.001 | 0.0003 | 0.2442 | 1.4601 | 5.1094 |
| 0.001 | 0.0005 | 0.2284 | 1.422 | 4.4981 |
| 0.001 | 0.001 | 0.1888 | 1.3329 | 3.0154 |

## C. What was verified / fixed

- verified: engine R math matches independent re-derivation within 1e-6
- verified: funding charged as a separate, auditable term on held positions
- fixed: (none) — shared engine unchanged; funding/trailing added only in trend_sim.py
