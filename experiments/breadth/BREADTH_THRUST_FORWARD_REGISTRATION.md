# Breadth-Thrust:6 — Forward Paper Registration (frozen 2026-06-27)

Pre-registers the forward paper test that resolves the
`OOS-POSITIVE IN SIGN, UNDERPOWERED` verdict of `REOPENED_OOS_2026-06-27.md`
into **CONFIRM (paper)** or **REFUTE** — using fresh out-of-time trades, NOT a
re-cut of the 6.5y path and NOT post-hoc tuning of any band/threshold. The
mechanism's only deficiency is statistical power (pooled OOS n = 23, expectancy
CI [−0.62, +1.12] straddles zero); thrust events are ~5/year, so the resolution
is to accumulate forward trades until the sample is large enough to separate the
+0.21R/trade OOS edge from zero. All criteria are frozen at this date.

## Signal under test (byte-identical to the frozen lane)
- `breadth_thrust` cell, axis (window) = 6, base_period = 50, low_band = 0.40,
  high_band = 0.60, h = 48, exit `atr_trail` {k_trail 2.0, max_bars 120,
  atr_period 14}, symmetric long/short.
- Breadth source: top-20 USDT-perp by 30d vol, min_history 365d, rebalance 30d,
  **BTC excluded**; signal trades **BTCUSDT 4h**.
- Source of truth: `moonface.research.breadth` (signals/grid/evaluate), unchanged.

## t0 and counting
- t0 = **1782300000000** (the sealed-window end / registration boundary).
- A **forward trade** is a closed `breadth_thrust:6` trade whose entry bar
  timestamp ≥ t0, evaluated on BTCUSDT 4h + the daily universe extended to the
  evaluation date.
- **Pooled OOS** = the 23 frozen validate+sealed trades (REOPENED_OOS) + all
  forward trades. State at registration: 23 pooled OOS trades, 0 forward trades.

## Frozen resolution rule
| Outcome | Pre-committed trigger |
|---|---|
| **CONFIRM (paper)** | pooled_n ≥ 30 AND practical bar holds (PF ≥ 1.15, exp > 0, \|maxDD\| ≤ 30R) AND pooled bootstrap 95% CI **lower bound > 0** (significant positive, 100k resamples, seed 7) AND forward-only expectancy > 0 (same sign as the OOS-to-date). |
| **REFUTE** | pooled_n ≥ 30 AND (pooled expectancy ≤ 0 OR forward-only PF < 1.0) — the OOS edge did not survive once powered. |
| **REFUTE — early kill** | pooled equity max drawdown breaches −30R at ANY evaluation → refute immediately, before reaching n = 30. |
| **Stay INCONCLUSIVE** | none of the above — keep accumulating; re-evaluate on each fresh data pull. |

No threshold may be changed after this date. CONFIRM means the breadth-internal
axis produces a real OOS edge **on paper** — it clears the research bar only;
going live remains a separate human-only decision.

## Evaluate (read-only, committed code)
Extend the window end to the current date and re-run the REOPENED_OOS reproduce
block; the pooled-OOS metrics and bootstrap CI are the resolution inputs. Count
forward trades as entries with timestamp ≥ t0.

## Honest caveats
- Single-asset BTC, paper-only. CONFIRM ≠ live.
- Thrust events fire ~5/year; reaching ≥ 7 fresh forward trades (to pass pooled
  n = 30) will likely take well beyond a year. Continued INCONCLUSIVE with an
  accumulating sample is the expected near-term state, not a failure. The
  −30R early-kill guards against a slow bleed during accumulation.
- Requires a daily universe cache covering the full window on each evaluation
  (stale-`uni1d_*.csv` gotcha; `universe_covers_train` guards it).

## Out of scope
- No scheduler/daemon, no live watch-loop wiring, no new gate/engine code, no
  threshold changes. The frozen lane gate, EXIT_REGISTRY, and DSR calibration are
  untouched.
