# Macro event-window study verdict (FOMC/CPI event time, BTC)

- generated: 2026-07-03T02:42:58.201694+00:00
- **status: closed_negative** - no event window clears the frozen gate; family CLOSED (no window, event-set, or direction drift)
- winner: -
- candles: 39216 (BTCUSDT 1h)
- gate: net mean > 0, p_le0 < 0.0125, halves sign-consistent, n >= 20; cost 0.001 round trip per event

| cell | n | net mean | p(mean<=0) | 1st half | 2nd half | halves | clears |
|---|---:|---:|---:|---:|---:|---|---|
| fomc_pre24h | 36 | 0.003374 | 0.1913 | 0.008704 | -0.001956 | fail | fail |
| fomc_post24h | 36 | -0.007143 | 0.8724 | -0.004197 | -0.010089 | fail | fail |
| cpi_pre24h | 53 | 0.003704 | 0.1810 | 0.005520 | 0.001956 | PASS | fail |
| cpi_post24h | 53 | 0.003924 | 0.1730 | -0.002491 | 0.010101 | fail | fail |
