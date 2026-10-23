# MTF Regime-Quality LONG-ONLY — Forward Paper Registration (frozen)

The BTC-beta hedge (`NEUTRAL.md`) proved the cross-asset "confirmation" was crypto
beta, leaving BTC's own counter-trend signal as the one independent component. The
characterization (`CHARACTERIZE.md`, `LONG_ONLY.md`) then showed that signal's edge
is carried by its **long book** — counter-trend dip-buys inside a 4h up-regime — the
cleanest-shaped object the lane has produced: it clears 4 of 5 ECON gates (PF 1.57,
exp 1.94R, MAR 8.67, robust 0.857) versus the L/S basket's 3/5, with lower drawdown
than the L/S whole. This registers the long-only book for forward, out-of-sample
paper evaluation.

**This is a POST-HOC side filter** (chosen after seeing the short book lose on this
sample), so in-sample it is *selection, not discovery*. The forward window is the
only instrument that resolves that selection honestly. Tracked in parallel with —
NOT replacing — the L/S headline, broadened-best, and basket registrations; no
winner-version-bumping. Paper only; promotes nothing to live. The 4h Donchian
Slice-3 strategy is untouched.

- **asof:** 2026-07-01
- **frozen cell (single source of truth):** `grid.broaden_best_cell()`
  = `4h:trend_strength|rsi_reversion|horizon_hold@2d`, **LONG trades only**
- **symbol / base:** BTCUSDT, 15m base (every HTF is a closed-bar resample)

## The frozen signal (no refit, ever)

```
regime  (4h): trade only when |close − SMA(50)| ≥ 1·σ(50) on the 4h resample
trigger (15m): RSI(14) ≤ 30 -> dip
entry        : take the dip ONLY when the 4h regime side is +1 (up-regime); the
               short side of the same cell is DISCARDED (this registration)
exit         : hold 2 days (192 × 15m), NO stop (horizon_hold)
costs        : 0.1% round-trip (COST_FRACTION, already in single_trade_r)
sizing note  : no-stop paper carries large R-drawdown; deploy thinking is
               f ~ 0.0034 (so the in-sample −87.5R single-path DD ≈ 30% equity)
```

Reproduce: `trade_stream(candles, broaden_best_cell())` filtered to `side=="LONG"`,
then `period_stats(start_ms=forward_start)` (the exact path `tools/mtf_long_only.py`
runs).

## Forward window & resolution

- **forward_start_ms:** 1_782_000_000_000 (end of the registration dataset). Only
  trades whose entry timestamp is >= this boundary count toward resolution.
- **minimum sample:** resolve at the FIRST point where forward LONG trades n >= 40
  AND >= 6 calendar months have elapsed (whichever is later). The long book yields
  ~60 trades/yr, so ~8 months reaches n=40.
- **live-faithful:** bias and trigger use only closed bars (point-in-time by
  construction); no look-ahead; costs applied.

### Gate (frozen)

| outcome | condition on the forward LONG sample |
|---|---|
| **REAFFIRM** (long-only paper candidate stands) | PF >= 1.20 AND expectancy_r > 0 AND total_r > 0 |
| **DOWNGRADE / CLOSE** | PF < 1.20 OR expectancy_r <= 0 OR total_r <= 0 |

The bar is set at PF >= 1.20 (the ECON_BAR profit-factor floor the long book clears
in-sample at 1.57), stricter than the L/S registrations' 1.10, precisely because
this is a post-hoc selection and must show it was not curve-fit to the visible
sample. A DOWNGRADE closes this lineage — no parameter rescue, no v2 on the same
data. A REAFFIRM earns continued paper tracking only; it does NOT authorise live
capital and does NOT override the in-sample DSR / drawdown-cap failures.

## In-sample reference (what forward is judged against)

Full 6.5y single path, BTC LONG-only: n=391, PF 1.573, expectancy +1.942R,
totalR +759, single-path DD −87.5R, MAR 8.67, **positive in 6 of 7 years**
(robust_frac 0.857). Recent window (entries >= 2024-06): n=121, PF 1.439,
expectancy +1.689R, MAR 2.61. The forward sample should look like the recent
window if the long dip-buy timing is real.

## Caveats (load-bearing)

1. **Post-hoc selection.** The long side was isolated after observing the short
   book's full-history loss. Winner's-curse risk is real; the PF >= 1.20 forward
   bar and the multi-year in-sample breadth are the only mitigations.
2. **Not all-weather — carries partial long beta.** The long-only book was
   NEGATIVE in the severe 2022 bear (−33.6R while BTC fell −64%; the short book was
   that year's hero, which is why the L/S whole survived 2022). It WAS positive in
   the shallow down years 2025 (+68R vs BTC −6%) and 2026 (+16R vs BTC −27%) — real
   timing alpha in mild drawdowns, but a full-cycle bear overwhelms it. A live
   deployment inherits crypto-bear tail risk the L/S structure partly hedged.
3. **Still wall-bound.** Fails the 30R fixed-f drawdown cap (−87.5R) and the DSR
   bar in-sample; only conservative sizing (f ~ 0.0034) maps it under a 30% equity
   budget. A better-shaped paper candidate, NOT a deployable edge.

## ADDENDUM — WITHDRAWN, SUSPENDED UNRESOLVED (2026-07-03)

Administrative withdrawal by the human v2-only refocus mandate of 2026-07-03
(spec: docs/research-log/specs/2026-07-03-v2-only-refocus-design.md). This is
NOT a REAFFIRM and NOT a DOWNGRADE — the frozen resolution rule above was
never triggered.

- State at withdrawal: frozen 2026-07-01, 0 closed forward trades; all 39
  journal entries at df023c2… are WAIT.
- The forward clock is VOID as of this date. The strategy config and its
  styles manifest are archived verbatim under
  promotion/archive/2026-07-03-v2-refocus/mtf_long/ and are no longer loadable
  from any promotion path.
- Journal history is preserved untouched (journal/signals.jsonl, filtered by
  strategy_version df023c2…).
- Resuming this lineage requires a NEW registration with a fresh clock and
  fresh criteria; this document stays closed forever.
