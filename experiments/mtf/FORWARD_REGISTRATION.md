# MTF Headline Signal — Forward Paper Registration (frozen)

Registering the lane's best signal for forward, out-of-sample paper evaluation.
This is the honest resolution of an in-sample finding: the signal looked good on
2020–2026 history and stayed positive in the recent window, but it fails the
academic DSR gate and the fixed-f drawdown cap. Forward data — bars the signal
was never fitted on — is the only clean arbiter. Paper only; promotes nothing to
live. The frozen 4h Donchian Slice-3 strategy is untouched.

- **asof:** 2026-07-01
- **frozen cell (single source of truth):** `grid.headline_cell()`
  = `1d:price_vs_sma|rsi_reversion|horizon_wide_stop`
- **symbol / base:** BTCUSDT, 15m base (every HTF is a closed-bar resample)

## The frozen signal (no refit, ever)

```
regime  (1d) : long-only when daily close > SMA(50d), short-only when below
trigger (15m): RSI(14) <= 30 -> dip ; RSI(14) >= 70 -> rip
entry        : take the trigger only on the 1d-regime-allowed side
exit         : hold 2 days (192 x 15m) behind a 3xATR(14) wide stop
costs        : 0.1% round-trip (COST_FRACTION, already in single_trade_r)
sizing note  : paper carries large R-drawdown; deploy thinking is f ~ 0.002
               (so the in-sample -125R single-path DD maps to ~25% equity DD)
```

## Forward window & resolution

- **forward_start_ms:** 1_782_000_000_000 (end of the registration dataset). Only
  trades whose entry timestamp is >= this boundary count toward resolution.
- **minimum sample:** resolve at the FIRST point where forward trades n >= 40
  AND >= 6 calendar months have elapsed (whichever is later). RSI 30/70 on 15m
  with the 1d gate yields ~150 trades/yr, so ~3–4 months reaches n=40.
- **live-faithful:** bias and trigger use only closed bars (already point-in-time
  by construction); no look-ahead, costs applied. Re-run with `mtf_transfer.py`
  semantics (`attribute.trade_stream` + `period_stats(start_ms=forward_start)`).

### Gate (frozen)

| outcome | condition on the forward sample |
|---|---|
| **REAFFIRM** (paper-candidate stands) | PF >= 1.10 AND expectancy_r > 0 AND total_r > 0 AND both LONG and SHORT trades taken |
| **DOWNGRADE / CLOSE** | PF < 1.10 OR expectancy_r <= 0 OR total_r <= 0 |

Kill rule: a DOWNGRADE closes the lineage — no parameter rescue, no v2 on the
same data. A REAFFIRM only earns continued paper tracking and a cross-asset
transfer recheck; it does NOT authorise live capital.

## In-sample reference (what forward is judged against)

Headline cell, BTCUSDT, full 6.5y single-path: n=973, balanced 520L/453S,
PF ~1.25, expectancy ~+0.6R, MAR ~4.5, max single-path DD -125R. Recent
in-sample window (entries >= 2024-06): PF ~1.14, expectancy ~+0.36R, positive.
The forward sample should look like the recent window if the edge is real.
