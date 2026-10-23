# Pre-registration: pooled cross-asset book-depth imbalance mechanism study

- **Registered:** 2026-06-12, frozen before any bookDepth archive data is
  downloaded. Recon consulted only file *sizes, dates, and one schema sample*
  (one day of BTCUSDT, 2026-06-01) — no historical analysis of any kind.
- **Information set:** Binance Vision UM `bookDepth` daily archive — order
  book depth snapshots every ~30s at fixed percentage bands, 863 symbols,
  history from 2023-01. This is the last unexplored free information set:
  `aggTrades`/`trades`/`bookTicker` are size-infeasible at universe scale
  (~300–630 GB for 16 assets × 2y) and their only cheap aggregate (kline
  taker-buy volume) is informationally adjacent to the falsified taker-flow
  family. Recorded here as the reason they are not studied.
- **Hypothesis (external prior, not derived from our data):** excess resting
  bid liquidity near the touch relative to ask liquidity predicts positive
  forward returns, and vice versa — the standard order-book imbalance result
  from the microstructure literature. Because the hypothesis does not come
  from any asset we tested, there is **no contaminated discovery set**;
  BTC/ETH/SOL participate as ordinary universe members.
- **Null hypothesis:** no edge; directional forward returns after imbalance
  extremes have mean ≤ 0.
- Mechanism science only: no exits, stops, sizing, or optimization.

## Frozen design

### Feature

Per snapshot: imbalance = (bid₁% − ask₁%) / (bid₁% + ask₁%), where bid₁% /
ask₁% are the archive's `notional` at the −1.00 / +1.00 percentage levels.
The series is as-of joined to 1h candle opens by the existing `align_metric`
(no lookahead). Snapshot staleness gate: the existing `fresh_coverage`
≥ 80% with max age 1 hour.

### Event (level-follow generator, reused verbatim)

`_make_level_follow` — the exact generator behind `toptrader_follow` /
`taker_flow_momentum` in `positioning_signals.py`: rolling z-score of the
imbalance level over **window=180** 1h bars; z ≥ **+1.5** → LONG event,
z ≤ **−1.5** → SHORT event (follow the imbalance — the literature
direction, fixed a priori). Non-overlapping events (skip h bars after an
accepted event).

### Outcome

Gross directional simple forward return at **h = 6** 1h bars (primary).
Rationale fixed in advance: order-book imbalance effects decay fast; 6h is
the longest horizon at which the literature still reports sign
predictability, and anything shorter is unharvestable after fees anyway.
Secondary horizons {1, 24} are descriptive only.

### Universe

Identical machinery to the OI-build study: 2-year window of 1h bars ending
at registration; candidates = top 24 archived USDT perps by mean daily quote
volume over the 30 days ending at window start (volume caches already on
disk; they contain no depth information), listing ≥ 1y before window start,
**no exclusions**; the first 16 with ≥ 80% fresh depth coverage form the
confirmation set; < 8 evaluable ⇒ inconclusive.

### Endpoints and verdict (identical to the OI-build study)

Per asset (n ≥ 10 events): mean directional return and t. Co-primary:
exact one-sided sign test p ≤ 0.05 AND Stouffer Z ≥ 1.645. Verdict:
**exists** (both pass) / **does not exist** (equal-weight pooled mean ≤ 0) /
**inconclusive** (otherwise). Descriptive (no verdict influence): h ∈ {1,
24}; net-of-cost (0.1% round trip); liquidity halves; time halves;
leave-one-asset-out range. The lookback-variant slot from the OI study does
not apply (level generators have no lookback) and is omitted.

### Stopping rules

One-touch analysis; resumable downloads. Anything short of `exists`
permanently retires the book-depth imbalance lineage on this data. If
`exists`: signal research may still not begin until (a) a pre-registered
confirmation on a future window that does not yet exist, and (b) the
net-of-cost descriptive Z ≥ 1.645 — an imbalance effect that cannot pay one
round-trip at 6h is microstructure trivia, not a tradable mechanism.

### Known limitations (in advance)

- ±1% band notional is a coarse, venue-specific liquidity proxy; spoofable
  resting liquidity is part of what is being measured.
- ~30s snapshots aggregate away the sub-minute dynamics where this effect
  is strongest in the literature — the test is of a *slow residue* of the
  known fast effect; a negative here does not contradict the HFT-scale
  literature.
- 1h close-to-close returns ignore intrabar path.
