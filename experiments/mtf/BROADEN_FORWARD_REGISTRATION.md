# MTF Broadened Best Cell — Forward Paper Registration (frozen)

The broadened 72-cell search (`BROADEN_FINDINGS.md`) re-ranked the lane's best
paper candidate to a structurally new cell: a 4h regime-QUALITY gate (skip the
chop) on the 15m RSI counter-trend entry, held 2 days with no stop. On the full
single path it beats the frozen headline on expectancy/MAR/robustness (positive in
all 7 years vs 6/7), is materially stronger in the recent OOS window on BTC and
SOL, and transfers in sign to ETH/SOL. This registers it for forward, out-of-
sample paper evaluation. It is **tracked in parallel with — NOT replacing —** the
frozen headline registration (`FORWARD_REGISTRATION.md`); both resolve honestly on
their own forward samples (no winner-version-bumping). Paper only; promotes
nothing to live. The 4h Donchian Slice-3 strategy is untouched.

- **asof:** 2026-07-01
- **frozen cell (single source of truth):** `grid.broaden_best_cell()`
  = `4h:trend_strength|rsi_reversion|horizon_hold@2d`
- **symbol / base:** BTCUSDT, 15m base (every HTF is a closed-bar resample)

## The frozen signal (no refit, ever)

```
regime  (4h): trade only when |close − SMA(50)| ≥ 1·σ(50) on the 4h resample;
              side = +1 above the mean / −1 below; FLAT (no trade) in chop
trigger (15m): RSI(14) ≤ 30 -> dip ; RSI(14) >= 70 -> rip
entry        : take the trigger only on the 4h-regime-allowed side
exit         : hold 2 days (192 × 15m), NO stop (horizon_hold)
costs        : 0.1% round-trip (COST_FRACTION, already in single_trade_r)
sizing note  : no-stop paper carries large R-drawdown; deploy thinking is
               f ~ 0.0022 (so the in-sample −135.6R single-path DD ≈ 30% equity)
```

## Forward window & resolution

- **forward_start_ms:** 1_782_000_000_000 (end of the registration dataset). Only
  trades whose entry timestamp is >= this boundary count toward resolution.
- **minimum sample:** resolve at the FIRST point where forward trades n >= 40 AND
  >= 6 calendar months have elapsed (whichever is later). The 4h chop-skip gate
  yields ~110 trades/yr, so ~4-5 months reaches n=40.
- **live-faithful:** bias and trigger use only closed bars (point-in-time by
  construction); no look-ahead; costs applied. Re-run with `mtf_transfer.py`
  semantics (`trade_stream(candles, broaden_best_cell())` ->
  `period_stats(start_ms=forward_start)`).

### Gate (frozen)

| outcome | condition on the forward sample |
|---|---|
| **REAFFIRM** (re-ranked paper candidate stands) | PF >= 1.10 AND expectancy_r > 0 AND total_r > 0 AND both LONG and SHORT taken |
| **DOWNGRADE / CLOSE** | PF < 1.10 OR expectancy_r <= 0 OR total_r <= 0 |

Kill rule: a DOWNGRADE closes this lineage — no parameter rescue, no v2 on the
same data, and the lane reverts to the frozen headline as its best. A REAFFIRM
only earns continued paper tracking and a cross-asset transfer recheck; it does
NOT authorise live capital and does NOT override the fact that the cell fails the
DSR and drawdown-cap bars in-sample.

## In-sample reference (what forward is judged against)

Full 6.5y single path, BTC: n=731, PF 1.240, expectancy +0.897R, totalR +656,
single-path DD −135.6R, MAR 4.83, positive in all 7 years. Recent window
(entries >= 2024-06): n=237, PF 1.406, expectancy +1.413R, MAR 3.23 — stronger
than the recent headline. The forward sample should look like the recent window
if the regime-quality edge is real and not a 2024-25 / selection artifact.

## Caveat (load-bearing)

Selected as the single-path MAR leader (among PF >= headline cells) from a 72-cell
grid, so winner's-curse risk is real; the recent-OOS strength and ETH/SOL transfer
are the mitigations, but ETH is weak (recent MAR 0.29) and crypto majors share
beta (the breadth-neutral finding: this is crypto-beta timing, not market-neutral
alpha). The no-stop exit means a worse absolute tail than the headline's wide
stop. Underpowered (DSR 0.376) and wall-bound — a better-ranked paper candidate,
not a deployable edge.
