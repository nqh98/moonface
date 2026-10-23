# Aggressor Trades Rung-0 - Pre-Registration V2 (Option A Re-Freeze)

Frozen date: 2026-07-02. Supersedes `AGGRESSOR_TRADES_RUNG0_PREREGISTRATION.md`
(v1), which was PARKED before any data run.

## Why v1 was never run

The v1 frozen feature `imbalance = (buy_volume - sell_volume) / (buy_volume +
sell_volume)` was refuted as not-new by
`FREE_DATA_FEASIBILITY_binance_aggtrades.md` (Q6): it is a strictly monotonic
transform of Binance `sum_taker_long_short_vol_ratio`, whose predictive test
(`taker_flow_momentum`) already returned `mechanism_does_not_exist`. A
rank-based gate is invariant to monotonic transforms, so running v1 would have
been a disguised re-test. This document executes the memo's **option A**:
amend the feature to something genuinely trade-level and re-freeze.

## Hypothesis

Directional information lives in the *temporal clustering* of aggressive
trade arrivals, not in their net volume. Self-exciting (bursty) arrival
timing on one side marks a single urgent participant sweeping or a stop
cascade — informed or forced flow — and predicts short-horizon continuation
in that side's direction. Two windows with identical taker volume ratios can
carry opposite excitation asymmetry, so no binned volume ratio can reproduce
this feature; the new-data claim survives at the feature level.

## Data

- Binance Vision USDT-M futures daily `aggTrades` archive (free, keyless,
  MIT), BTCUSDT only, reduced on download to per-second aggressor print
  counts per side plus last trade price (`ts_ms, symbol, buy_count,
  sell_count, last_price`). Volumes are dropped at acquisition and the
  harness rejects volume columns outright.
- Side convention: `is_buyer_maker` False -> buy aggressor, True -> sell.
- Frozen window: 180 archive days, 2026-01-02T00:00Z (1767312000000) to
  2026-07-01T00:00Z (1782864000000), the audit-minimum history bounding
  download to feasible size (~52k buckets is ample n for a 5-minute-horizon
  information test). Chosen before any of this data was seen.

## Feature (single frozen definition, no grid)

Per 5-minute bucket, over the trailing 6h (21600 s) of per-second counts
ending at the bucket close:

    feature = acf1(buy counts) - acf1(sell counts)

where acf1 is the lag-1 autocorrelation — a deterministic Hawkes-branching
proxy (no MLE). Missing seconds count zero. Buckets before the first full
window are warmup and emit nothing.

Rejected alternatives (listed so they cannot become a v3 feature-shop):
large-print/whale imbalance, size-vs-count divergence, print-rate,
Fano-factor variants, fitted-Hawkes branching ratios, other window lengths.

## Test and gate (byte-identical to v1)

Feature vs next-bucket log return on the first 80% of buckets; final 20% is
a sealed lockbox. Gate: 6 chronological folds; median fold Spearman IC >
0.015; at least two-thirds of folds positive; Newey-West t >= 2.0 (lag 5);
highest feature quintile beats lowest; sign survives top-1% activity trim;
lockbox untouched. Audit: >= 180 days history, coverage >= 0.95 at 5-min
cadence, monotonic timestamps, duplicate ratio <= 0.01. This is an
information test only — no strategy backtest, no trading result.

## Kill Rule

If the gate fails, arrival-timing excitation asymmetry carries no usable
5-minute-horizon information on BTCUSDT and the aggressor-trades lane closes
for good — no window grid, no horizon grid, no alternative clustering
statistic, no v3. The sealed lockbox is opened only after a nonlockbox pass,
under a separately approved plan.
